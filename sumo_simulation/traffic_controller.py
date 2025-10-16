"""
Basic Adaptive Traffic Light Controller for VANET System
Uses SUMO TraCI for real-time traffic signal control
"""

import traci
import time
import threading
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
import sys
import os

# Add sensor network to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'sensors'))
from sensor_network import SensorNetwork, SensorReading

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
    """Basic adaptive traffic light controller using sensor data"""
    
    def __init__(self, sumo_config_path: str = None):
        self.sensor_network = SensorNetwork()
        self.intersections: Dict[str, IntersectionData] = {}
        self.running = False
        self.simulation_step = 0
        
        # Traffic light programs - 4-way intersections
        # State format: 6 connections per intersection (3 per direction)
        # Format: [N-S lane0, N-S lane1, N-S turn, E-W lane0, E-W lane1, E-W turn]
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
        
        # Adaptive timing parameters
        self.min_green_time = 15
        self.max_green_time = 60
        self.yellow_time = 5
        self.extension_time = 5
        
    def connect_to_sumo(self, config_path: str = None):
        """Connect to SUMO simulation"""
        try:
            # Close any existing connections
            try:
                traci.close()
            except:
                pass
            
            # Start SUMO with GUI
            if config_path:
                traci.start(["sumo-gui", "-c", config_path])
            else:
                traci.start(["sumo-gui", "-c", "simulation.sumocfg"])
            print("Connected to SUMO simulation")
            self._initialize_intersections()
            # Initialize central pole visualization in SUMO (if available)
            try:
                self.sensor_network.initialize_central_pole()
            except Exception:
                # Non-fatal: continue even if visualization can't be created
                pass
            return True
        except Exception as e:
            print(f"Failed to connect to SUMO: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _initialize_intersections(self):
        """Initialize intersection data"""
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
    
    def get_vehicle_data_from_sumo(self) -> Dict[str, List[Dict]]:
        """Get vehicle data from SUMO for sensor simulation"""
        sensor_vehicles = {}
        
        try:
            # Get all vehicles in simulation
            vehicle_ids = traci.vehicle.getIDList()
            
            # Group vehicles by approaching lanes for sensor simulation
            for vehicle_id in vehicle_ids:
                try:
                    lane_id = traci.vehicle.getLaneID(vehicle_id)
                    position = traci.vehicle.getLanePosition(vehicle_id)
                    speed = traci.vehicle.getSpeed(vehicle_id)
                    vehicle_type = traci.vehicle.getTypeID(vehicle_id)
                    
                    # Calculate distance from intersection
                    lane_length = traci.lane.getLength(lane_id)
                    distance_from_end = lane_length - position
                    
                    vehicle_data = {
                        'id': vehicle_id,
                        'speed': speed * 3.6,  # Convert m/s to km/h
                        'distance': distance_from_end,
                        'type': vehicle_type,
                        'lane': lane_id
                    }
                    
                    # Map to sensor groups
                    if 'E1' in lane_id:
                        sensor_group = 'E1'
                    elif 'E2' in lane_id:
                        sensor_group = 'E2'
                    elif 'E5' in lane_id:
                        sensor_group = 'E5'
                    elif 'E7' in lane_id:
                        sensor_group = 'E7'
                    else:
                        continue
                    
                    if sensor_group not in sensor_vehicles:
                        sensor_vehicles[sensor_group] = []
                    sensor_vehicles[sensor_group].append(vehicle_data)
                    
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"Error getting vehicle data: {e}")
        
        return sensor_vehicles
    
    def update_sensor_data(self):
        """Update sensor readings with SUMO vehicle data"""
        vehicle_data = self.get_vehicle_data_from_sumo()
        
        # Update sensors for each approach
        for sensor_group, vehicles in vehicle_data.items():
            # Filter vehicles for each sensor based on distance
            for distance in [500, 400, 300, 200, 100, 50]:
                sensor_id = f"sensor_{sensor_group}_{distance}m"
                vehicles_in_range = [v for v in vehicles if v['distance'] <= distance and v['distance'] > distance - 100]
                
                # Alternate between radar and LIDAR simulation
                if distance % 200 == 0:  # LIDAR at 500m, 300m, 100m
                    self.sensor_network.simulate_lidar_detection(sensor_id, vehicles_in_range)
                else:  # Radar at other positions
                    self.sensor_network.simulate_radar_detection(sensor_id, vehicles_in_range)
    
    def calculate_adaptive_timing(self, intersection_id: str) -> Tuple[int, bool]:
        """Calculate adaptive signal timing based on sensor data"""
        intersection = self.intersections[intersection_id]

        # Get current phase information
        current_phase = intersection.current_phase
        phases = self.default_phases.get(intersection_id, [])
        if not phases:
            return 30, False

        phase = phases[current_phase]

        # Determine which lanes are currently green
        if current_phase == 0:  # East-West Green
            green_lanes = ['E1_0', 'E2_0'] if intersection_id == 'J2' else ['E2_0', 'E3_0']
            red_lanes = ['E5_0'] if intersection_id == 'J2' else ['E7_0']
        elif current_phase == 2:  # North-South Green
            green_lanes = ['E5_0'] if intersection_id == 'J2' else ['E7_0']
            red_lanes = ['E1_0', 'E2_0'] if intersection_id == 'J2' else ['E2_0', 'E3_0']
        else:
            # Yellow phases - keep default timing
            return phase.duration, False

        # Check for emergency vehicles FIRST
        emergency_vehicles = self.sensor_network.detect_emergency_vehicles()
        emergency_priority = False
        emergency_direction = None

        for emergency in emergency_vehicles:
            if emergency.distance_from_intersection < 300:  # Emergency vehicle within 300m
                # Determine which direction the emergency vehicle is approaching from
                if emergency.lane_id in red_lanes:
                    emergency_priority = True
                    emergency_direction = 'red_lanes'  # Need to switch to red lanes
                    break
                elif emergency.lane_id in green_lanes:
                    # Emergency vehicle already has green light, maintain it
                    return min(self.max_green_time, intersection.time_in_phase + 10), False

        # If emergency vehicle detected, immediately switch
        if emergency_priority:
            print(f"🚨 EMERGENCY VEHICLE DETECTED at {intersection_id} - switching to {emergency_direction}")
            return 5, True  # Cut current phase short

        # Calculate traffic metrics for normal operation
        green_demand = 0
        red_demand = 0

        for lane in green_lanes:
            density, value = self.sensor_network.get_traffic_density(lane)
            queue_length = self.sensor_network.get_queue_length(lane)
            green_demand += value + (queue_length / 100)  # Normalize queue length

        for lane in red_lanes:
            density, value = self.sensor_network.get_traffic_density(lane)
            queue_length = self.sensor_network.get_queue_length(lane)
            red_demand += value + (queue_length / 100)

        # Adaptive timing logic
        if intersection.time_in_phase >= self.min_green_time:
            demand_ratio = green_demand / (red_demand + 0.1)  # Avoid division by zero

            if demand_ratio > 2.0 and intersection.time_in_phase < self.max_green_time:
                # Extend green phase
                return intersection.phase_duration + self.extension_time, False
            elif demand_ratio < 0.5:
                # Early termination if no demand
                return max(self.min_green_time, intersection.time_in_phase + 5), False

        return phase.duration, False
    
    def control_intersection(self, intersection_id: str):
        """Control a single intersection"""
        if intersection_id not in self.intersections:
            return
        
        intersection = self.intersections[intersection_id]
        phases = self.default_phases.get(intersection_id, [])
        
        if not phases:
            return
        
        # Calculate adaptive timing
        new_duration, emergency_switch = self.calculate_adaptive_timing(intersection_id)
        
        current_phase = phases[intersection.current_phase]
        
        # Update timing
        intersection.time_in_phase += 1
        
        # Check if phase should switch
        should_switch = False
        if emergency_switch:
            should_switch = True
            print(f"Emergency vehicle detected at {intersection_id} - switching phase")
        elif intersection.time_in_phase >= intersection.phase_duration:
            should_switch = True
        
        if should_switch:
            # Move to next phase
            intersection.current_phase = (intersection.current_phase + 1) % len(phases)
            intersection.time_in_phase = 0
            
            # Set new phase duration (adaptive)
            if intersection.current_phase in [0, 2]:  # Green phases
                intersection.phase_duration, _ = self.calculate_adaptive_timing(intersection_id)
            else:  # Yellow phases
                intersection.phase_duration = self.yellow_time
            
            # Apply new signal state
            new_phase = phases[intersection.current_phase]
            try:
                traci.trafficlight.setRedYellowGreenState(intersection_id, new_phase.state)
                print(f"{intersection_id}: Phase {intersection.current_phase} - {new_phase.description} ({intersection.phase_duration}s)")
            except Exception as e:
                print(f"Error setting traffic light state for {intersection_id}: {e}")
    
    def run_simulation_step(self):
        """Run one simulation step"""
        try:
            # Advance SUMO simulation
            traci.simulationStep()
            self.simulation_step += 1
            
            # Update sensor data every step
            self.update_sensor_data()

            # Update central pole visualization based on emergency detection
            try:
                self.sensor_network.detect_emergency_vehicles_and_update_pole()
            except Exception:
                # Don't break simulation if visualization update fails
                pass
            
            # Control intersections every second
            if self.simulation_step % 1 == 0:
                for intersection_id in self.intersections:
                    self.control_intersection(intersection_id)
            
            return True
        except Exception as e:
            print(f"Error in simulation step: {e}")
            return False
    
    def run_simulation(self, steps: int = 3600):
        """Run the complete simulation"""
        print(f"Starting adaptive traffic control simulation for {steps} steps")
        self.running = True
        
        try:
            for step in range(steps):
                if not self.running:
                    break
                
                success = self.run_simulation_step()
                if not success:
                    break
                
                # Print status every 60 seconds
                if step % 60 == 0:
                    self.print_status()
                
                time.sleep(0.1)  # Small delay for visualization
                
        except KeyboardInterrupt:
            print("Simulation interrupted by user")
        finally:
            self.stop_simulation()
    
    def print_status(self):
        """Print current status"""
        print(f"\n--- Simulation Step {self.simulation_step} ---")
        
        for intersection_id, intersection in self.intersections.items():
            phase = self.default_phases[intersection_id][intersection.current_phase]
            print(f"{intersection_id}: Phase {intersection.current_phase} ({phase.description}) - {intersection.time_in_phase}/{intersection.phase_duration}s")
        
        # Print sensor summary
        summary = self.sensor_network.get_sensor_data_summary()
        print(f"Vehicles detected: {summary['total_vehicles_detected']}, Emergency: {summary['emergency_vehicles']}")
        
        for lane, density in summary['lane_densities'].items():
            queue = summary['queue_lengths'].get(lane, 0)
            print(f"  {lane}: {density['level']} density ({density['value']:.2f}), Queue: {queue:.1f}m")
    
    def stop_simulation(self):
        """Stop the simulation"""
        self.running = False
        try:
            traci.close()
            print("SUMO simulation closed")
        except:
            pass
    
    def get_metrics(self) -> Dict:
        """Get performance metrics for evaluation"""
        sensor_summary = self.sensor_network.get_sensor_data_summary()
        
        metrics = {
            'simulation_step': self.simulation_step,
            'total_vehicles': sensor_summary['total_vehicles_detected'],
            'emergency_vehicles': sensor_summary['emergency_vehicles'],
            'intersection_states': {},
            'sensor_data': sensor_summary,
            'timestamp': time.time()
        }
        
        for intersection_id, intersection in self.intersections.items():
            metrics['intersection_states'][intersection_id] = {
                'current_phase': intersection.current_phase,
                'time_in_phase': intersection.time_in_phase,
                'phase_duration': intersection.phase_duration
            }
        
    def run_simulation_with_rl(self, rl_controller, steps: int = 3600):
        """Run simulation with RL controller"""
        print(f"Starting RL-based traffic control simulation for {steps} steps")
        self.running = True

        try:
            for step in range(steps):
                if not self.running:
                    break

                # Update sensor data
                try:
                    self.update_sensor_data()
                except Exception as e:
                    print(f"Error updating sensor data: {e}")
                    break

                # Update central pole visualization based on emergency detection
                try:
                    self.sensor_network.detect_emergency_vehicles_and_update_pole()
                except Exception:
                    pass
                # Apply RL control
                try:
                    rl_metrics = rl_controller.step()
                    if 'error' in rl_metrics:
                        print(f"RL Error: {rl_metrics['error']}")
                        break
                except Exception as e:
                    print(f"RL controller error: {e}")
                    break

                # Print status every 60 seconds
                if step % 60 == 0:
                    self.print_status()

                time.sleep(0.1)  # Small delay for visualization

        except KeyboardInterrupt:
            print("RL simulation interrupted by user")
        except Exception as e:
            print(f"Simulation error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop_simulation()


# Main execution
if __name__ == "__main__":
    controller = AdaptiveTrafficController()

    # Connect to SUMO
    config_path = "simulation.sumocfg"
    if controller.connect_to_sumo(config_path):
        print("Starting adaptive traffic control...")
        controller.run_simulation(3600)  # Run for 1 hour simulation time
    else:
        print("Failed to start simulation")