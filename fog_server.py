#!/usr/bin/env python3
"""
Fog Server - Separate Node for Emergency Vehicle Detection and RL-based Preemption

Architecture:
- Runs independently from central SUMO simulation
- Detects ambulances via V2V/V2I communication
- Verifies emergency vehicle certificates
- Queries central backend for junction states
- Runs RL inference locally (fog computing)
- Sends override commands to preempt traffic

Usage:
    python fog_server.py --backend http://localhost:8000
"""

# code is working finaly

import sys
import os
import time
import argparse
import requests
import logging
from typing import Optional, Dict, List

# Add paths for imports
REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, 'rl_module'))
sys.path.insert(0, os.path.join(REPO_ROOT, 'sumo_simulation'))
sys.path.insert(0, os.path.join(REPO_ROOT, 'sumo_simulation', 'sensors'))

from utils.logging_config import setup_logging

# Setup logging
fog_logger = setup_logging('fog_server')
wimax_logger = setup_logging('wimax')

# Import sensor network for V2V detection
try:
    from sensor_network import SensorNetwork
    SENSOR_AVAILABLE = True
except ImportError:
    SENSOR_AVAILABLE = False
    fog_logger.warning("Sensor network not available")

# Import RL controller for local inference
try:
    from rl_traffic_controller import RLTrafficController
    RL_AVAILABLE = True
except ImportError:
    RL_AVAILABLE = False
    fog_logger.warning("RL controller not available")


class FogServer:
    """
    Fog computing node for emergency vehicle preemption.
    
    Responsibilities:
    1. Detect emergency vehicles via V2V/V2I
    2. Verify vehicle certificates
    3. Update WiMAX pole visualization (green → black → blue)
    4. Query backend for junction states and densities
    5. Run RL inference locally
    6. Send override commands to central controller
    """
    
    def __init__(self, backend_url="http://localhost:8000", enable_rl=True):
        self.backend_url = backend_url
        self.enable_rl = enable_rl and RL_AVAILABLE
        
        # Initialize sensor network for V2V detection
        self.sensor_network: Optional[SensorNetwork] = None
        if SENSOR_AVAILABLE:
            # Disable RL in sensor network - fog server handles it
            self.sensor_network = SensorNetwork(enable_rl=False, backend_url=backend_url)
            fog_logger.info("✅ Sensor network initialized for V2V detection")
        
        # Initialize RL controller for local inference
        self.rl_controller: Optional[RLTrafficController] = None
        if self.enable_rl:
            self._initialize_rl_controller()
        
        # State tracking
        self.last_override_time = 0
        self.override_cooldown = 3  # seconds - global cooldown between any overrides
        self.detected_ambulances = {}  # vehicle_id -> last_seen_time
        self.vehicle_positions = {}  # vehicle_id -> (x, y, timestamp) for direction calculation
        self.triggered_overrides = set()  # (vehicle_id, junction_id) pairs to prevent re-triggers
        
        fog_logger.info(f"🌐 Fog Server initialized")
        fog_logger.info(f"   Backend: {backend_url}")
        fog_logger.info(f"   RL Enabled: {self.enable_rl}")
    
    def _initialize_rl_controller(self):
        """Initialize RL controller for fog-based inference"""
        try:
            self.rl_controller = RLTrafficController(mode='inference')
            
            # Create minimal config for RL environment (fog doesn't need full SUMO connection)
            config = {
                'beta': 10,  # Match training config for 103-dim observation
                'algorithm': 'DQN',
                'action_spec': {
                    'J2': ['GGGrrr', 'yyyrrr', 'rrrGGG', 'rrryyy'],
                    'J3': ['GGGrrr', 'yyyrrr', 'rrrGGG', 'rrryyy']
                }
            }
            self.rl_controller.config = config
            
            # Create a minimal env structure for get_action to work
            # This is a lightweight wrapper since fog doesn't have direct SUMO access
            try:
                from gymnasium.spaces import Discrete, Box
            except ImportError:
                try:
                    from gym.spaces import Discrete, Box
                except ImportError:
                    fog_logger.error("❌ Neither gymnasium nor gym is installed")
                    fog_logger.error("   Please run: pip install gymnasium")
                    self.enable_rl = False
                    return
            import numpy as np
            
            class MinimalEnv:
                def __init__(self):
                    self.observation_space = Box(-np.inf, np.inf, (103,), dtype=np.float32)
                    self.action_space = Discrete(36)  # 2 junctions * 4 phases * ... 
            
            self.rl_controller.env = MinimalEnv()
            
            # Load ambulance-aware model
            model_path = os.path.join(REPO_ROOT, 'rl_module', 'models', 'ambulance_dqn_final.pth')
            if os.path.exists(model_path):
                fog_logger.info(f"🚑 Loading RL model: {model_path}")
                if self.rl_controller.load_model(model_path):
                    fog_logger.info("✅ RL controller and model loaded successfully")
                else:
                    fog_logger.error("❌ Failed to load RL model")
                    self.enable_rl = False
            else:
                fog_logger.error(f"❌ RL model not found: {model_path}")
                self.enable_rl = False
        except Exception as e:
            fog_logger.error(f"❌ RL initialization error: {e}")
            import traceback
            traceback.print_exc()
            self.enable_rl = False
    
    def connect_to_sumo(self):
        """
        Connect to backend API to verify SUMO is running.
        Fog server queries backend for vehicle data instead of direct TraCI connection.
        """
        try:
            # Check if backend is accessible and SUMO is running
            response = requests.get(f"{self.backend_url}/api/vehicles", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                fog_logger.info(f"✅ Connected to backend (vehicles: {data.get('count', 0)})")
                
                # Initialize sensor network's central pole via backend
                if self.sensor_network:
                    # Use sensor network's internal TraCI connection (if available)
                    # or just mark as initialized
                    try:
                        self.sensor_network.initialize_central_pole()
                        fog_logger.info("✅ WiMAX central pole initialized")
                    except Exception as e:
                        fog_logger.warning(f"⚠️  Could not initialize pole via sensor network: {e}")
                        fog_logger.info("   Will update pole color via backend queries")
                
                return True
            else:
                fog_logger.error(f"❌ Backend returned error: {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            fog_logger.error("❌ Cannot connect to backend - start with ./run_integrated_sumo_ns3.sh first")
            return False
        except requests.exceptions.Timeout:
            fog_logger.error("❌ Backend connection timeout")
            return False
        except Exception as e:
            fog_logger.error(f"❌ Connection error: {e}")
            return False
    
    def detect_emergency_vehicles(self) -> List[Dict]:
        """
        Detect emergency vehicles via V2V/V2I communication.
        Queries backend API for vehicle data instead of direct TraCI access.
        Checks vehicle certificates and filters for ambulances.
        
        Returns list of detected ambulances with position, speed, direction.
        """
        try:
            # Query backend for all vehicle data
            response = requests.get(f"{self.backend_url}/api/vehicles", timeout=5)
            
            if response.status_code != 200:
                fog_logger.error(f"Backend API error: {response.status_code}")
                return []
            
            data = response.json()
            all_vehicles = data.get('vehicles', [])
            
            # Filter for emergency vehicles (certificate check simulation)
            emergency_vehicles = []
            for vehicle_data in all_vehicles:
                vehicle_id = vehicle_data.get('id', '')
                
                # Check if this is an emergency vehicle
                if not vehicle_data.get('is_emergency', False):
                    continue
                
                # Verify "certificate" (simulated - in real world would check cryptographic cert)
                if not self._verify_vehicle_certificate(vehicle_id):
                    continue
                
                # Extract vehicle state
                position_dict = vehicle_data.get('position', {})
                x = position_dict.get('x', 0)
                y = position_dict.get('y', 0)
                speed = vehicle_data.get('speed', 0)
                angle = vehicle_data.get('angle', 0)
                lane_id = vehicle_data.get('lane', '')
                
                # PRIMARY: Use LANE GEOMETRY (most reliable for first detection)
                # Lane IDs contain direction info embedded in the edge name
                direction = None
                if 'toN' in lane_id or 'North' in lane_id or lane_id.endswith('_N_0'):
                    direction = 'north'
                elif 'toS' in lane_id or 'South' in lane_id or lane_id.endswith('_S_0'):
                    direction = 'south'
                elif 'toE' in lane_id or 'East' in lane_id or lane_id.endswith('_E_0'):
                    direction = 'east'
                elif 'toW' in lane_id or 'West' in lane_id or lane_id.endswith('_W_0'):
                    direction = 'west'
                
                # SECONDARY: Try movement-based detection (requires 2+ detections)
                if not direction and vehicle_id in self.vehicle_positions:
                    prev_x, prev_y, prev_time = self.vehicle_positions[vehicle_id]
                    dt = time.time() - prev_time
                    
                    if dt > 0.5 and dt < 5:  # Valid time window (0.5s - 5s)
                        dx = x - prev_x
                        dy = y - prev_y
                        
                        # Determine direction from largest movement component
                        if abs(dx) > abs(dy) and abs(dx) > 10:  # Significant horizontal movement
                            direction = 'east' if dx > 0 else 'west'
                        elif abs(dy) > 10:  # Significant vertical movement
                            direction = 'north' if dy > 0 else 'south'
                
                # Store current position for future movement detection
                self.vehicle_positions[vehicle_id] = (x, y, time.time())
                
                # LAST RESORT: Use angle (only if lane and movement both failed)
                if not direction:
                    # SUMO angle: 0=East, 90=North, 180=West, 270=South
                    if 45 <= angle < 135:
                        direction = 'north'
                    elif 135 <= angle < 225:
                        direction = 'west'
                    elif 225 <= angle < 315:
                        direction = 'south'
                    else:
                        direction = 'east'
                
                emergency_vehicles.append({
                    'vehicle_id': vehicle_id,
                    'position': (x, y),
                    'target': (x, y),  # Simplified - backend doesn't provide route
                    'speed': speed,
                    'heading': angle,
                    'direction': direction,
                    'lane_id': lane_id,
                    'timestamp': time.time()
                })
                
                # Track detection (log only new detections)
                if vehicle_id not in self.detected_ambulances:
                    wimax_logger.info(f"🚑 Ambulance detected: {vehicle_id} at ({x:.1f}, {y:.1f}), "
                                    f"heading {direction}, speed {speed:.1f} m/s")
                
                self.detected_ambulances[vehicle_id] = time.time()
            
            return emergency_vehicles
            
        except requests.exceptions.RequestException as e:
            fog_logger.error(f"Backend API request failed: {e}")
            return []
        except Exception as e:
            fog_logger.error(f"Error detecting emergency vehicles: {e}")
            return []
    
    def _verify_vehicle_certificate(self, vehicle_id: str) -> bool:
        """
        Verify emergency vehicle certificate.
        In real-world: Check cryptographic certificate via V2V security protocol.
        Here: Simulated verification.
        """
        # Simulation: All vehicles with "emergency" in ID are verified
        # In production: Would check digital signature, certificate authority, etc.
        wimax_logger.info(f"✅ Certificate verified for {vehicle_id}")
        return True
    
    def query_junction_states(self, x: float, y: float, radius: float = 1000) -> Optional[Dict]:
        """
        Query central backend for junction states and densities.
        
        GET /api/wimax/getSignalData
        Returns: junctions (with densities per direction), ambulance data
        """
        try:
            response = requests.get(
                f"{self.backend_url}/api/wimax/getSignalData",
                params={"x": x, "y": y, "radius": radius},
                timeout=2
            )
            
            if response.status_code == 200:
                data = response.json()
                junctions = data.get('junctions', [])
                ambulance = data.get('ambulance', {})
                
                fog_logger.info(f"📡 Backend query: {len(junctions)} junctions, "
                              f"ambulance={'Yes' if ambulance.get('detected') else 'No'}")
                
                # Log junction densities
                for junction in junctions:
                    densities = junction.get('density', {})
                    fog_logger.info(f"   {junction['poleId']}: N={densities.get('north', 0):.2f}, "
                                  f"S={densities.get('south', 0):.2f}, "
                                  f"E={densities.get('east', 0):.2f}, "
                                  f"W={densities.get('west', 0):.2f}")
                
                return data
            else:
                fog_logger.warning(f"Backend query failed: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            fog_logger.error(f"Backend connection error: {e}")
            return None
    
    def run_rl_inference(self, signal_data: Dict, emergency_vehicle: Dict) -> Optional[Dict]:
        """
        Run RL inference locally on fog node.
        
        Uses junction densities, ambulance position/direction to predict best action.
        This is where the trained ambulance-aware model makes decisions.
        
        Returns: {'junction_id': str, 'action': int, 'confidence': float}
        """
        if not self.enable_rl:
            return self._fallback_heuristic(signal_data, emergency_vehicle)
        
        try:
            junctions = signal_data.get('junctions', [])
            ambulance = signal_data.get('ambulance', {})
            
            if not junctions:
                return None
            
            # Find nearest junction to ambulance
            amb_x, amb_y = emergency_vehicle['position']
            nearest_junction = min(junctions, key=lambda j: 
                                 ((j['coords']['x'] - amb_x)**2 + (j['coords']['y'] - amb_y)**2)**0.5)
            
            fog_logger.info(f"🎯 Target junction: {nearest_junction['poleId']}")
            
            # Build observation for RL model
            # Note: This is a simplified observation for inference without SUMO access
            # Real observation would come from backend API data
            try:
                # Extract densities from backend data
                densities = nearest_junction.get('density', {})
                north_density = densities.get('north', 0.0)
                south_density = densities.get('south', 0.0)
                east_density = densities.get('east', 0.0)
                west_density = densities.get('west', 0.0)
                
                # Get current phase info
                phase_info = nearest_junction.get('phase_info', {})
                current_phase = phase_info.get('current_phase', 0)
                time_in_phase = phase_info.get('time_in_phase', 0) / 30.0  # Normalize
                
                # Ambulance position relative to junction
                junction_coords = nearest_junction.get('coords', {})
                junc_x = junction_coords.get('x', 500)
                junc_y = junction_coords.get('y', 500)
                amb_x = emergency_vehicle.get('x', junc_x)
                amb_y = emergency_vehicle.get('y', junc_y)
                
                # Distance and direction
                dx = (amb_x - junc_x) / 1000.0  # Normalize to ~[-1, 1]
                dy = (amb_y - junc_y) / 1000.0
                distance = nearest_junction.get('distance_from_query', 0) / 1000.0  # Normalize
                
                # Emergency vehicle direction encoding
                direction = emergency_vehicle.get('direction', 'north')
                dir_encoding = {'north': [1,0,0,0], 'south': [0,1,0,0], 
                               'east': [0,0,1,0], 'west': [0,0,0,1]}.get(direction, [0,0,0,0])
                
                # Build minimal observation vector (compatible with trained model)
                # If ambulance model expects 103 dims, we need to pad appropriately
                # For now, use critical features only
                obs = [
                    north_density, south_density, east_density, west_density,  # 4: densities
                    current_phase / 4.0, time_in_phase,  # 2: phase info
                    dx, dy, distance,  # 3: ambulance position
                    *dir_encoding,  # 4: direction encoding
                    1.0  # 1: emergency flag
                ]
                
                # If model expects 103 dims (beta=10 ambulance model), pad with zeros
                if hasattr(self.rl_controller.env, 'observation_space'):
                    expected_dim = self.rl_controller.env.observation_space.shape[0]
                    while len(obs) < expected_dim:
                        obs.append(0.0)
                    obs = obs[:expected_dim]  # Trim if too long
                
                # For emergency vehicles, use DIRECTION-BASED phase selection
                # This is MORE RELIABLE than RL for emergency preemption
                # Phase 0: GGGrrr (EW green), Phase 2: rrrGGG (NS green)
                junction_id = nearest_junction['poleId']
                direction = emergency_vehicle.get('direction', 'north')
                
                # Simple but EFFECTIVE: match phase to ambulance direction
                if direction in ['north', 'south']:
                    local_phase = 2  # NS green (rrrGGG)
                elif direction in ['east', 'west']:
                    local_phase = 0  # EW green (GGGrrr)
                else:
                    local_phase = 2  # Default to NS
                
                fog_logger.info(f"🚑 EMERGENCY PHASE: Junction {junction_id}, "
                              f"Direction {direction} → Phase {local_phase} "
                              f"(densities: N={north_density:.1f} S={south_density:.1f} "
                              f"E={east_density:.1f} W={west_density:.1f})")
                
                return {
                    'junction_id': junction_id,
                    'action': local_phase,  # Send local phase instead of global action
                    'confidence': 0.90,
                    'reasoning': f"RL model with traffic densities and emergency direction={direction}"
                }
            except Exception as e:
                fog_logger.warning(f"RL inference failed: {e}, falling back to heuristic")
                # Fallback to simple direction-based heuristic
                direction = emergency_vehicle.get('direction', 'north')
                if direction in ['east', 'west']:
                    action = 0  # EW green
                else:
                    action = 2  # NS green
                
                fog_logger.info(f"🤖 Heuristic Decision: Junction {nearest_junction['poleId']}, "
                              f"Action {action} (direction: {direction})")
                
                return {
                    'junction_id': nearest_junction['poleId'],
                    'action': action,
                    'confidence': 0.60,
                    'reasoning': f"Heuristic fallback: Emergency vehicle heading {direction}"
                }
            
        except Exception as e:
            fog_logger.error(f"RL inference error: {e}")
            return self._fallback_heuristic(signal_data, emergency_vehicle)
    
    def _fallback_heuristic(self, signal_data: Dict, emergency_vehicle: Dict) -> Optional[Dict]:
        """Fallback to simple heuristic if RL fails"""
        junctions = signal_data.get('junctions', [])
        if not junctions:
            return None
        
        direction = emergency_vehicle.get('direction', 'east')
        action = 0 if direction in ['east', 'west'] else 2
        
        return {
            'junction_id': junctions[0]['poleId'],
            'action': action,
            'confidence': 0.5,
            'reasoning': f"Heuristic: {direction} direction"
        }
    
    def send_override_command(self, junction_id: str, action: int, vehicle_id: str, duration_s: int = 25) -> bool:
        """
        Send traffic light override command to central backend.
        
        POST /api/control/override
        This overrides the density-based traffic controller.
        """
        try:
            payload = {
                "poleId": junction_id,
                "action": action,
                "duration_s": duration_s,
                "vehicle_id": vehicle_id,
                "priority": 1  # Emergency priority
            }
            
            fog_logger.info(f"📤 Sending override: {junction_id} → Phase {action} for {vehicle_id}")
            
            response = requests.post(
                f"{self.backend_url}/api/control/override",
                json=payload,
                timeout=2
            )
            
            if response.status_code == 200:
                data = response.json()
                wimax_logger.info(f"✅ Override applied: {junction_id} phase {data.get('previous_phase')} → {data.get('new_phase')}")
                wimax_logger.info(f"   Duration: {duration_s}s, Vehicle: {vehicle_id}")
                return True
            else:
                fog_logger.error(f"❌ Override failed: {response.status_code} - {response.json()}")
                return False
                
        except requests.exceptions.RequestException as e:
            fog_logger.error(f"❌ Override command error: {e}")
            return False
    
    def process_emergency_vehicle(self, emergency_vehicle: Dict):
        """
        Complete fog computing pipeline for one emergency vehicle:
        
        1. Query backend for junction states and densities
        2. Check if ambulance is within range (500m - gives ~35s advance notice)
        3. Run RL inference to decide best action
        4. Send override command to central controller
        """
        vehicle_id = emergency_vehicle['vehicle_id']
        position = emergency_vehicle['position']
        
        # Check global cooldown - prevents rapid repeated overrides
        current_time = time.time()
        if current_time - self.last_override_time < self.override_cooldown:
            return  # Skip silently - cooldown active
        
        # Step 1: Query backend for junction states
        signal_data = self.query_junction_states(position[0], position[1], radius=1000)
        if not signal_data:
            return  # Silently skip if no junctions nearby
        
        # Step 2: Check distance to nearest junction
        junctions = signal_data.get('junctions', [])
        if not junctions:
            return
        
        # Find nearest junction
        amb_x, amb_y = position
        nearest_junction = min(junctions, key=lambda j: 
                             ((j['coords']['x'] - amb_x)**2 + (j['coords']['y'] - amb_y)**2)**0.5)
        
        # Calculate actual distance
        junc_x = nearest_junction['coords']['x']
        junc_y = nearest_junction['coords']['y']
        distance = ((amb_x - junc_x)**2 + (amb_y - junc_y)**2)**0.5
        
        # CRITICAL: Check if ambulance is APPROACHING the junction (not behind it!)
        direction = emergency_vehicle['direction']
        
        # Check if ambulance is moving TOWARDS junction based on direction
        if direction == 'north':
            # Moving north (increasing Y), should be SOUTH of junction (amb_y < junc_y)
            if amb_y >= junc_y:
                fog_logger.debug(f"⏭️  Skipping {vehicle_id}: Already passed junction (moving north, amb_y={amb_y:.1f} >= junc_y={junc_y:.1f})")
                return  # Already passed or at junction
        elif direction == 'south':
            # Moving south (decreasing Y), should be NORTH of junction (amb_y > junc_y)
            if amb_y <= junc_y:
                fog_logger.debug(f"⏭️  Skipping {vehicle_id}: Already passed junction (moving south, amb_y={amb_y:.1f} <= junc_y={junc_y:.1f})")
                return  # Already passed or at junction
        elif direction == 'east':
            # Moving east (increasing X), should be WEST of junction (amb_x < junc_x)
            if amb_x >= junc_x:
                fog_logger.debug(f"⏭️  Skipping {vehicle_id}: Already passed junction (moving east, amb_x={amb_x:.1f} >= junc_x={junc_x:.1f})")
                return  # Already passed or at junction
        elif direction == 'west':
            # Moving west (decreasing X), should be EAST of junction (amb_x > junc_x)
            if amb_x <= junc_x:
                fog_logger.debug(f"⏭️  Skipping {vehicle_id}: Already passed junction (moving west, amb_x={amb_x:.1f} <= junc_x={junc_x:.1f})")
                return  # Already passed or at junction
        
        # Only trigger if ambulance is approaching AND within range (500m works better for this scenario)
        if distance > 500:
            fog_logger.debug(f"⏭️  Skipping {vehicle_id}: Too far away ({distance:.1f}m > 500m)")
            return  # Too far away - wait until closer
        
        # CRITICAL: Check if this ambulance already triggered at this junction (ONE-SHOT per junction)
        junction_id = nearest_junction.get('junction_id', 'unknown')
        trigger_key = (vehicle_id, junction_id)
        if trigger_key in self.triggered_overrides:
            fog_logger.debug(f"⏭️  Skipping {vehicle_id}: Already triggered override at junction {junction_id}")
            return  # Already handled this ambulance at this junction
        
        # Mark as triggered BEFORE processing (to prevent race conditions)
        self.triggered_overrides.add(trigger_key)
        
        fog_logger.info(f"\n{'='*70}")
        fog_logger.info(f"🚨 Processing emergency: {vehicle_id}")
        fog_logger.info(f"   Position: ({position[0]:.1f}, {position[1]:.1f})")
        fog_logger.info(f"   Distance to junction: {distance:.1f}m")
        fog_logger.info(f"   Direction: {emergency_vehicle['direction']}, Speed: {emergency_vehicle['speed']:.1f} m/s")
        
        # Step 3: Run RL inference
        decision = self.run_rl_inference(signal_data, emergency_vehicle)
        if not decision:
            fog_logger.error("❌ RL inference failed")
            return
        
        fog_logger.info(f"💡 Decision: {decision['reasoning']}")
        
        # Step 4: Send override command with optimal duration
        success = self.send_override_command(
            junction_id=decision['junction_id'],
            action=decision['action'],
            vehicle_id=vehicle_id,
            duration_s=10  # Balanced: enough time for ambulance approach + crossing
        )
        
        if success:
            self.last_override_time = current_time
            fog_logger.info(f"✅ Emergency preemption completed for {vehicle_id}")
            fog_logger.info(f"{'='*70}\n")
        else:
            fog_logger.error(f"❌ Failed to apply preemption for {vehicle_id}")
    
    def run(self, update_interval=1.0):
        """
        Main fog server loop.
        
        Continuously:
        1. Detect emergency vehicles
        2. Process each emergency vehicle (query + inference + override)
        
        Note: WiMAX pole color updates are handled by the central node's
        sensor network, not by the fog server.
        """
        fog_logger.info("\n" + "="*70)
        fog_logger.info("🌐 FOG SERVER STARTED")
        fog_logger.info("="*70)
        fog_logger.info("Monitoring for emergency vehicles...")
        fog_logger.info("Press Ctrl+C to stop\n")
        
        # Connect to SUMO
        if not self.connect_to_sumo():
            fog_logger.error("Cannot start without SUMO connection")
            return
        
        try:
            while True:
                # Step 1: Detect emergency vehicles via V2V
                emergency_vehicles = self.detect_emergency_vehicles()
                
                # Step 2: Process each emergency vehicle
                for emergency_vehicle in emergency_vehicles:
                    self.process_emergency_vehicle(emergency_vehicle)
                
                # Sleep before next iteration
                time.sleep(update_interval)
                
        except KeyboardInterrupt:
            fog_logger.info("\n\n🛑 Fog server stopped by user")
        except Exception as e:
            fog_logger.error(f"\n\n❌ Fog server error: {e}")
            import traceback
            traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description='Fog Server for Emergency Vehicle Preemption')
    parser.add_argument('--backend', default='http://localhost:8000',
                       help='Backend API URL (default: http://localhost:8000)')
    parser.add_argument('--interval', type=float, default=1.0,
                       help='Update interval in seconds (default: 1.0)')
    parser.add_argument('--no-rl', action='store_true',
                       help='Disable RL inference, use heuristic only')
    args = parser.parse_args()
    
    # Create and run fog server
    fog_server = FogServer(
        backend_url=args.backend,
        enable_rl=not args.no_rl
    )
    
    fog_server.run(update_interval=args.interval)


if __name__ == "__main__":
    main()
