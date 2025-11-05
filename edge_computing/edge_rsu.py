"""
Edge RSU - Smart RSU with Edge Computing Capabilities
"""
import time
from typing import Dict, List, Tuple, Optional
from .services.caching import CacheManager
from .services.traffic_flow import TrafficFlowService
from .services.collision_avoidance import CollisionAvoidanceService
from .services.emergency_support import EmergencyService
from .services.data_aggregation import DataAggregationService


class EdgeRSU:
    """
    Edge RSU with computing capabilities and services
    
    Provides:
    - Local traffic processing and analytics
    - Collision avoidance services
    - Emergency vehicle support
    - Data aggregation and caching
    - Computational offloading
    """
    
    def __init__(self, rsu_id: str, position: Tuple[float, float], tier: int = 2,
                 compute_capacity: str = 'medium'):
        """
        Initialize Edge RSU
        
        Args:
            rsu_id: Unique RSU identifier
            position: (x, y) position
            tier: RSU tier (1=intersection, 2=road, 3=coverage)
            compute_capacity: Computing power (high/medium/light)
        """
        self.rsu_id = rsu_id
        self.position = position
        self.tier = tier
        self.compute_capacity = compute_capacity
        
        # Set resources based on tier
        self.resources = self._initialize_resources(tier, compute_capacity)
        
        # Initialize cache manager
        cache_size = {'high': 100, 'medium': 50, 'light': 20}
        self.cache = CacheManager(max_size_mb=cache_size.get(compute_capacity, 50))
        
        # Initialize services
        self.services = {
            'traffic_flow': TrafficFlowService(rsu_id, self.cache),
            'collision_avoidance': CollisionAvoidanceService(rsu_id, 
                                                            coverage_radius=self.resources['coverage_radius']),
            'emergency': EmergencyService(rsu_id, tier),
            'data_aggregation': DataAggregationService(rsu_id, upload_interval=60)
        }
        
        # State
        self.active = True
        self.startup_time = time.time()
        
        # Track unique vehicles seen by this RSU
        self.unique_vehicles_seen = set()  # Set of vehicle IDs
        
        # Metrics
        self.metrics = {
            'vehicles_in_range': 0,
            'total_computations': 0,
            'avg_cpu_usage': 0,
            'uptime': 0
        }
    
    def _initialize_resources(self, tier: int, capacity: str) -> Dict:
        """Initialize computing resources based on tier and capacity"""
        resource_map = {
            1: {'high': {'cpu_cores': 8, 'memory_gb': 16, 'storage_gb': 100}},
            2: {'medium': {'cpu_cores': 4, 'memory_gb': 8, 'storage_gb': 50}},
            3: {'light': {'cpu_cores': 2, 'memory_gb': 4, 'storage_gb': 20}}
        }
        
        default_resources = {
            'cpu_cores': 4,
            'memory_gb': 8,
            'storage_gb': 50,
            'coverage_radius': 300  # meters
        }
        
        if tier in resource_map and capacity in resource_map[tier]:
            resources = resource_map[tier][capacity].copy()
            resources['coverage_radius'] = 300
            return resources
        
        return default_resources
    
    def update_vehicle(self, vehicle_id: str, position: Tuple[float, float],
                      speed: float, heading: float, edge_id: str = None,
                      vehicle_type: str = 'normal') -> None:
        """
        Update vehicle information
        
        Args:
            vehicle_id: Vehicle identifier
            position: (x, y) position
            speed: Speed in m/s
            heading: Direction in degrees
            edge_id: Current road edge ID
            vehicle_type: Type of vehicle (normal/emergency)
        """
        # Track unique vehicles (add to set if first time seeing this vehicle)
        is_new_vehicle = vehicle_id not in self.unique_vehicles_seen
        if is_new_vehicle:
            self.unique_vehicles_seen.add(vehicle_id)
        
        # Update traffic flow service
        self.services['traffic_flow'].update_vehicle_data(
            vehicle_id, position, speed, heading, edge_id
        )
        
        # Update collision avoidance service
        self.services['collision_avoidance'].update_vehicle(
            vehicle_id, position, speed, heading
        )
        
        # Collect data for aggregation
        self.services['data_aggregation'].collect_vehicle_data(vehicle_id, {
            'position': position,
            'speed': speed,
            'heading': heading,
            'edge_id': edge_id,
            'vehicle_type': vehicle_type
        })
        
        # Handle emergency vehicles
        if vehicle_type == 'emergency':
            if vehicle_id not in self.services['emergency'].active_emergencies:
                # Register new emergency vehicle
                # (destination would be provided by vehicle in real system)
                destination = (position[0] + 500, position[1])  # Placeholder
                self.services['emergency'].register_emergency_vehicle(
                    vehicle_id, position, destination
                )
            else:
                # Update existing emergency vehicle
                self.services['emergency'].update_emergency_vehicle(
                    vehicle_id, position, speed, heading
                )
        
        # Only count as computation if it's a new vehicle or significant update
        if is_new_vehicle:
            self.metrics['total_computations'] += 1
    
    def process_requests(self) -> List[Dict]:
        """
        Process pending requests and return responses
        
        Returns:
            List of responses (warnings, route info, etc.)
        """
        responses = []
        
        # 1. Check for collisions
        conflicts = self.services['collision_avoidance'].detect_conflicts()
        for conflict in conflicts:
            warning = self.services['collision_avoidance'].issue_warning(conflict)
            if warning.get('status') != 'rate_limited':
                responses.append(warning)
        
        # 2. Analyze traffic flow
        traffic_analysis = self.services['traffic_flow'].analyze_traffic_flow()
        if traffic_analysis.get('is_congested', False):
            # Detect anomalies
            anomaly = self.services['traffic_flow'].detect_anomaly()
            if anomaly:
                responses.append({
                    'type': 'traffic_anomaly',
                    'anomaly': anomaly,
                    'rsu_id': self.rsu_id
                })
        
        # 3. Handle emergency vehicles
        active_emergencies = self.services['emergency'].get_active_emergencies()
        for emergency in active_emergencies:
            # Get vehicles in emergency path
            all_tracked = {
                vid: {
                    'position': v['position'],
                    'speed': v['speed']
                }
                for vid, v in self.services['collision_avoidance'].tracked_vehicles.items()
            }
            
            vehicles_to_notify = self.services['emergency'].get_vehicles_to_notify(
                emergency['vehicle_id'], all_tracked
            )
            
            if vehicles_to_notify:
                yield_warning = self.services['emergency'].issue_yield_warning(
                    vehicles_to_notify, emergency['vehicle_id']
                )
                responses.append(yield_warning)
        
        # 4. Check if data upload needed
        if self.services['data_aggregation'].should_upload():
            upload_package = self.services['data_aggregation'].prepare_upload_package()
            responses.append({
                'type': 'cloud_upload',
                'package': upload_package,
                'rsu_id': self.rsu_id
            })
            self.services['data_aggregation'].mark_upload_complete()
        
        return responses
    
    def compute_route(self, start: Tuple[float, float], end: Tuple[float, float]) -> Dict:
        """
        Compute route locally (edge computing)
        
        Args:
            start: Start position (x, y)
            end: End position (x, y)
            
        Returns:
            Route information
        """
        start_time = time.time()
        route_info = self.services['traffic_flow'].optimize_route(start, end)
        
        # Record computation time
        computation_time = (time.time() - start_time) * 1000  # ms
        
        self.metrics['total_computations'] += 1
        
        return {
            **route_info,
            'rsu_id': self.rsu_id,
            'computation_latency_ms': computation_time
        }
    
    def predict_traffic(self, prediction_window: int = 300) -> Dict:
        """
        Predict traffic conditions
        
        Args:
            prediction_window: Prediction horizon in seconds
            
        Returns:
            Traffic prediction
        """
        prediction = self.services['traffic_flow'].predict_traffic_flow(prediction_window)
        return {
            **prediction,
            'rsu_id': self.rsu_id
        }
    
    def get_cache_statistics(self) -> Dict:
        """Get cache performance statistics"""
        return self.cache.get_cache_stats()
    
    def get_service_statistics(self) -> Dict:
        """Get statistics from all services"""
        return {
            'rsu_id': self.rsu_id,
            'tier': self.tier,
            'position': self.position,
            'uptime': time.time() - self.startup_time,
            'unique_vehicles_served': len(self.unique_vehicles_seen),  # Count unique vehicles
            'cache': self.cache.get_cache_stats(),
            'traffic_flow': self.services['traffic_flow'].get_statistics(),
            'collision_avoidance': self.services['collision_avoidance'].get_statistics(),
            'emergency': self.services['emergency'].get_statistics(),
            'data_aggregation': self.services['data_aggregation'].get_statistics(),
            'total_computations': self.metrics['total_computations']
        }
    
    def cleanup(self) -> None:
        """Clean up old data and vehicles"""
        # Clean up old vehicles from collision avoidance
        self.services['collision_avoidance'].cleanup_old_vehicles()
        
        # Clean up old emergencies
        self.services['emergency'].cleanup_old_emergencies()
        
        # Clear expired cache entries
        self.cache.clear_expired()
    
    def is_vehicle_in_range(self, vehicle_position: Tuple[float, float]) -> bool:
        """Check if vehicle is within RSU coverage"""
        import math
        distance = math.sqrt(
            (vehicle_position[0] - self.position[0])**2 +
            (vehicle_position[1] - self.position[1])**2
        )
        return distance <= self.resources['coverage_radius']
    
    def get_coverage_radius(self) -> float:
        """Get RSU coverage radius"""
        return self.resources['coverage_radius']
    
    def __repr__(self) -> str:
        return (f"EdgeRSU(id={self.rsu_id}, tier={self.tier}, "
                f"position={self.position}, capacity={self.compute_capacity})")
