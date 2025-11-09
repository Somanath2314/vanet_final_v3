"""
Emergency Vehicle Coordinator for Greenwave System
Integrates with RSUs to detect ambulances and coordinate greenwave across junctions
"""

import traci
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from collections import defaultdict
import numpy as np
from rsu_config import get_junction_rsus, get_rsu_positions



@dataclass
class EmergencyVehicle:
    """Represents an emergency vehicle in the system"""
    vehicle_id: str
    current_edge: str
    current_lane: str
    position: float  # Position on current edge
    speed: float
    route: List[str]  # List of edges in route
    detected_by_rsu: Optional[str] = None
    greenwave_active: bool = False
    last_update_time: float = 0


@dataclass
class Junction:
    """Represents a junction/intersection"""
    junction_id: str
    tl_id: Optional[str]  # Traffic light ID
    position: Tuple[float, float]
    incoming_edges: List[str]
    outgoing_edges: List[str]


class EmergencyVehicleCoordinator:
    """
    Coordinates emergency vehicle detection and greenwave creation.
    
    Works with RSUs to:
    1. Detect ambulances entering coverage area
    2. Predict their route/path
    3. Coordinate traffic lights ahead to create greenwave
    4. Relay information between RSUs
    """
    
    def __init__(self, rsu_range: float = 300.0):
        """
        Initialize the emergency coordinator.
        
        Parameters
        ----------
        rsu_range : float
            Detection range of RSUs in meters
        """
        self.rsu_range = rsu_range
        
        # Track emergency vehicles
        self.emergency_vehicles: Dict[str, EmergencyVehicle] = {}
        self.active_greenwaves: Dict[str, List[str]] = {}  # vehicle_id -> list of junction IDs
        
        # RSU-Junction mapping
        self.rsu_positions: Dict[str, Tuple[float, float]] = {}  # RSU_id -> (x, y)
        self.junction_info: Dict[str, Junction] = {}
        
        # Historical data
        self.emergency_detections: List[Tuple[float, str, str]] = []  # (time, veh_id, rsu_id)
    
    def reset(self):
        """
        Reset coordinator state between episodes.
        Clears all emergency vehicle tracking and greenwave states.
        Does NOT reset network topology (RSU positions, junction info).
        """
        self.emergency_vehicles.clear()
        self.active_greenwaves.clear()
        self.emergency_detections.clear()
        
    def initialize_network_topology(self):
        """Initialize network topology from SUMO."""
        try:
            # Get all junctions
            junction_ids = traci.junction.getIDList()
            
            for junc_id in junction_ids:
                # Get junction position
                x, y = traci.junction.getPosition(junc_id)
                
                # Get incoming and outgoing edges
                # Use edge API instead of junction API for compatibility
                incoming = []
                outgoing = []
                
                # Get all edges and check which ones connect to this junction
                try:
                    all_edges = traci.edge.getIDList()
                    for edge_id in all_edges:
                        # Skip internal edges (they start with ':')
                        if edge_id.startswith(':'):
                            continue
                        
                        try:
                            # Get edge's to and from junctions
                            from_junc = traci.edge.getFromJunction(edge_id) if hasattr(traci.edge, 'getFromJunction') else None
                            to_junc = traci.edge.getToJunction(edge_id) if hasattr(traci.edge, 'getToJunction') else None
                            
                            if to_junc == junc_id:
                                incoming.append(edge_id)
                            if from_junc == junc_id:
                                outgoing.append(edge_id)
                        except:
                            continue
                except Exception as e:
                    # If edge API doesn't work, use a simple approach
                    pass
                
                # Try to find associated traffic light
                tl_id = None
                tl_ids = traci.trafficlight.getIDList()
                for tl in tl_ids:
                    try:
                        tl_junctions = traci.trafficlight.getControlledJunctions(tl) if hasattr(traci.trafficlight, 'getControlledJunctions') else []
                        if junc_id in tl_junctions or tl == junc_id:
                            tl_id = tl
                            break
                    except:
                        # If junction doesn't match, try matching by name
                        if tl == junc_id:
                            tl_id = tl
                            break
                
                self.junction_info[junc_id] = Junction(
                    junction_id=junc_id,
                    tl_id=tl_id,
                    position=(x, y),
                    incoming_edges=incoming,
                    outgoing_edges=outgoing
                )
            
            print(f"✓ Emergency coordinator initialized: {len(self.junction_info)} junctions")
            
            # Initialize RSU positions from unified configuration
            # Use centralized RSU config for consistency across all modules
            junction_rsus = get_junction_rsus()
            for junction_id, rsu_def in junction_rsus.items():
                self.rsu_positions[rsu_def.rsu_id] = rsu_def.position
            
            # Also load all RSU positions (not just junction ones) for detection
            all_rsu_positions = get_rsu_positions()
            for rsu_id, pos in all_rsu_positions.items():
                if rsu_id not in self.rsu_positions:
                    self.rsu_positions[rsu_id] = pos
            
            print(f"✓ RSU network mapped: {len(self.rsu_positions)} RSUs")
            
        except Exception as e:
            print(f"Error initializing network topology: {e}")
            import traceback
            traceback.print_exc()
    
    def detect_emergency_vehicles(self, current_time: float) -> List[EmergencyVehicle]:
        """
        Detect emergency vehicles in the simulation via RSUs.
        
        Returns
        -------
        list of EmergencyVehicle
            List of detected emergency vehicles
        """
        detected = []
        
        try:
            all_vehicles = traci.vehicle.getIDList()
            
            for veh_id in all_vehicles:
                # Check if vehicle is an emergency vehicle
                if not self._is_emergency_vehicle(veh_id):
                    continue
                
                # Get vehicle information
                try:
                    # Check if vehicle still exists before querying
                    if veh_id not in all_vehicles:
                        continue
                    
                    edge_id = traci.vehicle.getRoadID(veh_id)
                    lane_id = traci.vehicle.getLaneID(veh_id)
                    position = traci.vehicle.getLanePosition(veh_id)
                    speed = traci.vehicle.getSpeed(veh_id)
                    route = traci.vehicle.getRoute(veh_id)
                    veh_pos = traci.vehicle.getPosition(veh_id)
                    
                    # Check if vehicle is within range of any RSU
                    detecting_rsu = self._find_nearest_rsu(veh_pos)
                    
                    if detecting_rsu:
                        # Create or update emergency vehicle entry
                        if veh_id not in self.emergency_vehicles:
                            print(f"🚨 Emergency vehicle detected: {veh_id} by {detecting_rsu}")
                            self.emergency_detections.append((current_time, veh_id, detecting_rsu))
                        
                        emergency_veh = EmergencyVehicle(
                            vehicle_id=veh_id,
                            current_edge=edge_id,
                            current_lane=lane_id,
                            position=position,
                            speed=speed,
                            route=list(route),
                            detected_by_rsu=detecting_rsu,
                            greenwave_active=veh_id in self.active_greenwaves,
                            last_update_time=current_time
                        )
                        
                        self.emergency_vehicles[veh_id] = emergency_veh
                        detected.append(emergency_veh)
                
                except Exception as e:
                    # Vehicle might have left simulation
                    continue
            
            # Clean up vehicles that have left the simulation
            self._cleanup_completed_vehicles(all_vehicles)
            
        except Exception as e:
            print(f"Error detecting emergency vehicles: {e}")
        
        return detected
    
    def _is_emergency_vehicle(self, veh_id: str) -> bool:
        """Check if vehicle is an emergency vehicle."""
        # Check by ID pattern
        if any(keyword in veh_id.lower() for keyword in ['emergency', 'ambulance', 'fire', 'police']):
            return True
        
        # Check by vehicle type
        try:
            veh_type = traci.vehicle.getTypeID(veh_id)
            if veh_type == 'emergency':
                return True
        except:
            pass
        
        return False
    
    def _find_nearest_rsu(self, vehicle_pos: Tuple[float, float]) -> Optional[str]:
        """Find the nearest RSU within detection range."""
        min_distance = float('inf')
        nearest_rsu = None
        
        for rsu_id, rsu_pos in self.rsu_positions.items():
            distance = np.sqrt((vehicle_pos[0] - rsu_pos[0])**2 + 
                             (vehicle_pos[1] - rsu_pos[1])**2)
            
            if distance <= self.rsu_range and distance < min_distance:
                min_distance = distance
                nearest_rsu = rsu_id
        
        return nearest_rsu
    
    def create_greenwave(self, emergency_veh: EmergencyVehicle) -> List[str]:
        """
        Create greenwave for emergency vehicle along its route.
        
        Returns
        -------
        list of str
            List of junction/traffic light IDs that should be set to green
        """
        greenwave_junctions = []
        
        try:
            # Get vehicle's remaining route
            route_edges = emergency_veh.route
            current_edge = emergency_veh.current_edge
            
            # Find current position in route
            try:
                current_idx = route_edges.index(current_edge)
            except ValueError:
                current_idx = 0
            
            # Look ahead up to 3-5 junctions
            lookahead_edges = route_edges[current_idx:current_idx + 5]
            
            # Find junctions along the route
            for edge in lookahead_edges:
                for junc_id, junc in self.junction_info.items():
                    if edge in junc.incoming_edges or edge in junc.outgoing_edges:
                        if junc.tl_id and junc.tl_id not in greenwave_junctions:
                            greenwave_junctions.append(junc.tl_id)
            
            # Update active greenwaves
            if greenwave_junctions:
                self.active_greenwaves[emergency_veh.vehicle_id] = greenwave_junctions
                print(f"🟢 Greenwave created for {emergency_veh.vehicle_id}: {greenwave_junctions}")
            
        except Exception as e:
            print(f"Error creating greenwave: {e}")
        
        return greenwave_junctions
    
    def apply_greenwave(self, tl_id: str, emergency_edge: str) -> Optional[int]:
        """
        Apply greenwave to a specific traffic light.
        
        Parameters
        ----------
        tl_id : str
            Traffic light ID
        emergency_edge : str
            Edge where emergency vehicle is located
        
        Returns
        -------
        int or None
            Phase index to set, or None if no change needed
        """
        try:
            # Get current traffic light state
            current_phase = traci.trafficlight.getPhase(tl_id)
            controlled_links = traci.trafficlight.getControlledLinks(tl_id)
            
            # Find which links correspond to the emergency vehicle's edge
            target_link_indices = []
            for link_idx, link in enumerate(controlled_links):
                incoming_lane = link[0][0]  # First element is incoming lane
                incoming_edge = incoming_lane.rsplit('_', 1)[0]  # Remove lane suffix
                
                if incoming_edge == emergency_edge:
                    target_link_indices.append(link_idx)
            
            if not target_link_indices:
                return None
            
            # Find a phase that gives green to these links
            programs = traci.trafficlight.getAllProgramLogics(tl_id)
            if not programs:
                return None
            
            phases = programs[0].getPhases()
            
            for phase_idx, phase in enumerate(phases):
                state = phase.getRedYellowGreenState()
                
                # Check if this phase gives green to emergency vehicle's direction
                all_green = all(
                    link_idx < len(state) and state[link_idx] == 'G'
                    for link_idx in target_link_indices
                )
                
                if all_green and phase_idx != current_phase:
                    return phase_idx
            
        except Exception as e:
            print(f"Error applying greenwave to {tl_id}: {e}")
        
        return None
    
    def _cleanup_completed_vehicles(self, active_vehicles: List[str]):
        """Remove emergency vehicles that have completed their routes."""
        completed = []
        
        for veh_id in list(self.emergency_vehicles.keys()):
            if veh_id not in active_vehicles:
                completed.append(veh_id)
                del self.emergency_vehicles[veh_id]
                
                if veh_id in self.active_greenwaves:
                    del self.active_greenwaves[veh_id]
                    print(f"✓ Emergency vehicle {veh_id} completed route, greenwave deactivated")
        
        return completed
    
    def get_active_emergency_vehicles(self) -> List[EmergencyVehicle]:
        """Get list of currently active emergency vehicles."""
        return list(self.emergency_vehicles.values())
    
    def get_greenwave_status(self) -> Dict[str, List[str]]:
        """Get current greenwave status for all emergency vehicles."""
        return self.active_greenwaves.copy()
    
    def get_statistics(self) -> Dict:
        """Get coordinator statistics."""
        return {
            'total_detections': len(self.emergency_detections),
            'active_emergency_vehicles': len(self.emergency_vehicles),
            'active_greenwaves': len(self.active_greenwaves),
            'rsu_count': len(self.rsu_positions),
            'junction_count': len(self.junction_info),
        }
