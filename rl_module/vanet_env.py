"""
VANET Traffic RL Environment
Gym-compatible environment for traffic light optimization using reinforcement learning.
Adapted from RL-Traffic-optimization_CIL4sys for VANET final v3
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import traci
from collections import OrderedDict
import itertools

# Import with proper path handling
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__)))

from rewards import Rewards
from states import States
from emergency_coordinator import EmergencyVehicleCoordinator


class VANETTrafficEnv(gym.Env):
    """
    Reinforcement Learning Environment for VANET Traffic Optimization.
    
    This environment provides:
    - State: Vehicle positions, speeds, emissions, traffic light states
    - Actions: Traffic light phase changes
    - Rewards: Based on traffic flow, emissions, and waiting times
    """
    
    metadata = {'render.modes': ['human']}
    
    def __init__(self, config=None):
        """
        Initialize the VANET Traffic RL Environment.
        
        Parameters
        ----------
        config : dict
            Configuration dictionary with keys:
            - beta: number of observable vehicles
            - action_spec: dict of traffic light IDs and their allowed states
            - tl_constraint_min: minimum time before traffic light can change
            - tl_constraint_max: maximum time before traffic light must change
            - sim_step: simulation step size in seconds
            - algorithm: 'DQN' or 'PPO'
            - horizon: episode length
        """
        super(VANETTrafficEnv, self).__init__()
        
        # Default configuration
        default_config = {
            'beta': 10,  # Number of observable vehicles
            'action_spec': {},  # Will be populated from SUMO
            'tl_constraint_min': 5,  # Min 5 seconds before change
            'tl_constraint_max': 60,  # Max 60 seconds before forced change
            'sim_step': 1.0,
            'algorithm': 'DQN',
            'horizon': 1000,
        }
        
        self.config = {**default_config, **(config or {})}
        
        # Extract config parameters
        self.beta = self.config['beta']
        self.action_spec = self.config['action_spec']
        self.tl_constraint_min = self.config['tl_constraint_min']
        self.tl_constraint_max = self.config['tl_constraint_max']
        self.sim_step = self.config['sim_step']
        self.algorithm = self.config['algorithm']
        self.horizon = self.config['horizon']
        
        # Initialize RL components
        self.rewards = Rewards(self.action_spec)
        self.states = States(self.beta)
        
        # Initialize emergency vehicle coordinator
        self.emergency_coordinator = EmergencyVehicleCoordinator(rsu_range=300.0)
        self.emergency_coordinator_initialized = False
        
        # Initialize tracking variables
        self._init_obs_veh_acc()
        self._init_obs_veh_wait_steps()
        self._init_obs_tl_wait_steps()
        
        # Track all vehicles ever seen (to handle disappearing vehicles)
        self.all_seen_vehicles: set = set()
        self.completed_vehicles: set = set()
        
        # Episode tracking
        self.current_step = 0
        self.episode_reward = 0
        
        # Emergency vehicle tracking
        self.emergency_vehicle_delays = []  # Track delays caused to emergency vehicles
        self.successful_greenwaves = 0
        
        # Define action and observation spaces
        self._setup_spaces()
        
    def _setup_spaces(self):
        """Setup action and observation spaces for the RL algorithm."""
        # Action space
        if self.algorithm == "DQN":
            num_actions = self.get_num_actions()
            self.action_space = spaces.Discrete(num_actions)
        elif self.algorithm == "PPO":
            num_intersections = len(self.action_spec.keys())
            self.action_space = spaces.Box(
                low=0, high=1, 
                shape=(num_intersections,), 
                dtype=np.float32
            )
        else:
            raise NotImplementedError(f"Algorithm {self.algorithm} not supported")
        
        # Observation space
        num_obs_veh = self.beta
        num_tl = self.get_num_traffic_lights()
        num_intersections = len(self.action_spec.keys())
        
        # State: [speeds, orientations(3D), CO2, wait_steps, acc, tl_binary, tl_wait]
        obs_dim = (
            7 * num_obs_veh +  # speeds, orientations(3), CO2, wait, acc
            num_tl +            # traffic light binary states
            num_intersections   # traffic light wait steps
        )
        
        self.observation_space = spaces.Box(
            low=-float("inf"), 
            high=float("inf"), 
            shape=(obs_dim,), 
            dtype=np.float32
        )
    
    def _init_obs_veh_acc(self):
        """Initializes the data structures that will store vehicle speeds and accelerations"""
        self._obs_veh_vel = OrderedDict([('vehicle_' + str(i), 0) for i in range(self.beta)])
        self.obs_veh_acc = OrderedDict([('vehicle_' + str(i), [0]) for i in range(self.beta)])

    def _update_obs_veh_acc(self):
        """Updates the observed vehicle speed and acceleration data structures."""
        placeholder = 0.
        obs_veh_ids = self.get_observable_veh_ids()

        # Create speed dict with actual vehicle IDs
        speed_odict = OrderedDict()
        for i, veh_id in enumerate(obs_veh_ids[:self.beta]):
            try:
                speed_odict[veh_id] = traci.vehicle.getSpeed(veh_id)
            except:
                speed_odict[veh_id] = 0.

        # Fill remaining slots with placeholders
        for i in range(len(speed_odict), self.beta):
            speed_odict['vehicle_' + str(i)] = placeholder

        # Update accelerations
        for veh_id in speed_odict.keys():
            if veh_id in self._obs_veh_vel:
                new_acc = (speed_odict[veh_id] - self._obs_veh_vel[veh_id]) / self.sim_step
            else:
                new_acc = 0.

            if veh_id not in self.obs_veh_acc:
                self.obs_veh_acc[veh_id] = [0]

            list_acc = self.obs_veh_acc[veh_id].copy()
            list_acc.append(new_acc)
            self.obs_veh_acc[veh_id] = list_acc

        self._obs_veh_vel = speed_odict

    def _init_obs_veh_wait_steps(self):
        """Initializes attributes that will store the number of steps stayed idle by vehicles"""
        self._all_obs_veh_names = ['vehicle_' + str(i) for i in range(self.beta)]
        self.obs_veh_wait_steps = {veh_id: 0 for veh_id in self._all_obs_veh_names}

    def _init_obs_tl_wait_steps(self):
        """Initializes attributes that will store the number of steps stayed idle by traffic lights"""
        self._all_tl_names = list(self.action_spec.keys())
        self.obs_tl_wait_steps = {
            tl_id: {'current_state': '', 'timer': 0} 
            for tl_id in self._all_tl_names
        }
    
    def get_observable_veh_ids(self):
        """Get the ids of all the vehicles observable by the model."""
        try:
            all_vehs = traci.vehicle.getIDList()
            
            # Update tracking of all vehicles
            for veh in all_vehs:
                if veh not in self.all_seen_vehicles:
                    self.all_seen_vehicles.add(veh)
            
            # Detect completed vehicles (vehicles that were seen but are no longer in simulation)
            current_vehs_set = set(all_vehs)
            newly_completed = self.all_seen_vehicles - current_vehs_set - self.completed_vehicles
            self.completed_vehicles.update(newly_completed)
            
            # Return first beta vehicles
            return list(all_vehs)[:self.beta]
        except Exception as e:
            return []
    
    def get_controlled_tl_ids(self):
        """Returns the list of RL controlled traffic lights."""
        try:
            all_tls = traci.trafficlight.getIDList()
            return [tl_id for tl_id in all_tls if tl_id in self.action_spec.keys()]
        except:
            return []
    
    def get_num_traffic_lights(self):
        """Counts the number of traffic lights by summing the state string length."""
        count = 0
        for k in self.action_spec.keys():
            if self.action_spec[k]:
                count += len(self.action_spec[k][0])
        return count if count > 0 else 1
    
    def get_num_actions(self):
        """Calculates the number of possible actions."""
        if not self.action_spec:
            return 1
        
        count = 1
        for k in self.action_spec.keys():
            count *= len(self.action_spec[k])
        
        if self.algorithm == "DQN":
            return count
        elif self.algorithm == "PPO":
            return len(self.action_spec.keys())
        else:
            raise NotImplementedError
    
    def map_action_to_tl_states(self, rl_actions):
        """Maps an rl_action to new traffic light states."""
        if not self.action_spec:
            return []
        
        new_state = []
        if self.algorithm == "DQN":
            all_actions = list(itertools.product(*list(self.action_spec.values())))
            if rl_actions < len(all_actions):
                new_state = all_actions[rl_actions]
            else:
                new_state = all_actions[0]
        elif self.algorithm == "PPO":
            new_state = [
                v[int(rl_actions[i])] 
                for i, v in enumerate(list(self.action_spec.values()))
            ]
        else:
            raise NotImplementedError

        # Don't update traffic lights that have not exceeded the timer
        new_state = list(new_state)
        for i, tl_id in enumerate(self.action_spec.keys()):
            try:
                current_state = traci.trafficlight.getRedYellowGreenState(tl_id)
                timer_value = self.obs_tl_wait_steps[tl_id]['timer']
                
                if timer_value < self.tl_constraint_min:
                    new_state[i] = current_state
                else:
                    # Pick new state if tl state hasn't changed in a while
                    cond_A = timer_value > self.tl_constraint_max
                    cond_B = new_state[i] == current_state
                    if cond_A and cond_B:
                        possible_states = list(self.action_spec[tl_id])
                        if current_state in possible_states:
                            possible_states.remove(current_state)
                        num_states = len(possible_states)
                        if num_states:
                            new_state_index = np.random.randint(num_states)
                            new_state[i] = possible_states[new_state_index]

                    # Update state and timer if state changed
                    if new_state[i] != current_state:
                        self.obs_tl_wait_steps[tl_id] = {
                            'current_state': new_state[i],
                            'timer': 0
                        }
            except:
                pass

        return new_state
    
    def _apply_rl_actions(self, rl_actions):
        """Apply RL actions to traffic lights."""
        if not self.action_spec:
            return
        
        new_tl_states = self.map_action_to_tl_states(rl_actions)
        
        for counter, tl_id in enumerate(self.action_spec.keys()):
            try:
                if counter < len(new_tl_states):
                    traci.trafficlight.setRedYellowGreenState(tl_id, new_tl_states[counter])
            except Exception as e:
                print(f"Error setting traffic light {tl_id}: {e}")
    
    def _update_obs_wait_steps(self):
        """Update vehicle wait steps."""
        obs_veh_ids = self.get_observable_veh_ids()
        
        # Update wait steps for observed vehicles
        for veh_id in obs_veh_ids:
            try:
                speed = traci.vehicle.getSpeed(veh_id)
                if veh_id not in self.obs_veh_wait_steps:
                    self.obs_veh_wait_steps[veh_id] = 0
                    
                if speed < 0.1:  # Vehicle is waiting
                    self.obs_veh_wait_steps[veh_id] += 1
                else:
                    self.obs_veh_wait_steps[veh_id] = 0
            except:
                if veh_id not in self.obs_veh_wait_steps:
                    self.obs_veh_wait_steps[veh_id] = 0
        
        # Patch for missing vehicles
        for k in self._all_obs_veh_names:
            if k not in self.obs_veh_wait_steps:
                self.obs_veh_wait_steps[k] = 0
    
    def _increment_obs_tl_wait_steps(self):
        """Increment traffic light wait steps."""
        for tl_id in self.action_spec.keys():
            self.obs_tl_wait_steps[tl_id]['timer'] += 1
    
    def get_state(self):
        """Get current state observation."""
        veh_ids = self.get_observable_veh_ids()
        tl_ids = self.get_controlled_tl_ids()
        
        current_accelerations = [
            item[-1] for item in self.obs_veh_acc.values()
        ]
        
        state = np.concatenate((
            self.states.veh.speeds(veh_ids),
            self.states.veh.orientations(veh_ids),
            self.states.veh.CO2_emissions(veh_ids),
            self.states.veh.wait_steps(self.obs_veh_wait_steps),
            current_accelerations,
            self.states.tl.binary_state_ohe(tl_ids) if tl_ids else [0],
            self.states.tl.wait_steps(self.obs_tl_wait_steps),
        ))
        
        # Ensure state matches observation space
        expected_size = self.observation_space.shape[0]
        if len(state) < expected_size:
            state = np.pad(state, (0, expected_size - len(state)), 'constant')
        elif len(state) > expected_size:
            state = state[:expected_size]
        
        return state.astype(np.float32)
    
    def compute_reward(self, rl_actions):
        """
        Compute reward based on traffic metrics with emphasis on emergency vehicle handling.
        
        Reward components:
        1. Base reward: Traffic flow, waiting times, acceleration
        2. Emergency bonus: HUGE reward for successfully handling emergency vehicles
        3. Queue penalty: Penalize congestion
        4. Greenwave bonus: Extra reward for maintaining greenwave
        """
        min_speed = 8  # km/h (lower threshold for better flow)
        idled_max_steps = 60  # steps (reduced from 80 for more sensitivity)
        max_abs_acc = 0.1  # m/s^2 (stricter acceleration control)
        c = 0.01  # Base reward scaling

        # Base reward from traffic metrics with stronger penalties
        base_reward = c * (
            self.rewards.penalize_min_speed(min_speed) +
            self.rewards.penalize_max_wait(self.obs_veh_wait_steps, idled_max_steps, 0, -50) +  # Increased penalty
            self.rewards.penalize_max_acc(self.obs_veh_acc, max_abs_acc, 1, 0)
        )

        # ========== EMERGENCY VEHICLE REWARDS (HIGHEST PRIORITY) ==========
        emergency_bonus = 0
        emergency_penalty = 0
        
        try:
            # Get active emergency vehicles from coordinator
            active_emergencies = self.emergency_coordinator.get_active_emergency_vehicles()
            
            if active_emergencies:
                for emerg_veh in active_emergencies:
                    try:
                        # Get emergency vehicle metrics
                        veh_id = emerg_veh.vehicle_id
                        speed = traci.vehicle.getSpeed(veh_id)
                        waiting_time = traci.vehicle.getWaitingTime(veh_id)
                        
                        # HUGE bonus for emergency vehicles moving at good speed
                        if speed > 10.0:  # Moving faster than 10 m/s (36 km/h)
                            emergency_bonus += 200  # Massive reward
                            
                        elif speed > 5.0:  # Moderate speed (18 km/h)
                            emergency_bonus += 100  # Good reward
                            
                        else:  # Slow or stopped
                            emergency_penalty -= 150  # Heavy penalty
                        
                        # Penalty for waiting emergency vehicles
                        if waiting_time > 5.0:  # Waiting more than 5 seconds
                            emergency_penalty -= 100  # Severe penalty
                            self.emergency_vehicle_delays.append(waiting_time)
                        
                        # Bonus for successful greenwave
                        if emerg_veh.greenwave_active:
                            emergency_bonus += 50  # Reward for active greenwave
                        
                    except Exception as e:
                        # Vehicle may have completed route
                        continue
                        
        except Exception as e:
            pass

        # Queue length penalty - heavily penalize long queues
        queue_penalty = 0
        try:
            # Check queue lengths across all lanes
            all_lanes = []
            for tl_id in self.action_spec.keys():
                try:
                    controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
                    all_lanes.extend(controlled_lanes)
                except:
                    pass
            
            # Remove duplicates
            all_lanes = list(set(all_lanes))
            
            for lane_id in all_lanes:
                try:
                    # Get vehicles on lane
                    vehicles_on_lane = traci.lane.getLastStepVehicleIDs(lane_id)
                    if vehicles_on_lane:
                        # Calculate average speed on this lane
                        speeds = [traci.vehicle.getSpeed(v) for v in vehicles_on_lane[:5]]  # First 5 vehicles
                        avg_speed = sum(speeds) / len(speeds) if speeds else 0

                        # Heavily penalize slow-moving traffic (congestion indicator)
                        if avg_speed < 2.0:  # Less than 2 m/s (7.2 km/h)
                            queue_penalty -= 20  # Penalty for congestion
                        elif avg_speed < 5.0:  # Less than 5 m/s (18 km/h)
                            queue_penalty -= 5   # Small penalty for moderate congestion
                except:
                    continue
        except:
            pass

        # Combine all reward components
        total_reward = base_reward + emergency_bonus + emergency_penalty + queue_penalty

        # Emergency vehicles have absolute priority - if emergency present, scale other rewards
        active_emergencies = self.emergency_coordinator.get_active_emergency_vehicles()
        if len(active_emergencies) > 0:
            # Scale down base rewards when emergency is active
            total_reward = (base_reward * 0.3) + emergency_bonus + emergency_penalty + (queue_penalty * 0.5)

        # Ensure minimum reward to prevent agent from giving up
        return max(total_reward, -300)  # Allow larger negative rewards for emergencies
    
    def reset(self, seed=None, options=None):
        """Reset the environment to initial state."""
        super().reset(seed=seed)

        self.current_step = 0
        self.episode_reward = 0

        # Reset tracking variables
        self._init_obs_veh_acc()
        self._init_obs_veh_wait_steps()
        self._init_obs_tl_wait_steps()
        
        # Reset vehicle tracking
        self.all_seen_vehicles.clear()
        self.completed_vehicles.clear()
        
        # Reset emergency tracking
        self.emergency_vehicle_delays = []
        self.successful_greenwaves = 0

        # Get initial state
        try:
            state = self.get_state()
        except:
            # Return zero state if SUMO not connected
            state = np.zeros(self.observation_space.shape[0], dtype=np.float32)

        return state, {}
    
    def emergency_override(self):
        """Override traffic lights to prioritize emergency vehicles using RSU-based detection."""
        try:
            # Initialize emergency coordinator if not already done
            if not self.emergency_coordinator_initialized:
                self.emergency_coordinator.initialize_network_topology()
                self.emergency_coordinator_initialized = True
            
            current_time = traci.simulation.getTime()
            
            # Detect emergency vehicles via RSUs
            emergency_vehicles = self.emergency_coordinator.detect_emergency_vehicles(current_time)
            
            if not emergency_vehicles:
                return
            
            # Process each emergency vehicle
            for emerg_veh in emergency_vehicles:
                # Create greenwave for this emergency vehicle
                greenwave_tls = self.emergency_coordinator.create_greenwave(emerg_veh)
                
                if greenwave_tls:
                    # Apply greenwave to traffic lights
                    for tl_id in greenwave_tls:
                        if tl_id not in self.action_spec:
                            continue
                        
                        # Get the appropriate phase for the emergency vehicle
                        phase_idx = self.emergency_coordinator.apply_greenwave(
                            tl_id, 
                            emerg_veh.current_edge
                        )
                        
                        if phase_idx is not None:
                            # Check minimum green constraint (can be overridden for emergencies)
                            timer = self.obs_tl_wait_steps.get(tl_id, {}).get('timer', 0)
                            
                            # For emergency vehicles, force change even if min green not met
                            if timer >= self.tl_constraint_min or timer < 3:
                                traci.trafficlight.setPhase(tl_id, phase_idx)
                                self.successful_greenwaves += 1
                                print(f"🟢 Greenwave: {tl_id} set to phase {phase_idx} for {emerg_veh.vehicle_id}")
                            else:
                                # Emergency override - force immediate change
                                traci.trafficlight.setPhase(tl_id, phase_idx)
                                self.successful_greenwaves += 1
                                print(f"🚨 Emergency override: {tl_id} forced to phase {phase_idx} for {emerg_veh.vehicle_id}")
                
        except Exception as e:
            print(f"Error in emergency override: {e}")
            import traceback
            traceback.print_exc()

    def density_based_override(self):
        """Override traffic lights based on vehicle density when no emergency vehicles are detected."""
        try:
            all_vehicles = traci.vehicle.getIDList()
            emergency_detected = any(
                'emergency' in veh_id.lower() or 'ambulance' in veh_id.lower() or 'fire' in veh_id.lower()
                for veh_id in all_vehicles
            )

            if emergency_detected:
                return  # Emergency override will handle this

            controlled_tls = self.get_controlled_tl_ids()
            lane_densities = {}

            # Measure density for all lanes connected to traffic lights
            for tl_id in controlled_tls:
                connections = traci.trafficlight.getControlledLinks(tl_id)
                for link in connections:
                    lane_id = link[0][0]  # Get lane ID
                    try:
                        density = traci.lane.getLastStepOccupancy(lane_id)  # Get density
                        lane_densities[lane_id] = density
                    except Exception as e:
                        print(f"Error getting density for lane {lane_id}: {e}")

            # Find the lane with the highest density
            if lane_densities:
                max_density_lane = max(lane_densities, key=lane_densities.get)
                max_density = lane_densities[max_density_lane]

                # Set appropriate phase for the traffic light controlling the lane with the highest density
                for tl_id in controlled_tls:
                    connections = traci.trafficlight.getControlledLinks(tl_id)
                    for link_index, link in enumerate(connections):
                        if link[0][0] == max_density_lane:  # Match lane to traffic light
                            phase_index = self._find_phase_for_link(tl_id, link_index)
                            if phase_index is not None:
                                # Hysteresis: only override if density sufficiently higher than current green lanes
                                # Compute current green lanes density
                                current_state = traci.trafficlight.getRedYellowGreenState(tl_id)
                                green_indices = [i for i, ch in enumerate(current_state) if ch == 'G']
                                green_density = 0.0
                                if green_indices:
                                    vals = []
                                    for gi in green_indices:
                                        try:
                                            lane_i = connections[gi][0][0]
                                            vals.append(traci.lane.getLastStepOccupancy(lane_i))
                                        except Exception:
                                            pass
                                    if vals:
                                        green_density = sum(vals) / len(vals)

                                # Only switch if target density noticeably higher (20% more) or current green very low
                                if max_density > max(green_density * 1.2, 0.05):
                                    timer = self.obs_tl_wait_steps.get(tl_id, {}).get('timer', 0)
                                    if timer >= self.tl_constraint_min:
                                        traci.trafficlight.setPhase(tl_id, phase_index)
                                        print(f"Density-based override: Set phase {phase_index} for lane {max_density_lane} at traffic light {tl_id} with density {max_density}")
                                        return
                                    else:
                                        # defer change until min green reached
                                        print(f"Density override skipped for {tl_id} (min green not met)")
                                        return
        except Exception as e:
            print(f"Error in density-based override: {e}")

    def _find_phase_for_link(self, tl_id: str, link_index: int):
        """Find a phase index for a traffic light that gives green to the given controlled link index.

        Returns None if no phase found.
        """
        try:
            # Get all program logics (including phases)
            programs = traci.trafficlight.getAllProgramLogics(tl_id)
            if not programs:
                return None
            # Use the first program's phases
            phases = programs[0].getPhases()
            for idx, phase in enumerate(phases):
                state = phase.getRedYellowGreenState()
                # Ensure state length aligns with controlled links, otherwise skip
                if link_index < len(state) and state[link_index] == 'G':
                    return idx
            return None
        except Exception:
            return None

    def step(self, action):
        """Execute one step in the environment."""
        # Apply emergency override or density-based override before RL actions
        self.emergency_override()
        self.density_based_override()

        # Apply RL actions
        self._apply_rl_actions(action)

        # Advance simulation
        try:
            traci.simulationStep()
        except Exception as e:
            print(f"Error advancing simulation: {e}")
            # Return a safe state if simulation fails
            state = np.zeros(self.observation_space.shape[0], dtype=np.float32)
            reward = -10.0  # Penalty for connection issues
            terminated = True
            truncated = False
            info = {'episode_reward': self.episode_reward, 'mean_speed': 0, 'mean_emission': 0}
            return state, reward, terminated, truncated, info

        # Update tracking
        try:
            self._update_obs_wait_steps()
            self._increment_obs_tl_wait_steps()
            self._update_obs_veh_acc()
        except Exception as e:
            print(f"Error updating observations: {e}")

        # Get new state
        state = self.get_state()

        # Compute reward
        reward = self.compute_reward(action)
        self.episode_reward += reward

        # Check if done
        self.current_step += 1
        terminated = self.current_step >= self.horizon
        truncated = False

        # Info dict with emergency vehicle statistics
        active_emergencies = self.emergency_coordinator.get_active_emergency_vehicles()
        emergency_stats = self.emergency_coordinator.get_statistics()
        
        info = {
            'episode_reward': self.episode_reward,
            'mean_speed': self.rewards.mean_speed(),
            'mean_emission': self.rewards.mean_emission(),
            'active_emergencies': len(active_emergencies),
            'successful_greenwaves': self.successful_greenwaves,
            'emergency_detections': emergency_stats.get('total_detections', 0),
            'completed_vehicles': len(self.completed_vehicles),
        }

        return state, reward, terminated, truncated, info
    
    def render(self, mode='human'):
        """Render the environment (SUMO GUI handles this)."""
        pass
    
    def close(self):
        """Close the environment."""
        # Don't close TraCI connection during simulation - let main controller handle it
        pass
