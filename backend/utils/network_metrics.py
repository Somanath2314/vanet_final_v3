"""
Network Performance Metrics Framework for VANET System
Collects and analyzes network performance data for research publication
"""

import time
import json
import threading
import random
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from enum import Enum
from collections import deque
import statistics

class MetricType(Enum):
    PACKET_DELIVERY_RATIO = "packet_delivery_ratio"
    END_TO_END_LATENCY = "end_to_end_latency"
    PACKET_LOSS_RATE = "packet_loss_rate"
    THROUGHPUT = "throughput"
    JITTER = "jitter"
    CHANNEL_UTILIZATION = "channel_utilization"
    HANDOFF_SUCCESS_RATE = "handoff_success_rate"
    AUTHENTICATION_DELAY = "authentication_delay"

@dataclass
class NetworkPacket:
    packet_id: str
    source_id: str
    destination_id: str
    packet_type: str
    size_bytes: int
    timestamp_sent: float
    timestamp_received: Optional[float] = None
    hop_count: int = 0
    is_delivered: bool = False
    latency_ms: Optional[float] = None

@dataclass
class NetworkMetrics:
    timestamp: float
    packet_delivery_ratio: float
    end_to_end_latency: float
    packet_loss_rate: float
    throughput_mbps: float
    jitter_ms: float
    channel_utilization: float
    handoff_success_rate: float
    authentication_delay_ms: float
    total_packets_sent: int
    total_packets_received: int
    total_bytes_transmitted: int

class NetworkMetricsCollector:
    """Collects and analyzes network performance metrics"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.packets: deque = deque(maxlen=1000)  # Store last 1000 packets
        self.metrics_history: deque = deque(maxlen=500)  # Store last 500 metric samples
        
        # Real-time counters
        self.total_packets_sent = 0
        self.total_packets_received = 0
        self.total_bytes_transmitted = 0
        self.handoff_attempts = 0
        self.handoff_successes = 0
        self.authentication_attempts = 0
        self.authentication_delays = deque(maxlen=100)
        
        # Channel simulation
        self.channel_busy_time = 0
        self.total_observation_time = 0
        self.last_observation_time = time.time()
        
        # Jitter calculation
        self.latency_samples = deque(maxlen=100)
        
        # Thread safety
        self.lock = threading.Lock()
        
    def send_packet(self, source_id: str, destination_id: str, packet_type: str, size_bytes: int) -> str:
        """Simulate sending a packet"""
        packet_id = f"pkt_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        
        packet = NetworkPacket(
            packet_id=packet_id,
            source_id=source_id,
            destination_id=destination_id,
            packet_type=packet_type,
            size_bytes=size_bytes,
            timestamp_sent=time.time()
        )
        
        with self.lock:
            self.packets.append(packet)
            self.total_packets_sent += 1
            
        return packet_id
    
    def receive_packet(self, packet_id: str, hop_count: int = 1) -> bool:
        """Simulate receiving a packet"""
        with self.lock:
            # Find the packet
            for packet in self.packets:
                if packet.packet_id == packet_id and not packet.is_delivered:
                    packet.timestamp_received = time.time()
                    packet.is_delivered = True
                    packet.hop_count = hop_count
                    packet.latency_ms = (packet.timestamp_received - packet.timestamp_sent) * 1000
                    
                    self.total_packets_received += 1
                    self.total_bytes_transmitted += packet.size_bytes
                    self.latency_samples.append(packet.latency_ms)
                    
                    return True
            return False
    
    def simulate_packet_loss(self, packet_id: str):
        """Simulate packet loss"""
        with self.lock:
            for packet in self.packets:
                if packet.packet_id == packet_id:
                    # Packet is lost - no need to mark as received
                    break
    
    def record_handoff_attempt(self, success: bool):
        """Record handoff attempt and result"""
        with self.lock:
            self.handoff_attempts += 1
            if success:
                self.handoff_successes += 1
    
    def record_authentication_delay(self, delay_ms: float):
        """Record authentication delay"""
        with self.lock:
            self.authentication_attempts += 1
            self.authentication_delays.append(delay_ms)
    
    def update_channel_utilization(self, busy_duration_ms: float):
        """Update channel utilization metrics"""
        current_time = time.time()
        
        with self.lock:
            observation_period = current_time - self.last_observation_time
            self.total_observation_time += observation_period
            self.channel_busy_time += busy_duration_ms / 1000  # Convert to seconds
            self.last_observation_time = current_time
    
    def calculate_packet_delivery_ratio(self) -> float:
        """Calculate Packet Delivery Ratio (PDR)"""
        if self.total_packets_sent == 0:
            return 0.0
        return (self.total_packets_received / self.total_packets_sent) * 100
    
    def calculate_end_to_end_latency(self) -> float:
        """Calculate average end-to-end latency"""
        if not self.latency_samples:
            return 0.0
        return statistics.mean(self.latency_samples)
    
    def calculate_packet_loss_rate(self) -> float:
        """Calculate packet loss rate"""
        if self.total_packets_sent == 0:
            return 0.0
        lost_packets = self.total_packets_sent - self.total_packets_received
        return (lost_packets / self.total_packets_sent) * 100
    
    def calculate_throughput(self, time_window_seconds: float = 1.0) -> float:
        """Calculate throughput in Mbps"""
        current_time = time.time()
        recent_bytes = 0
        
        with self.lock:
            for packet in self.packets:
                if (packet.is_delivered and 
                    packet.timestamp_received and 
                    current_time - packet.timestamp_received <= time_window_seconds):
                    recent_bytes += packet.size_bytes
        
        # Convert bytes to megabits and divide by time window
        throughput_mbps = (recent_bytes * 8) / (time_window_seconds * 1_000_000)
        return throughput_mbps
    
    def calculate_jitter(self) -> float:
        """Calculate jitter (variation in latency)"""
        if len(self.latency_samples) < 2:
            return 0.0
        
        # Calculate standard deviation of latency samples
        return statistics.stdev(self.latency_samples)
    
    def calculate_channel_utilization(self) -> float:
        """Calculate channel utilization percentage"""
        if self.total_observation_time == 0:
            return 0.0
        return (self.channel_busy_time / self.total_observation_time) * 100
    
    def calculate_handoff_success_rate(self) -> float:
        """Calculate handoff success rate"""
        if self.handoff_attempts == 0:
            return 0.0
        return (self.handoff_successes / self.handoff_attempts) * 100
    
    def calculate_authentication_delay(self) -> float:
        """Calculate average authentication delay"""
        if not self.authentication_delays:
            return 0.0
        return statistics.mean(self.authentication_delays)
    
    def get_current_metrics(self) -> NetworkMetrics:
        """Get current network performance metrics"""
        with self.lock:
            metrics = NetworkMetrics(
                timestamp=time.time(),
                packet_delivery_ratio=self.calculate_packet_delivery_ratio(),
                end_to_end_latency=self.calculate_end_to_end_latency(),
                packet_loss_rate=self.calculate_packet_loss_rate(),
                throughput_mbps=self.calculate_throughput(),
                jitter_ms=self.calculate_jitter(),
                channel_utilization=self.calculate_channel_utilization(),
                handoff_success_rate=self.calculate_handoff_success_rate(),
                authentication_delay_ms=self.calculate_authentication_delay(),
                total_packets_sent=self.total_packets_sent,
                total_packets_received=self.total_packets_received,
                total_bytes_transmitted=self.total_bytes_transmitted
            )
            
            self.metrics_history.append(metrics)
            return metrics
    
    def get_metrics_summary(self, duration_minutes: int = 5) -> Dict:
        """Get metrics summary for specified duration"""
        current_time = time.time()
        cutoff_time = current_time - (duration_minutes * 60)
        
        recent_metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        
        if not recent_metrics:
            return self._get_empty_summary()
        
        summary = {
            "duration_minutes": duration_minutes,
            "sample_count": len(recent_metrics),
            "packet_delivery_ratio": {
                "avg": statistics.mean([m.packet_delivery_ratio for m in recent_metrics]),
                "min": min([m.packet_delivery_ratio for m in recent_metrics]),
                "max": max([m.packet_delivery_ratio for m in recent_metrics]),
                "std": statistics.stdev([m.packet_delivery_ratio for m in recent_metrics]) if len(recent_metrics) > 1 else 0
            },
            "end_to_end_latency": {
                "avg": statistics.mean([m.end_to_end_latency for m in recent_metrics]),
                "min": min([m.end_to_end_latency for m in recent_metrics]),
                "max": max([m.end_to_end_latency for m in recent_metrics]),
                "std": statistics.stdev([m.end_to_end_latency for m in recent_metrics]) if len(recent_metrics) > 1 else 0
            },
            "packet_loss_rate": {
                "avg": statistics.mean([m.packet_loss_rate for m in recent_metrics]),
                "min": min([m.packet_loss_rate for m in recent_metrics]),
                "max": max([m.packet_loss_rate for m in recent_metrics]),
                "std": statistics.stdev([m.packet_loss_rate for m in recent_metrics]) if len(recent_metrics) > 1 else 0
            },
            "throughput_mbps": {
                "avg": statistics.mean([m.throughput_mbps for m in recent_metrics]),
                "min": min([m.throughput_mbps for m in recent_metrics]),
                "max": max([m.throughput_mbps for m in recent_metrics]),
                "std": statistics.stdev([m.throughput_mbps for m in recent_metrics]) if len(recent_metrics) > 1 else 0
            },
            "timestamp": current_time
        }
        
        return summary
    
    def _get_empty_summary(self) -> Dict:
        """Get empty metrics summary"""
        return {
            "duration_minutes": 0,
            "sample_count": 0,
            "packet_delivery_ratio": {"avg": 0, "min": 0, "max": 0, "std": 0},
            "end_to_end_latency": {"avg": 0, "min": 0, "max": 0, "std": 0},
            "packet_loss_rate": {"avg": 0, "min": 0, "max": 0, "std": 0},
            "throughput_mbps": {"avg": 0, "min": 0, "max": 0, "std": 0},
            "timestamp": time.time()
        }
    
    def export_metrics_for_paper(self, filename: str = None) -> Dict:
        """Export metrics in format suitable for research paper"""
        if filename is None:
            filename = f"network_metrics_{int(time.time())}.json"
        
        export_data = {
            "experiment_info": {
                "total_duration_seconds": time.time() - self.metrics_history[0].timestamp if self.metrics_history else 0,
                "total_samples": len(self.metrics_history),
                "sample_rate": "1 sample per second",
                "window_size": self.window_size
            },
            "performance_metrics": {
                "packet_delivery_ratio_percent": [m.packet_delivery_ratio for m in self.metrics_history],
                "end_to_end_latency_ms": [m.end_to_end_latency for m in self.metrics_history],
                "packet_loss_rate_percent": [m.packet_loss_rate for m in self.metrics_history],
                "throughput_mbps": [m.throughput_mbps for m in self.metrics_history],
                "jitter_ms": [m.jitter_ms for m in self.metrics_history],
                "channel_utilization_percent": [m.channel_utilization for m in self.metrics_history],
                "handoff_success_rate_percent": [m.handoff_success_rate for m in self.metrics_history],
                "authentication_delay_ms": [m.authentication_delay_ms for m in self.metrics_history]
            },
            "statistical_summary": self.get_metrics_summary(duration_minutes=len(self.metrics_history) // 60),
            "raw_data": [asdict(m) for m in self.metrics_history]
        }
        
        # Save to file
        try:
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2)
            print(f"Metrics exported to {filename}")
        except Exception as e:
            print(f"Error saving metrics: {e}")
        
        return export_data
    
    def reset_metrics(self):
        """Reset all metrics and counters"""
        with self.lock:
            self.packets.clear()
            self.metrics_history.clear()
            self.latency_samples.clear()
            self.authentication_delays.clear()
            
            self.total_packets_sent = 0
            self.total_packets_received = 0
            self.total_bytes_transmitted = 0
            self.handoff_attempts = 0
            self.handoff_successes = 0
            self.authentication_attempts = 0
            self.channel_busy_time = 0
            self.total_observation_time = 0
            self.last_observation_time = time.time()

# Example usage and testing
if __name__ == "__main__":
    # Create metrics collector
    collector = NetworkMetricsCollector()
    
    # Simulate network activity
    print("Simulating network activity...")
    
    # Send some packets
    packet_ids = []
    for i in range(100):
        packet_id = collector.send_packet(f"vehicle_{i%10}", "rsu_1", "traffic_data", 1024)
        packet_ids.append(packet_id)
        
        # Simulate some packet loss (5%)
        if random.random() < 0.05:
            collector.simulate_packet_loss(packet_id)
        else:
            # Simulate variable delay (20-100ms)
            delay = random.uniform(0.02, 0.1)
            time.sleep(delay)
            collector.receive_packet(packet_id, hop_count=random.randint(1, 3))
        
        # Simulate handoffs
        if random.random() < 0.1:
            collector.record_handoff_attempt(random.random() > 0.05)
        
        # Simulate authentication
        if random.random() < 0.2:
            auth_delay = random.uniform(10, 50)
            collector.record_authentication_delay(auth_delay)
        
        # Update channel utilization
        collector.update_channel_utilization(random.uniform(1, 10))
    
    # Get current metrics
    metrics = collector.get_current_metrics()
    print(f"\nCurrent Metrics:")
    print(f"PDR: {metrics.packet_delivery_ratio:.2f}%")
    print(f"Latency: {metrics.end_to_end_latency:.2f}ms")
    print(f"Loss Rate: {metrics.packet_loss_rate:.2f}%")
    print(f"Throughput: {metrics.throughput_mbps:.2f} Mbps")
    print(f"Jitter: {metrics.jitter_ms:.2f}ms")
    
    # Export for paper
    export_data = collector.export_metrics_for_paper("test_metrics.json")
    print(f"\nMetrics exported with {len(export_data['raw_data'])} samples")