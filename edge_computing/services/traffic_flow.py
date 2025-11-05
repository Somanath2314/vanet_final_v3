"""
Traffic Flow Service for Edge RSUs
Provides real-time traffic analysis, congestion detection, and route optimization
"""
import time
import math
from typing import Dict, List, Tuple, Optional
from collections import deque


class TrafficFlowService:
    """Analyzes traffic flow and provides route optimization"""
    
    def __init__(self, rsu_id: str, cache_manager):
        """
        Initialize traffic flow service
        
        Args:
            rsu_id: ID of the RSU hosting this service
            cache_manager: CacheManager instance for data storage
        """
        self.rsu_id = rsu_id
        self.cache = cache_manager
        
        # Traffic monitoring
        self.vehicle_history = deque(maxlen=100)  # Last 100 vehicles
        self.speed_samples = deque(maxlen=50)
        self.density_samples = deque(maxlen=30)
        
        # Congestion detection
        self.congestion_threshold = 0.7  # 70% of road capacity
        self.speed_threshold = 0.3  # 30% of speed limit
        
        # Statistics
        self.vehicles_analyzed = 0
        self.routes_computed = 0
        self.congestion_events = 0
    
    def update_vehicle_data(self, vehicle_id: str, position: Tuple[float, float],
                           speed: float, heading: float, edge_id: str = None) -> None:
        """
        Update traffic data with vehicle information
        
        Args:
            vehicle_id: Vehicle identifier
            position: (x, y) position
            speed: Current speed in m/s
            heading: Direction in degrees
            edge_id: Current road edge ID
        """
        current_time = time.time()
        
        vehicle_data = {
            'vehicle_id': vehicle_id,
            'position': position,
            'speed': speed,
            'heading': heading,
            'edge_id': edge_id,
            'timestamp': current_time
        }
        
        # Add to history
        self.vehicle_history.append(vehicle_data)
        self.speed_samples.append(speed)
        self.vehicles_analyzed += 1
        
        # Cache for other services
        self.cache.put_traffic_data(vehicle_id, vehicle_data)
    
    def analyze_traffic_flow(self, time_window: int = 60) -> Dict:
        """
        Analyze traffic flow in the last time window
        
        Args:
            time_window: Time window in seconds (default: 60)
            
        Returns:
            Dictionary with traffic analysis results
        """
        current_time = time.time()
        cutoff_time = current_time - time_window
        
        # Get recent vehicles
        recent_vehicles = [
            v for v in self.vehicle_history
            if v['timestamp'] >= cutoff_time
        ]
        
        if not recent_vehicles:
            return {
                'vehicle_count': 0,
                'avg_speed': 0,
                'congestion_level': 0,
                'flow_rate': 0
            }
        
        # Calculate metrics
        vehicle_count = len(recent_vehicles)
        avg_speed = sum(v['speed'] for v in recent_vehicles) / vehicle_count
        flow_rate = vehicle_count / time_window  # vehicles per second
        
        # Estimate density (vehicles per km)
        # Assume coverage area of 0.3 km radius
        coverage_area_km = 0.3 * 2  # diameter
        density = vehicle_count / coverage_area_km if coverage_area_km > 0 else 0
        
        # Congestion level (0-1)
        # Based on density and speed
        max_density = 50  # vehicles per km (typical highway capacity)
        density_factor = min(density / max_density, 1.0)
        
        # Speed factor (inverse - lower speed = more congestion)
        typical_speed = 13.89  # 50 km/h in m/s
        speed_factor = 1 - min(avg_speed / typical_speed, 1.0)
        
        congestion_level = (density_factor * 0.6 + speed_factor * 0.4)
        
        if congestion_level > 0.7:
            self.congestion_events += 1
        
        self.density_samples.append(density)
        
        return {
            'vehicle_count': vehicle_count,
            'avg_speed': avg_speed,
            'density': density,
            'congestion_level': congestion_level,
            'flow_rate': flow_rate,
            'is_congested': congestion_level > self.congestion_threshold,
            'timestamp': current_time
        }
    
    def predict_traffic_flow(self, prediction_window: int = 300) -> Dict:
        """
        Predict traffic flow for the next time window
        
        Args:
            prediction_window: Prediction window in seconds (default: 300 = 5 min)
            
        Returns:
            Dictionary with predicted traffic conditions
        """
        # Simple linear extrapolation based on recent trends
        if len(self.density_samples) < 3:
            return {
                'predicted_congestion': 0.5,
                'confidence': 0.0,
                'recommendation': 'insufficient_data'
            }
        
        # Calculate trend
        recent_densities = list(self.density_samples)
        trend = (recent_densities[-1] - recent_densities[0]) / len(recent_densities)
        
        # Predict next value
        predicted_density = recent_densities[-1] + trend * (prediction_window / 60)
        predicted_density = max(0, predicted_density)  # Non-negative
        
        # Convert to congestion level
        max_density = 50
        predicted_congestion = min(predicted_density / max_density, 1.0)
        
        # Confidence based on trend stability
        variance = sum((d - sum(recent_densities) / len(recent_densities))**2 
                      for d in recent_densities) / len(recent_densities)
        confidence = 1.0 / (1.0 + variance)  # Higher variance = lower confidence
        
        # Recommendation
        if predicted_congestion > 0.8:
            recommendation = 'avoid_route'
        elif predicted_congestion > 0.6:
            recommendation = 'expect_delays'
        else:
            recommendation = 'clear'
        
        return {
            'predicted_congestion': predicted_congestion,
            'predicted_density': predicted_density,
            'confidence': confidence,
            'recommendation': recommendation,
            'prediction_time': prediction_window
        }
    
    def optimize_route(self, start: Tuple[float, float], end: Tuple[float, float],
                      avoid_congestion: bool = True) -> Optional[Dict]:
        """
        Compute optimal route locally
        
        Args:
            start: Start position (x, y)
            end: End position (x, y)
            avoid_congestion: Whether to avoid congested areas
            
        Returns:
            Route information or None if not computable
        """
        start_time = time.time()
        
        # Check cache first
        cached_route = self.cache.get_route(start, end)
        if cached_route:
            return {
                'route': cached_route,
                'source': 'cache',
                'computation_time': time.time() - start_time
            }
        
        # Simple straight-line route (in real implementation, use actual road network)
        # This is a placeholder for demonstration
        route_points = [start, end]
        
        # Calculate distance and estimated time
        distance = math.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)
        
        # Get current traffic conditions
        traffic_analysis = self.analyze_traffic_flow()
        avg_speed = traffic_analysis['avg_speed']
        if avg_speed < 1:
            avg_speed = 13.89  # Default: 50 km/h
        
        estimated_time = distance / avg_speed
        
        # Cache the route
        self.cache.put_route(start, end, route_points)
        self.routes_computed += 1
        
        computation_time = time.time() - start_time
        
        return {
            'route': route_points,
            'distance': distance,
            'estimated_time': estimated_time,
            'congestion_level': traffic_analysis['congestion_level'],
            'source': 'computed',
            'computation_time': computation_time
        }
    
    def detect_anomaly(self) -> Optional[Dict]:
        """
        Detect traffic anomalies (sudden congestion, accidents, etc.)
        
        Returns:
            Anomaly information or None if no anomaly detected
        """
        if len(self.speed_samples) < 10:
            return None
        
        # Check for sudden speed drop
        recent_speeds = list(self.speed_samples)[-10:]
        avg_recent = sum(recent_speeds) / len(recent_speeds)
        
        older_speeds = list(self.speed_samples)[-20:-10] if len(self.speed_samples) >= 20 else []
        if older_speeds:
            avg_older = sum(older_speeds) / len(older_speeds)
            
            # Sudden drop > 50%
            if avg_recent < avg_older * 0.5 and avg_older > 5:
                return {
                    'type': 'sudden_slowdown',
                    'severity': 'high',
                    'avg_speed_before': avg_older,
                    'avg_speed_now': avg_recent,
                    'timestamp': time.time()
                }
        
        # Check for very low speeds (potential blockage)
        if avg_recent < 2 and len(self.vehicle_history) > 5:
            return {
                'type': 'potential_blockage',
                'severity': 'critical',
                'avg_speed': avg_recent,
                'vehicles_affected': len(self.vehicle_history),
                'timestamp': time.time()
            }
        
        return None
    
    def get_statistics(self) -> Dict:
        """Get service statistics"""
        return {
            'vehicles_analyzed': self.vehicles_analyzed,
            'routes_computed': self.routes_computed,
            'congestion_events': self.congestion_events,
            'current_vehicles': len(self.vehicle_history),
            'avg_speed': sum(self.speed_samples) / len(self.speed_samples) if self.speed_samples else 0
        }
