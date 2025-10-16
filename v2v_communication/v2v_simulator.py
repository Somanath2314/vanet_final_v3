"""
V2V Communication Simulator
Integrates secure V2V communication with the VANET traffic simulation
"""

import time
import random
import json
import threading
from typing import Dict, List, Optional, Tuple
import traci
from collections import defaultdict

# Import V2V security module
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'v2v_communication'))
from v2v_security import RSASecurityManager, V2VCommunicationManager, VehicleIdentity


class V2VSimulator:
    """V2V Communication Simulator for VANET"""

    def __init__(self, communication_range: float = 300.0):
        self.communication_range = communication_range
        self.security_manager = RSASecurityManager()
        self.v2v_manager = V2VCommunicationManager(self.security_manager)

        # Vehicle tracking
        self.vehicles: Dict[str, Dict] = {}
        self.vehicle_locations: Dict[str, Tuple[float, float]] = {}

        # Communication statistics
        self.message_stats = {
            'total_sent': 0,
            'total_received': 0,
            'safety_messages': 0,
            'traffic_info_messages': 0,
            'emergency_messages': 0
        }

        # Simulation state
        self.running = False
        self.simulation_thread = None

    def register_vehicle(self, vehicle_id: str) -> bool:
        """Register a new vehicle in the V2V network"""
        try:
            # Register with security manager
            cert = self.security_manager.register_vehicle(vehicle_id)

            # Initialize vehicle data
            self.vehicles[vehicle_id] = {
                'id': vehicle_id,
                'certificate': cert,
                'location': (0.0, 0.0),
                'speed': 0.0,
                'lane': '',
                'route': [],
                'last_update': time.time()
            }

            print(f"Registered vehicle {vehicle_id} with certificate {cert.certificate_hash[:16]}...")
            return True

        except Exception as e:
            print(f"Failed to register vehicle {vehicle_id}: {e}")
            return False

    def update_vehicle_position(self, vehicle_id: str, x: float, y: float, speed: float, lane: str):
        """Update vehicle position and trigger V2V communications"""
        if vehicle_id not in self.vehicles:
            return

        # Update vehicle data
        self.vehicles[vehicle_id]['location'] = (x, y)
        self.vehicles[vehicle_id]['speed'] = speed
        self.vehicles[vehicle_id]['lane'] = lane
        self.vehicles[vehicle_id]['last_update'] = time.time()

        # Find nearby vehicles for communication
        nearby_vehicles = self._find_nearby_vehicles(vehicle_id)

        if nearby_vehicles:
            self._perform_v2v_communications(vehicle_id, nearby_vehicles)

    def _find_nearby_vehicles(self, vehicle_id: str) -> List[str]:
        """Find vehicles within communication range"""
        if vehicle_id not in self.vehicles:
            return []

        current_pos = self.vehicles[vehicle_id]['location']
        nearby = []

        for other_id, other_vehicle in self.vehicles.items():
            if other_id == vehicle_id:
                continue

            other_pos = other_vehicle['location']

            # Calculate distance
            distance = ((current_pos[0] - other_pos[0])**2 + (current_pos[1] - other_pos[1])**2)**0.5

            if distance <= self.communication_range:
                nearby.append(other_id)

        return nearby

    def _perform_v2v_communications(self, vehicle_id: str, nearby_vehicles: List[str]):
        """Perform V2V communications with nearby vehicles"""
        current_vehicle = self.vehicles[vehicle_id]

        for other_id in nearby_vehicles:
            # Skip if already communicated recently (simulate communication frequency)
            if random.random() < 0.3:  # 30% chance per nearby vehicle per update
                self._send_safety_message(vehicle_id, other_id)

            if random.random() < 0.2:  # 20% chance for traffic info
                self._send_traffic_info(vehicle_id, other_id)

    def _send_safety_message(self, sender_id: str, receiver_id: str):
        """Send safety message between vehicles"""
        sender_vehicle = self.vehicles[sender_id]
        location = {'x': sender_vehicle['location'][0], 'y': sender_vehicle['location'][1]}
        speed = sender_vehicle['speed']

        # Determine if emergency (simplified logic)
        emergency = speed > 80 or random.random() < 0.05  # 5% chance of emergency

        message = self.v2v_manager.broadcast_safety_message(
            sender_id=sender_id,
            location=location,
            speed=speed,
            emergency=emergency
        )

        if message:
            self.message_stats['total_sent'] += 1
            self.message_stats['safety_messages'] += 1
            if emergency:
                self.message_stats['emergency_messages'] += 1

    def _send_traffic_info(self, sender_id: str, receiver_id: str):
        """Send traffic information between vehicles"""
        # Generate traffic data based on current situation
        traffic_data = {
            'condition': random.choice(['light', 'moderate', 'heavy']),
            'congestion': random.uniform(0.1, 0.9),
            'action': random.choice(['proceed_normally', 'slow_down', 'find_alternate_route'])
        }

        message = self.v2v_manager.send_traffic_info(
            sender_id=sender_id,
            receiver_id=receiver_id,
            traffic_data=traffic_data
        )

        if message:
            self.message_stats['total_sent'] += 1
            self.message_stats['traffic_info_messages'] += 1

    def process_received_messages(self, vehicle_id: str) -> List:
        """Process messages received by a vehicle"""
        received_messages = self.v2v_manager.receive_message(vehicle_id)

        for message in received_messages:
            self.message_stats['total_received'] += 1

            # Process different message types
            if message.message_type == 'safety':
                self._process_safety_message(vehicle_id, message)
            elif message.message_type == 'traffic_info':
                self._process_traffic_info(vehicle_id, message)

        return received_messages

    def _process_safety_message(self, vehicle_id: str, message: Dict):
        """Process received safety message"""
        # In a real implementation, this would trigger safety actions
        print(f"Vehicle {vehicle_id} received safety message from {message.sender_id}")

        if message.payload.get('emergency'):
            print(f"  EMERGENCY ALERT from {message.sender_id}!")

    def _process_traffic_info(self, vehicle_id: str, message: Dict):
        """Process received traffic information"""
        # In a real implementation, this would update route planning
        print(f"Vehicle {vehicle_id} received traffic info from {message.sender_id}")
        print(f"  Traffic condition: {message.payload.get('condition', 'unknown')}")
        print(f"  Recommended action: {message.payload.get('action', 'unknown')}")

    def get_communication_stats(self) -> Dict:
        """Get V2V communication statistics"""
        stats = self.message_stats.copy()
        stats.update(self.v2v_manager.get_performance_metrics())
        stats['active_vehicles'] = len(self.vehicles)
        stats['communication_range'] = self.communication_range
        return stats

    def start_simulation(self, update_interval: float = 1.0):
        """Start the V2V simulation"""
        self.running = True
        self.simulation_thread = threading.Thread(target=self._simulation_loop, args=(update_interval,))
        self.simulation_thread.daemon = True
        self.simulation_thread.start()
        print("V2V simulation started")

    def stop_simulation(self):
        """Stop the V2V simulation"""
        self.running = False
        if self.simulation_thread:
            self.simulation_thread.join(timeout=2.0)
        print("V2V simulation stopped")

    def _simulation_loop(self, update_interval: float):
        """Main simulation loop"""
        while self.running:
            try:
                # Process any pending operations
                time.sleep(update_interval)
            except Exception as e:
                print(f"Error in V2V simulation loop: {e}")
                break

    def integrate_with_sumo(self, sumo_config_path: str = None):
        """Integrate V2V communication with SUMO simulation"""
        try:
            # Connect to SUMO
            if sumo_config_path:
                traci.start(["sumo-gui", "-c", sumo_config_path])
            else:
                traci.start(["sumo-gui", "-c", "../sumo_simulation/simulation.sumocfg"])

            print("Connected to SUMO for V2V integration")

            # Register all vehicles currently in simulation
            vehicle_ids = traci.vehicle.getIDList()
            for veh_id in vehicle_ids:
                self.register_vehicle(veh_id)

            # Main simulation loop
            step = 0
            while traci.simulation.getMinExpectedNumber() > 0:
                traci.simulationStep()

                # Update vehicle positions and handle V2V communication
                for veh_id in traci.vehicle.getIDList():
                    if veh_id in self.vehicles:
                        x, y = traci.vehicle.getPosition(veh_id)
                        speed = traci.vehicle.getSpeed(veh_id)
                        lane = traci.vehicle.getLaneID(veh_id)

                        self.update_vehicle_position(veh_id, x, y, speed, lane)

                        # Process received messages periodically
                        if step % 10 == 0:  # Every 10 steps
                            self.process_received_messages(veh_id)

                step += 1

                # Print stats periodically
                if step % 100 == 0:
                    stats = self.get_communication_stats()
                    print(f"V2V Stats at step {step}: {stats['total_sent']} sent, "
                          f"{stats['total_received']} received, "
                          f"{stats['active_vehicles']} vehicles")

            traci.close()
            print("SUMO-V2V integration completed")

        except Exception as e:
            print(f"Error in SUMO-V2V integration: {e}")
            if 'traci' in locals():
                traci.close()


# Example usage
if __name__ == "__main__":
    # Create V2V simulator
    v2v_sim = V2VSimulator(communication_range=300.0)

    # Register some test vehicles
    v2v_sim.register_vehicle("test_vehicle_1")
    v2v_sim.register_vehicle("test_vehicle_2")
    v2v_sim.register_vehicle("test_vehicle_3")

    # Simulate some movement and communication
    positions = [
        (100, 100, 50), (110, 105, 45), (120, 110, 40),  # Vehicle 1
        (200, 200, 60), (210, 205, 55), (220, 210, 50),  # Vehicle 2
        (150, 300, 30), (155, 305, 25), (160, 310, 35)   # Vehicle 3
    ]

    for i, (x1, y1, s1, x2, y2, s2, x3, y3, s3) in enumerate([
        (100, 100, 50, 200, 200, 60, 150, 300, 30),
        (110, 105, 45, 210, 205, 55, 155, 305, 25),
        (120, 110, 40, 220, 210, 50, 160, 310, 35)
    ]):
        print(f"\n--- Time Step {i+1} ---")

        # Update positions
        v2v_sim.update_vehicle_position("test_vehicle_1", x1, y1, s1, "E1_0")
        v2v_sim.update_vehicle_position("test_vehicle_2", x2, y2, s2, "E2_0")
        v2v_sim.update_vehicle_position("test_vehicle_3", x3, y3, s3, "E5_0")

        # Process received messages
        for veh_id in ["test_vehicle_1", "test_vehicle_2", "test_vehicle_3"]:
            messages = v2v_sim.process_received_messages(veh_id)

        time.sleep(0.1)  # Simulate time passing

    # Print final statistics
    final_stats = v2v_sim.get_communication_stats()
    print(f"\nFinal V2V Communication Statistics:")
    print(json.dumps(final_stats, indent=2))
