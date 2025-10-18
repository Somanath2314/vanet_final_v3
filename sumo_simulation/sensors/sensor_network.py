"""
Sensor Detection System for VANET Traffic Management
Simulates radar/LIDAR sensors placed every 100m over 0.5km approaches
"""

import random
import time
import json
from dataclasses import dataclass
from typing import Dict, List, Tuple
from enum import Enum
import os
import sys
import logging

# Make sure repo root is on path so we can import utils.logging_config
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from utils.logging_config import setup_logging

# WiMAX logger (writes to backend/updated_logs/wimax/wimax.log)
wimax_logger = setup_logging('wimax')

class SensorType(Enum):
    RADAR = "radar"
    LIDAR = "lidar"
    INDUCTION_LOOP = "induction_loop"

@dataclass
class VehicleDetection:
    vehicle_id: str
    timestamp: float
    speed: float
    distance_from_intersection: float
    lane_id: str
    vehicle_type: str
    is_emergency: bool = False

@dataclass
class SensorReading:
    sensor_id: str
    sensor_type: SensorType
    position: Tuple[float, float]
    distance_from_intersection: float
    lane_id: str
    occupancy: float  # 0.0 to 1.0
    vehicle_count: int
    average_speed: float
    detections: List[VehicleDetection]
    timestamp: float

class SensorNetwork:
    """Manages a network of sensors for vehicle detection"""
    
    def __init__(self):
        self.sensors: Dict[str, SensorReading] = {}
        self.detection_history: List[VehicleDetection] = []
        self.sensor_positions = self._initialize_sensor_positions()
        # Central pole / visualization state and debounce counters
        self.central_pole_id = None
        self.central_pole_position = None
        # central_pole_state: 'green', 'black' (in-network), 'blue' (near)
        self.central_pole_state = 'green'
        # debounce counters for 'blue' (close) detection
        self._emergency_counter = 0
        self._no_emergency_counter = 0
        self._emergency_debounce_threshold = 3  # steps required to switch to blue
        self._no_emergency_debounce_threshold = 5  # steps required to switch back to green from blue
        self._pole_detection_distance = 150.0  # meters for pole-triggering events
        # counters for global (in-network) emergency presence -> 'black' state
        self._global_emergency_counter = 0
        self._no_global_emergency_counter = 0
        self._global_debounce_threshold = 1
        self._global_no_debounce_threshold = 3
        # cache of verified vehicle_ids to avoid re-verification within a session
        self._verified_cache = set()
        
    def _initialize_sensor_positions(self) -> Dict[str, Tuple[float, float, str]]:
        """Initialize sensor positions (x, y, lane_id) every 100m over 0.5km"""
        positions = {}
        
        # E1 approach sensors (East-West)
        for i, distance in enumerate([500, 400, 300, 200, 100, 50]):
            sensor_id = f"sensor_E1_{distance}m"
            positions[sensor_id] = (500 - distance, 500, "E1_0")
            
        # E2 approach sensors
        for i, distance in enumerate([500, 400, 300, 200, 100, 50]):
            sensor_id = f"sensor_E2_{distance}m"
            positions[sensor_id] = (1000 - distance, 500, "E2_0")
            
        # E5 approach sensors (North-South)
        for i, distance in enumerate([500, 400, 300, 200, 100, 50]):
            sensor_id = f"sensor_E5_{distance}m"
            positions[sensor_id] = (500, 500 - distance, "E5_0")
            
        # E7 approach sensors
        for i, distance in enumerate([500, 400, 300, 200, 100, 50]):
            sensor_id = f"sensor_E7_{distance}m"
            positions[sensor_id] = (1000, 500 - distance, "E7_0")
            
        return positions
    
    def simulate_radar_detection(self, sensor_id: str, vehicles_in_range: List[Dict]) -> SensorReading:
        """Simulate radar sensor detection with noise and accuracy"""
        if sensor_id not in self.sensor_positions:
            return None
            
        pos = self.sensor_positions[sensor_id]
        detections = []
        
        for vehicle in vehicles_in_range:
            # Add radar noise (±2 km/h speed, ±1m distance)
            speed_noise = random.uniform(-2, 2)
            distance_noise = random.uniform(-1, 1)
            
            detection = VehicleDetection(
                vehicle_id=vehicle.get('id', f"v_{random.randint(1000, 9999)}"),
                timestamp=time.time(),
                speed=max(0, vehicle.get('speed', 30) + speed_noise),
                distance_from_intersection=max(0, vehicle.get('distance', 100) + distance_noise),
                lane_id=pos[2],
                vehicle_type=vehicle.get('type', 'passenger'),
                is_emergency=vehicle.get('type') == 'emergency'
            )
            detections.append(detection)
        
        # Calculate sensor metrics
        occupancy = min(1.0, len(detections) / 10.0)  # Max 10 vehicles per sensor range
        avg_speed = sum(d.speed for d in detections) / len(detections) if detections else 0
        
        reading = SensorReading(
            sensor_id=sensor_id,
            sensor_type=SensorType.RADAR,
            position=pos[:2],
            distance_from_intersection=self._extract_distance_from_id(sensor_id),
            lane_id=pos[2],
            occupancy=occupancy,
            vehicle_count=len(detections),
            average_speed=avg_speed,
            detections=detections,
            timestamp=time.time()
        )
        
        self.sensors[sensor_id] = reading
        self.detection_history.extend(detections)
        return reading
    
    def simulate_lidar_detection(self, sensor_id: str, vehicles_in_range: List[Dict]) -> SensorReading:
        """Simulate LIDAR sensor detection with high precision"""
        if sensor_id not in self.sensor_positions:
            return None
            
        pos = self.sensor_positions[sensor_id]
        detections = []
        
        for vehicle in vehicles_in_range:
            # LIDAR has higher precision (±0.5 km/h speed, ±0.1m distance)
            speed_noise = random.uniform(-0.5, 0.5)
            distance_noise = random.uniform(-0.1, 0.1)
            
            detection = VehicleDetection(
                vehicle_id=vehicle.get('id', f"v_{random.randint(1000, 9999)}"),
                timestamp=time.time(),
                speed=max(0, vehicle.get('speed', 30) + speed_noise),
                distance_from_intersection=max(0, vehicle.get('distance', 100) + distance_noise),
                lane_id=pos[2],
                vehicle_type=vehicle.get('type', 'passenger'),
                is_emergency=vehicle.get('type') == 'emergency'
            )
            detections.append(detection)
        
        # Calculate sensor metrics
        occupancy = min(1.0, len(detections) / 8.0)  # LIDAR more precise
        avg_speed = sum(d.speed for d in detections) / len(detections) if detections else 0
        
        reading = SensorReading(
            sensor_id=sensor_id,
            sensor_type=SensorType.LIDAR,
            position=pos[:2],
            distance_from_intersection=self._extract_distance_from_id(sensor_id),
            lane_id=pos[2],
            occupancy=occupancy,
            vehicle_count=len(detections),
            average_speed=avg_speed,
            detections=detections,
            timestamp=time.time()
        )
        
        self.sensors[sensor_id] = reading
        self.detection_history.extend(detections)
        return reading
    
    def _extract_distance_from_id(self, sensor_id: str) -> float:
        """Extract distance from sensor ID"""
        try:
            parts = sensor_id.split('_')
            distance_str = parts[-1].replace('m', '')
            return float(distance_str)
        except:
            return 100.0
    
    def get_traffic_density(self, lane_id: str) -> Tuple[str, float]:
        """Calculate traffic density for a lane"""
        lane_sensors = [s for s in self.sensors.values() if s.lane_id == lane_id]
        if not lane_sensors:
            return "LOW", 0.0
            
        avg_occupancy = sum(s.occupancy for s in lane_sensors) / len(lane_sensors)
        total_vehicles = sum(s.vehicle_count for s in lane_sensors)
        
        if avg_occupancy < 0.3:
            return "LOW", avg_occupancy
        elif avg_occupancy < 0.7:
            return "MEDIUM", avg_occupancy
        else:
            return "HIGH", avg_occupancy
    
    def get_queue_length(self, lane_id: str) -> float:
        """Estimate queue length based on sensor data"""
        lane_sensors = [s for s in self.sensors.values() if s.lane_id == lane_id]
        if not lane_sensors:
            return 0.0
            
        # Sort sensors by distance from intersection
        lane_sensors.sort(key=lambda s: s.distance_from_intersection)
        
        queue_length = 0.0
        for sensor in lane_sensors:
            if sensor.occupancy > 0.5 and sensor.average_speed < 5.0:  # Stopped/slow traffic
                queue_length = max(queue_length, sensor.distance_from_intersection)
        
        return queue_length
    
    def detect_emergency_vehicles(self) -> List[VehicleDetection]:
        """Detect emergency vehicles from all sensors"""
        emergency_vehicles = []

        # Check recent detections (last 10 time steps)
        for detection in self.detection_history[-100:]:  # Check last 100 detections
            if detection.is_emergency and detection.timestamp > time.time() - 10:  # Within last 10 seconds
                emergency_vehicles.append(detection)

        # Also check current sensor readings
        for sensor in self.sensors.values():
            for detection in sensor.detections:
                if detection.is_emergency:
                    emergency_vehicles.append(detection)

        # Also check SUMO directly for emergency vehicles
        try:
            import traci
            all_vehicles = traci.vehicle.getIDList()
            for veh_id in all_vehicles:
                if 'emergency' in veh_id.lower() or 'ambulance' in veh_id.lower() or 'fire' in veh_id.lower():
                    try:
                        lane_id = traci.vehicle.getLaneID(veh_id)
                        distance = traci.vehicle.getLanePosition(veh_id)
                        lane_length = traci.lane.getLength(lane_id)
                        distance_from_intersection = lane_length - distance

                        # Create emergency detection
                        emergency_detection = VehicleDetection(
                            vehicle_id=veh_id,
                            timestamp=time.time(),
                            speed=traci.vehicle.getSpeed(veh_id) * 3.6,  # Convert to km/h
                            distance_from_intersection=distance_from_intersection,
                            lane_id=lane_id,
                            vehicle_type='emergency',
                            is_emergency=True
                        )
                        emergency_vehicles.append(emergency_detection)
                    except:
                        continue
        except:
            pass

        # Remove duplicates based on vehicle_id
        seen_ids = set()
        unique_emergencies = []
        for emergency in emergency_vehicles:
            if emergency.vehicle_id not in seen_ids:
                seen_ids.add(emergency.vehicle_id)
                unique_emergencies.append(emergency)

        # WiMAX verification: check persisted verified store and update logs
        try:
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            wimax_dir = os.path.join(repo_root, 'backend', 'updated_logs', 'wimax')
            store_path = os.path.join(wimax_dir, 'verified_vehicles.json')

            verified_store = {}
            if os.path.exists(store_path):
                try:
                    with open(store_path, 'r') as sf:
                        verified_store = json.load(sf)
                except Exception:
                    verified_store = {}

            for det in unique_emergencies:
                vid = det.vehicle_id
                if vid in self._verified_cache:
                    continue

                if vid in verified_store:
                    wimax_logger.info("Verified vehicle detected", extra={'extra': {'vehicle_id': vid, 'status': 'verified_store'}})
                    self._verified_cache.add(vid)
                else:
                    # heuristic: if ID contains 'emergency' treat as ambulance and auto-register
                    if 'emergency' in vid.lower() or 'ambulance' in vid.lower():
                        wimax_logger.warning("Unverified emergency id seen; auto-registering in store", extra={'extra': {'vehicle_id': vid}})
                        try:
                            os.makedirs(wimax_dir, exist_ok=True)
                            verified_store[vid] = {'vehicle_id': vid, 'registered_at': time.time(), 'note': 'auto_registered_by_wimax'}
                            with open(store_path, 'w') as sf:
                                json.dump(verified_store, sf)
                            self._verified_cache.add(vid)
                        except Exception as e:
                            wimax_logger.error("Failed to auto-register vehicle", extra={'extra': {'vehicle_id': vid, 'error': str(e)}})
                    else:
                        wimax_logger.warning("Suspicious vehicle signal (not verified)", extra={'extra': {'vehicle_id': vid}})
        except Exception as e:
            wimax_logger.error("WiMAX verification failure", extra={'extra': {'error': str(e)}})

        return unique_emergencies
    
    def get_sensor_data_summary(self) -> Dict:
        """Get summary of all sensor data for API"""
        summary = {
            'total_sensors': len(self.sensors),
            'active_sensors': len([s for s in self.sensors.values() if s.vehicle_count > 0]),
            'total_vehicles_detected': sum(s.vehicle_count for s in self.sensors.values()),
            'emergency_vehicles': len(self.detect_emergency_vehicles()),
            'lane_densities': {},
            'queue_lengths': {},
            'timestamp': time.time()
        }
        
        # Calculate per-lane metrics
        lanes = set(s.lane_id for s in self.sensors.values())
        for lane in lanes:
            density, value = self.get_traffic_density(lane)
            summary['lane_densities'][lane] = {'level': density, 'value': value}
            summary['queue_lengths'][lane] = self.get_queue_length(lane)
        
        return summary
    
    def initialize_central_pole(self):
        """Initialize a central pole in the SUMO simulation."""
        try:
            import traci
            # Define the position of the central pole and draw a circular marker
            self.central_pole_id = "central_pole"
            # place the pole at y=530 as requested
            self.central_pole_position = (750, 530)

            # Create a circular polygon approximation (32 points) for a smooth circle
            import math
            cx, cy = self.central_pole_position
            radius = 8  # pixels/meters depending on SUMO view scale; tweak if needed
            points = []
            steps = 32
            for i in range(steps):
                theta = 2 * math.pi * i / steps
                x = cx + radius * math.cos(theta)
                y = cy + radius * math.sin(theta)
                points.append((x, y))

            # Add the circular polygon to SUMO GUI
            traci.polygon.add(self.central_pole_id, shape=points, color=(0, 255, 0, 255))
            print("Central pole initialized at position:", self.central_pole_position)
            # reset debounce counters/state
            self.central_pole_state = 'green'
            self._emergency_counter = 0
            self._no_emergency_counter = 0
        except ImportError:
            print("traci module not available. Ensure SUMO is properly configured.")
        except Exception as e:
            print("Error initializing central pole:", e)

    def update_central_pole_color(self, is_emergency_detected: bool):
        """Update the color of the central pole based on emergency detection."""
        # Deprecated boolean API kept for compatibility
        try:
            import traci
            print("Attempting to update central pole color...")
            # allow callers to pass a state string directly
            if isinstance(is_emergency_detected, str):
                state = is_emergency_detected
            else:
                state = 'blue' if is_emergency_detected else 'green'

            if state == 'blue':
                traci.polygon.setColor(self.central_pole_id, (0, 0, 255, 255))
                print("Central pole color set to blue.")
            elif state == 'black':
                # black (in-network emergency)
                traci.polygon.setColor(self.central_pole_id, (0, 0, 0, 255))
                print("Central pole color set to black.")
            else:
                traci.polygon.setColor(self.central_pole_id, (0, 255, 0, 255))
                print("Central pole color set to green.")
        except ImportError:
            print("traci module not available. Ensure SUMO is properly configured.")
        except Exception as e:
            print("Error updating central pole color:", e)
            print("Debug: state=", is_emergency_detected)

    def detect_emergency_vehicles_and_update_pole(self) -> List[VehicleDetection]:
        """Detect emergency vehicles and update the central pole color."""
        emergency_vehicles = self.detect_emergency_vehicles()

        # Any emergency anywhere (global/in-network)
        any_emergency = len(emergency_vehicles) > 0

        # Filter emergency detections by proximity to intersection/pole
        close_emergencies = [e for e in emergency_vehicles if getattr(e, 'distance_from_intersection', float('inf')) <= self._pole_detection_distance]

        # Update global counters
        if any_emergency:
            print(f"Emergency anywhere in network: {[v.vehicle_id for v in emergency_vehicles]}")
            self._global_emergency_counter += 1
            self._no_global_emergency_counter = 0
        else:
            self._no_global_emergency_counter += 1
            self._global_emergency_counter = 0

        # Update close-emergency counters
        if close_emergencies:
            print(f"Emergency vehicles close: {[v.vehicle_id for v in close_emergencies]}")
            self._emergency_counter += 1
            self._no_emergency_counter = 0
        else:
            print("No emergency vehicles detected.")
            self._no_emergency_counter += 1
            self._emergency_counter = 0

        # Decide desired state, priority: blue (close) > black (in-network) > green
        desired_state = self.central_pole_state

        if self._emergency_counter >= self._emergency_debounce_threshold:
            desired_state = 'blue'
        elif self._global_emergency_counter >= self._global_debounce_threshold:
            desired_state = 'black'
        elif self._no_emergency_counter >= self._no_emergency_debounce_threshold and self._no_global_emergency_counter >= self._global_no_debounce_threshold:
            desired_state = 'green'

        # Apply state change if different
        if desired_state != self.central_pole_state:
            self.central_pole_state = desired_state
            try:
                self.update_central_pole_color(desired_state)
            except Exception:
                pass
            print(f"Central pole color updated to {desired_state}.")
        else:
            # Keep traci state consistent each step
            try:
                self.update_central_pole_color(self.central_pole_state)
            except Exception:
                pass

        return emergency_vehicles

# Example usage and testing
if __name__ == "__main__":
    sensor_network = SensorNetwork()
    
    # Simulate some vehicle data
    test_vehicles = [
        {'id': 'v1', 'speed': 45, 'distance': 150, 'type': 'passenger'},
        {'id': 'v2', 'speed': 30, 'distance': 200, 'type': 'passenger'},
        {'id': 'emergency1', 'speed': 60, 'distance': 300, 'type': 'emergency'},
    ]
    
    # Test radar detection
    reading = sensor_network.simulate_radar_detection("sensor_E1_200m", test_vehicles)
    print("Radar Detection:", reading)
    
    # Test LIDAR detection
    reading = sensor_network.simulate_lidar_detection("sensor_E5_100m", test_vehicles)
    print("LIDAR Detection:", reading)
    
    # Get summary
    summary = sensor_network.get_sensor_data_summary()
    print("Summary:", json.dumps(summary, indent=2))
    
    # Initialize central pole in SUMO
    sensor_network.initialize_central_pole()
    
    # Detect emergency vehicles and update pole color
    emergency_detections = sensor_network.detect_emergency_vehicles_and_update_pole()
    print("Emergency Detections:", emergency_detections)