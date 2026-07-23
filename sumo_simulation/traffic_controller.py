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
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum

# Add sensor network to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'sensors'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'v2v_communication'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__)))  # Add sumo_simulation to path

# Try relative imports first (when run as module), fallback to direct imports (when run as script)
try:
    from sensor_network import SensorNetwork, SensorReading
except ImportError:
    from sumo_simulation.sensors.sensor_network import SensorNetwork, SensorReading

# WiMAX imports
try:
    from sumo_simulation.wimax import WiMAXConfig, WiMAXBaseStation, WiMAXMobileStation
    from sumo_simulation.wimax.secure_wimax import SecureWiMAXBaseStation, SecureWiMAXMobileStation
except ImportError:
    # Fallback for when running within sumo_simulation directory
    from wimax import WiMAXConfig, WiMAXBaseStation, WiMAXMobileStation
    from wimax.secure_wimax import SecureWiMAXBaseStation, SecureWiMAXMobileStation

# Edge computing imports
from edge_computing import EdgeRSU
from edge_computing.metrics.edge_metrics import EdgeMetricsTracker

class AdaptiveTrafficController:
    def __init__(self, output_dir="./output_rule", mode="rule", security_managers=None, security_pending=False, edge_computing_enabled=False, emergency_priority_enabled=False):
        self.sensor_network = SensorNetwork()
        self.intersections = {}
        self.running = False
        self.simulation_step = 0
        self.output_dir = output_dir
        self.mode = mode
        self.externally_controlled_tls = set()
        
        # Emergency vehicle priority control
        self.emergency_priority_enabled = emergency_priority_enabled
        if emergency_priority_enabled:
            print("🚑 Emergency vehicle priority ENABLED (greenwave, first-come-first-served)")
        else:
            print("🚗 Emergency vehicles treated as NORMAL vehicles (no priority)")
        
        # Edge computing
        self.edge_enabled = edge_computing_enabled
        self.edge_rsus: Dict[str, EdgeRSU] = {}
        self.edge_metrics_tracker = None
        if edge_computing_enabled:
            print("🔷 Edge computing enabled: Smart RSUs with local processing")
            self.edge_metrics_tracker = EdgeMetricsTracker(output_dir=f"{output_dir}_edge")
        
        # Security infrastructure
        if security_managers:
            self.ca, self.rsu_managers, self.vehicle_managers = security_managers
            self.security_enabled = True
            print("🔐 Security enabled: Hybrid RSA-AES encryption + CA authentication")
        else:
            self.ca = None
            self.rsu_managers = {}
            self.vehicle_managers = {}
            self.security_enabled = False
            if not security_pending:
                print("⚠️  Security disabled: Running without encryption")
        
        # Initialize DataFrames for metrics and packets
        self.packets_df = pd.DataFrame(columns=["timestamp", "bs_id", "vehicle_id", "packet_type", "size_bytes"])
        self.metrics_df = pd.DataFrame(columns=["timestamp", "bs_id", "connected_vehicles", "packets_sent", "packets_received"])
        self.last_metrics_update = 0
        self.metrics_interval = 5  # Update metrics every 5 seconds
        
        # Store simulation time for metrics calculation after SUMO closes
        self.last_simulation_time = 0
        
        # NS3 Bridge reference for accurate V2I statistics
        self.ns3_bridge = None

        # WiMAX setup
        self.wimax_config = WiMAXConfig()
        self.wimax_base_stations: Dict[str, WiMAXBaseStation] = {}
        self.wimax_mobile_stations: Dict[str, WiMAXMobileStation] = {}  # Track vehicles
        self.wimax_last_beacon_step = 0
        self.wimax_metrics_snapshot: Dict = {}

        # Traffic-light phase data is populated dynamically from the loaded SUMO net.
        self.default_phases: Dict[str, List[str]] = {}
        self.phase_durations: Dict[str, List[float]] = {}
        self.tl_positions: Dict[str, Tuple[float, float]] = {}
        self.tl_incoming_links: Dict[str, Dict[str, List[int]]] = {}
        self.edge_to_tl: Dict[str, set] = defaultdict(set)
        self._edge_phase_cache: Dict[str, Dict[str, Optional[int]]] = defaultdict(dict)
        # Optimized timing parameters for better flow
        self.min_green_time = 10      # Reduced from 15 (faster response)
        self.max_green_time = 45      # Reduced from 60 (prevent starvation)
        self.yellow_time = 3          # Reduced from 5 (standard timing)
        self.extension_time = 3       # Reduced from 5 (quicker adaptation)
        
        # Emergency vehicle detection and control ranges (meters)
        # Detection range: When to start giving green light priority
        self.emergency_detection_range = 150.0  # meters - balanced for response time vs normal traffic flow
        # Pass-through range: when an emergency has effectively cleared the junction.
        self.emergency_pass_through_range = 30.0
        # Proactive corridor preemption range and depth.
        self.green_corridor_enabled = True
        self.green_corridor_max_distance = 450.0
        self.green_corridor_junction_lookahead = 3
        self.green_corridor_edge_lookahead = 12
        # Hold green after preemption to let emergency vehicle pass safely.
        self.emergency_green_hold_time = 12
        
        # Track emergency vehicles that have been served at each junction
        # Format: {junction_id: {vehicle_id: 'served'}}
        self.served_emergencies = defaultdict(set)
        
        # Track which emergency vehicle has priority at each junction (first-come-first-served)
        # Format: {junction_id: vehicle_id}
        self.junction_priority_vehicle = {}
        
        # Fixed-time green duration (used only in 'fixed' mode)
        self.fixed_green_time = 30  # seconds per green phase

        # Density thresholds for adaptive control
        self.low_density_threshold = 3    # vehicles
        self.high_density_threshold = 10  # vehicles

    # ------------------- SUMO -------------------
    def connect_to_sumo(self, config_path, use_gui=True, seed=None):
        try:
            try: traci.close()
            except: pass

            # Ensure output directory exists
            os.makedirs(self.output_dir, exist_ok=True)
            
            summary_path = os.path.join(self.output_dir, "summary.xml")
            tripinfo_path = os.path.join(self.output_dir, "tripinfo.xml")

            sumo_binary = "sumo-gui" if use_gui else "sumo"
            
            cmd = [
                sumo_binary,
                "-c", config_path,
                "--summary-output", summary_path,
                "--tripinfo-output", tripinfo_path,
                "--start"  # Auto-start simulation
            ]
            
            # Add seed for reproducibility
            if seed is not None:
                cmd.extend(["--seed", str(seed)])
            
            traci.start(cmd)
            print(f"Connected to SUMO ({sumo_binary}).")
            self.sumo_connected = True
            self._initialize_intersections()
            self._initialize_wimax()
            self._initialize_edge_rsus()
            return True
        except Exception as e:
            print(f"Failed to connect to SUMO: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def set_ns3_bridge(self, ns3_bridge):
        """Set reference to NS3 bridge for accurate V2I statistics"""
        self.ns3_bridge = ns3_bridge
        print("  ✓ NS3 bridge reference set for accurate V2I metrics")

    def set_externally_controlled_tls(self, tl_ids):
        """Allow an external controller (e.g., proximity RL) to drive selected TLs."""
        self.externally_controlled_tls = set(tl_ids or [])

    def configure_emergency_priority(
        self,
        detection_range=None,
        pass_through_range=None,
        corridor_depth=None,
        corridor_max_distance=None,
    ):
        """Configure emergency preemption and proactive green-corridor behavior."""
        if detection_range is not None:
            self.emergency_detection_range = max(30.0, float(detection_range))

        if pass_through_range is not None:
            self.emergency_pass_through_range = max(10.0, float(pass_through_range))

        if corridor_depth is not None:
            depth = max(1, int(corridor_depth))
            self.green_corridor_junction_lookahead = depth
            # Approximate edge horizon from requested junction depth.
            self.green_corridor_edge_lookahead = max(4, depth * 4)

        if corridor_max_distance is not None:
            self.green_corridor_max_distance = max(100.0, float(corridor_max_distance))

    def _initialize_intersections(self):
        self.intersections.clear()
        self.default_phases.clear()
        self.phase_durations.clear()
        self.tl_positions.clear()
        self.tl_incoming_links.clear()
        self.edge_to_tl.clear()
        self._edge_phase_cache.clear()

        tl_ids = traci.trafficlight.getIDList()
        for tl in tl_ids:
            phase_states = []
            phase_durations = []

            try:
                programs = traci.trafficlight.getAllProgramLogics(tl)
                if programs:
                    for phase in programs[0].getPhases():
                        state = getattr(phase, "state", None)
                        if state is None and hasattr(phase, "getRedYellowGreenState"):
                            state = phase.getRedYellowGreenState()
                        duration = float(getattr(phase, "duration", 0) or 0)
                        if duration <= 0 and hasattr(phase, "getDuration"):
                            duration = float(phase.getDuration())
                        if state:
                            phase_states.append(state)
                            phase_durations.append(max(duration, 1.0))
            except Exception:
                pass

            if not phase_states:
                try:
                    fallback_state = traci.trafficlight.getRedYellowGreenState(tl)
                except Exception:
                    continue
                phase_states = [fallback_state]
                phase_durations = [float(self.fixed_green_time)]

            current_phase = int(traci.trafficlight.getPhase(tl))
            if current_phase >= len(phase_states):
                current_phase = 0

            try:
                spent = int(traci.trafficlight.getSpentDuration(tl))
            except Exception:
                spent = 0

            controlled_lanes = list(dict.fromkeys(traci.trafficlight.getControlledLanes(tl)))
            self.intersections[tl] = {
                "current_phase": current_phase,
                "time_in_phase": spent,
                "lanes": controlled_lanes,
            }
            self.default_phases[tl] = phase_states
            self.phase_durations[tl] = phase_durations
            self.tl_positions[tl] = self._get_traffic_light_position(tl, controlled_lanes)
            self.tl_incoming_links[tl] = self._build_incoming_link_index(tl)
            for edge_id in self.tl_incoming_links[tl].keys():
                self.edge_to_tl[edge_id].add(tl)

        print(f"  ✓ Initialized {len(self.intersections)} traffic lights from active network")

    def _get_traffic_light_position(self, tl_id, controlled_lanes):
        """Resolve a stable position for a traffic light."""
        try:
            return traci.junction.getPosition(tl_id)
        except Exception:
            pass

        points = []
        for lane in controlled_lanes[:10]:
            try:
                lane_shape = traci.lane.getShape(lane)
                if lane_shape:
                    points.append(lane_shape[-1])
            except Exception:
                continue

        if not points:
            return (0.0, 0.0)

        x = sum(p[0] for p in points) / len(points)
        y = sum(p[1] for p in points) / len(points)
        return (x, y)

    def _build_incoming_link_index(self, tl_id):
        """Map incoming edges to controlled-link indices for a traffic light."""
        incoming = defaultdict(list)
        try:
            controlled_links = traci.trafficlight.getControlledLinks(tl_id)
            for link_idx, links in enumerate(controlled_links):
                if not links:
                    continue
                incoming_lane = links[0][0]
                if not incoming_lane:
                    continue
                edge_id = incoming_lane.rsplit('_', 1)[0]
                incoming[edge_id].append(link_idx)
        except Exception:
            pass
        return dict(incoming)

    def _determine_emergency_phase(self, tl_id, edge_id):
        """Find a green phase at tl_id that serves edge_id incoming links."""
        if edge_id in self._edge_phase_cache[tl_id]:
            return self._edge_phase_cache[tl_id][edge_id]

        phase_states = self.default_phases.get(tl_id, [])
        incoming_links = self.tl_incoming_links.get(tl_id, {}).get(edge_id, [])
        if not phase_states or not incoming_links:
            self._edge_phase_cache[tl_id][edge_id] = None
            return None

        best_phase = None
        best_score = 0
        for phase_idx, phase_state in enumerate(phase_states):
            state_lower = phase_state.lower()
            if 'y' in state_lower:
                continue

            score = sum(
                1 for link_idx in incoming_links
                if link_idx < len(phase_state) and phase_state[link_idx] in ('G', 'g')
            )
            if score > best_score:
                best_score = score
                best_phase = phase_idx

        self._edge_phase_cache[tl_id][edge_id] = best_phase if best_score > 0 else None
        return self._edge_phase_cache[tl_id][edge_id]

    @staticmethod
    def _position_too_close(position, existing_positions, min_distance=150.0):
        for ex, ey in existing_positions:
            dx = position[0] - ex
            dy = position[1] - ey
            if (dx * dx + dy * dy) ** 0.5 < min_distance:
                return True
        return False

    def _get_lane_density(self, tl_id, phase_index):
        """Get vehicle density on lanes with green light in current phase"""
        try:
            if tl_id not in self.intersections:
                return 0

            phase_states = self.default_phases.get(tl_id, [])
            if not phase_states:
                return 0

            phase_index = phase_index % len(phase_states)
            phase_state = phase_states[phase_index]
            controlled_lanes = self.intersections[tl_id]["lanes"]

            total_vehicles = 0
            green_lanes = 0

            # Count vehicles on lanes that have green in current phase.
            for i, signal in enumerate(phase_state):
                if signal in ('G', 'g') and i < len(controlled_lanes):
                    lane = controlled_lanes[i]
                    vehicles = traci.lane.getLastStepVehicleNumber(lane)
                    halting = traci.lane.getLastStepHaltingNumber(lane)
                    total_vehicles += vehicles + (halting * 0.5)
                    green_lanes += 1

            return total_vehicles / max(green_lanes, 1)

        except Exception:
            return 5

    def _initialize_wimax(self):
        self.wimax_base_stations.clear()
        for tl_id, (x, y) in self.tl_positions.items():
            rsu_id = f"RSU_{tl_id}"

            # Use secure WiMAX when security is enabled and key managers are available.
            if self.security_enabled and rsu_id in self.rsu_managers:
                self.wimax_base_stations[tl_id] = SecureWiMAXBaseStation(
                    bs_id=rsu_id,
                    x=x,
                    y=y,
                    config=self.wimax_config,
                    key_manager=self.rsu_managers[rsu_id]
                )
                print(f"  🔐 Secure RSU initialized: {rsu_id} at ({x:.1f}, {y:.1f})")
            else:
                if self.security_enabled and rsu_id not in self.rsu_managers:
                    print(f"  ⚠️  No key manager for {rsu_id}, using insecure WiMAX")
                self.wimax_base_stations[tl_id] = WiMAXBaseStation(rsu_id, x, y, self.wimax_config)

    def _initialize_edge_rsus(self):
        """Initialize edge RSUs from the active SUMO network (no hardcoded map assumptions)."""
        if not self.edge_enabled:
            return

        print("\n🔷 Initializing Edge Computing Infrastructure...")
        self.edge_rsus.clear()

        tier1_positions = []
        for tl_id, pos in self.tl_positions.items():
            rsu_id = f"EDGE_RSU_{tl_id}"
            self.edge_rsus[rsu_id] = EdgeRSU(
                rsu_id=rsu_id,
                position=pos,
                tier=1,
                compute_capacity='high'
            )
            tier1_positions.append(pos)

        edge_candidates = []
        tl_ids = set(self.tl_positions.keys())
        for edge_id in traci.edge.getIDList():
            if edge_id.startswith(':'):
                continue

            lane_id = f"{edge_id}_0"
            try:
                shape = traci.lane.getShape(lane_id)
                if len(shape) < 2:
                    continue
                start = shape[0]
                end = shape[-1]
                length = float(traci.lane.getLength(lane_id))
            except Exception:
                continue

            try:
                from_j = traci.edge.getFromJunction(edge_id)
                to_j = traci.edge.getToJunction(edge_id)
            except Exception:
                from_j = None
                to_j = None

            bonus = 1000.0 if (from_j in tl_ids or to_j in tl_ids) else 0.0
            edge_candidates.append((length + bonus, edge_id, start, end))

        edge_candidates.sort(reverse=True)
        max_tier2 = max(20, min(40, len(edge_candidates) // 30 + 20))

        placed_positions = list(tier1_positions)
        tier2_count = 0
        for _, edge_id, start, end in edge_candidates:
            if tier2_count >= max_tier2:
                break

            midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
            if self._position_too_close(midpoint, placed_positions, min_distance=180.0):
                continue

            rsu_id = f"EDGE_RSU_{edge_id}"
            self.edge_rsus[rsu_id] = EdgeRSU(
                rsu_id=rsu_id,
                position=midpoint,
                tier=2,
                compute_capacity='medium'
            )
            placed_positions.append(midpoint)
            tier2_count += 1

        print(f"\n✅ Edge infrastructure ready:")
        print(f"   - Total RSUs: {len(self.edge_rsus)}")
        print(f"   - Tier 1 (Intersection): {sum(1 for r in self.edge_rsus.values() if r.tier == 1)}")
        print(f"   - Tier 2 (Road): {sum(1 for r in self.edge_rsus.values() if r.tier == 2)}")
        print(f"   - Tier 3 (Coverage): {sum(1 for r in self.edge_rsus.values() if r.tier == 3)}")

    def _register_new_vehicles(self):
        """Dynamically register new vehicles that appear in simulation"""
        if not self.security_enabled:
            return
        
        # Get all current vehicles
        all_vehicle_ids = traci.vehicle.getIDList()
        
        for vehicle_id in all_vehicle_ids:
            # Skip if already registered
            if vehicle_id in self.vehicle_managers:
                continue
            
            # Create new key manager for this vehicle
            from v2v_communication.key_management import KeyManager
            
            # Determine vehicle type (check if emergency)
            try:
                vehicle_type = traci.vehicle.getTypeID(vehicle_id)
                entity_type = "emergency_vehicle" if "ambulance" in vehicle_type.lower() or "emergency" in vehicle_type.lower() else "vehicle"
            except:
                entity_type = "vehicle"
            
            # Create key manager
            vehicle_mgr = KeyManager(vehicle_id, entity_type=entity_type, ca=self.ca)
            self.vehicle_managers[vehicle_id] = vehicle_mgr
            
            # Exchange keys with all RSUs
            for rsu_id, rsu_mgr in self.rsu_managers.items():
                # Vehicle registers RSU's certificate
                rsu_cert = rsu_mgr.get_certificate()
                if rsu_cert:
                    vehicle_mgr.register_peer_from_certificate(rsu_cert)
                
                # RSU registers vehicle's certificate
                vehicle_cert = vehicle_mgr.get_certificate()
                if vehicle_cert:
                    rsu_mgr.register_peer_from_certificate(vehicle_cert)
            
            # Create secure mobile station
            position = traci.vehicle.getPosition(vehicle_id)
            self.wimax_mobile_stations[vehicle_id] = SecureWiMAXMobileStation(
                ms_id=vehicle_id,
                x=position[0],
                y=position[1],
                key_manager=vehicle_mgr
            )
            
            if entity_type == "emergency_vehicle":
                print(f"  🚑 Emergency vehicle registered: {vehicle_id} (encrypted)")
            # else:
            #     print(f"  🚗 Vehicle registered: {vehicle_id} (encrypted)")

    def _handle_emergency_vehicles(self):
        """Detect emergency vehicles and send encrypted priority requests to nearby RSUs"""
        if not self.security_enabled:
            return
        
        # If emergency priority is disabled, don't send priority messages (but still send normal V2I)
        # Emergency vehicles will be treated as normal vehicles
        
        # Get all vehicles
        all_vehicles = traci.vehicle.getIDList()
        current_time = traci.simulation.getTime()
        
        for vehicle_id in all_vehicles:
            # Check if this is an emergency vehicle
            try:
                vehicle_type = traci.vehicle.getTypeID(vehicle_id)
                is_emergency = "ambulance" in vehicle_type.lower() or "emergency" in vehicle_type.lower()
                
                if not is_emergency:
                    continue
                
                # If emergency priority is disabled, treat emergency vehicles as normal
                # Skip sending priority messages, but still count them for metrics
                if not self.emergency_priority_enabled:
                    continue
                
                # Get vehicle position
                x, y = traci.vehicle.getPosition(vehicle_id)
                speed = traci.vehicle.getSpeed(vehicle_id)
                
                # Get vehicle manager
                if vehicle_id not in self.vehicle_managers:
                    continue  # Vehicle not yet registered
                
                vehicle_mgr = self.vehicle_managers[vehicle_id]
                
                # Find nearest RSU and send encrypted emergency message
                for tl_id, bs in self.wimax_base_stations.items():
                    position = self.tl_positions.get(tl_id)
                    if position is None:
                        continue

                    rsu_x, rsu_y = position
                    distance = ((x - rsu_x)**2 + (y - rsu_y)**2)**0.5
                    
                    # If within emergency detection range, send encrypted request
                    if distance < self.emergency_detection_range:
                        rsu_id = f"RSU_{tl_id}"
                        
                        # Create emergency message
                        emergency_data = {
                            "type": "emergency_request",
                            "priority": "HIGH",
                            "vehicle_id": vehicle_id,
                            "location": {"x": x, "y": y},
                            "speed": speed,
                            "timestamp": current_time,
                            "request": "clear_path"
                        }
                        
                        # Encrypt and send via secure WiMAX
                        if isinstance(bs, SecureWiMAXBaseStation):
                            encrypted_msg = vehicle_mgr.handler.encrypt_message(
                                rsu_id,
                                emergency_data,
                                message_type="emergency"
                            )
                            
                            if encrypted_msg:
                                # Log encrypted packet
                                self._log_packet(
                                    bs_id=tl_id,
                                    vehicle_id=vehicle_id,
                                    packet_type="emergency_encrypted",
                                    size_bytes=len(encrypted_msg.encrypted_data) + len(encrypted_msg.signature)
                                )
                                
                                # Simulate RSU receiving and decrypting (for demo)
                                rsu_mgr = self.rsu_managers.get(rsu_id)
                                if rsu_mgr:
                                    decrypted = rsu_mgr.handler.decrypt_message(encrypted_msg)
                                    if decrypted:
                                        # RSU successfully received emergency request
                                        # In real system, this would trigger traffic light priority
                                        pass  # Traffic light adjustment happens in rule-based logic
                
            except Exception as e:
                # Silently handle errors (vehicle may have left simulation)
                pass
    
    def _check_emergency_priority(self):
        """
        Check if emergency vehicles are approaching intersections and need priority.

        Strategy:
        1) Reactive preemption for nearby emergencies.
        2) Proactive route-ahead preemption for a limited junction horizon.
        3) Keep first-assigned vehicle priority until it clears pass-through range.

        Returns dict {junction_id: (required_phase, vehicle_id)}
        """
        # If emergency priority is disabled, return empty dict
        if not self.emergency_priority_enabled:
            return {}
        emergency_priorities = {}
        
        try:
            all_vehicles = traci.vehicle.getIDList()

            # Track candidate emergency preemptions per junction.
            current_emergencies_near_junction = defaultdict(list)

            all_junction_positions = [
                (junc_id, pos)
                for junc_id, pos in self.tl_positions.items()
                if junc_id in self.intersections
            ]

            for vehicle_id in all_vehicles:
                try:
                    vehicle_type = traci.vehicle.getTypeID(vehicle_id)
                    is_emergency = "ambulance" in vehicle_type.lower() or "emergency" in vehicle_type.lower()

                    if not is_emergency:
                        continue

                    x, y = traci.vehicle.getPosition(vehicle_id)
                    route = traci.vehicle.getRoute(vehicle_id)
                    route_index = traci.vehicle.getRouteIndex(vehicle_id)
                    if route_index < 0 or route_index >= len(route):
                        continue

                    current_edge = route[route_index]

                    # Housekeeping: mark served when emergency passes, and release stale serves
                    # once emergency has moved far enough from a junction.
                    release_range = max(self.emergency_detection_range, self.green_corridor_max_distance) + 50.0
                    for junc_id, position in all_junction_positions:
                        junc_x, junc_y = position
                        distance = ((x - junc_x) ** 2 + (y - junc_y) ** 2) ** 0.5

                        if distance < self.emergency_pass_through_range:
                            if vehicle_id not in self.served_emergencies[junc_id]:
                                self.served_emergencies[junc_id].add(vehicle_id)
                                if (
                                    junc_id in self.junction_priority_vehicle
                                    and self.junction_priority_vehicle[junc_id] == vehicle_id
                                ):
                                    print(
                                        f"✅ EMERGENCY CLEARED: {vehicle_id} passed "
                                        f"{self.emergency_pass_through_range:.0f}m at {junc_id}, "
                                        "returning to adaptive control"
                                    )
                                    del self.junction_priority_vehicle[junc_id]
                            continue

                        if distance > release_range:
                            self.served_emergencies[junc_id].discard(vehicle_id)

                    # 1) Reactive preemption near current position.
                    for junc_id, position in all_junction_positions:
                        if vehicle_id in self.served_emergencies[junc_id]:
                            continue

                        junc_x, junc_y = position
                        distance = ((x - junc_x) ** 2 + (y - junc_y) ** 2) ** 0.5
                        if distance > self.emergency_detection_range:
                            continue

                        required_phase = self._determine_emergency_phase(junc_id, current_edge)
                        if required_phase is None:
                            continue

                        current_emergencies_near_junction[junc_id].append({
                            'vehicle_id': vehicle_id,
                            'distance': distance,
                            'phase': required_phase,
                            'corridor_rank': 0,
                            'source': 'nearby',
                        })

                    # 2) Proactive route-ahead corridor preemption.
                    if self.green_corridor_enabled and self.green_corridor_edge_lookahead > 0:
                        end_idx = min(len(route), route_index + self.green_corridor_edge_lookahead)
                        upcoming_edges = route[route_index:end_idx]

                        for edge_rank, edge_id in enumerate(upcoming_edges, start=1):
                            target_tls = self.edge_to_tl.get(edge_id, set())
                            if not target_tls:
                                continue

                            for junc_id in target_tls:
                                if junc_id not in self.intersections:
                                    continue
                                if vehicle_id in self.served_emergencies[junc_id]:
                                    continue

                                pos = self.tl_positions.get(junc_id)
                                if not pos:
                                    continue

                                junc_x, junc_y = pos
                                distance = ((x - junc_x) ** 2 + (y - junc_y) ** 2) ** 0.5
                                if distance > self.green_corridor_max_distance:
                                    continue

                                required_phase = self._determine_emergency_phase(junc_id, edge_id)
                                if required_phase is None:
                                    continue

                                current_emergencies_near_junction[junc_id].append({
                                    'vehicle_id': vehicle_id,
                                    'distance': distance,
                                    'phase': required_phase,
                                    'corridor_rank': edge_rank,
                                    'source': 'corridor',
                                })

                except traci.exceptions.TraCIException:
                    continue
            
            # Process priorities per junction: keep current assignment if still valid,
            # otherwise choose best candidate (lower corridor_rank, then lower distance).
            for junc_id, emergencies in current_emergencies_near_junction.items():
                if not emergencies:
                    continue

                # Keep one best candidate per vehicle to avoid duplicate edge-derived entries.
                by_vehicle = {}
                for entry in emergencies:
                    vid = entry['vehicle_id']
                    prev = by_vehicle.get(vid)
                    if prev is None:
                        by_vehicle[vid] = entry
                        continue

                    prev_key = (prev.get('corridor_rank', 999), prev['distance'])
                    new_key = (entry.get('corridor_rank', 999), entry['distance'])
                    if new_key < prev_key:
                        by_vehicle[vid] = entry

                emergencies = list(by_vehicle.values())
                
                # Check if there's already a vehicle being served at this junction
                if junc_id in self.junction_priority_vehicle:
                    current_priority = self.junction_priority_vehicle[junc_id]
                    # Check if current priority vehicle is still in the list
                    current_priority_found = any(e['vehicle_id'] == current_priority for e in emergencies)
                    
                    if current_priority_found:
                        # Continue serving the current priority vehicle
                        for e in emergencies:
                            if e['vehicle_id'] == current_priority:
                                emergency_priorities[junc_id] = (e['phase'], e['vehicle_id'])
                                break
                    else:
                        # Current priority vehicle is gone, assign new priority.
                        emergencies.sort(key=lambda e: (e.get('corridor_rank', 999), e['distance']))
                        new_priority = emergencies[0]
                        self.junction_priority_vehicle[junc_id] = new_priority['vehicle_id']
                        emergency_priorities[junc_id] = (new_priority['phase'], new_priority['vehicle_id'])
                        
                        if len(emergencies) > 1:
                            waiting_vehicles = [e['vehicle_id'] for e in emergencies[1:]]
                            print(f"🚦 {junc_id}: {new_priority['vehicle_id']} gets priority (first detected), "
                                  f"{len(emergencies)-1} waiting: {', '.join(waiting_vehicles)}")
                else:
                    # No current priority, assign best candidate.
                    emergencies.sort(key=lambda e: (e.get('corridor_rank', 999), e['distance']))
                    first_emergency = emergencies[0]
                    self.junction_priority_vehicle[junc_id] = first_emergency['vehicle_id']
                    emergency_priorities[junc_id] = (first_emergency['phase'], first_emergency['vehicle_id'])
                    src = first_emergency.get('source', 'nearby')
                    print(
                        f"🚨 EMERGENCY PRIORITY: {junc_id} → {first_emergency['vehicle_id']} "
                        f"at {first_emergency['distance']:.1f}m ({src})"
                    )
                    
                    if len(emergencies) > 1:
                        waiting_vehicles = [e['vehicle_id'] for e in emergencies[1:]]
                        print(f"   ⏳ Waiting: {', '.join(waiting_vehicles)}")
        
        except Exception as e:
            pass
        
        return emergency_priorities

    # ------------------- SIMULATION -------------------
    def run_simulation_step(self):
        try:
            # Check if simulation is still running
            if not hasattr(self, 'sumo_connected') or not self.sumo_connected:
                return False
                
            traci.simulationStep()
            self.simulation_step += 1
            
            # Store current simulation time for metrics
            self.last_simulation_time = traci.simulation.getTime()
            
            # Check for emergency vehicles and handle priority
            emergency_at_junction = self._check_emergency_priority()

            # Traffic light control (skip if RL mode)
            if self.mode != "rl":
                for tl_id, data in self.intersections.items():
                    phase_states = self.default_phases.get(tl_id, [])
                    if not phase_states:
                        continue

                    # Keep controller state aligned with SUMO if another module changes phases.
                    try:
                        live_phase = int(traci.trafficlight.getPhase(tl_id))
                        if live_phase != data["current_phase"]:
                            data["current_phase"] = live_phase % len(phase_states)
                            data["time_in_phase"] = 0
                    except Exception:
                        pass

                    # EMERGENCY OVERRIDE: If emergency vehicle detected at this junction
                    if tl_id in emergency_at_junction:
                        emergency_phase, vehicle_id = emergency_at_junction[tl_id]
                        current_phase = data["current_phase"]
                        
                        # Force switch to emergency vehicle's direction if not already green
                        if current_phase != emergency_phase:
                            print(f"🚨 EMERGENCY PRIORITY: {tl_id} → {vehicle_id} switching to phase {emergency_phase}")
                            data["current_phase"] = emergency_phase
                            data["time_in_phase"] = 0
                            traci.trafficlight.setPhase(tl_id, emergency_phase)
                            try:
                                traci.trafficlight.setPhaseDuration(tl_id, float(self.emergency_green_hold_time))
                            except Exception:
                                pass
                        # If already in correct phase, extend green time
                        else:
                            data["time_in_phase"] = max(0, data["time_in_phase"] - 5)  # Reset timer
                            try:
                                traci.trafficlight.setPhaseDuration(tl_id, float(self.emergency_green_hold_time))
                            except Exception:
                                pass
                        continue  # Skip normal adaptive control for this junction

                    # External controllers can own selected traffic lights while still
                    # preserving emergency override behavior above.
                    if tl_id in self.externally_controlled_tls:
                        data["time_in_phase"] += 1
                        continue
                    
                    data["time_in_phase"] += 1
                    current_phase = data["current_phase"] % len(phase_states)
                    phase_state = phase_states[current_phase]
                    phase_state_lower = phase_state.lower()
                    
                    # Check if in green phase (contains 'G')
                    if 'g' in phase_state_lower:
                        if self.mode == 'fixed':
                            # FIXED-TIME: constant green duration, no adaptation
                            target_duration = self.fixed_green_time
                        else:
                            # DENSITY-ADAPTIVE: scale green time with vehicle count
                            density = self._get_lane_density(tl_id, current_phase)
                            
                            if density >= self.high_density_threshold:
                                target_duration = self.max_green_time
                            elif density <= self.low_density_threshold:
                                target_duration = self.min_green_time
                            else:
                                scale = (density - self.low_density_threshold) / \
                                        (self.high_density_threshold - self.low_density_threshold)
                                target_duration = int(self.min_green_time + 
                                                    scale * (self.max_green_time - self.min_green_time))
                        
                        # Advance phase when target duration reached.
                        if data["time_in_phase"] >= target_duration:
                            data["current_phase"] = (current_phase + 1) % len(phase_states)
                            data["time_in_phase"] = 0
                            traci.trafficlight.setPhase(tl_id, data["current_phase"])
                    
                    else:
                        # Preserve transition phases from the loaded program (yellow/all-red).
                        phase_durations = self.phase_durations.get(tl_id, [])
                        fallback_duration = max(1, self.yellow_time)
                        if current_phase < len(phase_durations):
                            transition_duration = max(1, int(round(phase_durations[current_phase])))
                        else:
                            transition_duration = fallback_duration

                        if 'y' in phase_state_lower:
                            transition_duration = min(transition_duration, fallback_duration)

                        if data["time_in_phase"] >= transition_duration:
                            data["current_phase"] = (current_phase + 1) % len(phase_states)
                            data["time_in_phase"] = 0
                            traci.trafficlight.setPhase(tl_id, data["current_phase"])

            # Update edge RSUs with vehicle data
            if self.edge_enabled:
                self._update_edge_rsus()

            # Check for emergency vehicles and send encrypted messages
            if self.security_enabled:
                self._handle_emergency_vehicles()

            # Update WiMAX metrics
            self._update_wimax()
            return True
            
        except traci.exceptions.FatalTraCIError as e:
            # Save metrics when simulation ends (only if not already saved)
            if hasattr(self, 'sumo_connected') and self.sumo_connected:
                print("\n⚠️  SUMO simulation ended, saving metrics...")
                self._save_v2i_metrics()
                self.sumo_connected = False
            return False
            
        except Exception as e:
            print(f"Error in simulation step: {e}")
            self._save_v2i_metrics()  # Save metrics on error
            return False

    def _update_edge_rsus(self):
        """Update edge RSUs with current vehicle data and process requests"""
        try:
            all_vehicles = traci.vehicle.getIDList()
            
            for vehicle_id in all_vehicles:
                try:
                    # Get vehicle state
                    position = traci.vehicle.getPosition(vehicle_id)
                    speed = traci.vehicle.getSpeed(vehicle_id)
                    angle = traci.vehicle.getAngle(vehicle_id)
                    edge_id = traci.vehicle.getRoadID(vehicle_id)
                    vehicle_type_id = traci.vehicle.getTypeID(vehicle_id)
                    
                    # Determine if emergency
                    is_emergency = "ambulance" in vehicle_type_id.lower() or "emergency" in vehicle_type_id.lower()
                    v_type = "emergency" if is_emergency else "normal"
                    
                    # Update all RSUs that can see this vehicle
                    for rsu_id, edge_rsu in self.edge_rsus.items():
                        if edge_rsu.is_vehicle_in_range(position):
                            edge_rsu.update_vehicle(
                                vehicle_id=vehicle_id,
                                position=position,
                                speed=speed,
                                heading=angle,
                                edge_id=edge_id,
                                vehicle_type=v_type
                            )
                            # Note: Metrics are now tracked inside EdgeRSU.update_vehicle()
                            # which only counts unique vehicles, not every update
                
                except Exception as e:
                    # Vehicle may have left simulation
                    pass
            
            # Process RSU requests and handle responses
            for rsu_id, edge_rsu in self.edge_rsus.items():
                responses = edge_rsu.process_requests()
                
                for response in responses:
                    response_type = response.get('type')
                    
                    # Handle collision warnings
                    if response_type == 'collision_warning':
                        # In real system, would broadcast warning to vehicles
                        pass
                    
                    # Handle traffic anomalies
                    elif response_type == 'traffic_anomaly':
                        # Could trigger traffic management actions
                        pass
                    
                    # Handle emergency yield warnings
                    elif response_type == 'emergency_yield_warning':
                        # In real system, would notify vehicles to yield
                        pass
                    
                    # Handle cloud uploads
                    elif response_type == 'cloud_upload':
                        # In real system, would upload to cloud server
                        if self.edge_metrics_tracker:
                            package_size = len(str(response.get('package', '')))
                            self.edge_metrics_tracker.update_system_metrics(
                                'total_data_uploaded', package_size
                            )
            
            # Periodic cleanup (every 10 steps)
            if self.simulation_step % 10 == 0:
                for edge_rsu in self.edge_rsus.values():
                    edge_rsu.cleanup()
        
        except Exception as e:
            print(f"Error updating edge RSUs: {e}")

    def _update_wimax(self):
        current_time = traci.simulation.getTime()
        
        # Register new vehicles dynamically if security is enabled
        if self.security_enabled:
            self._register_new_vehicles()
        
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
    
    def run_simulation_with_rl(self, rl_controller, steps=3600):
        """
        Run simulation with HYBRID control:
        - Normal: Density-based adaptive traffic control
        - Emergency: RL-based control with greenwave
        
        Parameters
        ----------
        rl_controller : RLTrafficController
            The RL controller instance
        steps : int
            Number of simulation steps to run
        """
        self.running = True
        step_count = 0
        
        # Control mode tracking
        control_mode = "DENSITY"  # Start with density-based
        emergency_active = False
        last_emergency_check = 0
        
        print(f"\n🚦 Running HYBRID traffic control for {steps} steps...")
        print("   • Normal: DENSITY-based adaptive control")
        print("   • Emergency: RL-based control with greenwave")
        print("=" * 70)
        
        try:
            while step_count < steps and traci.simulation.getMinExpectedNumber() > 0:
                current_time = traci.simulation.getTime()
                
                # Check for emergency vehicles every 5 steps
                if step_count % 5 == 0 or step_count - last_emergency_check >= 5:
                    last_emergency_check = step_count
                    
                    # Check if any emergency vehicles are active
                    if hasattr(rl_controller.env, 'emergency_coordinator'):
                        active_emergencies = rl_controller.env.emergency_coordinator.get_active_emergency_vehicles()
                        
                        if len(active_emergencies) > 0 and not emergency_active:
                            # Switch to RL mode
                            emergency_active = True
                            control_mode = "RL-EMERGENCY"
                            self.mode = "rl"
                            print(f"\n🚨 EMERGENCY DETECTED at step {step_count}!")
                            print(f"   Switching to RL control with greenwave...")
                            for emerg in active_emergencies:
                                print(f"   • {emerg.vehicle_id} detected by {emerg.detected_by_rsu}")
                        
                        elif len(active_emergencies) == 0 and emergency_active:
                            # Switch back to density-based mode
                            emergency_active = False
                            control_mode = "DENSITY"
                            self.mode = "rule"
                            print(f"\n✅ EMERGENCY CLEARED at step {step_count}")
                            print(f"   Switching back to density-based control...")
                
                # Execute appropriate control strategy
                if emergency_active:
                    # RL control during emergency
                    rl_metrics = rl_controller.step()
                    
                    if 'error' in rl_metrics:
                        print(f"\n❌ RL Error at step {step_count}: {rl_metrics['error']}")
                        # Fall back to density-based
                        emergency_active = False
                        control_mode = "DENSITY"
                        self.mode = "rule"
                else:
                    # Run density-based control (this happens in run_simulation_step)
                    rl_metrics = {
                        'reward': 0,
                        'episode_reward': 0,
                        'mean_speed': 0,
                        'active_emergencies': 0
                    }
                
                # Run regular traffic controller step (handles sensors, WiMAX, density control when not in RL mode)
                self.run_simulation_step()
                
                # Print progress
                if step_count % 50 == 0:
                    print(f"\n╔══════════════════════════════════════════════════════════╗")
                    print(f"║ Step {step_count:4d}/{steps} │ Mode: {control_mode:15s} │ Time: {current_time:.1f}s ║")
                    print(f"╠══════════════════════════════════════════════════════════╣")
                    
                    if emergency_active:
                        print(f"║ 🚨 EMERGENCY MODE                                        ║")
                        print(f"║   Reward: {rl_metrics.get('reward', 0):6.2f}                                     ║")
                        print(f"║   Active Emergencies: {rl_metrics.get('active_emergencies', 0):2d}                          ║")
                        print(f"║   Greenwaves Created: {rl_metrics.get('successful_greenwaves', 0):2d}                          ║")
                        print(f"║   Mean Speed: {rl_metrics.get('mean_speed', 0):5.2f} m/s                            ║")
                    else:
                        print(f"║ 🚦 DENSITY-BASED ADAPTIVE CONTROL                        ║")
                        # Get traffic stats
                        try:
                            all_vehicles = traci.vehicle.getIDList()
                            if all_vehicles:
                                speeds = [traci.vehicle.getSpeed(v) for v in all_vehicles[:20]]
                                avg_speed = sum(speeds) / len(speeds) if speeds else 0
                                print(f"║   Active Vehicles: {len(all_vehicles):3d}                                 ║")
                                print(f"║   Mean Speed: {avg_speed:5.2f} m/s                            ║")
                                
                                # Show a small sample of traffic light states
                                for tl_id in sorted(self.intersections.keys())[:3]:
                                    if tl_id in self.intersections:
                                        phase = self.intersections[tl_id]['current_phase']
                                        time_in_phase = self.intersections[tl_id]['time_in_phase']
                                        density = self._get_lane_density(tl_id, phase)
                                        print(f"║   {tl_id}: Phase {phase} ({time_in_phase:2d}s) Density: {density:4.1f}           ║")
                        except:
                            pass
                    
                    print(f"╚══════════════════════════════════════════════════════════╝")
                
                step_count += 1
                time.sleep(0.01)  # Small delay for visualization
                
        except KeyboardInterrupt:
            print("\n\n⚠️  Simulation stopped by user (Ctrl+C)")
        except Exception as e:
            print(f"\n\n❌ Simulation error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print(f"\n\n📊 Simulation Summary:")
            print("=" * 70)
            print(f"Total steps: {step_count}")
            print(f"Final control mode: {control_mode}")
            
            # Get final RL metrics
            final_metrics = rl_controller.get_metrics()
            print(f"\nRL Performance (Emergency Mode):")
            print(f"  Total episodes: {final_metrics.get('total_episodes', 0)}")
            print(f"  Avg episode reward: {final_metrics.get('avg_episode_reward', 0):.2f}")
            
            # Emergency vehicle statistics
            if hasattr(rl_controller.env, 'emergency_coordinator'):
                emerg_stats = rl_controller.env.emergency_coordinator.get_statistics()
                print(f"\nEmergency Vehicle Statistics:")
                print(f"  Total detections: {emerg_stats.get('total_detections', 0)}")
                print(f"  Successful greenwaves: {rl_controller.env.successful_greenwaves}")
                
                if emerg_stats.get('total_detections', 0) > 0:
                    print(f"  ✅ Hybrid system worked: Density control + Emergency RL")
                else:
                    print(f"  ℹ️  No emergencies detected: Pure density-based control")
            
            # Save metrics
            self._save_v2i_metrics()
            self.stop_simulation()
            
            print("\n✅ HYBRID Simulation completed")
            print("=" * 70)

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
        # Prioritize NS3 bridge statistics if available (actual simulation data)
        if self.ns3_bridge is not None:
            try:
                ns3_metrics = self.ns3_bridge.get_metrics()
                
                # Extract V2I WiMAX statistics
                v2i_data = ns3_metrics.get('v2i_wimax', {})
                combined_data = ns3_metrics.get('combined', {})
                emergency_data = ns3_metrics.get('emergency', {})
                
                # Get RSU statistics from NS3
                rsu_stats = {}
                for bs_id, bs in self.wimax_base_stations.items():
                    metrics = bs.get_metrics()
                    rsu_stats[f'rsu_{bs_id}'] = {
                        'utilization': metrics.get('utilization', 0),
                        'tx_bytes': metrics.get('tx_bytes', 0),
                        'rx_bytes': metrics.get('rx_bytes', 0),
                        'connected_vehicles': metrics.get('connected_vehicles', 0)
                    }
                
                # Build summary using NS3 bridge actual data
                return {
                    'total_packets': v2i_data.get('packets_sent', 0),
                    'successful_packets': v2i_data.get('packets_received', 0),
                    'PDR': v2i_data.get('pdr', 0.0),
                    'mean_latency_s': combined_data.get('average_delay_ms', 0.0) / 1000.0,  # Convert ms to s
                    'jitter_s': 0.0,  # NS3 bridge doesn't track jitter yet
                    'packet_loss_rate': 1.0 - v2i_data.get('pdr', 0.0),
                    'throughput_bps': combined_data.get('throughput_mbps', 0.0) * 1_000_000,  # Convert Mbps to bps
                    'loss_reasons': {'rx_error': 0},  # Placeholder
                    'handoff_success_rate': None,  # Not tracked - broadcast model doesn't maintain connections
                    'rsu_stats_sample': rsu_stats,
                    'emergency_vehicles': ns3_metrics.get('vehicles', {}).get('emergency', 0),
                    'emergency_events': emergency_data.get('total_events', 0),
                    'emergency_success_rate': emergency_data.get('success_rate', 0.0),
                    'data_source': 'ns3_bridge'  # Indicate this is authoritative NS3 data
                }
            except Exception as e:
                print(f"  ⚠️  Failed to get NS3 bridge metrics: {e}")
                print("     Falling back to internal tracking (may be incomplete)")
        
        # Fallback to internal tracking (legacy behavior - may be incomplete)
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
        # Use stored simulation time instead of calling TraCI (which may be closed)
        sim_time = self.last_simulation_time
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
            'handoff_success_rate': None,  # Not tracked - broadcast model
            'rsu_stats_sample': rsu_stats,
            'data_source': 'internal_tracking'  # Indicate this is legacy incomplete data
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
        
        # Save edge computing metrics
        if self.edge_enabled and self.edge_metrics_tracker:
            self._save_edge_metrics()
            
        try: 
            traci.close()
            self.sumo_connected = False
        except: 
            pass
            
        print("SUMO simulation closed.")

    def _save_edge_metrics(self):
        """Save edge computing performance metrics"""
        if not self.edge_enabled or not self.edge_metrics_tracker:
            return
        
        try:
            print("\n📊 Saving edge computing metrics...")
            
            # Collect statistics from all RSUs
            for rsu_id, edge_rsu in self.edge_rsus.items():
                stats = edge_rsu.get_service_statistics()
                
                # Record unique vehicles served (not every update)
                self.edge_metrics_tracker.record_rsu_activity(
                    rsu_id, 'vehicle_served', stats['unique_vehicles_served']
                )
                
                # Record computations
                self.edge_metrics_tracker.record_rsu_activity(
                    rsu_id, 'computation', stats['total_computations']
                )
                
                # Record cache statistics
                cache_stats = stats['cache']
                self.edge_metrics_tracker.record_rsu_activity(
                    rsu_id, 'cache_hit', cache_stats['hits']
                )
                self.edge_metrics_tracker.record_rsu_activity(
                    rsu_id, 'cache_miss', cache_stats['misses']
                )
                
                # Record service statistics (final counts from services)
                collision_stats = stats['collision_avoidance']
                self.edge_metrics_tracker.record_rsu_activity(
                    rsu_id, 'warning_issued', collision_stats['warnings_issued']
                )
                
                traffic_stats = stats['traffic_flow']
                self.edge_metrics_tracker.record_rsu_activity(
                    rsu_id, 'route_computed', traffic_stats.get('routes_computed', 0)
                )
                
                emergency_stats = stats['emergency']
                self.edge_metrics_tracker.record_rsu_activity(
                    rsu_id, 'emergency_handled', emergency_stats['emergencies_handled']
                )
            
            # Save to files
            metrics_file = self.edge_metrics_tracker.save_metrics("edge_metrics.csv")
            summary_file = self.edge_metrics_tracker.save_summary("edge_summary.json")
            
            print(f"  ✅ Saved {metrics_file}")
            print(f"  ✅ Saved {summary_file}")
            
            # Print summary to console
            self.edge_metrics_tracker.print_summary()
            
        except Exception as e:
            print(f"Error saving edge metrics: {e}")
