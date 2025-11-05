"""
Emergency Support Service for Edge RSUs
Provides emergency vehicle priority, path clearing, and coordination
"""
import time
import math
from typing import Dict, List, Tuple, Optional


class EmergencyService:
    """Handles emergency vehicle priority and coordination"""
    
    def __init__(self, rsu_id: str, tier: int = 2):
        """
        Initialize emergency service
        
        Args:
            rsu_id: ID of the RSU hosting this service
            tier: RSU tier (1=intersection, 2=road, 3=coverage)
        """
        self.rsu_id = rsu_id
        self.tier = tier
        self.priority_radius = 500  # meters for emergency priority
        
        # Emergency vehicle tracking
        self.active_emergencies: Dict[str, Dict] = {}
        self.emergency_corridors: List[Dict] = []
        
        # Track unique emergencies seen (not just currently active)
        self.unique_emergencies_seen = set()
        
        # Statistics
        self.emergencies_handled = 0  # Count of unique emergency vehicles seen
        self.vehicles_notified = 0
        self.lights_preempted = 0
    
    def register_emergency_vehicle(self, vehicle_id: str, position: Tuple[float, float],
                                  destination: Tuple[float, float],
                                  emergency_type: str = 'ambulance') -> Dict:
        """
        Register an emergency vehicle entering coverage area
        
        Args:
            vehicle_id: Emergency vehicle ID
            position: Current (x, y) position
            destination: Target (x, y) destination
            emergency_type: Type of emergency (ambulance, fire, police)
            
        Returns:
            Emergency response details
        """
        current_time = time.time()
        
        # Only increment counter if this is a NEW emergency vehicle we haven't seen before
        if vehicle_id not in self.unique_emergencies_seen:
            self.unique_emergencies_seen.add(vehicle_id)
            self.emergencies_handled += 1
        
        self.active_emergencies[vehicle_id] = {
            'type': emergency_type,
            'position': position,
            'destination': destination,
            'registered_time': current_time,
            'last_update': current_time,
            'priority_level': 1,  # Highest priority
            'status': 'active'
        }
        
        # Create emergency corridor
        corridor = self._create_emergency_corridor(position, destination)
        self.emergency_corridors.append({
            'vehicle_id': vehicle_id,
            'corridor': corridor,
            'created_time': current_time
        })
        
        return {
            'status': 'registered',
            'vehicle_id': vehicle_id,
            'corridor_id': len(self.emergency_corridors) - 1,
            'estimated_clearance_time': 10,  # seconds
            'rsu_id': self.rsu_id
        }
    
    def update_emergency_vehicle(self, vehicle_id: str, position: Tuple[float, float],
                                speed: float, heading: float) -> None:
        """Update emergency vehicle position"""
        if vehicle_id in self.active_emergencies:
            self.active_emergencies[vehicle_id]['position'] = position
            self.active_emergencies[vehicle_id]['speed'] = speed
            self.active_emergencies[vehicle_id]['heading'] = heading
            self.active_emergencies[vehicle_id]['last_update'] = time.time()
    
    def deregister_emergency_vehicle(self, vehicle_id: str) -> None:
        """Deregister emergency vehicle (reached destination or left area)"""
        if vehicle_id in self.active_emergencies:
            self.active_emergencies[vehicle_id]['status'] = 'completed'
            del self.active_emergencies[vehicle_id]
        
        # Remove corridor
        self.emergency_corridors = [
            c for c in self.emergency_corridors 
            if c['vehicle_id'] != vehicle_id
        ]
    
    def get_vehicles_to_notify(self, emergency_vehicle_id: str,
                              all_vehicles: Dict[str, Dict]) -> List[str]:
        """
        Get list of vehicles that should be notified to yield
        
        Args:
            emergency_vehicle_id: ID of emergency vehicle
            all_vehicles: Dictionary of all tracked vehicles
            
        Returns:
            List of vehicle IDs to notify
        """
        if emergency_vehicle_id not in self.active_emergencies:
            return []
        
        emergency = self.active_emergencies[emergency_vehicle_id]
        emergency_pos = emergency['position']
        
        vehicles_to_notify = []
        
        for vid, vehicle in all_vehicles.items():
            if vid == emergency_vehicle_id:
                continue
            
            # Calculate distance to emergency vehicle
            vehicle_pos = vehicle.get('position', (0, 0))
            distance = self._calculate_distance(emergency_pos, vehicle_pos)
            
            # Notify if within priority radius
            if distance < self.priority_radius:
                # Check if vehicle is ahead of emergency vehicle
                if self._is_in_path(emergency_pos, emergency['destination'], vehicle_pos):
                    vehicles_to_notify.append(vid)
        
        return vehicles_to_notify
    
    def issue_yield_warning(self, target_vehicle_ids: List[str],
                           emergency_vehicle_id: str) -> Dict:
        """
        Issue yield warning to vehicles
        
        Args:
            target_vehicle_ids: List of vehicles to warn
            emergency_vehicle_id: ID of approaching emergency vehicle
            
        Returns:
            Warning message details
        """
        if emergency_vehicle_id not in self.active_emergencies:
            return {'status': 'error', 'message': 'Unknown emergency vehicle'}
        
        emergency = self.active_emergencies[emergency_vehicle_id]
        
        warning = {
            'type': 'emergency_yield_warning',
            'emergency_vehicle': emergency_vehicle_id,
            'emergency_type': emergency['type'],
            'emergency_position': emergency['position'],
            'target_vehicles': target_vehicle_ids,
            'action': 'pull_over_and_yield',
            'urgency': 'high',
            'timestamp': time.time(),
            'rsu_id': self.rsu_id
        }
        
        self.vehicles_notified += len(target_vehicle_ids)
        
        return warning
    
    def request_traffic_light_preemption(self, intersection_id: str,
                                        emergency_vehicle_id: str,
                                        approach_direction: str) -> Dict:
        """
        Request traffic light preemption for emergency vehicle
        
        Args:
            intersection_id: Traffic light ID
            emergency_vehicle_id: ID of emergency vehicle
            approach_direction: Direction of approach
            
        Returns:
            Preemption request details
        """
        if self.tier != 1:  # Only Tier 1 (intersection) RSUs can preempt lights
            return {
                'status': 'forwarded',
                'message': 'Request forwarded to intersection RSU'
            }
        
        if emergency_vehicle_id not in self.active_emergencies:
            return {'status': 'error', 'message': 'Unknown emergency vehicle'}
        
        emergency = self.active_emergencies[emergency_vehicle_id]
        
        # Calculate ETA to intersection
        # (In real implementation, would get actual intersection position)
        speed = emergency.get('speed', 15)  # m/s
        distance = 100  # placeholder
        eta = distance / speed if speed > 0 else 10
        
        preemption_request = {
            'type': 'traffic_light_preemption',
            'intersection_id': intersection_id,
            'emergency_vehicle': emergency_vehicle_id,
            'approach_direction': approach_direction,
            'eta': eta,
            'priority': 1,
            'requested_time': time.time(),
            'requested_by_rsu': self.rsu_id
        }
        
        self.lights_preempted += 1
        
        return preemption_request
    
    def coordinate_with_nearby_rsus(self, nearby_rsu_ids: List[str],
                                   emergency_vehicle_id: str) -> Dict:
        """
        Coordinate emergency response with nearby RSUs
        
        Args:
            nearby_rsu_ids: List of nearby RSU IDs
            emergency_vehicle_id: ID of emergency vehicle
            
        Returns:
            Coordination message
        """
        if emergency_vehicle_id not in self.active_emergencies:
            return {'status': 'error'}
        
        emergency = self.active_emergencies[emergency_vehicle_id]
        
        coordination_message = {
            'type': 'emergency_coordination',
            'emergency_vehicle': emergency_vehicle_id,
            'emergency_type': emergency['type'],
            'position': emergency['position'],
            'destination': emergency['destination'],
            'target_rsus': nearby_rsu_ids,
            'action': 'prepare_corridor',
            'timestamp': time.time(),
            'coordinating_rsu': self.rsu_id
        }
        
        return coordination_message
    
    def create_green_wave(self, start_intersection: str,
                         end_intersection: str,
                         emergency_speed: float = 15) -> Dict:
        """
        Create green wave corridor for emergency vehicle
        
        Args:
            start_intersection: Starting intersection ID
            end_intersection: Ending intersection ID
            emergency_speed: Average emergency vehicle speed in m/s
            
        Returns:
            Green wave configuration
        """
        if self.tier != 1:
            return {'status': 'error', 'message': 'Only intersection RSUs can create green waves'}
        
        # Calculate timing for green wave
        # (Simplified - in real implementation would use actual road network)
        distance = 500  # placeholder distance between intersections
        travel_time = distance / emergency_speed
        
        green_wave = {
            'type': 'green_wave',
            'start_intersection': start_intersection,
            'end_intersection': end_intersection,
            'timing_offset': travel_time,
            'duration': 30,  # seconds
            'priority': 1,
            'created_by': self.rsu_id,
            'timestamp': time.time()
        }
        
        return green_wave
    
    def get_active_emergencies(self) -> List[Dict]:
        """Get list of all active emergencies"""
        return [
            {
                'vehicle_id': vid,
                **emergency
            }
            for vid, emergency in self.active_emergencies.items()
            if emergency['status'] == 'active'
        ]
    
    def _create_emergency_corridor(self, start: Tuple[float, float],
                                  end: Tuple[float, float]) -> List[Tuple[float, float]]:
        """Create corridor path from start to end"""
        # Simple straight corridor (in real implementation, use road network)
        corridor = [start, end]
        
        # Add intermediate waypoints if distance is large
        distance = self._calculate_distance(start, end)
        if distance > 100:
            num_waypoints = int(distance / 100)
            for i in range(1, num_waypoints):
                t = i / num_waypoints
                waypoint = (
                    start[0] + t * (end[0] - start[0]),
                    start[1] + t * (end[1] - start[1])
                )
                corridor.insert(i, waypoint)
        
        return corridor
    
    def _is_in_path(self, start: Tuple[float, float], end: Tuple[float, float],
                   point: Tuple[float, float], tolerance: float = 50) -> bool:
        """Check if point is in the path from start to end"""
        # Calculate perpendicular distance from point to line
        x0, y0 = point
        x1, y1 = start
        x2, y2 = end
        
        # Line equation: (y2-y1)x - (x2-x1)y + (x2-x1)y1 - (y2-y1)x1 = 0
        numerator = abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1)
        denominator = math.sqrt((y2 - y1)**2 + (x2 - x1)**2)
        
        if denominator == 0:
            return False
        
        distance = numerator / denominator
        
        return distance < tolerance
    
    def _calculate_distance(self, pos1: Tuple[float, float],
                          pos2: Tuple[float, float]) -> float:
        """Calculate Euclidean distance"""
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
    
    def get_statistics(self) -> Dict:
        """Get service statistics"""
        return {
            'emergencies_handled': self.emergencies_handled,
            'active_emergencies': len(self.active_emergencies),
            'vehicles_notified': self.vehicles_notified,
            'lights_preempted': self.lights_preempted,
            'active_corridors': len(self.emergency_corridors)
        }
    
    def cleanup_old_emergencies(self, max_age: float = 300) -> int:
        """Remove old/stale emergency entries"""
        current_time = time.time()
        old_emergencies = [
            vid for vid, emergency in self.active_emergencies.items()
            if current_time - emergency['last_update'] > max_age
        ]
        
        for vid in old_emergencies:
            self.deregister_emergency_vehicle(vid)
        
        return len(old_emergencies)
