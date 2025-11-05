"""
Cache Manager for Edge RSUs
Implements LRU caching for traffic data, routes, and hazards
"""
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple


class CacheManager:
    """Manages caching for edge RSUs with LRU eviction policy"""
    
    def __init__(self, max_size_mb: int = 50):
        """
        Initialize cache manager
        
        Args:
            max_size_mb: Maximum cache size in MB (tier-dependent)
        """
        self.max_size = max_size_mb
        
        # Different cache types
        self.traffic_data_cache = OrderedDict()  # Last 5 minutes of traffic data
        self.route_cache = OrderedDict()  # Pre-computed routes
        self.hazard_cache = OrderedDict()  # Active hazards
        self.map_data_cache = OrderedDict()  # Road geometry
        
        # Cache statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        
        # Time-to-live settings (seconds)
        self.ttl = {
            'traffic_data': 300,  # 5 minutes
            'routes': 600,  # 10 minutes
            'hazards': 180,  # 3 minutes
            'map_data': 3600  # 1 hour
        }
    
    def get(self, cache_type: str, key: str) -> Optional[Any]:
        """
        Get value from cache
        
        Args:
            cache_type: Type of cache ('traffic_data', 'routes', etc.)
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        cache = self._get_cache(cache_type)
        if cache is None:
            return None
        
        if key in cache:
            entry = cache[key]
            # Check if expired
            if time.time() - entry['timestamp'] > self.ttl.get(cache_type, 600):
                del cache[key]
                self.misses += 1
                return None
            
            # Move to end (LRU)
            cache.move_to_end(key)
            self.hits += 1
            return entry['value']
        
        self.misses += 1
        return None
    
    def put(self, cache_type: str, key: str, value: Any) -> None:
        """
        Put value into cache
        
        Args:
            cache_type: Type of cache
            key: Cache key
            value: Value to cache
        """
        cache = self._get_cache(cache_type)
        if cache is None:
            return
        
        # Add/update entry
        cache[key] = {
            'value': value,
            'timestamp': time.time()
        }
        cache.move_to_end(key)
        
        # Evict oldest if cache too large
        max_entries = {
            'traffic_data': 1000,
            'routes': 500,
            'hazards': 100,
            'map_data': 200
        }
        
        while len(cache) > max_entries.get(cache_type, 500):
            cache.popitem(last=False)
            self.evictions += 1
    
    def put_traffic_data(self, vehicle_id: str, data: Dict) -> None:
        """Cache traffic data for a vehicle"""
        key = f"{vehicle_id}_{int(time.time())}"
        self.put('traffic_data', key, data)
    
    def get_recent_traffic_data(self, time_window: int = 300) -> List[Dict]:
        """Get all traffic data within time window (seconds)"""
        current_time = time.time()
        recent_data = []
        
        for key, entry in self.traffic_data_cache.items():
            if current_time - entry['timestamp'] <= time_window:
                recent_data.append(entry['value'])
        
        return recent_data
    
    def put_route(self, start: Tuple[float, float], end: Tuple[float, float],
                  route: List[Tuple[float, float]]) -> None:
        """Cache a computed route"""
        key = f"{start[0]:.1f},{start[1]:.1f}_to_{end[0]:.1f},{end[1]:.1f}"
        self.put('routes', key, route)
    
    def get_route(self, start: Tuple[float, float], 
                  end: Tuple[float, float]) -> Optional[List[Tuple[float, float]]]:
        """Get cached route"""
        key = f"{start[0]:.1f},{start[1]:.1f}_to_{end[0]:.1f},{end[1]:.1f}"
        return self.get('routes', key)
    
    def put_hazard(self, hazard_id: str, hazard_data: Dict) -> None:
        """Cache hazard information"""
        self.put('hazards', hazard_id, hazard_data)
    
    def get_active_hazards(self) -> List[Dict]:
        """Get all active hazards (not expired)"""
        current_time = time.time()
        active_hazards = []
        
        for key, entry in list(self.hazard_cache.items()):
            if current_time - entry['timestamp'] <= self.ttl['hazards']:
                active_hazards.append(entry['value'])
            else:
                del self.hazard_cache[key]
        
        return active_hazards
    
    def put_map_data(self, edge_id: str, geometry: Dict) -> None:
        """Cache map/road geometry data"""
        self.put('map_data', edge_id, geometry)
    
    def get_map_data(self, edge_id: str) -> Optional[Dict]:
        """Get cached map data"""
        return self.get('map_data', edge_id)
    
    def clear_expired(self) -> int:
        """Clear all expired entries from all caches"""
        current_time = time.time()
        cleared = 0
        
        for cache_type in ['traffic_data', 'routes', 'hazards', 'map_data']:
            cache = self._get_cache(cache_type)
            ttl = self.ttl.get(cache_type, 600)
            
            expired_keys = [
                key for key, entry in cache.items()
                if current_time - entry['timestamp'] > ttl
            ]
            
            for key in expired_keys:
                del cache[key]
                cleared += 1
        
        return cleared
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0
        
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': hit_rate,
            'evictions': self.evictions,
            'sizes': {
                'traffic_data': len(self.traffic_data_cache),
                'routes': len(self.route_cache),
                'hazards': len(self.hazard_cache),
                'map_data': len(self.map_data_cache)
            }
        }
    
    def reset_stats(self) -> None:
        """Reset cache statistics"""
        self.hits = 0
        self.misses = 0
        self.evictions = 0
    
    def _get_cache(self, cache_type: str) -> Optional[OrderedDict]:
        """Get the appropriate cache by type"""
        cache_map = {
            'traffic_data': self.traffic_data_cache,
            'routes': self.route_cache,
            'hazards': self.hazard_cache,
            'map_data': self.map_data_cache
        }
        return cache_map.get(cache_type)
