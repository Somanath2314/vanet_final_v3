from dataclasses import dataclass, field
from typing import Dict, List
import time
from .config import WiMAXConfig
from .phy import WiMAXPhy, PhyLinkState


@dataclass
class FlowKPI:
    bytes_sent: int = 0
    bytes_dropped: int = 0
    latency_samples_ms: List[float] = field(default_factory=list)

    def to_dict(self):
        avg_latency = sum(self.latency_samples_ms) / len(self.latency_samples_ms) if self.latency_samples_ms else 0.0
        return {
            "bytes_sent": self.bytes_sent,
            "bytes_dropped": self.bytes_dropped,
            "avg_latency_ms": round(avg_latency, 2),
        }


class WiMAXMac:
    def __init__(self, config: WiMAXConfig, phy: WiMAXPhy):
        self.config = config
        self.phy = phy
        self.ms_to_buffer_bytes: Dict[str, int] = {}
        self.ms_to_last_update_s: Dict[str, float] = {}
        self.ms_to_kpi: Dict[str, FlowKPI] = {}
        self.last_schedule_time_s = time.time()
        
        # Metrics tracking
        self.tx_packets = 0
        self.rx_packets = 0
        self.collisions = 0
        self.total_rssi = 0.0
        self.total_snr = 0.0
        self.metric_updates = 0
        
        # Track timing for utilization
        self.tx_start_time = 0.0
        self.rx_start_time = 0.0
        self.total_tx_time = 0.0
        self.total_rx_time = 0.0
        self.last_update_time = time.time()
        
        # Received packets buffer
        self.received_packets = []

    def enqueue(self, ms_id: str, bytes_count: int):
        self.ms_to_buffer_bytes[ms_id] = self.ms_to_buffer_bytes.get(ms_id, 0) + bytes_count
        self.ms_to_kpi.setdefault(ms_id, FlowKPI())

    def schedule(self, ms_id_to_distance_m: Dict[str, float]):
        now = time.time()
        if now - self.last_schedule_time_s < self.config.scheduling_granularity_s:
            return

        capacities_bps: Dict[str, float] = {}
        for ms_id, dist in ms_id_to_distance_m.items():
            link: PhyLinkState = self.phy.evaluate_link(dist)
            capacities_bps[ms_id] = link.capacity_bps
            
            # Update metrics
            self.total_rssi += link.rssi_dBm
            self.total_snr += link.snr_db
            self.metric_updates += 1

        total_capacity_bps = sum(capacities_bps.values())
        if total_capacity_bps <= 0:
            # drop oldest bytes based on target reliability
            for ms_id, buf in list(self.ms_to_buffer_bytes.items()):
                drop = int(buf * (1.0 - self.config.target_reliability))
                if drop > 0:
                    self.ms_to_buffer_bytes[ms_id] -= drop
                    self.ms_to_kpi.setdefault(ms_id, FlowKPI()).bytes_dropped += drop
            self.last_schedule_time_s = now
            return

        frame_bytes = int(total_capacity_bps * self.config.frame_duration_s / 8.0)
        if frame_bytes <= 0:
            self.last_schedule_time_s = now
            return

        # proportional fair: allocate by capacity weight
        for ms_id, capacity in capacities_bps.items():
            share = capacity / total_capacity_bps if total_capacity_bps > 0 else 0.0
            alloc = int(frame_bytes * share)
            if alloc <= 0:
                continue
            sent = min(buf, alloc)
            self.ms_to_buffer_bytes[ms_id] = max(0, buf - sent)
            kpi = self.ms_to_kpi.setdefault(ms_id, FlowKPI())
            kpi.bytes_sent += sent
            # rough latency approximation: time since last update
            bytes_to_send = min(buf, alloc)
            kpi.bytes_sent += bytes_to_send
            self.tx_packets += 1  # Count sent packets.
            self.ms_to_last_update_s[ms_id] = now

        self.last_schedule_time_s = now

    def _update_timing(self):
        """Update the total TX/RX times based on current state"""
        now = time.time()
        time_diff = now - self.last_update_time
        
        # Update TX time if currently transmitting
        if self.tx_start_time > 0:
            self.total_tx_time += time_diff
            
        # Update RX time if currently receiving
        if self.rx_start_time > 0:
            self.total_rx_time += time_diff
            
        self.last_update_time = now
        
    def start_tx(self):
        """Mark the start of a transmission"""
        self._update_timing()
        self.tx_start_time = time.time()
        
    def end_tx(self):
        """Mark the end of a transmission"""
        self._update_timing()
        self.tx_start_time = 0.0
        
    def start_rx(self):
        """Mark the start of a reception"""
        self._update_timing()
        self.rx_start_time = time.time()
        
    def receive_packet(self, packet: dict):
        """Handle a received packet"""
        self.rx_packets += 1
        self.received_packets.append(packet)
        # Update RX timing
        now = time.time()
        if self.rx_start_time > 0:
            self.total_rx_time += now - self.rx_start_time
        self.rx_start_time = now
        
    def get_received_packets(self):
        """Get and clear the received packets buffer"""
        packets = self.received_packets.copy()
        self.received_packets = []
        return packets
        
    def metrics(self) -> dict:
        """Get current metrics"""
        now = time.time()
        self._update_timing()
        
        avg_rssi = self.total_rssi / self.metric_updates if self.metric_updates > 0 else 0
        avg_snr = self.total_snr / self.metric_updates if self.metric_updates > 0 else 0
        
        return {
            'tx_packets': self.tx_packets,
            'rx_packets': self.rx_packets,
            'collisions': self.collisions,
            'avg_rssi': avg_rssi,
            'avg_snr': avg_snr,
            'tx_time': self.total_tx_time,
            'rx_time': self.total_rx_time,
            'utilization': (self.total_tx_time + self.total_rx_time) / (now - self.last_update_time) if now > self.last_update_time else 0.0
        }
