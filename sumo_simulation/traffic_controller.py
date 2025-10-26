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
from sensor_network import SensorNetwork, SensorReading
from wimax import WiMAXConfig, WiMAXBaseStation, WiMAXMobileStation

class SignalState(Enum):
    GREEN = "G"
    YELLOW = "y"
    RED = "r"

@dataclass
class TrafficPhase:
    duration: int
    state: str
    description: str

@dataclass
class IntersectionData:
    intersection_id: str
    current_phase: int
    phase_duration: int
    time_in_phase: int
    queue_lengths: Dict[str, float]
    traffic_densities: Dict[str, float]
    emergency_detected: bool

class AdaptiveTrafficController:
    """Adaptive traffic light controller using sensor data with ambulance priority"""
    
    def __init__(self, sumo_config_path: str = None):
        self.sensor_network = SensorNetwork()
        self.intersections: Dict[str, IntersectionData] = {}
        self.running = False
        self.simulation_step = 0

        # WiMAX integration
        self.wimax_config = WiMAXConfig()
        self.wimax_base_stations: Dict[str, WiMAXBaseStation] = {}
        self.wimax_last_beacon_step = 0
        self.wimax_metrics_snapshot: Dict = {}

        # Traffic light programs - 4-way intersections
        self.default_phases = {
            "J2": [
                TrafficPhase(30, "rrrGGG", "East-West Green"),
                TrafficPhase(5, "rrryyy", "East-West Yellow"),
                TrafficPhase(30, "GGGrrr", "North-South Green"),
                TrafficPhase(5, "yyyrrr", "North-South Yellow")
            ],
            "J3": [
                TrafficPhase(30, "rrrGGG", "East-West Green"),
                TrafficPhase(5, "rrryyy", "East-West Yellow"),
                TrafficPhase(30, "GGGrrr", "North-South Green"),
                TrafficPhase(5, "yyyrrr", "North-South Yellow")
            ]
        }

        # Adaptive timing
        self.min_green_time = 15
        self.max_green_time = 60
        self.yellow_time = 5
        self.extension_time = 5

    # ------------------- SUMO Connection -------------------
    def connect_to_sumo(self, config_path: str = None):
        try:
            try:
                traci.close()
            except:
                pass
            
            if config_path:
                traci.start(["sumo-gui", "-c", config_path])
            else:
                traci.start(["sumo-gui", "-c", "simulation.sumocfg"])
            print("Connected to SUMO simulation")
            self._initialize_intersections()
            self._initialize_wimax()
            return True
        except Exception as e:
            print(f"Failed to connect to SUMO: {e}")
            import traceback; traceback.print_exc()
            return False

    def _initialize_intersections(self):
        """Initialize intersections"""
        traffic_lights = traci.trafficlight.getIDList()
        print(f"Found traffic lights: {traffic_lights}")
        for tl_id in traffic_lights:
            self.intersections[tl_id] = IntersectionData(
                intersection_id=tl_id,
                current_phase=0,
                phase_duration=30,
                time_in_phase=0,
                queue_lengths={},
                traffic_densities={},
                emergency_detected=False
            )

    def _initialize_wimax(self):
        """Initialize WiMAX base stations"""
        bs_coords = {"J2": (500.0, 500.0), "J3": (1000.0, 500.0)}
        for tl_id, coords in bs_coords.items():
            if tl_id in self.intersections:
                x, y = coords
                self.wimax_base_stations[tl_id] = WiMAXBaseStation(
                    bs_id=tl_id, x=x, y=y, config=self.wimax_config
                )

    # ------------------- Sensor & WiMAX -------------------
    def _update_wimax(self):
        """Update WiMAX communications"""
        try:
            vehicle_ids = traci.vehicle.getIDList()
        except Exception:
            return

        association_radius_m = 800.0
        for veh_id in vehicle_ids:
            try:
                pos = traci.vehicle.getPosition(veh_id)
                vx, vy = float(pos[0]), float(pos[1])
            except:
                continue
            nearest_bs, nearest_dist = None, None
            for bs in self.wimax_base_stations.values():
                dx, dy = bs.x - vx, bs.y - vy
                dist = (dx*dx + dy*dy)**0.5
                if nearest_dist is None or dist < nearest_dist:
                    nearest_dist, nearest_bs = dist, bs
            if nearest_bs and nearest_dist <= association_radius_m:
                if veh_id not in nearest_bs.mobiles:
                    nearest_bs.attach(WiMAXMobileStation(ms_id=veh_id, x=vx, y=vy))
                else:
                    nearest_bs.mobiles[veh_id].x, nearest_bs.mobiles[veh_id].y = vx, vy

        if self.simulation_step - self.wimax_last_beacon_step >= 10:
            for bs in self.wimax_base_stations.values():
                for ms_id in list(bs.mobiles.keys()):
                    bs.enqueue_beacon(ms_id, payload_bytes=200)
            self.wimax_last_beacon_step = self.simulation_step

        for bs in self.wimax_base_stations.values():
            bs.step()
        self.wimax_metrics_snapshot = {bs_id: bs.get_metrics() for bs_id, bs in self.wimax_base_stations.items()}

    def get_vehicle_data_from_sumo(self) -> Dict[str, List[Dict]]:
        """Get vehicle data from SUMO"""
        sensor_vehicles = {}
        try:
            vehicle_ids = traci.vehicle.getIDList()
            for vid in vehicle_ids:
                try:
                    lane_id = traci.vehicle.getLaneID(vid)
                    pos = traci.vehicle.getLanePosition(vid)
                    speed = traci.vehicle.getSpeed(vid)
                    vehicle_type = traci.vehicle.getTypeID(vid)
                    lane_length = traci.lane.getLength(lane_id)
                    distance_from_end = lane_length - pos
                    sensor_group = lane_id.split("_")[0]
                    vehicle_data = {'id': vid, 'speed': speed*3.6, 'distance': distance_from_end, 'type': vehicle_type, 'lane': lane_id}
                    sensor_vehicles.setdefault(sensor_group, []).append(vehicle_data)
                except:
                    continue
        except:
            pass
        return sensor_vehicles

    def update_sensor_data(self):
        vehicle_data = self.get_vehicle_data_from_sumo()
        for group, vehicles in vehicle_data.items():
            for distance in [500, 400, 300, 200, 100, 50]:
                sensor_id = f"sensor_{group}_{distance}m"
                vehicles_in_range = [v for v in vehicles if distance-100 < v['distance'] <= distance]
                if distance % 200 == 0:
                    self.sensor_network.simulate_lidar_detection(sensor_id, vehicles_in_range)
                else:
                    self.sensor_network.simulate_radar_detection(sensor_id, vehicles_in_range)

    # ------------------- Ambulance Priority -------------------
    def check_ambulance_priority(self):
        """Force green for ambulances near any junction"""
        try:
            vehicle_ids = traci.vehicle.getIDList()
        except:
            return
        for vid in vehicle_ids:
            vtype = traci.vehicle.getTypeID(vid)
            if vtype != "ambulance":
                continue
            x, y = traci.vehicle.getPosition(vid)
            for intersection_id, intersection in self.intersections.items():
                jx, jy = traci.junction.getPosition(intersection_id)
                distance = ((x - jx)**2 + (y - jy)**2)**0.5
                if distance < 50:  # Within 50m of junction
                    phases = self.default_phases.get(intersection_id, [])
                    if not phases:
                        continue
                    # Force green
                    current_phase = intersection.current_phase
                    if current_phase % 2 == 1:  # yellow -> switch
                        intersection.current_phase = (current_phase + 1) % len(phases)
                    traci.trafficlight.setRedYellowGreenState(intersection_id, phases[intersection.current_phase].state)
                    intersection.time_in_phase = 0
                    print(f"🚑 Ambulance near {intersection_id} -> GREEN")

    # ------------------- Adaptive Timing -------------------
    def calculate_adaptive_timing(self, intersection_id: str) -> Tuple[int, bool]:
        intersection = self.intersections[intersection_id]
        phases = self.default_phases.get(intersection_id, [])
        if not phases:
            return 30, False
        phase = phases[intersection.current_phase]
        if intersection.current_phase % 2 == 1:  # Yellow
            return phase.duration, False

        # Compute traffic demand
        green_demand, red_demand = 0, 0
        vehicle_data = self.sensor_network.get_sensor_data_summary()
        # Simplified for demo: extend green if any vehicle is queued
        if vehicle_data['total_vehicles_detected'] > 0:
            return min(self.max_green_time, intersection.time_in_phase + self.extension_time), False
        return phase.duration, False

    def control_intersection(self, intersection_id: str):
        if intersection_id not in self.intersections:
            return
        intersection = self.intersections[intersection_id]
        phases = self.default_phases.get(intersection_id, [])
        if not phases:
            return

        new_duration, _ = self.calculate_adaptive_timing(intersection_id)
        intersection.time_in_phase += 1
        should_switch = intersection.time_in_phase >= intersection.phase_duration

        if should_switch:
            intersection.current_phase = (intersection.current_phase + 1) % len(phases)
            intersection.time_in_phase = 0
            if intersection.current_phase % 2 == 0:  # Green
                intersection.phase_duration = new_duration
            else:  # Yellow
                intersection.phase_duration = self.yellow_time
            try:
                traci.trafficlight.setRedYellowGreenState(intersection_id, phases[intersection.current_phase].state)
                print(f"{intersection_id}: Phase {intersection.current_phase} ({phases[intersection.current_phase].description}) - {intersection.phase_duration}s")
            except Exception as e:
                print(f"Error setting traffic light state for {intersection_id}: {e}")

    # ------------------- Simulation -------------------
    def run_simulation_step(self):
        try:
            traci.simulationStep()
            self.simulation_step += 1
            self.update_sensor_data()
            self._update_wimax()
            self.check_ambulance_priority()
            for intersection_id in self.intersections:
                self.control_intersection(intersection_id)
            return True
        except Exception as e:
            print(f"Error in simulation step: {e}")
            return False

    def run_simulation(self, steps: int = 3600):
        print(f"Starting simulation for {steps} steps")
        self.running = True
        try:
            for step in range(steps):
                if not self.running:
                    break
                if not self.run_simulation_step():
                    break
                if step % 60 == 0:
                    self.print_status()
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("Simulation interrupted by user")
        finally:
            self.stop_simulation()

    def print_status(self):
        print(f"\n--- Step {self.simulation_step} ---")
        for intersection_id, intersection in self.intersections.items():
            phase = self.default_phases[intersection_id][intersection.current_phase]
            print(f"{intersection_id}: Phase {intersection.current_phase} ({phase.description}) - {intersection.time_in_phase}/{intersection.phase_duration}s")

    def stop_simulation(self):
        self.running = False
        try:
            traci.close()
            print("SUMO simulation closed")
        except:
            pass

# ------------------- MAIN -------------------
if __name__ == "__main__":
    controller = AdaptiveTrafficController()
    config_path = "simulation.sumocfg"
    if controller.connect_to_sumo(config_path):
        controller.run_simulation(3600)
    else:
        print("Failed to start simulation")
