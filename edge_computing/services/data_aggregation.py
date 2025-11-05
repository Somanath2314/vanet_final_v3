"""
Data Aggregation Service for Edge RSUs
Provides data compression, anonymization, and periodic cloud upload
"""
import time
import json
import hashlib
from typing import Dict, List, Tuple, Any
from collections import defaultdict, deque


class DataAggregationService:
    """Aggregates and compresses data before cloud upload"""
    
    def __init__(self, rsu_id: str, upload_interval: int = 60):
        """
        Initialize data aggregation service
        
        Args:
            rsu_id: ID of the RSU hosting this service
            upload_interval: Seconds between cloud uploads (default: 60)
        """
        self.rsu_id = rsu_id
        self.upload_interval = upload_interval
        
        # Data buffers
        self.raw_data_buffer: deque = deque(maxlen=1000)
        self.aggregated_data: Dict[str, Any] = {}
        self.last_upload_time = time.time()
        
        # Anonymization
        self.vehicle_id_map: Dict[str, str] = {}  # Real ID -> Anonymous ID
        self.next_anon_id = 1
        
        # Statistics
        self.total_data_collected = 0
        self.total_data_uploaded = 0
        self.compression_ratio = 0
        self.uploads_completed = 0
    
    def collect_vehicle_data(self, vehicle_id: str, data: Dict) -> None:
        """
        Collect data from a vehicle
        
        Args:
            vehicle_id: Vehicle identifier
            data: Vehicle data dictionary
        """
        # Anonymize vehicle ID
        anon_id = self._anonymize_id(vehicle_id)
        
        # Add to buffer with anonymized ID
        anonymized_data = {
            **data,
            'vehicle_id': anon_id,
            'collection_time': time.time(),
            'rsu_id': self.rsu_id
        }
        
        self.raw_data_buffer.append(anonymized_data)
        self.total_data_collected += 1
    
    def aggregate_traffic_data(self) -> Dict:
        """
        Aggregate traffic data from buffer
        
        Returns:
            Aggregated summary statistics
        """
        if not self.raw_data_buffer:
            return {}
        
        current_time = time.time()
        time_window = 60  # Last 60 seconds
        cutoff_time = current_time - time_window
        
        # Filter recent data
        recent_data = [
            d for d in self.raw_data_buffer
            if d.get('collection_time', 0) >= cutoff_time
        ]
        
        if not recent_data:
            return {}
        
        # Aggregate by time bins (5-second intervals)
        bin_size = 5
        binned_data = defaultdict(list)
        
        for data in recent_data:
            timestamp = data.get('collection_time', current_time)
            bin_id = int((timestamp - cutoff_time) / bin_size)
            binned_data[bin_id].append(data)
        
        # Calculate statistics per bin
        aggregated_bins = []
        for bin_id in sorted(binned_data.keys()):
            bin_vehicles = binned_data[bin_id]
            
            speeds = [v.get('speed', 0) for v in bin_vehicles]
            positions = [v.get('position', (0, 0)) for v in bin_vehicles]
            
            aggregated_bins.append({
                'time_offset': bin_id * bin_size,
                'vehicle_count': len(bin_vehicles),
                'avg_speed': sum(speeds) / len(speeds) if speeds else 0,
                'min_speed': min(speeds) if speeds else 0,
                'max_speed': max(speeds) if speeds else 0,
                'density': len(bin_vehicles) / 0.6  # vehicles per km
            })
        
        aggregated = {
            'rsu_id': self.rsu_id,
            'time_window': time_window,
            'timestamp': current_time,
            'total_vehicles': len(recent_data),
            'unique_vehicles': len(set(d['vehicle_id'] for d in recent_data)),
            'bins': aggregated_bins
        }
        
        return aggregated
    
    def aggregate_event_data(self, events: List[Dict]) -> Dict:
        """
        Aggregate event data (collisions, emergencies, etc.)
        
        Args:
            events: List of event dictionaries
            
        Returns:
            Aggregated event summary
        """
        if not events:
            return {}
        
        # Group by event type
        events_by_type = defaultdict(list)
        for event in events:
            event_type = event.get('type', 'unknown')
            events_by_type[event_type].append(event)
        
        # Summarize each type
        summary = {
            'rsu_id': self.rsu_id,
            'timestamp': time.time(),
            'total_events': len(events),
            'event_types': {}
        }
        
        for event_type, type_events in events_by_type.items():
            summary['event_types'][event_type] = {
                'count': len(type_events),
                'severity_distribution': self._get_severity_distribution(type_events),
                'time_range': {
                    'start': min(e.get('timestamp', 0) for e in type_events),
                    'end': max(e.get('timestamp', 0) for e in type_events)
                }
            }
        
        return summary
    
    def prepare_upload_package(self) -> Dict:
        """
        Prepare aggregated data package for cloud upload
        
        Returns:
            Compressed data package
        """
        current_time = time.time()
        
        # Aggregate all collected data
        traffic_aggregate = self.aggregate_traffic_data()
        
        # Create upload package
        upload_package = {
            'rsu_id': self.rsu_id,
            'upload_time': current_time,
            'time_since_last_upload': current_time - self.last_upload_time,
            'data': {
                'traffic': traffic_aggregate,
                'summary': self._create_summary_statistics()
            },
            'metadata': {
                'raw_samples': len(self.raw_data_buffer),
                'anonymized_vehicles': len(self.vehicle_id_map)
            }
        }
        
        # Calculate compression ratio
        raw_size = len(json.dumps(list(self.raw_data_buffer)))
        compressed_size = len(json.dumps(upload_package))
        self.compression_ratio = raw_size / compressed_size if compressed_size > 0 else 1.0
        
        return upload_package
    
    def should_upload(self) -> bool:
        """Check if it's time to upload data to cloud"""
        current_time = time.time()
        return (current_time - self.last_upload_time) >= self.upload_interval
    
    def mark_upload_complete(self, bytes_uploaded: int = 0) -> None:
        """Mark upload as complete and reset buffers"""
        self.last_upload_time = time.time()
        self.total_data_uploaded += bytes_uploaded
        self.uploads_completed += 1
        
        # Clear old data from buffer (keep last 10 seconds for overlap)
        current_time = time.time()
        cutoff_time = current_time - 10
        
        # Keep only recent data
        self.raw_data_buffer = deque(
            [d for d in self.raw_data_buffer if d.get('collection_time', 0) >= cutoff_time],
            maxlen=1000
        )
    
    def _anonymize_id(self, vehicle_id: str) -> str:
        """
        Anonymize vehicle ID for privacy
        
        Args:
            vehicle_id: Real vehicle ID
            
        Returns:
            Anonymous ID
        """
        if vehicle_id not in self.vehicle_id_map:
            # Create hash-based anonymous ID
            hash_obj = hashlib.sha256(vehicle_id.encode())
            anon_id = f"V{hash_obj.hexdigest()[:8]}"
            self.vehicle_id_map[vehicle_id] = anon_id
        
        return self.vehicle_id_map[vehicle_id]
    
    def _create_summary_statistics(self) -> Dict:
        """Create summary statistics from buffer"""
        if not self.raw_data_buffer:
            return {}
        
        speeds = [d.get('speed', 0) for d in self.raw_data_buffer]
        
        return {
            'total_samples': len(self.raw_data_buffer),
            'avg_speed': sum(speeds) / len(speeds) if speeds else 0,
            'min_speed': min(speeds) if speeds else 0,
            'max_speed': max(speeds) if speeds else 0,
            'speed_std': self._calculate_std(speeds) if len(speeds) > 1 else 0
        }
    
    def _calculate_std(self, values: List[float]) -> float:
        """Calculate standard deviation"""
        if not values:
            return 0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5
    
    def _get_severity_distribution(self, events: List[Dict]) -> Dict[str, int]:
        """Get distribution of event severities"""
        distribution = defaultdict(int)
        for event in events:
            severity = event.get('severity', 'unknown')
            distribution[severity] += 1
        return dict(distribution)
    
    def get_bandwidth_savings(self) -> float:
        """
        Calculate bandwidth savings from aggregation
        
        Returns:
            Percentage of bandwidth saved (0-100)
        """
        if self.compression_ratio <= 1.0:
            return 0.0
        
        savings = (1 - 1 / self.compression_ratio) * 100
        return savings
    
    def get_statistics(self) -> Dict:
        """Get service statistics"""
        return {
            'total_data_collected': self.total_data_collected,
            'total_data_uploaded': self.total_data_uploaded,
            'uploads_completed': self.uploads_completed,
            'compression_ratio': self.compression_ratio,
            'bandwidth_savings_percent': self.get_bandwidth_savings(),
            'buffer_size': len(self.raw_data_buffer),
            'anonymized_vehicles': len(self.vehicle_id_map),
            'time_since_last_upload': time.time() - self.last_upload_time
        }
    
    def reset(self) -> None:
        """Reset all buffers and statistics"""
        self.raw_data_buffer.clear()
        self.aggregated_data.clear()
        self.vehicle_id_map.clear()
        self.total_data_collected = 0
        self.next_anon_id = 1
