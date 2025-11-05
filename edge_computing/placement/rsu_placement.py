"""
RSU Placement Manager - Smart placement of RSUs at regular intervals
"""
import math
from typing import List, Tuple, Dict


class RSUPlacementManager:
    """Manages intelligent placement of RSUs across the VANET network"""
    
    def __init__(self, interval_meters: int = 400):
        """
        Initialize RSU placement manager
        
        Args:
            interval_meters: Distance between RSUs along roads (default: 400m)
        """
        self.interval = interval_meters
        self.rsu_positions: List[Dict] = []
        self.tier_assignments: Dict[str, int] = {}
        
    def calculate_rsu_positions(self, network_bounds: Tuple[float, float, float, float],
                               junction_positions: List[Tuple[float, float]],
                               edge_definitions: List[Dict]) -> List[Dict]:
        """
        Calculate optimal RSU positions for complete network coverage
        
        Args:
            network_bounds: (min_x, min_y, max_x, max_y) of network
            junction_positions: List of (x, y) junction coordinates
            edge_definitions: List of edge definitions with from/to positions
            
        Returns:
            List of RSU definitions with position, tier, and ID
        """
        self.rsu_positions = []
        rsu_counter = 0
        
        # Tier 1: Intersection RSUs (highest priority)
        print("\n🔷 Calculating Tier 1 RSUs (Intersections)...")
        for idx, (x, y) in enumerate(junction_positions):
            rsu_id = f"RSU_J{idx}_TIER1"
            self.rsu_positions.append({
                'id': rsu_id,
                'position': (x, y),
                'tier': 1,
                'type': 'intersection',
                'compute_capacity': 'high',
                'coverage_radius': 300  # WiFi range
            })
            self.tier_assignments[rsu_id] = 1
            rsu_counter += 1
            print(f"  ✓ {rsu_id} at ({x:.1f}, {y:.1f})")
        
        # Tier 2: Road Segment RSUs (regular intervals)
        print(f"\n🔷 Calculating Tier 2 RSUs (Road Segments, interval={self.interval}m)...")
        for edge in edge_definitions:
            edge_rsus = self._place_rsus_along_edge(edge, rsu_counter)
            self.rsu_positions.extend(edge_rsus)
            rsu_counter += len(edge_rsus)
            
        # Tier 3: Coverage RSUs (fill gaps)
        print(f"\n🔷 Calculating Tier 3 RSUs (Coverage gaps)...")
        coverage_rsus = self._fill_coverage_gaps(network_bounds, rsu_counter)
        self.rsu_positions.extend(coverage_rsus)
        
        print(f"\n✅ Total RSUs placed: {len(self.rsu_positions)}")
        print(f"   - Tier 1 (Intersection): {sum(1 for r in self.rsu_positions if r['tier'] == 1)}")
        print(f"   - Tier 2 (Road Segment): {sum(1 for r in self.rsu_positions if r['tier'] == 2)}")
        print(f"   - Tier 3 (Coverage): {sum(1 for r in self.rsu_positions if r['tier'] == 3)}")
        
        return self.rsu_positions
    
    def _place_rsus_along_edge(self, edge: Dict, start_counter: int) -> List[Dict]:
        """Place RSUs at regular intervals along a road edge"""
        rsus = []
        edge_id = edge.get('id', 'unknown')
        from_pos = edge.get('from_pos', (0, 0))
        to_pos = edge.get('to_pos', (0, 0))
        
        # Calculate edge length and direction
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        length = math.sqrt(dx**2 + dy**2)
        
        if length < self.interval:
            # Edge too short, place one RSU in the middle
            mid_x = (from_pos[0] + to_pos[0]) / 2
            mid_y = (from_pos[1] + to_pos[1]) / 2
            rsu_id = f"RSU_{edge_id}_0_TIER2"
            rsus.append({
                'id': rsu_id,
                'position': (mid_x, mid_y),
                'tier': 2,
                'type': 'road_segment',
                'edge_id': edge_id,
                'compute_capacity': 'medium',
                'coverage_radius': 300
            })
            self.tier_assignments[rsu_id] = 2
            return rsus
        
        # Place RSUs at regular intervals
        num_rsus = int(length / self.interval)
        unit_dx = dx / length
        unit_dy = dy / length
        
        for i in range(num_rsus):
            # Position along the edge
            distance = (i + 0.5) * self.interval  # Center of each segment
            x = from_pos[0] + unit_dx * distance
            y = from_pos[1] + unit_dy * distance
            
            rsu_id = f"RSU_{edge_id}_{i}_TIER2"
            rsus.append({
                'id': rsu_id,
                'position': (x, y),
                'tier': 2,
                'type': 'road_segment',
                'edge_id': edge_id,
                'compute_capacity': 'medium',
                'coverage_radius': 300
            })
            self.tier_assignments[rsu_id] = 2
            print(f"  ✓ {rsu_id} at ({x:.1f}, {y:.1f})")
        
        return rsus
    
    def _fill_coverage_gaps(self, network_bounds: Tuple[float, float, float, float],
                           start_counter: int) -> List[Dict]:
        """Fill gaps in coverage with Tier 3 RSUs"""
        rsus = []
        min_x, min_y, max_x, max_y = network_bounds
        
        # Grid-based gap filling
        coverage_radius = 300  # meters
        grid_spacing = coverage_radius * 1.5  # Ensure overlap
        
        gap_counter = 0
        x = min_x + grid_spacing / 2
        while x < max_x:
            y = min_y + grid_spacing / 2
            while y < max_y:
                # Check if this position is too close to existing RSUs
                if not self._too_close_to_existing((x, y), min_distance=200):
                    rsu_id = f"RSU_GAP{gap_counter}_TIER3"
                    rsus.append({
                        'id': rsu_id,
                        'position': (x, y),
                        'tier': 3,
                        'type': 'coverage',
                        'compute_capacity': 'light',
                        'coverage_radius': 300
                    })
                    self.tier_assignments[rsu_id] = 3
                    gap_counter += 1
                    print(f"  ✓ {rsu_id} at ({x:.1f}, {y:.1f})")
                y += grid_spacing
            x += grid_spacing
        
        return rsus
    
    def _too_close_to_existing(self, position: Tuple[float, float], 
                               min_distance: float = 200) -> bool:
        """Check if position is too close to existing RSUs"""
        x, y = position
        for rsu in self.rsu_positions:
            rx, ry = rsu['position']
            distance = math.sqrt((x - rx)**2 + (y - ry)**2)
            if distance < min_distance:
                return True
        return False
    
    def get_rsu_by_tier(self, tier: int) -> List[Dict]:
        """Get all RSUs of a specific tier"""
        return [rsu for rsu in self.rsu_positions if rsu['tier'] == tier]
    
    def get_nearest_rsu(self, position: Tuple[float, float], 
                       tier: int = None) -> Dict:
        """Find nearest RSU to a given position"""
        x, y = position
        min_distance = float('inf')
        nearest = None
        
        for rsu in self.rsu_positions:
            if tier is not None and rsu['tier'] != tier:
                continue
            
            rx, ry = rsu['position']
            distance = math.sqrt((x - rx)**2 + (y - ry)**2)
            
            if distance < min_distance:
                min_distance = distance
                nearest = rsu
        
        return nearest
    
    def get_rsus_in_range(self, position: Tuple[float, float], 
                         radius: float = 300) -> List[Dict]:
        """Get all RSUs within range of a position"""
        x, y = position
        rsus_in_range = []
        
        for rsu in self.rsu_positions:
            rx, ry = rsu['position']
            distance = math.sqrt((x - rx)**2 + (y - ry)**2)
            
            if distance <= radius:
                rsus_in_range.append({
                    **rsu,
                    'distance': distance
                })
        
        return sorted(rsus_in_range, key=lambda r: r['distance'])
