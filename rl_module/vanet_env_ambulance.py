"""
Ambulance-Aware VANET Traffic RL Environment
Extended environment that includes ambulance routing, target coordinates, and direction.
Trains RL agent to optimize traffic light preemption for emergency vehicles.
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import traci
import random
import math
from typing import Dict, List, Tuple, Optional
import sys
import os

# Import base environment
sys.path.append(os.path.join(os.path.dirname(__file__)))
from vanet_env import VANETTrafficEnv


class AmbulanceAwareVANETEnv(VANETTrafficEnv):
    """
    Extended RL environment that includes ambulance scenarios.
    
    Key additions over base VANETTrafficEnv:
    - Spawns ambulances at random intervals
    - Tracks ambulance position, target, direction, ETA
    - Augments observation space with ambulance routing info
    - Modifies reward to heavily penalize ambulance delays
    - Adds "preempt" action for each junction
    """
    
    def __init__(self, config=None):
        """Initialize ambulance-aware environment."""
        # Default ambulance-specific config
        ambulance_config = {
            'ambulance_spawn_prob': 0.15,  # 15% chance per episode
            'ambulance_spawn_interval': 300,  # Spawn every 300 steps if enabled
            'ambulance_target_range': 2000,  # Max distance to target (meters)
            'ambulance_min_speed': 15.0,  # m/s (~54 km/h)
            'ambulance_max_speed': 25.0,  # m/s (~90 km/h)
            'preemption_distance': 200.0,  # Distance to trigger preemption consideration
            'ambulance_penalty_weight': 100.0,  # Multiplier for ambulance delay penalty
        }
        
        # Merge with provided config
        if config:
            config.update(ambulance_config)
        else:
            config = ambulance_config
        
        # Initialize base environment
        super().__init__(config)
        
        # Ambulance tracking
        self.ambulance_config = ambulance_config
        self.ambulance_active = False
        self.ambulance_id = None
        self.ambulance_target = None  # (x, y) coordinates
        self.ambulance_spawn_timer = 0
        self.ambulance_start_time = 0
        self.ambulance_cleared = False
        
        # Junction positions (from SUMO network)
        self.junction_positions = {
            'J2': (500.0, 500.0),
            'J3': (1000.0, 500.0),
        }
        
        # Direction mapping
        self.direction_map = {
            'north': 0,
            'south': 1,
            'east': 2,
            'west': 3,
        }
        
        # Update action and observation spaces
        self._setup_ambulance_spaces()
    
    def _setup_ambulance_spaces(self):
        """Extend action and observation spaces for ambulance handling."""
        # Action space: Add "preempt" action for each junction
        # Actions per junction: [phase0, phase1, phase2, phase3, preempt, hold]
        num_junctions = len(self.action_spec.keys()) if self.action_spec else 2
        
        if self.algorithm == "DQN":
            # Discrete: all combinations of junction actions
            actions_per_junction = 6  # 4 phases + preempt + hold
            total_actions = actions_per_junction ** num_junctions
            self.action_space = spaces.Discrete(total_actions)
        elif self.algorithm == "PPO":
            # Continuous: one action per junction
            self.action_space = spaces.Box(
                low=0, high=5, 
                shape=(num_junctions,), 
                dtype=np.float32
            )
        
        # Observation space: Base + ambulance features
        base_obs_dim = self.observation_space.shape[0]
        
        # Ambulance features per junction
        ambulance_features_per_junction = 4  # distance, eta, is_target, direction_match
        
        # Global ambulance features
        global_ambulance_features = 11  # present, x, y, target_x, target_y, speed, heading, direction(4-hot)
        
        total_obs_dim = (
            base_obs_dim + 
            global_ambulance_features +
            (ambulance_features_per_junction * num_junctions)
        )
        
        self.observation_space = spaces.Box(
            low=-float("inf"), 
            high=float("inf"), 
            shape=(total_obs_dim,), 
            dtype=np.float32
        )
    
    def reset(self, seed=None, options=None):
        """Reset environment and potentially spawn an ambulance."""
        if seed is not None:
            np.random.seed(seed)
            random.seed(seed)
        
        # Reset base environment
        obs = super().reset()
        
        # Reset ambulance tracking
        self.ambulance_active = False
        self.ambulance_id = None
        self.ambulance_target = None
        self.ambulance_spawn_timer = 0
        self.ambulance_start_time = 0
        self.ambulance_cleared = False
        
        # Decide if this episode will have an ambulance
        if random.random() < self.ambulance_config['ambulance_spawn_prob']:
            # Schedule ambulance spawn
            self.ambulance_spawn_timer = random.randint(50, 150)  # Spawn after 50-150 steps
        
        # Get extended observation
        extended_obs = self._get_ambulance_augmented_state()
        
        return extended_obs, {}
    
    def step(self, action):
        """Execute one step with ambulance-aware logic."""
        # Update ambulance spawn timer
        if not self.ambulance_active and self.ambulance_spawn_timer > 0:
            self.ambulance_spawn_timer -= 1
            if self.ambulance_spawn_timer == 0:
                self._spawn_ambulance()
        
        # Map action to traffic light states (including preemption)
        self._apply_ambulance_aware_actions(action)
        
        # Step SUMO simulation
        try:
            traci.simulationStep()
            self.current_step += 1
        except:
            # Simulation ended
            return self._get_ambulance_augmented_state(), 0.0, True, False, {}
        
        # Update tracking
        self._update_obs_veh_acc()
        self._update_obs_wait_steps()
        self._increment_obs_tl_wait_steps()
        
        # Check if ambulance cleared network
        if self.ambulance_active and not self.ambulance_cleared:
            self._check_ambulance_clearance()
        
        # Compute reward
        reward = self._compute_ambulance_aware_reward(action)
        self.episode_reward += reward
        
        # Check termination
        done = self.current_step >= self.horizon
        
        # Get observation
        obs = self._get_ambulance_augmented_state()
        
        return obs, reward, done, False, {
            'ambulance_active': self.ambulance_active,
            'ambulance_cleared': self.ambulance_cleared,
            'episode_reward': self.episode_reward,
        }
    
    def _spawn_ambulance(self):
        """Spawn an ambulance with random start/target positions."""
        try:
            # Define valid routes through your network
            # Based on network.edg.xml: E1→J2→E2→J3→E3 and E5→J2→E6, E7→J3→E8
            valid_routes = [
                ['E1', 'E2', 'E3'],  # West to East through both junctions
                ['E5', 'E6'],         # North to South through J2
                ['E7', 'E8'],         # North to South through J3
                ['E1', 'E2'],         # West to middle
                ['E2', 'E3'],         # Middle to east
            ]
            
            # Random route
            route_edges = random.choice(valid_routes)
            
            # Create ambulance route
            route_id = f"route_ambulance_{self.current_step}"
            try:
                traci.route.add(route_id, route_edges)
            except Exception as e:
                print(f"[RL Training] Failed to add route {route_edges}: {e}")
                # Fallback: simple E1→E2 route
                traci.route.add(route_id, ['E1', 'E2'])
            
            # Spawn ambulance vehicle
            self.ambulance_id = f"emergency_ambulance_{self.current_step}"
            try:
                traci.vehicle.add(
                    self.ambulance_id,
                    route_id,
                    typeID='passenger',  # Use 'passenger' type (emergency may not be defined)
                    depart='now'
                )
            except Exception as e:
                print(f"[RL Training] Failed to add vehicle: {e}")
                # Try with minimal parameters
                traci.vehicle.add(self.ambulance_id, route_id)
            
            # Set ambulance speed and appearance
            try:
                traci.vehicle.setSpeedMode(self.ambulance_id, 0)  # Ignore safety checks
                traci.vehicle.setSpeed(self.ambulance_id, self.ambulance_config['ambulance_max_speed'])
                traci.vehicle.setColor(self.ambulance_id, (255, 0, 0, 255))  # Red
            except Exception as e:
                print(f"[RL Training] Failed to set ambulance properties: {e}")
            
            # Get target position (approximate from last edge in route)
            try:
                last_edge = route_edges[-1]
                target_lane = last_edge + '_0'
                target_shape = traci.lane.getShape(target_lane)
                self.ambulance_target = target_shape[-1]  # End of lane
            except:
                # Fallback: use junction position
                self.ambulance_target = self.junction_positions.get('J3', (1000.0, 500.0))
            
            self.ambulance_active = True
            self.ambulance_start_time = self.current_step
            self.ambulance_cleared = False
            
            print(f"[RL Training] Spawned ambulance: {self.ambulance_id}, target: {self.ambulance_target}")
            
        except Exception as e:
            print(f"[RL Training] Failed to spawn ambulance: {e}")
            self.ambulance_active = False
    
    def _check_ambulance_clearance(self):
        """Check if ambulance has reached target or left network."""
        if not self.ambulance_id:
            return
        
        try:
            # Check if ambulance still exists in simulation
            if self.ambulance_id not in traci.vehicle.getIDList():
                self.ambulance_cleared = True
                print(f"[RL Training] Ambulance cleared network at step {self.current_step}")
                return
            
            # Check distance to target
            x, y = traci.vehicle.getPosition(self.ambulance_id)
            target_x, target_y = self.ambulance_target
            distance = math.sqrt((x - target_x)**2 + (y - target_y)**2)
            
            if distance < 50.0:  # Within 50m of target
                self.ambulance_cleared = True
                print(f"[RL Training] Ambulance reached target at step {self.current_step}")
                # Remove ambulance
                traci.vehicle.remove(self.ambulance_id)
        except:
            # Ambulance no longer exists
            self.ambulance_cleared = True
    
    def _get_ambulance_state(self) -> Dict:
        """Get current ambulance state information."""
        if not self.ambulance_active or not self.ambulance_id:
            # Return null state
            return {
                'present': 0,
                'x': 0.0, 'y': 0.0,
                'target_x': 0.0, 'target_y': 0.0,
                'speed': 0.0,
                'heading': 0.0,
                'direction': [0, 0, 0, 0],  # north, south, east, west
            }
        
        try:
            # Check if ambulance still exists
            if self.ambulance_id not in traci.vehicle.getIDList():
                # Ambulance left simulation
                self.ambulance_active = False
                self.ambulance_cleared = True
                return {
                    'present': 0,
                    'x': 0.0, 'y': 0.0,
                    'target_x': 0.0, 'target_y': 0.0,
                    'speed': 0.0,
                    'heading': 0.0,
                    'direction': [0, 0, 0, 0],
                }
            
            # Get ambulance position and motion
            x, y = traci.vehicle.getPosition(self.ambulance_id)
            speed = traci.vehicle.getSpeed(self.ambulance_id)
            angle = traci.vehicle.getAngle(self.ambulance_id)  # 0-360°
            
            # Target coordinates
            target_x, target_y = self.ambulance_target if self.ambulance_target else (0.0, 0.0)
            
            # Calculate direction vector and categorize
            dx = target_x - x
            dy = target_y - y
            heading_angle = math.atan2(dy, dx) * 180 / math.pi  # Convert to degrees
            
            # Categorize into cardinal directions (one-hot encoding)
            direction = [0, 0, 0, 0]  # [north, south, east, west]
            if abs(dy) > abs(dx):
                if dy > 0:
                    direction[0] = 1  # north
                else:
                    direction[1] = 1  # south
            else:
                if dx > 0:
                    direction[2] = 1  # east
                else:
                    direction[3] = 1  # west
            
            return {
                'present': 1,
                'x': x / 1000.0,  # Normalize to ~0-2 range
                'y': y / 1000.0,
                'target_x': target_x / 1000.0,
                'target_y': target_y / 1000.0,
                'speed': speed / 25.0,  # Normalize to 0-1 range
                'heading': heading_angle / 360.0,  # Normalize to 0-1
                'direction': direction,
            }
        except:
            # Error getting ambulance state
            return {
                'present': 0,
                'x': 0.0, 'y': 0.0,
                'target_x': 0.0, 'target_y': 0.0,
                'speed': 0.0,
                'heading': 0.0,
                'direction': [0, 0, 0, 0],
            }
    
    def _get_ambulance_junction_features(self) -> np.ndarray:
        """Get per-junction ambulance features (distance, ETA, etc.)."""
        features = []
        
        if not self.ambulance_active or not self.ambulance_id:
            # Return zeros for all junctions
            num_junctions = len(self.junction_positions)
            return np.zeros(num_junctions * 4, dtype=np.float32)
        
        try:
            # Check if ambulance still exists
            if self.ambulance_id not in traci.vehicle.getIDList():
                num_junctions = len(self.junction_positions)
                return np.zeros(num_junctions * 4, dtype=np.float32)
            
            x, y = traci.vehicle.getPosition(self.ambulance_id)
            speed = max(traci.vehicle.getSpeed(self.ambulance_id), 0.1)  # Avoid division by zero
            
            for junction_id, (jx, jy) in self.junction_positions.items():
                # Distance to junction
                distance = math.sqrt((x - jx)**2 + (y - jy)**2)
                
                # ETA to junction (simple: distance / speed)
                eta = distance / speed
                
                # Is this junction on ambulance's route?
                is_target = 1 if distance < 500.0 else 0  # Within 500m = likely target
                
                # Direction match (does ambulance need this junction?)
                # Check if ambulance heading points towards this junction
                dx = jx - x
                dy = jy - y
                angle_to_junction = math.atan2(dy, dx) * 180 / math.pi
                ambulance_angle = traci.vehicle.getAngle(self.ambulance_id)
                angle_diff = abs(angle_to_junction - ambulance_angle)
                direction_match = 1.0 if angle_diff < 45 else 0.0
                
                features.extend([
                    distance / 1000.0,  # Normalize
                    min(eta / 60.0, 1.0),  # Normalize (max 60s)
                    is_target,
                    direction_match,
                ])
        except:
            # Error: return zeros
            num_junctions = len(self.junction_positions)
            return np.zeros(num_junctions * 4, dtype=np.float32)
        
        return np.array(features, dtype=np.float32)
    
    def _get_ambulance_augmented_state(self) -> np.ndarray:
        """Get full observation including ambulance features."""
        # Base state from parent
        base_state = super().get_state()
        
        # Ambulance global features
        amb_state = self._get_ambulance_state()
        ambulance_features = np.array([
            amb_state['present'],
            amb_state['x'],
            amb_state['y'],
            amb_state['target_x'],
            amb_state['target_y'],
            amb_state['speed'],
            amb_state['heading'],
            *amb_state['direction'],  # 4 values
        ], dtype=np.float32)
        
        # Per-junction ambulance features
        junction_features = self._get_ambulance_junction_features()
        
        # Concatenate all
        full_state = np.concatenate([
            base_state,
            ambulance_features,
            junction_features,
        ])
        
        # Ensure matches observation space
        expected_size = self.observation_space.shape[0]
        if len(full_state) < expected_size:
            full_state = np.pad(full_state, (0, expected_size - len(full_state)), 'constant')
        elif len(full_state) > expected_size:
            full_state = full_state[:expected_size]
        
        return full_state.astype(np.float32)
    
    def _apply_ambulance_aware_actions(self, action):
        """Apply RL actions with ambulance preemption support."""
        if not self.action_spec:
            return
        
        # Decode action
        junction_actions = self._decode_action(action)
        
        # Apply to each junction
        for junction_id, junction_action in zip(self.action_spec.keys(), junction_actions):
            if junction_action == 4:  # Preempt action
                self._apply_preemption(junction_id)
            elif junction_action == 5:  # Hold action
                pass  # Do nothing
            else:  # Normal phase change (0-3)
                try:
                    phase_idx = int(junction_action)
                    if phase_idx < len(self.action_spec[junction_id]):
                        new_state = self.action_spec[junction_id][phase_idx]
                        traci.trafficlight.setRedYellowGreenState(junction_id, new_state)
                except:
                    pass
    
    def _decode_action(self, action) -> List[int]:
        """Decode RL action into per-junction actions."""
        num_junctions = len(self.action_spec.keys()) if self.action_spec else 2
        
        if self.algorithm == "DQN":
            # Decode discrete action
            actions_per_junction = 6
            junction_actions = []
            for _ in range(num_junctions):
                junction_actions.append(action % actions_per_junction)
                action //= actions_per_junction
            return junction_actions
        elif self.algorithm == "PPO":
            # Continuous action → discrete
            return [int(a) for a in action]
        else:
            return [0] * num_junctions
    
    def _apply_preemption(self, junction_id: str):
        """Apply traffic light preemption for ambulance."""
        if not self.ambulance_active or not self.ambulance_id:
            return
        
        try:
            # Check if ambulance still exists
            if self.ambulance_id not in traci.vehicle.getIDList():
                return
            
            # Get ambulance lane
            ambulance_lane = traci.vehicle.getLaneID(self.ambulance_id)
            
            # Map lane to direction and set appropriate phase
            # This is network-specific; adapt to your SUMO network
            if 'E1' in ambulance_lane or 'west' in ambulance_lane.lower():
                # Ambulance approaching from west → green west
                green_state = "GGGrrr"  # Example: west green
            elif 'E2' in ambulance_lane or 'east' in ambulance_lane.lower():
                green_state = "rrrGGG"  # East green
            elif 'E5' in ambulance_lane or 'north' in ambulance_lane.lower():
                green_state = "GGGrrr"  # North green
            else:
                green_state = "rrrGGG"  # South green
            
            traci.trafficlight.setRedYellowGreenState(junction_id, green_state)
            print(f"[RL Training] Preemption applied at {junction_id} for ambulance lane {ambulance_lane}")
        except Exception as e:
            print(f"[RL Training] Preemption failed: {e}")
    
    def _compute_ambulance_aware_reward(self, action) -> float:
        """Compute reward with heavy ambulance priority."""
        # Base reward from parent class
        base_reward = self.compute_reward(action)
        
        # Ambulance-specific rewards
        ambulance_reward = 0.0
        
        if self.ambulance_active and self.ambulance_id:
            try:
                # Check if ambulance still exists
                if self.ambulance_id not in traci.vehicle.getIDList():
                    # Ambulance left, no reward calculation needed
                    return base_reward
                
                speed = traci.vehicle.getSpeed(self.ambulance_id)
                x, y = traci.vehicle.getPosition(self.ambulance_id)
                
                # Find nearest junction
                min_distance = float('inf')
                for jx, jy in self.junction_positions.values():
                    dist = math.sqrt((x - jx)**2 + (y - jy)**2)
                    min_distance = min(min_distance, dist)
                
                # CRITICAL: Huge penalty if ambulance is stopped near junction
                if speed < 1.0 and min_distance < 100.0:
                    ambulance_reward -= 500 * self.ambulance_config['ambulance_penalty_weight']
                    print(f"[RL Training] PENALTY: Ambulance stopped near junction! Speed={speed:.1f}, dist={min_distance:.1f}")
                
                # Moderate penalty if ambulance is slow
                elif speed < 5.0 and min_distance < 200.0:
                    ambulance_reward -= 50 * self.ambulance_config['ambulance_penalty_weight']
                
                # Small reward for ambulance moving fast
                elif speed > 15.0:
                    ambulance_reward += 10
                
                # Check if ambulance just cleared (big reward!)
                if self.ambulance_cleared and (self.current_step - self.ambulance_start_time) < 200:
                    clearance_time = self.current_step - self.ambulance_start_time
                    ambulance_reward += 1000 / max(clearance_time, 1)
                    print(f"[RL Training] REWARD: Ambulance cleared in {clearance_time} steps!")
                
            except:
                pass
        
        total_reward = base_reward + ambulance_reward
        return total_reward
