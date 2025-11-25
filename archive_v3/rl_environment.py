#!/usr/bin/env python3
"""
RL Environment Wrapper for SUMO Traffic Simulation
Integrates Edge Computing and Security features into state/reward
"""

import os
import sys
import numpy as np
import traci
from typing import Dict, Tuple, List, Any

# Add paths
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'sumo_simulation'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'v2v_communication'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sumo_simulation.traffic_controller import AdaptiveTrafficController


class TrafficEnvironment:
    """
    OpenAI Gym-like environment for SUMO traffic simulation
    with Edge Computing and Security integration
    """
    
    def __init__(self, sumo_config, edge_enabled=True, security_enabled=True, use_gui=False):
        """
        Initialize traffic environment
        
        Args:
            sumo_config: Path to SUMO configuration file
            edge_enabled: Enable edge computing features
            security_enabled: Enable security features
            use_gui: Use SUMO GUI for visualization
        """
        self.sumo_config = sumo_config
        self.edge_enabled = edge_enabled
        self.security_enabled = security_enabled
        self.use_gui = use_gui
        
        # Traffic light IDs (will be populated after connection)
        self.tl_ids = []
        
        # State and action spaces
        self.state_dim = None
        self.action_dim = None
        
        # Simulation state
        self.current_step = 0
        self.max_steps = 1800  # 30 minutes
        
        # Metrics tracking
        self.total_waiting_time = 0
        self.total_vehicles_passed = 0
        self.collision_warnings = 0
        self.emergencies_handled = 0
        self.last_phase_change = {}
        
        # Controller (will be initialized in reset)
        self.controller = None
        
        print(f"🌐 Environment initialized:")
        print(f"  - SUMO Config: {sumo_config}")
        print(f"  - Edge Computing: {edge_enabled}")
        print(f"  - Security: {security_enabled}")
    
    def reset(self) -> np.ndarray:
        """
        Reset environment to initial state
        
        Returns:
            initial_state: Initial observation
        """
        # Close existing simulation if any
        if self.controller:
            try:
                self.controller.stop_simulation()
            except:
                pass
        
        # Initialize new simulation
        self.controller = AdaptiveTrafficController(
            output_dir="./output_rl_train",
            mode="rl",
            security_managers=None,
            security_pending=False,
            edge_computing_enabled=self.edge_enabled
        )
        
        # Connect to SUMO
        self.controller.connect_to_sumo(
            config_path=self.sumo_config,
            use_gui=self.use_gui
        )
        
        # Get traffic light IDs
        self.tl_ids = traci.trafficlight.getIDList()
        
        # Calculate state and action dimensions
        self._calculate_dimensions()
        
        # Reset metrics
        self.current_step = 0
        self.total_waiting_time = 0
        self.total_vehicles_passed = 0
        self.collision_warnings = 0
        self.emergencies_handled = 0
        self.last_phase_change = {tl: 0 for tl in self.tl_ids}
        
        # Get initial state
        initial_state = self._get_state()
        
        return initial_state
    
    def step(self, action: int) -> Tuple[np.ndarray, float, bool, Dict]:
        """
        Execute one time step
        
        Args:
            action: Action to take (phase index)
            
        Returns:
            next_state: Next observation
            reward: Reward for this step
            done: Whether episode is finished
            info: Additional information
        """
        # Execute action (set traffic light phases)
        self._execute_action(action)
        
        # Run simulation step
        self.controller.run_simulation_step()
        self.current_step += 1
        
        # Get next state
        next_state = self._get_state()
        
        # Collect info first (needed for reward calculation)
        info = self._get_info()
        
        # Calculate reward using info
        reward = self._calculate_reward(info)
        
        # Check if episode is done
        done = self.current_step >= self.max_steps
        
        return next_state, reward, done, info
    
    def _calculate_dimensions(self):
        """Calculate state and action space dimensions"""
        # Base state per traffic light:
        # - Queue lengths (4 lanes per intersection) = 4
        # - Waiting times (4 lanes) = 4
        # - Current phase (one-hot, 4 phases) = 4
        # - Time since last phase change = 1
        # Total per TL = 13
        
        base_dim_per_tl = 13
        
        # Additional features with edge computing:
        if self.edge_enabled:
            # - Collision warnings in area = 1
            # - Emergency vehicles in area = 1
            # - Average edge RSU load = 1
            # - Vehicles served by edge = 1
            base_dim_per_tl += 4
        
        # Additional features with security:
        if self.security_enabled:
            # - Encrypted messages ratio = 1
            # - Authentication failures = 1
            base_dim_per_tl += 2
        
        self.state_dim = base_dim_per_tl * len(self.tl_ids)
        
        # Get actual number of phases from SUMO for each TL
        self.phases_per_tl = {}
        for tl_id in self.tl_ids:
            try:
                num_phases = len(traci.trafficlight.getAllProgramLogics(tl_id)[0].phases)
                self.phases_per_tl[tl_id] = max(num_phases, 4)  # At least 4
            except:
                self.phases_per_tl[tl_id] = 4  # Default
        
        # Action space: product of phases for all TLs
        # For 2 TLs with N phases each: action_dim = N * N
        self.action_dim = 1
        for num_phases in self.phases_per_tl.values():
            self.action_dim *= num_phases
        
        print(f"📊 State dimension: {self.state_dim}")
        print(f"🎯 Action dimension: {self.action_dim}")
        print(f"🚦 Phases per TL: {self.phases_per_tl}")
    
    def _get_state(self) -> np.ndarray:
        """
        Get current state observation
        
        Returns:
            state: State vector
        """
        state = []
        
        for tl_id in self.tl_ids:
            # Get controlled lanes
            lanes = traci.trafficlight.getControlledLanes(tl_id)
            unique_lanes = list(set(lanes))[:4]  # Take first 4 unique lanes
            
            # Pad if less than 4 lanes
            while len(unique_lanes) < 4:
                unique_lanes.append(unique_lanes[0] if unique_lanes else 'dummy')
            
            # Queue lengths
            queue_lengths = []
            waiting_times = []
            for lane in unique_lanes:
                try:
                    queue = traci.lane.getLastStepHaltingNumber(lane)
                    wait = traci.lane.getWaitingTime(lane)
                    queue_lengths.append(queue)
                    waiting_times.append(wait)
                except:
                    queue_lengths.append(0)
                    waiting_times.append(0)
            
            # Current phase (one-hot encoding)
            try:
                current_phase = traci.trafficlight.getPhase(tl_id)
                phase_one_hot = [0] * 4
                if current_phase < 4:
                    phase_one_hot[current_phase] = 1
            except:
                phase_one_hot = [0, 0, 0, 0]
            
            # Time since last phase change
            time_since_change = self.current_step - self.last_phase_change.get(tl_id, 0)
            
            # Combine base features
            tl_state = queue_lengths + waiting_times + phase_one_hot + [time_since_change / 100.0]
            
            # Add edge computing features
            if self.edge_enabled and self.controller.edge_rsus:
                # Get edge metrics near this intersection
                edge_warnings = 0
                edge_emergencies = 0
                edge_load = 0
                edge_vehicles = 0
                
                # Find nearest RSU
                tl_pos = self._get_tl_position(tl_id)
                nearest_rsu = self._find_nearest_rsu(tl_pos)
                
                if nearest_rsu:
                    stats = nearest_rsu.get_service_statistics()
                    collision_stats = stats.get('collision_avoidance', {})
                    emergency_stats = stats.get('emergency', {})
                    
                    edge_warnings = collision_stats.get('warnings_issued', 0) / 100.0
                    edge_emergencies = emergency_stats.get('active_emergencies', 0)  # Already an int
                    edge_load = stats.get('total_computations', 0) / 1000.0
                    edge_vehicles = stats.get('unique_vehicles_served', 0) / 100.0
                
                tl_state.extend([edge_warnings, edge_emergencies, edge_load, edge_vehicles])
            
            # Add security features
            if self.security_enabled:
                # Placeholder for security metrics
                encrypted_ratio = 1.0  # Assume all encrypted
                auth_failures = 0
                tl_state.extend([encrypted_ratio, auth_failures])
            
            state.extend(tl_state)
        
        return np.array(state, dtype=np.float32)
    
    def _execute_action(self, action: int):
        """
        Execute action by setting traffic light phases
        
        Args:
            action: Combined action for all traffic lights
        """
        # Decode action based on actual number of phases per TL
        # For 2 TLs: action maps to (phase_tl1, phase_tl2)
        
        if len(self.tl_ids) >= 2:
            # Get number of phases for each TL
            phases_tl1 = self.phases_per_tl.get(self.tl_ids[0], 4)
            phases_tl2 = self.phases_per_tl.get(self.tl_ids[1], 4)
            
            # Decode action
            tl1_phase = action % phases_tl1
            tl2_phase = (action // phases_tl1) % phases_tl2
            
            try:
                # Only set phase if it's valid
                current_phase_tl1 = traci.trafficlight.getPhase(self.tl_ids[0])
                current_phase_tl2 = traci.trafficlight.getPhase(self.tl_ids[1])
                
                # Set phases
                traci.trafficlight.setPhase(self.tl_ids[0], tl1_phase)
                traci.trafficlight.setPhase(self.tl_ids[1], tl2_phase)
                
                # Track phase changes
                if current_phase_tl1 != tl1_phase:
                    self.last_phase_change[self.tl_ids[0]] = self.current_step
                if current_phase_tl2 != tl2_phase:
                    self.last_phase_change[self.tl_ids[1]] = self.current_step
            except Exception as e:
                # If phase setting fails, log but continue
                pass
        elif len(self.tl_ids) == 1:
            # Single TL case
            phases_tl = self.phases_per_tl.get(self.tl_ids[0], 4)
            tl_phase = action % phases_tl
            
            try:
                current_phase = traci.trafficlight.getPhase(self.tl_ids[0])
                traci.trafficlight.setPhase(self.tl_ids[0], tl_phase)
                
                if current_phase != tl_phase:
                    self.last_phase_change[self.tl_ids[0]] = self.current_step
            except Exception as e:
                pass
    
    def _calculate_reward(self, info: Dict) -> float:
        """
        Calculate reward for current state
        
        Returns:
            reward: Scalar reward value
        """
        reward = 0.0
        
        # 1. Negative reward for waiting time (primary objective)
        total_waiting = 0
        for tl_id in self.tl_ids:
            lanes = traci.trafficlight.getControlledLanes(tl_id)
            for lane in set(lanes):
                try:
                    total_waiting += traci.lane.getWaitingTime(lane)
                except:
                    pass
        
        reward -= total_waiting * 0.1  # Normalize
        
        # 2. Positive reward for throughput
        try:
            current_vehicles = len(traci.vehicle.getIDList())
            arrived = traci.simulation.getArrivedNumber()
            reward += arrived * 0.5
        except:
            pass
        
        # 3. Penalty for frequent phase changes
        recent_changes = sum(1 for t in self.last_phase_change.values() 
                           if self.current_step - t < 5)
        reward -= recent_changes * 0.1
        
        # 4. Edge computing bonuses/penalties
        if self.edge_enabled and self.controller.edge_rsus:
            # Bonus for efficient edge utilization
            for rsu in self.controller.edge_rsus.values():
                stats = rsu.get_service_statistics()
                computations = stats.get('total_computations', 0)
                if computations > 0:
                    reward += 0.01 * min(computations, 10)
                
                # Penalty for collision warnings
                collision_stats = stats.get('collision_avoidance', {})
                warnings = collision_stats.get('warnings_issued', 0)
                reward -= warnings * 0.05
                
                # Bonus for handling emergencies efficiently
                emergency_stats = stats.get('emergency', {})
                emergencies = emergency_stats.get('emergencies_handled', 0)
                reward += emergencies * 2.0
        
        # 5. Security bonuses (if enabled)
        if self.security_enabled:
            # Bonus for secure communication (placeholder)
            reward += 0.1
        
        return reward
    
    def _get_info(self) -> Dict[str, Any]:
        """
        Get additional information about current state
        
        Returns:
            info: Dictionary with metrics
        """
        info = {}
        
        # Calculate average waiting time
        total_waiting = 0
        num_vehicles = 0
        for tl_id in self.tl_ids:
            lanes = traci.trafficlight.getControlledLanes(tl_id)
            for lane in set(lanes):
                try:
                    total_waiting += traci.lane.getWaitingTime(lane)
                    num_vehicles += traci.lane.getLastStepVehicleNumber(lane)
                except:
                    pass
        
        info['avg_waiting_time'] = total_waiting / max(num_vehicles, 1)
        info['num_vehicles'] = num_vehicles
        
        # Edge computing metrics
        if self.edge_enabled and self.controller.edge_rsus:
            total_warnings = 0
            total_emergencies = 0
            for rsu in self.controller.edge_rsus.values():
                stats = rsu.get_service_statistics()
                collision_stats = stats.get('collision_avoidance', {})
                emergency_stats = stats.get('emergency', {})
                total_warnings += collision_stats.get('warnings_issued', 0)
                total_emergencies += emergency_stats.get('emergencies_handled', 0)
            
            info['collision_warnings'] = total_warnings
            info['emergencies_handled'] = total_emergencies
        else:
            info['collision_warnings'] = 0
            info['emergencies_handled'] = 0
        
        # Security metrics
        info['encrypted_messages'] = self.security_enabled
        
        return info
    
    def _get_tl_position(self, tl_id: str) -> Tuple[float, float]:
        """Get traffic light position"""
        try:
            # Get first controlled lane
            lanes = traci.trafficlight.getControlledLanes(tl_id)
            if lanes:
                shape = traci.lane.getShape(lanes[0])
                if shape:
                    return shape[-1]  # Last point of lane
        except:
            pass
        
        # Default positions if cannot determine
        if tl_id == "J2":
            return (500, 500)
        elif tl_id == "J3":
            return (1000, 500)
        return (0, 0)
    
    def _find_nearest_rsu(self, position: Tuple[float, float]):
        """Find nearest edge RSU to given position"""
        if not self.controller.edge_rsus:
            return None
        
        min_dist = float('inf')
        nearest = None
        
        for rsu in self.controller.edge_rsus.values():
            rsu_pos = rsu.position
            dist = ((position[0] - rsu_pos[0])**2 + (position[1] - rsu_pos[1])**2)**0.5
            if dist < min_dist:
                min_dist = dist
                nearest = rsu
        
        return nearest
    
    def get_traffic_light_ids(self) -> List[str]:
        """Get list of traffic light IDs"""
        return self.tl_ids
    
    def close(self):
        """Close environment and cleanup"""
        if self.controller:
            try:
                self.controller.stop_simulation()
            except:
                pass
        
        try:
            traci.close()
        except:
            pass
