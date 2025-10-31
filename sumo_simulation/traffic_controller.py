#!/usr/bin/env python3
"""
Adaptive Traffic Light Controller for VANET System with Ambulance Priority
Uses SUMO TraCI for real-time traffic signal control
"""

import traci
import time
import sys
import os
import csv
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

# Add sensor network to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'sensors'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'v2v_communication'))
from sumo_simulation.sensors.sensor_network import SensorNetwork, SensorReading

from wimax import WiMAXConfig, WiMAXBaseStation, WiMAXMobileStation

class AdaptiveTrafficController:
    def __init__(self, output_dir="./output_rule", mode="rule"):
        self.sensor_network = SensorNetwork()
        self.intersections = {}
        self.running = False
        self.simulation_step = 0
        self.output_dir = output_dir
        self.mode = mode
        
        # Suggestion and preemption state
        # suggestions[tl_id] = { direction: str (north/south/east/west), priority: int, expire_at: float, vehicle_id: Optional[str] }
        self.suggestions: Dict[str, Dict] = {}
        # preemptions[tl_id] = { active: bool, phase: int, vehicle_id: Optional[str], last_seen: float }
        self.preemptions: Dict[str, Dict] = {}

        # WiMAX setup
        self.wimax_config = WiMAXConfig()
        self.wimax_base_stations: Dict[str, WiMAXBaseStation] = {}
        self.wimax_last_beacon_step = 0
        self.wimax_metrics_snapshot: Dict = {}

        # We no longer rely on hard-coded state strings. We dynamically map the
        # SUMO program indices for EW/NS green and yellow phases per junction.
        self.default_phases = {}
        # Control parameters
        self.min_green_time = 15
        self.max_green_time = 60
        self.yellow_time = 5
        self.extension_time = 5
        # Local RSU emergency preemption threshold (meters)
        self.preempt_distance_m = 150.0

    # ------------------- SUMO -------------------
    def connect_to_sumo(self, config_path, use_gui=True):
        try:
            try: traci.close()
            except: pass

            summary_path = os.path.join(self.output_dir, "summary.xml")
            tripinfo_path = os.path.join(self.output_dir, "tripinfo.xml")

            sumo_binary = "sumo-gui" if use_gui else "sumo"
            
            # Start SUMO paused by default (no --start)
            traci.start([
                sumo_binary,
                "-c", config_path,
                "--summary-output", summary_path,
                "--tripinfo-output", tripinfo_path
            ])
            print(f"Connected to SUMO ({sumo_binary}).")
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
        # Known coordinates for our two junctions (used for logging/metrics)
        coords = {"J2": (500.0, 500.0), "J3": (1000.0, 500.0)}
        for tl in tl_ids:
            # Analyze the current SUMO traffic light program to learn indices
            phase_map = self._analyze_program(tl)
            self.intersections[tl] = {
                "current_phase": traci.trafficlight.getPhase(tl),
                "time_in_phase": 0,
                "phase_duration": 30,
                "coords": {"x": coords.get(tl, (0.0, 0.0))[0], "y": coords.get(tl, (0.0, 0.0))[1]},
                "queue_lengths": {"N": 0, "S": 0, "E": 0, "W": 0},
                "phase_map": phase_map,
                "pending_green": None  # None | "NS" | "EW"
            }

    def _initialize_wimax(self):
        coords = {"J2": (500,500), "J3": (1000,500)}
        for tl, (x,y) in coords.items():
            if tl in self.intersections:
                self.wimax_base_stations[tl] = WiMAXBaseStation(tl, x, y, self.wimax_config)

    def _analyze_program(self, tl_id: str) -> Dict[str, int]:
        """Inspect SUMO signal program to map indices for EW/NS green/yellow.
        We classify signal indices belonging to EW approaches (E2/E3/E4) vs NS (E5/E6/E7/E8)
        and then find phases where those signals are green or yellow.
        Returns keys: ew_green, ew_yellow, ns_green, ns_yellow. Falls back to 0..3 if unknown.
        """
        phase_map = {"ew_green": 0, "ew_yellow": 1, "ns_green": 2, "ns_yellow": 3}
        try:
            logics = traci.trafficlight.getAllProgramLogics(tl_id)
            if not logics:
                return phase_map
            logic = logics[0]
            states = [p.state for p in logic.phases]
            # Determine which signal indices correspond to EW vs NS using controlled links
            ctrl_links = traci.trafficlight.getControlledLinks(tl_id)
            ew_indices = set()
            ns_indices = set()
            for idx, links in enumerate(ctrl_links):
                # links: list of tuples (inLane, outLane, via)
                if not links:
                    continue
                in_lane = links[0][0]
                if any(edge in in_lane for edge in ["E2", "E3", "E4"]):
                    ew_indices.add(idx)
                elif any(edge in in_lane for edge in ["E5", "E6", "E7", "E8"]):
                    ns_indices.add(idx)

            def is_green_for(indices: set, s: str):
                return indices and all(s[i] in ("g", "G") for i in indices)

            def is_yellow_for(indices: set, s: str):
                # treat any yellow on those indices as yellow phase
                return indices and any(s[i] in ("y", "Y") for i in indices) and not is_green_for(indices, s)

            # Find best matches
            for i, s in enumerate(states):
                if is_green_for(ew_indices, s):
                    phase_map["ew_green"] = i
                if is_green_for(ns_indices, s):
                    phase_map["ns_green"] = i
                if is_yellow_for(ew_indices, s):
                    phase_map["ew_yellow"] = i
                if is_yellow_for(ns_indices, s):
                    phase_map["ns_yellow"] = i
        except Exception:
            pass
        return phase_map

    # ------------------- SIMULATION -------------------
    def update_traffic_lights(self):
        """
        Update traffic lights based on rule-based control logic.
        Does NOT call traci.simulationStep() - that's done by caller.
        """
        try:
            self.simulation_step += 1

            # Simple rule-based traffic light update with suggestion bias and local preemption
            for tl_id, data in self.intersections.items():
                # Get controlled lanes (incoming lanes to junction)
                try:
                    controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
                    
                    # Calculate queue lengths by counting halting vehicles
                    # For J2: E5 (south->north), E6 (north->south), E2 (east->west), E4 (west->east)
                    # For J3: E7 (south->north), E8 (north->south), E3 (continuing from E2), ...
                    queue_lengths = {"N": 0, "S": 0, "E": 0, "W": 0}
                    for lane in controlled_lanes:
                        halting = traci.lane.getLastStepHaltingNumber(lane)
                        
                        # Determine direction based on edge name (not lane index)
                        if "E5" in lane or "E7" in lane:  # South approach (vehicles heading north)
                            queue_lengths["N"] += halting
                        elif "E6" in lane or "E8" in lane:  # North approach (vehicles heading south)
                            queue_lengths["S"] += halting
                        elif "E4" in lane:  # West approach (vehicles heading east)
                            queue_lengths["E"] += halting
                        elif "E2" in lane or "E3" in lane:  # East approach (vehicles heading west)
                            queue_lengths["W"] += halting
                    
                    data["queue_lengths"] = queue_lengths
                except Exception as e:
                    # Fallback: set zero queue lengths
                    data["queue_lengths"] = {"N": 0, "S": 0, "E": 0, "W": 0}
                
                # Cleanup expired suggestions
                if tl_id in self.suggestions:
                    if time.time() >= self.suggestions[tl_id].get("expire_at", 0):
                        self.suggestions.pop(tl_id, None)
                
                # Local RSU emergency preemption: if emergency vehicle within threshold on any controlled lane
                try:
                    emergencies = self.sensor_network.detect_emergency_vehicles()
                except Exception:
                    emergencies = []

                triggered_preempt = False
                for ev in emergencies:
                    lane_id = getattr(ev, 'lane_id', '')
                    dist = float(getattr(ev, 'distance_from_intersection', 1e9))
                    if lane_id in controlled_lanes and dist <= self.preempt_distance_m:
                        # Determine target phase based on lane direction
                        target_is_ew = any(edge in lane_id for edge in ["E2", "E3", "E4"])
                        pm = data.get("phase_map", {})
                        target_phase = pm.get("ew_green") if target_is_ew else pm.get("ns_green")
                        # Apply immediate green to target phase
                        traci.trafficlight.setPhase(tl_id, int(target_phase))
                        traci.trafficlight.setPhaseDuration(tl_id, max(self.min_green_time, 10))
                        # Update local state
                        data["current_phase"] = int(target_phase)
                        data["time_in_phase"] = 0
                        data["pending_green"] = None
                        # Track preemption
                        self.preemptions[tl_id] = {"active": True, "phase": target_phase, "vehicle_id": getattr(ev, 'vehicle_id', None), "last_seen": time.time()}
                        triggered_preempt = True
                        break  # One preemption per junction per step is enough

                # If we just triggered preemption, skip normal decision for this junction
                if triggered_preempt:
                    continue

                # If preemption previously active, keep it until min green is served and no close EV
                if self.preemptions.get(tl_id, {}).get("active"):
                    data["time_in_phase"] += 1
                    # If min green served, and no emergency within threshold now, clear preemption
                    if data["time_in_phase"] >= self.min_green_time:
                        # Check if any emergency still close
                        still_close = False
                        for ev in emergencies:
                            if getattr(ev, 'lane_id', '') in controlled_lanes and float(getattr(ev, 'distance_from_intersection', 1e9)) <= self.preempt_distance_m:
                                still_close = True
                                self.preemptions[tl_id]["last_seen"] = time.time()
                                break
                        if not still_close:
                            self.preemptions[tl_id]["active"] = False
                            # If a suggestion exists for this tl and was tied to same vehicle, clear it
                            sug = self.suggestions.get(tl_id)
                            if sug and sug.get("vehicle_id") == self.preemptions[tl_id].get("vehicle_id"):
                                self.suggestions.pop(tl_id, None)
                    # Either way, do not change phase while in preemption management
                    continue
                
                # Density-based phase control for each junction INDEPENDENTLY
                data["time_in_phase"] += 1
                
                # Sync with SUMO phase index each tick
                current_phase_idx = traci.trafficlight.getPhase(tl_id)
                data["current_phase"] = current_phase_idx

                pm = data.get("phase_map", {})
                ew_green = pm.get("ew_green", 0)
                ew_yellow = pm.get("ew_yellow", 1)
                ns_green = pm.get("ns_green", 2)
                ns_yellow = pm.get("ns_yellow", 3)

                # 1) Handle yellow phases with dedicated short duration
                if current_phase_idx in [ew_yellow, ns_yellow]:
                    if data["time_in_phase"] >= self.yellow_time:
                        # Advance to the pending or opposite green
                        if data.get("pending_green") == "NS" or current_phase_idx == ew_yellow:
                            next_green = ns_green
                            data["pending_green"] = None
                        else:
                            next_green = ew_green
                            data["pending_green"] = None
                        data["current_phase"] = int(next_green)
                        data["time_in_phase"] = 0
                        traci.trafficlight.setPhase(tl_id, int(next_green))
                    # While in yellow, do not evaluate density switching
                    continue

                # 2) Green phase control: respect minimum green, then evaluate switch
                if data["time_in_phase"] < self.min_green_time:
                    # Keep current green until minimum green is met
                    continue

                # Evaluate demand after minimum green
                ns_demand = queue_lengths["N"] + queue_lengths["S"]
                ew_demand = queue_lengths["E"] + queue_lengths["W"]

                # Apply fog suggestion bias if any
                if tl_id in self.suggestions:
                    sug = self.suggestions[tl_id]
                    bias = max(1, int(sug.get("priority", 1))) * 2  # +2 per priority level
                    direction = sug.get("direction")
                    if direction in ["north", "south"]:
                        ns_demand += bias
                    elif direction in ["east", "west"]:
                        ew_demand += bias

                # Require significant difference to switch (prevents oscillation)
                SWITCH_THRESHOLD = 2
                should_be_ns = ns_demand > ew_demand + SWITCH_THRESHOLD
                should_be_ew = ew_demand > ns_demand + SWITCH_THRESHOLD

                if current_phase_idx == ew_green:  # Currently EW green
                    must_rotate = data["time_in_phase"] >= self.max_green_time and ns_demand > 0
                    if should_be_ns or must_rotate:
                        # Switch to EW yellow, then NS green next
                        data["current_phase"] = int(ew_yellow)
                        data["time_in_phase"] = 0
                        data["pending_green"] = "NS"
                        traci.trafficlight.setPhase(tl_id, int(ew_yellow))
                    else:
                        # Extend EW green by resetting timer
                        data["time_in_phase"] = 0

                elif current_phase_idx == ns_green:  # Currently NS green
                    must_rotate = data["time_in_phase"] >= self.max_green_time and ew_demand > 0
                    if should_be_ew or must_rotate:
                        # Switch to NS yellow, then EW green next
                        data["current_phase"] = int(ns_yellow)
                        data["time_in_phase"] = 0
                        data["pending_green"] = "EW"
                        traci.trafficlight.setPhase(tl_id, int(ns_yellow))
                    else:
                        # Extend NS green by resetting timer
                        data["time_in_phase"] = 0

            # Update WiMAX metrics
            self._update_wimax()
            return True
        except Exception as e:
            print(f"Error updating traffic lights: {e}")
            return False
    
    def run_simulation_step(self):
        """
        Full simulation step including SUMO step and traffic light update.
        Use this for standalone traffic controller.
        """
        try:
            traci.simulationStep()
            return self.update_traffic_lights()
        except Exception as e:
            print(f"Error in simulation step: {e}")
            return False

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

    # ------------------- API helpers -------------------
    def receive_suggestion(self, pole_id: str, direction: str, priority: int = 1, ttl: int = 20, vehicle_id: Optional[str] = None) -> Dict:
        """Receive a fog suggestion to bias density toward a lane group.
        direction: one of 'north','south','east','west' (lane group)
        priority: 1..5 (weight of bias)
        ttl: seconds to keep suggestion active
        """
        expire_at = time.time() + max(5, int(ttl))
        self.suggestions[pole_id] = {
            "direction": direction,
            "priority": int(priority),
            "expire_at": expire_at,
            "vehicle_id": vehicle_id
        }
        return {"status": "accepted", "poleId": pole_id, "direction": direction, "priority": priority, "expire_at": int(expire_at)}

    def get_metrics(self) -> Dict:
        """Return lightweight metrics used by backend for status endpoints."""
        return {
            "simulation_step": self.simulation_step,
            "intersections": {
                tl: {
                    "current_phase": data.get("current_phase", 0),
                    "time_in_phase": data.get("time_in_phase", 0),
                    "queue_lengths": data.get("queue_lengths", {}),
                    "suggestion": self.suggestions.get(tl)
                }
                for tl, data in self.intersections.items()
            }
        }

