#!/usr/bin/env python3
"""
Adaptive Traffic Light Controller for VANET System with Ambulance Priority
Uses SUMO TraCI for real-time traffic signal control
"""

import traci
import time
import sys
import os
from typing import Dict, List, Tuple
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
    def connect_to_sumo(self, config_path):
        try:
            try: traci.close()
            except: pass

            summary_path = os.path.join(self.output_dir, "summary.xml")
            tripinfo_path = os.path.join(self.output_dir, "tripinfo.xml")

            traci.start([
                "sumo-gui",
                "-c", config_path,
                "--summary-output", summary_path,
                "--tripinfo-output", tripinfo_path
            ])
            print("Connected to SUMO.")
            self._initialize_intersections()
            self._initialize_wimax()
            return True
        except Exception as e:
            print(f"Failed to connect to SUMO: {e}")
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

    def _update_wimax(self):
        # Basic snapshot of attached mobiles
        for bs in self.wimax_base_stations.values():
            bs.step()
        self.wimax_metrics_snapshot = {bs_id: bs.get_metrics() for bs_id, bs in self.wimax_base_stations.items()}

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
    def _save_v2i_metrics(self):
        v2i_metrics_file = os.path.join(self.output_dir, "v2i_metrics.csv")
        with open(v2i_metrics_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["bs_id", "connected_vehicles", "packets_sent", "packets_received"])
            writer.writeheader()
            for bs_id, metrics in self.wimax_metrics_snapshot.items():
                writer.writerow({
                    "bs_id": bs_id,
                    "connected_vehicles": metrics.get("connected_vehicles", 0),
                    "packets_sent": metrics.get("packets_sent", 0),
                    "packets_received": metrics.get("packets_received", 0)
                })
        print(f"Saved V2I metrics -> {v2i_metrics_file}")

    def stop_simulation(self):
        try: traci.close()
        except: pass
        print("SUMO simulation closed.")

