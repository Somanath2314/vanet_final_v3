import time
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from .config import WiMAXConfig
from .phy import WiMAXPhy
from .mac import WiMAXMac
import json

# Note: Encryption is now handled by SecureWiMAXBaseStation wrapper
# Legacy crypto imports removed - use secure_wimax.py for encrypted communications


@dataclass
class WiMAXMobileStation:
    ms_id: str
    x: float
    y: float


class WiMAXBaseStation:
    def __init__(self, bs_id: str, x: float, y: float, config: WiMAXConfig):
        self.bs_id = bs_id
        self.x = x
        self.y = y
        self.config = config
        self.phy = WiMAXPhy(config)
        self.mac = WiMAXMac(config, self.phy)
        self.mobiles: Dict[str, WiMAXMobileStation] = {}
        self.packet_log = []  # Store recent packets
        
        # Track metrics for summary statistics
        self.total_tx_bytes = 0
        self.total_rx_bytes = 0
        self.start_time = time.time()
        self.utilization = 0.0

    def attach(self, ms: WiMAXMobileStation):
        self.mobiles[ms.ms_id] = ms

    def detach(self, ms_id: str):
        self.mobiles.pop(ms_id, None)

    def _distance_to(self, x: float, y: float) -> float:
        dx = self.x - x
        dy = self.y - y
        return (dx * dx + dy * dy) ** 0.5

    def step(self):
        # Update mobile station positions and distances
        ms_to_distance = {}
        current_time = time.time()
        
        # Simulate packet transmission and reception
        self.mac.start_tx()
        
        # Send beacons to all connected mobile stations
        for ms_id, ms in list(self.mobiles.items()):
            # Calculate distance to this mobile station
            distance = self._distance_to(ms.x, ms.y)
            ms_to_distance[ms_id] = distance
            
            # Periodically send a beacon to each connected mobile station
            if hasattr(ms, 'last_beacon_time'):
                if current_time - ms.last_beacon_time >= 1.0:  # Send beacon every second
                    self.enqueue_beacon(ms_id, 100)  # 100 byte beacon
                    ms.last_beacon_time = current_time
                    
                    # Simulate receiving a response (ACK) from the mobile station
                    if distance < self.config.max_range_m:  # Only if in range
                        ack_packet = {
                            'from': ms_id,
                            'to': self.bs_id,
                            'type': 'ack',
                            'size': 50,  # 50 byte ACK
                            'timestamp': current_time
                        }
                        self.mac.receive_packet(ack_packet)
            else:
                # First time seeing this mobile station
                ms.last_beacon_time = current_time
                self.enqueue_beacon(ms_id, 100)  # Initial beacon
        
        # Let the MAC layer handle scheduling
        self.mac.schedule(ms_to_distance)
        self.mac.end_tx()
        
        # Process any other received packets
        rx_packets = self.mac.get_received_packets()
        for pkt in rx_packets:
            self._log_packet(pkt.get('from', 'unknown'), 
                           pkt.get('type', 'data'), 
                           pkt.get('size', 0))
            self.total_rx_bytes += pkt.get('size', 0)
            
        # Update metrics
        self.metrics = self.mac.metrics()

    def enqueue_beacon(self, ms_id: str, payload_bytes: int):
        """Enqueue a beacon packet and log it"""
        self.mac.enqueue(ms_id, payload_bytes)
        self._log_packet(ms_id, 'beacon', payload_bytes)
        self.total_tx_bytes += payload_bytes

    def _log_packet(self, ms_id: str, pkt_type: str, size_bytes: int):
        """Log a packet for later retrieval"""
        self.packet_log.append({
            'vehicle_id': ms_id,
            'type': pkt_type,
            'size': size_bytes,
            'timestamp': time.time()
        })
        
    def get_new_packets(self):
        """Get and clear the packet log"""
        packets = self.packet_log.copy()
        self.packet_log = []
        return packets
        
    def get_metrics(self):
        # Get MAC metrics if not already updated
        if not hasattr(self, 'metrics'):
            self.metrics = self.mac.metrics()
            
        # Calculate utilization (time busy / total time)
        current_time = time.time()
        total_time = current_time - self.start_time
        if total_time > 0:
            self.utilization = (self.metrics.get('tx_time', 0) + self.metrics.get('rx_time', 0)) / total_time
        
        return {
            "bs_id": self.bs_id,
            "connected_vehicles": len(self.mobiles),
            "packets_sent": self.metrics.get('tx_packets', 0),
            "packets_received": self.metrics.get('rx_packets', 0),
            "avg_rssi": self.metrics.get('avg_rssi', 0),
            "avg_snr": self.metrics.get('avg_snr', 0),
            "collisions": self.metrics.get('collisions', 0),
            "utilization": min(1.0, max(0.0, self.utilization)),  # Ensure between 0 and 1
            "tx_bytes": self.total_tx_bytes,
            "rx_bytes": self.total_rx_bytes,
            "tx_time": self.metrics.get('tx_time', 0),
            "rx_time": self.metrics.get('rx_time', 0),
            "timestamp": current_time
        }

