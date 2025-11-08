#!/usr/bin/env python3
"""
Proximity-Based Hybrid Control Logic for Integration
Provides junction-specific switching based on emergency vehicle proximity.
"""

import traci
import numpy as np


class ProximityHybridLogic:
    """
    Handles proximity-based switching logic for hybrid control.
    Can be integrated into existing simulation loops.
    """
    
    def __init__(self, proximity_threshold=250.0):
        """
        Initialize proximity logic.
        
        Parameters
        ----------
        proximity_threshold : float
            Distance threshold in meters (default: 250m)
        """
        self.proximity_threshold = proximity_threshold
        self.junction_positions = {}
        self.junction_modes = {}
        
        # Statistics
        self.stats = {
            'total_steps': 0,
            'density_steps': 0,
            'rl_steps': 0,
            'junction_switches': 0,
        }
    
    def initialize_junctions(self):
        """Initialize junction positions from SUMO."""
        tl_ids = traci.trafficlight.getIDList()
        
        for tl_id in tl_ids:
            try:
                # Try to get actual junction position
                junction_id = tl_id  # Traffic light ID usually matches junction ID
                junction_pos = traci.junction.getPosition(junction_id)
                self.junction_positions[tl_id] = junction_pos
                self.junction_modes[tl_id] = "DENSITY"
                print(f"  {tl_id}: Position ({junction_pos[0]:.1f}, {junction_pos[1]:.1f})")
            except:
                # Fallback: use controlled lanes average
                try:
                    links = traci.trafficlight.getControlledLinks(tl_id)
                    if links:
                        all_x = []
                        all_y = []
                        for link in links[:4]:
                            try:
                                lane = link[0][0]
                                lane_shape = traci.lane.getShape(lane)
                                all_x.append(lane_shape[-1][0])
                                all_y.append(lane_shape[-1][1])
                            except:
                                pass
                        
                        if all_x and all_y:
                            x = sum(all_x) / len(all_x)
                            y = sum(all_y) / len(all_y)
                            self.junction_positions[tl_id] = (x, y)
                            self.junction_modes[tl_id] = "DENSITY"
                            print(f"  {tl_id}: Position ({x:.1f}, {y:.1f}) [fallback]")
                except Exception as e:
                    print(f"  ⚠️  {tl_id}: Could not get position ({e})")
        
        return len(self.junction_positions)
    
    def get_emergency_vehicles(self):
        """Get list of emergency vehicles in simulation."""
        emergency_vehicles = []
        all_vehicles = traci.vehicle.getIDList()
        
        for veh_id in all_vehicles:
            try:
                veh_type = traci.vehicle.getTypeID(veh_id)
                if 'emergency' in veh_type.lower() or 'ambulance' in veh_type.lower():
                    emergency_vehicles.append(veh_id)
            except:
                pass
        
        return emergency_vehicles
    
    def get_emergency_junction_proximity(self):
        """
        Get junctions that should be in RL mode based on emergency proximity.
        
        Returns
        -------
        set
            Set of junction IDs that should use RL mode
        """
        emergency_vehicles = self.get_emergency_vehicles()
        
        if not emergency_vehicles:
            return set()
        
        rl_junctions = set()
        
        for veh_id in emergency_vehicles:
            try:
                veh_pos = traci.vehicle.getPosition(veh_id)
                
                # Check distance to each junction
                for junction_id, junction_pos in self.junction_positions.items():
                    distance = np.sqrt(
                        (veh_pos[0] - junction_pos[0])**2 + 
                        (veh_pos[1] - junction_pos[1])**2
                    )
                    
                    if distance <= self.proximity_threshold:
                        rl_junctions.add(junction_id)
            except:
                pass
        
        return rl_junctions
    
    def update_junction_modes(self):
        """
        Update junction modes based on emergency proximity.
        
        Returns
        -------
        dict
            Dictionary mapping junction_id -> mode ("DENSITY" or "RL")
        """
        rl_junctions = self.get_emergency_junction_proximity()
        
        # Update modes and track switches
        for junction_id in self.junction_modes:
            old_mode = self.junction_modes[junction_id]
            new_mode = "RL" if junction_id in rl_junctions else "DENSITY"
            
            if old_mode != new_mode:
                self.stats['junction_switches'] += 1
                print(f"  Junction {junction_id}: {old_mode} → {new_mode}")
            
            self.junction_modes[junction_id] = new_mode
        
        # Update step statistics
        self.stats['total_steps'] += 1
        for mode in self.junction_modes.values():
            if mode == "RL":
                self.stats['rl_steps'] += 1
            else:
                self.stats['density_steps'] += 1
        
        return self.junction_modes.copy()
    
    def should_use_rl(self, junction_id):
        """
        Check if a specific junction should use RL control.
        
        Parameters
        ----------
        junction_id : str
            Junction/traffic light ID
        
        Returns
        -------
        bool
            True if junction should use RL, False for density
        """
        return self.junction_modes.get(junction_id, "DENSITY") == "RL"
    
    def get_statistics(self):
        """Get control statistics."""
        total_junction_steps = self.stats['density_steps'] + self.stats['rl_steps']
        
        return {
            'total_steps': self.stats['total_steps'],
            'density_percentage': (self.stats['density_steps'] / total_junction_steps * 100) if total_junction_steps > 0 else 0,
            'rl_percentage': (self.stats['rl_steps'] / total_junction_steps * 100) if total_junction_steps > 0 else 0,
            'junction_switches': self.stats['junction_switches'],
            'avg_switches_per_100_steps': (self.stats['junction_switches'] / self.stats['total_steps'] * 100) if self.stats['total_steps'] > 0 else 0,
        }
    
    def print_statistics(self):
        """Print control statistics."""
        stats = self.get_statistics()
        
        print()
        print("=" * 80)
        print("PROXIMITY-BASED HYBRID CONTROL STATISTICS")
        print("=" * 80)
        print(f"Total steps: {stats['total_steps']}")
        print(f"Density mode: {self.stats['density_steps']} steps ({stats['density_percentage']:.1f}%)")
        print(f"RL mode: {self.stats['rl_steps']} steps ({stats['rl_percentage']:.1f}%)")
        print(f"Junction switches: {stats['junction_switches']}")
        print(f"Average switches per 100 steps: {stats['avg_switches_per_100_steps']:.1f}")
        print("=" * 80)
