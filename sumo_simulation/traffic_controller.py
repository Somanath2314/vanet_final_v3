#!/usr/bin/env python3
"""
Adaptive Traffic Light Controller for VANET System with Ambulance Priority
Uses SUMO TraCI for real-time traffic signal control
"""

import traci
import time
import sys
import os
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum

# Add sensor network to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'sensors'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'v2v_communication'))
from sensor_network import SensorNetwork, SensorReading

from wimax import WiMAXConfig, WiMAXBaseStation, WiMAXMobileStation

class AdaptiveTrafficController:
    def __init__(self, output_dir="./output_rule", mode="rule"):
        self.sensor_network = SensorNetwork()
        self.intersections = {}
        self.running = False
        self.simulation_step = 0
        self.output_dir = output_dir
        self.mode = mode
        
        # Initialize DataFrames for metrics and packets
        self.packets_df = pd.DataFrame(columns=["timestamp", "bs_id", "vehicle_id", "packet_type", "size_bytes"])
        self.metrics_df = pd.DataFrame(columns=["timestamp", "bs_id", "connected_vehicles", "packets_sent", "packets_received"])
        self.last_metrics_update = 0
        self.metrics_interval = 5  # Update metrics every 5 seconds

        # WiMAX setup
        self.wimax_config = WiMAXConfig()
        self.wimax_base_stations: Dict[str, WiMAXBaseStation] = {}
        self.wimax_last_beacon_step = 0
        self.wimax_metrics_snapshot: Dict = {}

        # Traffic light program
        self.default_phases = {
            "J2": ["rrrGGG", "rrryyy", "GGGrrr", "yyyrrr"],
            "J3": ["rrrGGG", "rrryyy", "GGGrrr", "yyyrrr"]
        }
        self.min_green_time = 15
        self.max_green_time = 60
        self.yellow_time = 5
        self.extension_time = 5

    # ------------------- SUMO -------------------
    def connect_to_sumo(self, config_path, use_gui=True):
        try:
            try: traci.close()
            except: pass

            # Ensure output directory exists
            os.makedirs(self.output_dir, exist_ok=True)
            
            summary_path = os.path.join(self.output_dir, "summary.xml")
            tripinfo_path = os.path.join(self.output_dir, "tripinfo.xml")

            sumo_binary = "sumo-gui" if use_gui else "sumo"
            
            traci.start([
                sumo_binary,
                "-c", config_path,
                "--summary-output", summary_path,
                "--tripinfo-output", tripinfo_path,
                "--start"  # Auto-start simulation
            ])
            print(f"Connected to SUMO ({sumo_binary}).")
            self.sumo_connected = True
            self._initialize_intersections()
            self._initialize_wimax()
            return True
        except Exception as e:
            print(f"Failed to connect to SUMO: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _initialize_intersections(self):
        tl_ids = traci.trafficlight.getIDList()
        for tl in tl_ids:
            self.intersections[tl] = {"current_phase": 0, "time_in_phase": 0, "phase_duration": 30}

    def _initialize_wimax(self):
        coords = {"J2": (500,500), "J3": (1000,500)}
        for tl, (x,y) in coords.items():
            if tl in self.intersections:
                self.wimax_base_stations[tl] = WiMAXBaseStation(tl, x, y, self.wimax_config)

    # ------------------- SIMULATION -------------------
    def run_simulation_step(self):
        try:
            # Check if simulation is still running
            if not hasattr(self, 'sumo_connected') or not self.sumo_connected:
                return False
                
            traci.simulationStep()
            self.simulation_step += 1

            # Simple rule-based traffic light update
            for tl_id, data in self.intersections.items():
                data["time_in_phase"] += 1
                if data["time_in_phase"] >= data["phase_duration"]:
                    data["current_phase"] = (data["current_phase"] + 1) % len(self.default_phases[tl_id])
                    data["time_in_phase"] = 0
                    traci.trafficlight.setRedYellowGreenState(tl_id, self.default_phases[tl_id][data["current_phase"]])

            # Update WiMAX metrics
            self._update_wimax()
            return True
            
        except traci.exceptions.FatalTraCIError as e:
            # Save metrics when simulation ends
            print("\n⚠️  SUMO simulation ended, saving metrics...")
            self._save_v2i_metrics()
            self.sumo_connected = False
            return False
            
        except Exception as e:
            print(f"Error in simulation step: {e}")
            self._save_v2i_metrics()  # Save metrics on error
            return False

    def _update_wimax(self):
        current_time = traci.simulation.getTime()
        
        # Update base stations
        for bs_id, bs in self.wimax_base_stations.items():
            bs.step()
            
            # Log any new packets (if get_new_packets is implemented in WiMAXBaseStation)
            if hasattr(bs, 'get_new_packets'):
                for packet in bs.get_new_packets():
                    self._log_packet(bs_id, packet.get('vehicle_id', 'unknown'),
                                   packet.get('type', 'data'),
                                   packet.get('size', 0))
        
        # Update metrics snapshot and log to dataframe
        current_time = traci.simulation.getTime()
        self.wimax_metrics_snapshot = {}
        
        for bs_id, bs in self.wimax_base_stations.items():
            metrics = bs.get_metrics()
            self.wimax_metrics_snapshot[bs_id] = metrics
            
            # Always add metrics to the dataframe
            new_metrics = {
                "timestamp": current_time,
                "bs_id": bs_id,
                "connected_vehicles": metrics.get("connected_vehicles", 0),
                "packets_sent": metrics.get("packets_sent", 0),
                "packets_received": metrics.get("packets_received", 0),
                "avg_rssi": metrics.get("avg_rssi", 0),
                "avg_snr": metrics.get("avg_snr", 0),
                "utilization": metrics.get("utilization", 0)
            }
            self.metrics_df = pd.concat([self.metrics_df, pd.DataFrame([new_metrics])], ignore_index=True)
        
        # Update last metrics update time
        self.last_metrics_update = current_time
        if current_time - self.last_metrics_update >= self.metrics_interval:
            for bs_id, metrics in self.wimax_metrics_snapshot.items():
                self.metrics_df = pd.concat([self.metrics_df, pd.DataFrame([{
                    "timestamp": current_time,
                    "bs_id": bs_id,
                    "connected_vehicles": metrics.get("connected_vehicles", 0),
                    "packets_sent": metrics.get("packets_sent", 0),
                    "packets_received": metrics.get("packets_received", 0)
                }])], ignore_index=True)
            self.last_metrics_update = current_time

    def run_simulation(self, steps=3600):
        self.running = True
        try:
            for _ in range(steps):
                self.run_simulation_step()
                time.sleep(0.05)
        except KeyboardInterrupt:
            print("Simulation stopped by user")
        finally:
            self._save_v2i_metrics()
            self.stop_simulation()

    # ------------------- OUTPUT -------------------
    def _log_packet(self, bs_id: str, vehicle_id: str, packet_type: str, size_bytes: int):
        """Log a single V2I packet"""
        try:
            current_time = traci.simulation.getTime()
            
            # Create a new DataFrame for the packet
            new_packet = pd.DataFrame([{
                "timestamp": current_time,
                "bs_id": bs_id,
                "vehicle_id": vehicle_id,
                "packet_type": packet_type,
                "size_bytes": size_bytes
            }])
            
            # Append to the main DataFrame
            if self.packets_df is None:
                self.packets_df = new_packet
            else:
                self.packets_df = pd.concat([self.packets_df, new_packet], ignore_index=True)
                
            # Print debug info for the first few packets
            if len(self.packets_df) <= 5:  # Only print first 5 packets for debugging
                print(f"Logged packet: time={current_time:.2f}, bs={bs_id}, vehicle={vehicle_id}, "
                      f"type={packet_type}, size={size_bytes} bytes")
                      
        except Exception as e:
            print(f"Error logging packet: {e}")
            import traceback
            traceback.print_exc()

    def _calculate_summary_stats(self):
        """Calculate summary statistics from the collected metrics"""
        if self.metrics_df.empty or self.packets_df.empty:
            return {}
            
        # Calculate packet delivery ratio (PDR)
        total_packets = len(self.packets_df)
        successful_packets = len(self.packets_df[self.packets_df['packet_type'] != 'dropped'])
        pdr = successful_packets / total_packets if total_packets > 0 else 0
        
        # Calculate latency stats (if available)
        if 'latency_ms' in self.packets_df.columns:
            mean_latency = self.packets_df['latency_ms'].mean() / 1000  # Convert to seconds
            jitter = self.packets_df['latency_ms'].std() / 1000  # Convert to seconds
        else:
            mean_latency = 0
            jitter = 0
            
        # Calculate throughput (total bytes / simulation time)
        sim_time = traci.simulation.getTime()
        total_bytes = self.packets_df['size_bytes'].sum()
        throughput_bps = (total_bytes * 8) / sim_time if sim_time > 0 else 0
        
        # Calculate packet loss rate
        packet_loss_rate = 1 - pdr
        
        # Get RSU statistics
        rsu_stats = {}
        for bs_id, bs in self.wimax_base_stations.items():
            metrics = bs.get_metrics()
            rsu_stats[f'rsu_{bs_id}'] = {
                'utilization': metrics.get('utilization', 0),
                'tx_bytes': metrics.get('tx_bytes', 0),
                'rx_bytes': metrics.get('rx_bytes', 0),
                'connected_vehicles': metrics.get('connected_vehicles', 0)
            }
        
        return {
            'total_packets': total_packets,
            'successful_packets': successful_packets,
            'PDR': pdr,
            'mean_latency_s': mean_latency,
            'jitter_s': jitter,
            'packet_loss_rate': packet_loss_rate,
            'throughput_bps': throughput_bps,
            'loss_reasons': {'rx_error': 0},  # Placeholder, update if you track error types
            'handoff_success_rate': float('nan'),  # Update if you track handoffs
            'rsu_stats_sample': rsu_stats
        }

    def _save_v2i_metrics(self):
        """Save both V2I metrics and packets to CSV files"""
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Save detailed metrics
        metrics_file = os.path.join(self.output_dir, "v2i_metrics.csv")
        if not self.metrics_df.empty:
            self.metrics_df.to_csv(metrics_file, index=False)
            print(f"Saved V2I metrics to {metrics_file}")
        
        # Save detailed packets
        packets_file = os.path.join(self.output_dir, "v2i_packets.csv")
        if not self.packets_df.empty:
            self.packets_df.to_csv(packets_file, index=False)
            print(f"Saved V2I packets to {packets_file}")
        
        # Calculate and save summary statistics
        summary_stats = self._calculate_summary_stats()
        if summary_stats:
            summary_file = os.path.join(self.output_dir, "v2i_summary.json")
            with open(summary_file, 'w') as f:
                import json
                # Convert numpy types to native Python types for JSON serialization
                def convert(obj):
                    if isinstance(obj, (np.integer, np.floating)):
                        return float(obj)
                    elif isinstance(obj, np.ndarray):
                        return obj.tolist()
                    elif isinstance(obj, dict):
                        return {k: convert(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [convert(x) for x in obj]
                    return obj
                
                json.dump(convert(summary_stats), f, indent=2)
            print(f"Saved V2I summary to {summary_file}")

    def stop_simulation(self):
        # Save metrics before closing
        if hasattr(self, 'sumo_connected') and self.sumo_connected:
            self._save_v2i_metrics()
            
        try: 
            traci.close()
            self.sumo_connected = False
        except: 
            pass
            
        print("SUMO simulation closed.")

