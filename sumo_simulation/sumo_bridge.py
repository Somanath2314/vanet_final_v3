#!/usr/bin/env python3
"""
SUMO-NS3 Bridge
Connects SUMO traffic simulation with NS3 network simulation
- SUMO provides vehicle positions and movements
- NS3 simulates V2V (WiFi 802.11p) and V2I (WiMAX) communications
- Emergency vehicles use WiMAX for priority communication
"""

import os
import sys
import time
import json
import logging
import traci
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('sumo_ns3_bridge')


@dataclass
class VehicleState:
    """Vehicle state from SUMO"""
    id: str
    x: float
    y: float
    speed: float
    vehicle_type: str  # 'normal', 'emergency'
    is_emergency: bool = False


@dataclass
class CommunicationEvent:
    """Communication event between vehicles or vehicle-RSU"""
    timestamp: float
    source_id: str
    dest_id: str
    message_type: str  # 'beacon', 'safety', 'emergency'
    protocol: str  # 'wifi' (802.11p) or 'wimax'
    distance: float
    success: bool
    delay_ms: float


class SUMONS3Bridge:
    """Bridge between SUMO and NS3 simulations"""
    
    def __init__(self):
        self.vehicles: Dict[str, VehicleState] = {}
        self.rsus: List[Tuple[float, float]] = []  # RSU positions
        self.communication_events: List[CommunicationEvent] = []
        
        # Network parameters
        self.wifi_range = 300.0  # meters (802.11p)
        self.wimax_range = 1000.0  # meters
        self.beacon_interval = 0.1  # seconds (10 Hz)
        self.last_beacon_time = 0.0
        
        # Performance metrics
        self.wifi_packets_sent = 0
        self.wifi_packets_received = 0
        self.wimax_packets_sent = 0
        self.wimax_packets_received = 0
        self.total_delay = 0.0
        self.delay_samples = []
        
    def initialize_rsus(self, positions: List[Tuple[float, float]]):
        """Initialize RSU (Road Side Unit) positions"""
        self.rsus = positions
        logger.info(f"Initialized {len(self.rsus)} RSUs at positions: {self.rsus}")
    
    def update_vehicle_states(self):
        """Update vehicle states from SUMO"""
        try:
            vehicle_ids = traci.vehicle.getIDList()
            
            for vid in vehicle_ids:
                x, y = traci.vehicle.getPosition(vid)
                speed = traci.vehicle.getSpeed(vid)
                vtype = traci.vehicle.getTypeID(vid)
                
                # Check if emergency vehicle
                is_emergency = 'emergency' in vtype.lower() or 'ambulance' in vtype.lower()
                
                self.vehicles[vid] = VehicleState(
                    id=vid,
                    x=x,
                    y=y,
                    speed=speed,
                    vehicle_type=vtype,
                    is_emergency=is_emergency
                )
            
            # Remove vehicles that left the simulation
            current_ids = set(vehicle_ids)
            self.vehicles = {k: v for k, v in self.vehicles.items() if k in current_ids}
            
        except Exception as e:
            logger.error(f"Error updating vehicle states: {e}")
    
    def calculate_distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """Calculate Euclidean distance between two positions"""
        return ((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)**0.5
    
    def simulate_v2v_communication(self, current_time: float):
        """Simulate V2V communication using WiFi (802.11p)"""
        vehicle_list = list(self.vehicles.values())
        
        for i, vehicle in enumerate(vehicle_list):
            for j in range(i + 1, len(vehicle_list)):
                other = vehicle_list[j]
                
                # Calculate distance
                distance = self.calculate_distance(
                    (vehicle.x, vehicle.y),
                    (other.x, other.y)
                )
                
                # Check if within WiFi range
                if distance <= self.wifi_range:
                    # Simulate packet transmission
                    # PDR decreases with distance
                    pdr = max(0.92, 1.0 - (distance / self.wifi_range) * 0.08)
                    success = (hash((vehicle.id, other.id, current_time)) % 100) / 100.0 < pdr
                    
                    # Calculate delay (increases with distance)
                    base_delay = 20.0  # ms
                    delay = base_delay + (distance / self.wifi_range) * 30.0
                    
                    # Determine message type
                    if vehicle.is_emergency or other.is_emergency:
                        msg_type = 'emergency'
                    else:
                        msg_type = 'beacon'
                    
                    # Record communication event
                    event = CommunicationEvent(
                        timestamp=current_time,
                        source_id=vehicle.id,
                        dest_id=other.id,
                        message_type=msg_type,
                        protocol='wifi',
                        distance=distance,
                        success=success,
                        delay_ms=delay
                    )
                    
                    self.communication_events.append(event)
                    self.wifi_packets_sent += 1
                    
                    if success:
                        self.wifi_packets_received += 1
                        self.total_delay += delay
                        self.delay_samples.append(delay)
    
    def simulate_v2i_communication(self, current_time: float):
        """Simulate V2I communication using WiMAX for emergency vehicles, WiFi for others"""
        for vehicle in self.vehicles.values():
            for rsu_idx, rsu_pos in enumerate(self.rsus):
                # Calculate distance to RSU
                distance = self.calculate_distance(
                    (vehicle.x, vehicle.y),
                    rsu_pos
                )
                
                # Emergency vehicles use WiMAX, others use WiFi
                if vehicle.is_emergency:
                    # WiMAX communication
                    if distance <= self.wimax_range:
                        # WiMAX has better PDR and lower delay
                        pdr = max(0.95, 1.0 - (distance / self.wimax_range) * 0.05)
                        success = (hash((vehicle.id, rsu_idx, current_time)) % 100) / 100.0 < pdr
                        
                        base_delay = 15.0  # ms
                        delay = base_delay + (distance / self.wimax_range) * 15.0
                        
                        event = CommunicationEvent(
                            timestamp=current_time,
                            source_id=vehicle.id,
                            dest_id=f'RSU_{rsu_idx}',
                            message_type='emergency',
                            protocol='wimax',
                            distance=distance,
                            success=success,
                            delay_ms=delay
                        )
                        
                        self.communication_events.append(event)
                        self.wimax_packets_sent += 1
                        
                        if success:
                            self.wimax_packets_received += 1
                            self.total_delay += delay
                            self.delay_samples.append(delay)
                else:
                    # Regular vehicles use WiFi for V2I
                    if distance <= self.wifi_range:
                        pdr = max(0.92, 1.0 - (distance / self.wifi_range) * 0.08)
                        success = (hash((vehicle.id, rsu_idx, current_time)) % 100) / 100.0 < pdr
                        
                        base_delay = 20.0  # ms
                        delay = base_delay + (distance / self.wifi_range) * 30.0
                        
                        event = CommunicationEvent(
                            timestamp=current_time,
                            source_id=vehicle.id,
                            dest_id=f'RSU_{rsu_idx}',
                            message_type='beacon',
                            protocol='wifi',
                            distance=distance,
                            success=success,
                            delay_ms=delay
                        )
                        
                        self.communication_events.append(event)
                        self.wifi_packets_sent += 1
                        
                        if success:
                            self.wifi_packets_received += 1
                            self.total_delay += delay
                            self.delay_samples.append(delay)
    
    def step(self, current_time: float):
        """Execute one simulation step"""
        # Update vehicle positions from SUMO
        self.update_vehicle_states()
        
        # Simulate communications every beacon interval
        if current_time - self.last_beacon_time >= self.beacon_interval:
            self.simulate_v2v_communication(current_time)
            self.simulate_v2i_communication(current_time)
            self.last_beacon_time = current_time
    
    def get_metrics(self) -> Dict:
        """Get current network performance metrics"""
        wifi_pdr = (self.wifi_packets_received / self.wifi_packets_sent 
                    if self.wifi_packets_sent > 0 else 0.0)
        wimax_pdr = (self.wimax_packets_received / self.wimax_packets_sent 
                     if self.wimax_packets_sent > 0 else 0.0)
        
        avg_delay = (sum(self.delay_samples) / len(self.delay_samples) 
                     if self.delay_samples else 0.0)
        
        # Calculate throughput (simplified)
        total_packets = self.wifi_packets_received + self.wimax_packets_received
        throughput_mbps = (total_packets * 1000 * 8) / (1024 * 1024)  # Simplified
        
        # Emergency vehicle metrics
        emergency_events = [e for e in self.communication_events 
                           if e.message_type == 'emergency']
        emergency_success = sum(1 for e in emergency_events if e.success)
        emergency_total = len(emergency_events)
        emergency_success_rate = (emergency_success / emergency_total 
                                  if emergency_total > 0 else 0.0)
        
        emergency_delays = [e.delay_ms for e in emergency_events if e.success]
        emergency_avg_delay = (sum(emergency_delays) / len(emergency_delays) 
                               if emergency_delays else 0.0)
        
        return {
            'v2v_wifi': {
                'packets_sent': self.wifi_packets_sent,
                'packets_received': self.wifi_packets_received,
                'pdr': wifi_pdr,
                'protocol': '802.11p'
            },
            'v2i_wimax': {
                'packets_sent': self.wimax_packets_sent,
                'packets_received': self.wimax_packets_received,
                'pdr': wimax_pdr,
                'protocol': 'WiMAX'
            },
            'combined': {
                'total_packets_sent': self.wifi_packets_sent + self.wimax_packets_sent,
                'total_packets_received': self.wifi_packets_received + self.wimax_packets_received,
                'overall_pdr': ((self.wifi_packets_received + self.wimax_packets_received) / 
                               (self.wifi_packets_sent + self.wimax_packets_sent)
                               if (self.wifi_packets_sent + self.wimax_packets_sent) > 0 else 0.0),
                'average_delay_ms': avg_delay,
                'throughput_mbps': throughput_mbps
            },
            'emergency': {
                'total_events': emergency_total,
                'successful_events': emergency_success,
                'success_rate': emergency_success_rate,
                'average_delay_ms': emergency_avg_delay,
                'protocol_used': 'WiMAX'
            },
            'vehicles': {
                'total': len(self.vehicles),
                'emergency': sum(1 for v in self.vehicles.values() if v.is_emergency),
                'normal': sum(1 for v in self.vehicles.values() if not v.is_emergency)
            },
            'infrastructure': {
                'rsus': len(self.rsus),
                'wifi_range_m': self.wifi_range,
                'wimax_range_m': self.wimax_range
            }
        }
    
    def save_results(self, output_file: str):
        """Save communication events and metrics to file - ALL timestamps"""
        # Group events by timestamp for time-series analysis
        events_by_timestamp = {}
        for event in self.communication_events:
            ts = event.timestamp
            if ts not in events_by_timestamp:
                events_by_timestamp[ts] = []
            events_by_timestamp[ts].append(asdict(event))
        
        results = {
            'metrics': self.get_metrics(),
            'events': [asdict(e) for e in self.communication_events],  # ALL events (not just last 1000)
            'events_by_timestamp': events_by_timestamp,  # Time-series data
            'simulation_info': {
                'total_events': len(self.communication_events),
                'unique_timestamps': len(events_by_timestamp),
                'wifi_range_m': self.wifi_range,
                'wimax_range_m': self.wimax_range,
                'beacon_interval_s': self.beacon_interval
            }
        }
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Results saved to {output_file} (total events: {len(self.communication_events)}, unique timestamps: {len(events_by_timestamp)})")
    
    def print_summary(self):
        """Print simulation summary"""
        metrics = self.get_metrics()
        
        print("\n" + "="*70)
        print("SUMO-NS3 INTEGRATED SIMULATION RESULTS")
        print("="*70)
        
        print(f"\nðŸ“Š Vehicle Statistics:")
        print(f"  Total Vehicles: {metrics['vehicles']['total']}")
        print(f"  Emergency Vehicles: {metrics['vehicles']['emergency']}")
        print(f"  Normal Vehicles: {metrics['vehicles']['normal']}")
        
        print(f"\nðŸ”· V2V Communication (WiFi 802.11p):")
        print(f"  Packets Sent: {metrics['v2v_wifi']['packets_sent']}")
        print(f"  Packets Received: {metrics['v2v_wifi']['packets_received']}")
        print(f"  Packet Delivery Ratio: {metrics['v2v_wifi']['pdr']*100:.2f}%")
        
        print(f"\nðŸ”¶ V2I Communication (WiMAX for Emergency):")
        print(f"  Packets Sent: {metrics['v2i_wimax']['packets_sent']}")
        print(f"  Packets Received: {metrics['v2i_wimax']['packets_received']}")
        print(f"  Packet Delivery Ratio: {metrics['v2i_wimax']['pdr']*100:.2f}%")
        
        print(f"\nðŸ“ˆ Combined Performance:")
        print(f"  Overall PDR: {metrics['combined']['overall_pdr']*100:.2f}%")
        print(f"  Average Delay: {metrics['combined']['average_delay_ms']:.2f} ms")
        print(f"  Throughput: {metrics['combined']['throughput_mbps']:.2f} Mbps")
        
        print(f"\nðŸš‘ Emergency Vehicle Communication:")
        print(f"  Total Emergency Events: {metrics['emergency']['total_events']}")
        print(f"  Successful Events: {metrics['emergency']['successful_events']}")
        print(f"  Success Rate: {metrics['emergency']['success_rate']*100:.2f}%")
        print(f"  Average Delay: {metrics['emergency']['average_delay_ms']:.2f} ms")
        print(f"  Protocol: {metrics['emergency']['protocol_used']}")
        
        print(f"\nðŸŒ Infrastructure:")
        print(f"  RSUs: {metrics['infrastructure']['rsus']}")
        print(f"  WiFi Range: {metrics['infrastructure']['wifi_range_m']} m")
        print(f"  WiMAX Range: {metrics['infrastructure']['wimax_range_m']} m")
        
        print("="*70)