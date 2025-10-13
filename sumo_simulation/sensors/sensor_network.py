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