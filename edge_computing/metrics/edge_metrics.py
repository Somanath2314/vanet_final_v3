"""
Edge Metrics Tracker
Tracks performance metrics for edge RSUs
"""
import time
import csv
import json
from typing import Dict, List
from collections import defaultdict, deque


class EdgeMetricsTracker:
    """Tracks and records edge computing metrics"""
    
    def __init__(self, output_dir: str = "./output_edge"):
        """
        Initialize metrics tracker
        
        Args:
            output_dir: Directory to save metrics files
        """
        self.output_dir = output_dir
        
        # Per-RSU metrics
        self.rsu_metrics: Dict[str, Dict] = defaultdict(lambda: {
            'vehicles_served': 0,
            'computations_performed': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'latencies': deque(maxlen=100),
            'cpu_usage': deque(maxlen=100),
            'warnings_issued': 0,
            'routes_computed': 0,
            'emergencies_handled': 0
        })
        
        # System-wide metrics
        self.system_metrics = {
            'total_rsus': 0,
            'active_rsus': 0,
            'total_computations': 0,
            'total_offloaded': 0,
            'bandwidth_saved_mb': 0,
            'avg_latency_ms': 0,
            'start_time': time.time()
        }
        
        # Service-specific metrics
        self.service_metrics = {
            'traffic_flow': {'requests': 0, 'avg_response_time': 0},
            'collision_avoidance': {'warnings': 0, 'prevented': 0},
            'emergency_support': {'events': 0, 'response_time': 0},
            'data_aggregation': {'uploads': 0, 'compression_ratio': 0}
        }
    
    def record_rsu_activity(self, rsu_id: str, activity_type: str,
                           value: float = 1, latency_ms: float = None) -> None:
        """
        Record RSU activity
        
        Args:
            rsu_id: RSU identifier
            activity_type: Type of activity (computation, cache_hit, etc.)
            value: Value to add (default: 1)
            latency_ms: Optional latency in milliseconds
        """
        metrics = self.rsu_metrics[rsu_id]
        
        if activity_type == 'computation':
            metrics['computations_performed'] += value
            self.system_metrics['total_computations'] += value
        elif activity_type == 'cache_hit':
            metrics['cache_hits'] += value
        elif activity_type == 'cache_miss':
            metrics['cache_misses'] += value
        elif activity_type == 'vehicle_served':
            metrics['vehicles_served'] += value
        elif activity_type == 'route_computed':
            metrics['routes_computed'] += value
        elif activity_type == 'warning_issued':
            metrics['warnings_issued'] += value
        elif activity_type == 'emergency_handled':
            metrics['emergencies_handled'] += value
        
        if latency_ms is not None:
            metrics['latencies'].append(latency_ms)
    
    def record_service_activity(self, service_name: str, metric_name: str,
                               value: float) -> None:
        """Record service-specific activity"""
        if service_name in self.service_metrics:
            if metric_name in self.service_metrics[service_name]:
                self.service_metrics[service_name][metric_name] += value
    
    def update_system_metrics(self, metric_name: str, value: float) -> None:
        """Update system-wide metrics"""
        if metric_name in self.system_metrics:
            self.system_metrics[metric_name] = value
    
    def calculate_summary_statistics(self) -> Dict:
        """Calculate summary statistics across all RSUs"""
        total_vehicles = sum(m['vehicles_served'] for m in self.rsu_metrics.values())
        total_computations = sum(m['computations_performed'] for m in self.rsu_metrics.values())
        total_cache_hits = sum(m['cache_hits'] for m in self.rsu_metrics.values())
        total_cache_misses = sum(m['cache_misses'] for m in self.rsu_metrics.values())
        
        # Calculate average cache hit rate
        total_cache_requests = total_cache_hits + total_cache_misses
        cache_hit_rate = total_cache_hits / total_cache_requests if total_cache_requests > 0 else 0
        
        # Calculate average latency
        all_latencies = []
        for metrics in self.rsu_metrics.values():
            all_latencies.extend(metrics['latencies'])
        avg_latency = sum(all_latencies) / len(all_latencies) if all_latencies else 0
        
        # Calculate uptime
        uptime = time.time() - self.system_metrics['start_time']
        
        return {
            'total_rsus': len(self.rsu_metrics),
            'total_vehicles_served': total_vehicles,
            'total_computations': total_computations,
            'cache_hit_rate': cache_hit_rate,
            'avg_latency_ms': avg_latency,
            'uptime_seconds': uptime,
            'computations_per_second': total_computations / uptime if uptime > 0 else 0
        }
    
    def get_rsu_statistics(self, rsu_id: str) -> Dict:
        """Get statistics for a specific RSU"""
        if rsu_id not in self.rsu_metrics:
            return {}
        
        metrics = self.rsu_metrics[rsu_id]
        
        # Calculate cache hit rate
        total_cache = metrics['cache_hits'] + metrics['cache_misses']
        cache_hit_rate = metrics['cache_hits'] / total_cache if total_cache > 0 else 0
        
        # Calculate average latency
        latencies = list(metrics['latencies'])
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        return {
            'rsu_id': rsu_id,
            'vehicles_served': metrics['vehicles_served'],
            'computations_performed': metrics['computations_performed'],
            'cache_hit_rate': cache_hit_rate,
            'avg_latency_ms': avg_latency,
            'warnings_issued': metrics['warnings_issued'],
            'routes_computed': metrics['routes_computed'],
            'emergencies_handled': metrics['emergencies_handled']
        }
    
    def save_metrics(self, filename: str = None) -> str:
        """
        Save metrics to CSV file
        
        Args:
            filename: Optional filename (default: edge_metrics.csv)
            
        Returns:
            Path to saved file
        """
        import os
        os.makedirs(self.output_dir, exist_ok=True)
        
        if filename is None:
            filename = f"edge_metrics_{int(time.time())}.csv"
        
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'RSU_ID', 'Tier', 'Vehicles_Served', 'Computations',
                'Cache_Hit_Rate', 'Avg_Latency_MS', 'Warnings_Issued',
                'Routes_Computed', 'Emergencies_Handled'
            ])
            
            for rsu_id in sorted(self.rsu_metrics.keys()):
                stats = self.get_rsu_statistics(rsu_id)
                # Extract tier from RSU ID
                tier = 'unknown'
                if 'TIER1' in rsu_id:
                    tier = '1'
                elif 'TIER2' in rsu_id:
                    tier = '2'
                elif 'TIER3' in rsu_id:
                    tier = '3'
                
                writer.writerow([
                    rsu_id,
                    tier,
                    stats['vehicles_served'],
                    stats['computations_performed'],
                    f"{stats['cache_hit_rate']:.2%}",
                    f"{stats['avg_latency_ms']:.2f}",
                    stats['warnings_issued'],
                    stats['routes_computed'],
                    stats['emergencies_handled']
                ])
        
        return filepath
    
    def save_summary(self, filename: str = None) -> str:
        """
        Save summary statistics to JSON file
        
        Args:
            filename: Optional filename (default: edge_summary.json)
            
        Returns:
            Path to saved file
        """
        import os
        os.makedirs(self.output_dir, exist_ok=True)
        
        if filename is None:
            filename = f"edge_summary_{int(time.time())}.json"
        
        filepath = os.path.join(self.output_dir, filename)
        
        summary = {
            'system_metrics': self.system_metrics,
            'summary_statistics': self.calculate_summary_statistics(),
            'service_metrics': self.service_metrics,
            'timestamp': time.time()
        }
        
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)
        
        return filepath
    
    def print_summary(self) -> None:
        """Print summary statistics to console"""
        summary = self.calculate_summary_statistics()
        
        print("\n" + "="*60)
        print("📊 EDGE COMPUTING PERFORMANCE SUMMARY")
        print("="*60)
        print(f"Total RSUs: {summary['total_rsus']}")
        print(f"  - Tier 1 (Intersection): {sum(1 for r in self.rsu_metrics if 'TIER1' in r)}")
        print(f"  - Tier 2 (Road): {sum(1 for r in self.rsu_metrics if 'TIER2' in r)}")
        print(f"  - Tier 3 (Coverage): {sum(1 for r in self.rsu_metrics if 'TIER3' in r)}")
        print(f"\nTotal Vehicles Served: {summary['total_vehicles_served']}")
        print(f"Total Computations: {summary['total_computations']}")
        print(f"Computations/sec: {summary['computations_per_second']:.2f}")
        print(f"\nCache Hit Rate: {summary['cache_hit_rate']:.2%}")
        print(f"Avg Latency: {summary['avg_latency_ms']:.2f} ms")
        print(f"\nUptime: {summary['uptime_seconds']:.1f} seconds")
        
        print("\n" + "-"*60)
        print("Service-Specific Metrics:")
        print("-"*60)
        for service, metrics in self.service_metrics.items():
            print(f"\n{service}:")
            for metric, value in metrics.items():
                print(f"  {metric}: {value}")
        
        print("\n" + "="*60 + "\n")
