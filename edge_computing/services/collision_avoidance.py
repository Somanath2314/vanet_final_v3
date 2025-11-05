"""
Collision Avoidance Service for Edge RSUs
Provides trajectory prediction, conflict detection, and warning system
"""
import time
import math
from typing import Dict, List, Tuple, Optional
from collections import defaultdict


class CollisionAvoidanceService:
    """Detects potential collisions and issues warnings"""
    
    def __init__(self, rsu_id: str, coverage_radius: float = 300):
        """
        Initialize collision avoidance service
        
        Args:
            rsu_id: ID of the RSU hosting this service
            coverage_radius: RSU coverage radius in meters
        """
        self.rsu_id = rsu_id
        self.coverage_radius = coverage_radius
        
        # Vehicle tracking
        self.tracked_vehicles: Dict[str, Dict] = {}
        
        # Collision parameters
        self.warning_distance = 50  # meters
        self.critical_distance = 20  # meters
        self.prediction_horizon = 5  # seconds
        
        # Track unique collision pairs to avoid double counting
        self.unique_collision_pairs = set()
        
        # Statistics
        self.warnings_issued = 0  # Count of unique collision warnings (per pair, not per message)
        self.collisions_prevented = 0
        self.false_positives = 0
    
    def update_vehicle(self, vehicle_id: str, position: Tuple[float, float],
                      speed: float, heading: float, vehicle_length: float = 4.5) -> None:
        """
        Update tracked vehicle information
        
        Args:
            vehicle_id: Vehicle identifier
            position: (x, y) position
            speed: Current speed in m/s
            heading: Direction in degrees
            vehicle_length: Vehicle length in meters
        """
        current_time = time.time()
        
        # Calculate velocity components
        heading_rad = math.radians(heading)
        vx = speed * math.cos(heading_rad)
        vy = speed * math.sin(heading_rad)
        
        self.tracked_vehicles[vehicle_id] = {
            'position': position,
            'speed': speed,
            'heading': heading,
            'velocity': (vx, vy),
            'length': vehicle_length,
            'timestamp': current_time,
            'last_warning': 0
        }
    
    def remove_vehicle(self, vehicle_id: str) -> None:
        """Remove vehicle from tracking"""
        if vehicle_id in self.tracked_vehicles:
            del self.tracked_vehicles[vehicle_id]
    
    def predict_trajectory(self, vehicle_id: str, time_steps: List[float]) -> List[Tuple[float, float]]:
        """
        Predict vehicle trajectory for given time steps
        
        Args:
            vehicle_id: Vehicle identifier
            time_steps: List of future time steps in seconds
            
        Returns:
            List of predicted (x, y) positions
        """
        if vehicle_id not in self.tracked_vehicles:
            return []
        
        vehicle = self.tracked_vehicles[vehicle_id]
        x0, y0 = vehicle['position']
        vx, vy = vehicle['velocity']
        
        trajectory = []
        for dt in time_steps:
            # Simple linear prediction (could be enhanced with acceleration)
            x = x0 + vx * dt
            y = y0 + vy * dt
            trajectory.append((x, y))
        
        return trajectory
    
    def detect_conflicts(self) -> List[Dict]:
        """
        Detect potential collision conflicts between tracked vehicles
        
        Returns:
            List of detected conflicts with details
        """
        conflicts = []
        current_time = time.time()
        
        vehicle_ids = list(self.tracked_vehicles.keys())
        
        # Check all pairs
        for i in range(len(vehicle_ids)):
            for j in range(i + 1, len(vehicle_ids)):
                vid1 = vehicle_ids[i]
                vid2 = vehicle_ids[j]
                
                # Skip if vehicles are too old
                if (current_time - self.tracked_vehicles[vid1]['timestamp'] > 2 or
                    current_time - self.tracked_vehicles[vid2]['timestamp'] > 2):
                    continue
                
                conflict = self._check_collision_risk(vid1, vid2)
                if conflict:
                    conflicts.append(conflict)
        
        return conflicts
    
    def _check_collision_risk(self, vid1: str, vid2: str) -> Optional[Dict]:
        """Check collision risk between two vehicles"""
        v1 = self.tracked_vehicles[vid1]
        v2 = self.tracked_vehicles[vid2]
        
        # Current distance
        current_distance = self._calculate_distance(v1['position'], v2['position'])
        
        # Predict future positions
        time_steps = [t * 0.5 for t in range(1, int(self.prediction_horizon * 2) + 1)]
        traj1 = self.predict_trajectory(vid1, time_steps)
        traj2 = self.predict_trajectory(vid2, time_steps)
        
        # Find minimum distance in predicted trajectories
        min_distance = current_distance
        min_distance_time = 0
        collision_point = None
        
        for t, (pos1, pos2) in enumerate(zip(traj1, traj2)):
            distance = self._calculate_distance(pos1, pos2)
            if distance < min_distance:
                min_distance = distance
                min_distance_time = time_steps[t]
                collision_point = ((pos1[0] + pos2[0]) / 2, (pos1[1] + pos2[1]) / 2)
        
        # Determine risk level
        safety_margin = (v1['length'] + v2['length']) / 2 + 2  # 2m extra margin
        
        if min_distance < safety_margin:
            severity = 'critical'
        elif min_distance < self.warning_distance:
            severity = 'warning'
        else:
            return None
        
        # Calculate time to collision
        if min_distance < current_distance and v1['speed'] > 0 and v2['speed'] > 0:
            # Approaching each other
            relative_speed = abs(v1['speed'] + v2['speed'])  # Worst case
            ttc = (current_distance - min_distance) / relative_speed if relative_speed > 0 else float('inf')
        else:
            ttc = float('inf')
        
        return {
            'vehicle_1': vid1,
            'vehicle_2': vid2,
            'current_distance': current_distance,
            'min_predicted_distance': min_distance,
            'time_to_min_distance': min_distance_time,
            'time_to_collision': ttc,
            'collision_point': collision_point,
            'severity': severity,
            'timestamp': time.time()
        }
    
    def issue_warning(self, conflict: Dict) -> Dict:
        """
        Issue collision warning to vehicles
        
        Args:
            conflict: Conflict information from detect_conflicts()
            
        Returns:
            Warning message details
        """
        current_time = time.time()
        
        # Check if warning already issued recently (avoid spam)
        v1_last_warning = self.tracked_vehicles[conflict['vehicle_1']].get('last_warning', 0)
        v2_last_warning = self.tracked_vehicles[conflict['vehicle_2']].get('last_warning', 0)
        
        if current_time - v1_last_warning < 2 and current_time - v2_last_warning < 2:
            return {'status': 'rate_limited'}
        
        # Update last warning times
        self.tracked_vehicles[conflict['vehicle_1']]['last_warning'] = current_time
        self.tracked_vehicles[conflict['vehicle_2']]['last_warning'] = current_time
        
        # Track unique collision pairs (only count first warning for each pair)
        vehicle_pair = tuple(sorted([conflict['vehicle_1'], conflict['vehicle_2']]))
        if vehicle_pair not in self.unique_collision_pairs:
            self.unique_collision_pairs.add(vehicle_pair)
            self.warnings_issued += 1  # Only increment for NEW collision pairs
        
        warning_message = {
            'type': 'collision_warning',
            'severity': conflict['severity'],
            'vehicles': [conflict['vehicle_1'], conflict['vehicle_2']],
            'min_distance': conflict['min_predicted_distance'],
            'time_to_collision': conflict['time_to_collision'],
            'collision_point': conflict['collision_point'],
            'recommended_action': self._get_recommended_action(conflict),
            'timestamp': current_time,
            'rsu_id': self.rsu_id
        }
        
        return warning_message
    
    def _get_recommended_action(self, conflict: Dict) -> str:
        """Get recommended action based on conflict severity"""
        if conflict['severity'] == 'critical':
            if conflict['time_to_collision'] < 2:
                return 'emergency_brake'
            else:
                return 'reduce_speed_immediately'
        elif conflict['severity'] == 'warning':
            return 'reduce_speed_and_increase_following_distance'
        else:
            return 'maintain_vigilance'
    
    def _calculate_distance(self, pos1: Tuple[float, float], 
                           pos2: Tuple[float, float]) -> float:
        """Calculate Euclidean distance between two positions"""
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
    
    def check_intersection_conflict(self, intersection_pos: Tuple[float, float],
                                   intersection_radius: float = 30) -> List[Dict]:
        """
        Check for conflicts at intersection
        
        Args:
            intersection_pos: (x, y) position of intersection
            intersection_radius: Intersection coverage radius
            
        Returns:
            List of potential intersection conflicts
        """
        conflicts = []
        vehicles_at_intersection = []
        
        # Find vehicles near intersection
        for vid, vehicle in self.tracked_vehicles.items():
            distance = self._calculate_distance(vehicle['position'], intersection_pos)
            
            # Check if vehicle is approaching or at intersection
            if distance < intersection_radius + 50:  # 50m approach zone
                # Predict if vehicle will enter intersection
                future_positions = self.predict_trajectory(vid, [1, 2, 3])
                will_enter = any(
                    self._calculate_distance(pos, intersection_pos) < intersection_radius
                    for pos in future_positions
                )
                
                if will_enter or distance < intersection_radius:
                    vehicles_at_intersection.append({
                        'vehicle_id': vid,
                        'distance': distance,
                        'speed': vehicle['speed'],
                        'heading': vehicle['heading'],
                        'eta': distance / vehicle['speed'] if vehicle['speed'] > 0 else float('inf')
                    })
        
        # Check for timing conflicts (vehicles arriving at similar times)
        for i in range(len(vehicles_at_intersection)):
            for j in range(i + 1, len(vehicles_at_intersection)):
                v1 = vehicles_at_intersection[i]
                v2 = vehicles_at_intersection[j]
                
                # If ETAs are close and headings are different (crossing paths)
                eta_diff = abs(v1['eta'] - v2['eta'])
                heading_diff = abs(v1['heading'] - v2['heading'])
                
                if eta_diff < 2 and heading_diff > 45:  # Crossing paths
                    conflicts.append({
                        'type': 'intersection_conflict',
                        'vehicle_1': v1['vehicle_id'],
                        'vehicle_2': v2['vehicle_id'],
                        'eta_1': v1['eta'],
                        'eta_2': v2['eta'],
                        'intersection_pos': intersection_pos,
                        'severity': 'warning' if eta_diff > 1 else 'critical'
                    })
        
        return conflicts
    
    def get_statistics(self) -> Dict:
        """Get service statistics"""
        return {
            'tracked_vehicles': len(self.tracked_vehicles),
            'warnings_issued': self.warnings_issued,
            'collisions_prevented': self.collisions_prevented,
            'false_positives': self.false_positives
        }
    
    def cleanup_old_vehicles(self, max_age: float = 5.0) -> int:
        """Remove vehicles not updated recently"""
        current_time = time.time()
        old_vehicles = [
            vid for vid, vehicle in self.tracked_vehicles.items()
            if current_time - vehicle['timestamp'] > max_age
        ]
        
        for vid in old_vehicles:
            del self.tracked_vehicles[vid]
        
        return len(old_vehicles)
