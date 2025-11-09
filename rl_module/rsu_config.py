"""
Unified RSU Configuration
Single source of truth for all RSU positions and naming across the system
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class RSUTier(Enum):
    """RSU tier classifications for edge computing hierarchy"""
    TIER1 = "TIER1"  # High-capacity RSUs at major intersections
    TIER2 = "TIER2"  # Medium-capacity RSUs along roads
    TIER3 = "TIER3"  # Coverage RSUs for gaps


@dataclass
class RSUDefinition:
    """Complete RSU definition with all metadata"""
    rsu_id: str                      # Unique RSU identifier (e.g., "RSU_J2")
    position: Tuple[float, float]    # (x, y) position in meters
    tier: RSUTier                    # Edge computing tier
    junction_id: Optional[str]       # Associated junction/traffic light (if any)
    coverage_radius: float           # Detection/coverage range in meters
    description: str                 # Human-readable description


# ============================================================================
# CANONICAL RSU DEFINITIONS - Single Source of Truth
# ============================================================================

# Based on SUMO network: simple_network.net.xml
# - Network dimensions: X: 0-2000m, Y: 0-1000m  
# - Main traffic lights: J2 at (500, 500), J3 at (1000, 500)
# - Other junctions: J0, J1, J4, J5, J6, J7, J8

RSU_DEFINITIONS = [
    # Tier 1: Major intersection RSUs (at traffic lights)
    RSUDefinition(
        rsu_id="RSU_J2",
        position=(500.0, 500.0),
        tier=RSUTier.TIER1,
        junction_id="J2",
        coverage_radius=300.0,
        description="Primary RSU at J2 traffic light intersection"
    ),
    RSUDefinition(
        rsu_id="RSU_J3",
        position=(1000.0, 500.0),
        tier=RSUTier.TIER1,
        junction_id="J3",
        coverage_radius=300.0,
        description="Primary RSU at J3 traffic light intersection"
    ),
    
    # Tier 2: Road segment RSUs (between intersections)
    RSUDefinition(
        rsu_id="RSU_E1_MID",
        position=(250.0, 500.0),
        tier=RSUTier.TIER2,
        junction_id=None,
        coverage_radius=250.0,
        description="Road RSU on E1 (between J0 and J2)"
    ),
    RSUDefinition(
        rsu_id="RSU_E2_MID",
        position=(750.0, 500.0),
        tier=RSUTier.TIER2,
        junction_id=None,
        coverage_radius=250.0,
        description="Road RSU on E2 (between J2 and J3)"
    ),
    RSUDefinition(
        rsu_id="RSU_E3_MID",
        position=(1250.0, 500.0),
        tier=RSUTier.TIER2,
        junction_id=None,
        coverage_radius=250.0,
        description="Road RSU on E3 (between J3 and J4)"
    ),
    RSUDefinition(
        rsu_id="RSU_E5_MID",
        position=(500.0, 250.0),
        tier=RSUTier.TIER2,
        junction_id=None,
        coverage_radius=250.0,
        description="Road RSU on E5 (between J5 and J2)"
    ),
    RSUDefinition(
        rsu_id="RSU_E6_MID",
        position=(500.0, 750.0),
        tier=RSUTier.TIER2,
        junction_id=None,
        coverage_radius=250.0,
        description="Road RSU on E6 (between J2 and J6)"
    ),
    RSUDefinition(
        rsu_id="RSU_E7_MID",
        position=(1000.0, 250.0),
        tier=RSUTier.TIER2,
        junction_id=None,
        coverage_radius=250.0,
        description="Road RSU on E7 (between J7 and J3)"
    ),
    RSUDefinition(
        rsu_id="RSU_E8_MID",
        position=(1000.0, 750.0),
        tier=RSUTier.TIER2,
        junction_id=None,
        coverage_radius=250.0,
        description="Road RSU on E8 (between J3 and J8)"
    ),
    
    # Tier 3: Coverage RSUs (fill gaps)
    RSUDefinition(
        rsu_id="RSU_SW",
        position=(250.0, 250.0),
        tier=RSUTier.TIER3,
        junction_id=None,
        coverage_radius=200.0,
        description="Southwest coverage RSU"
    ),
    RSUDefinition(
        rsu_id="RSU_NW",
        position=(250.0, 750.0),
        tier=RSUTier.TIER3,
        junction_id=None,
        coverage_radius=200.0,
        description="Northwest coverage RSU"
    ),
    RSUDefinition(
        rsu_id="RSU_SE",
        position=(1250.0, 250.0),
        tier=RSUTier.TIER3,
        junction_id=None,
        coverage_radius=200.0,
        description="Southeast coverage RSU"
    ),
    RSUDefinition(
        rsu_id="RSU_NE",
        position=(1250.0, 750.0),
        tier=RSUTier.TIER3,
        junction_id=None,
        coverage_radius=200.0,
        description="Northeast coverage RSU"
    ),
]


# ============================================================================
# CONVENIENCE ACCESSORS
# ============================================================================

def get_all_rsus() -> List[RSUDefinition]:
    """Get all RSU definitions"""
    return RSU_DEFINITIONS.copy()


def get_rsus_by_tier(tier: RSUTier) -> List[RSUDefinition]:
    """Get RSUs filtered by tier"""
    return [rsu for rsu in RSU_DEFINITIONS if rsu.tier == tier]


def get_rsu_by_id(rsu_id: str) -> Optional[RSUDefinition]:
    """Get RSU definition by ID"""
    for rsu in RSU_DEFINITIONS:
        if rsu.rsu_id == rsu_id:
            return rsu
    return None


def get_rsu_positions() -> Dict[str, Tuple[float, float]]:
    """Get dictionary mapping RSU IDs to positions (legacy format)"""
    return {rsu.rsu_id: rsu.position for rsu in RSU_DEFINITIONS}


def get_junction_rsus() -> Dict[str, RSUDefinition]:
    """Get RSUs associated with traffic light junctions"""
    return {
        rsu.junction_id: rsu 
        for rsu in RSU_DEFINITIONS 
        if rsu.junction_id is not None
    }


def get_rsu_ids() -> List[str]:
    """Get list of all RSU IDs"""
    return [rsu.rsu_id for rsu in RSU_DEFINITIONS]


def get_rsu_count() -> int:
    """Get total number of RSUs"""
    return len(RSU_DEFINITIONS)


def get_tier_counts() -> Dict[str, int]:
    """Get count of RSUs per tier"""
    return {
        "TIER1": len(get_rsus_by_tier(RSUTier.TIER1)),
        "TIER2": len(get_rsus_by_tier(RSUTier.TIER2)),
        "TIER3": len(get_rsus_by_tier(RSUTier.TIER3)),
    }


# ============================================================================
# NS3 INTEGRATION HELPERS
# ============================================================================

def get_ns3_rsu_positions() -> List[Tuple[float, float]]:
    """
    Get RSU positions in format expected by NS3 bridge.
    Returns list of (x, y) tuples for NS3 node creation.
    """
    return [rsu.position for rsu in RSU_DEFINITIONS]


def get_ns3_rsu_mapping() -> Dict[int, str]:
    """
    Get mapping from NS3 node index to RSU ID.
    NS3 creates nodes sequentially, so we map indices to our IDs.
    """
    return {idx: rsu.rsu_id for idx, rsu in enumerate(RSU_DEFINITIONS)}


# ============================================================================
# VALIDATION & DEBUGGING
# ============================================================================

def validate_rsu_config() -> Dict[str, any]:
    """Validate RSU configuration and return report"""
    issues = []
    
    # Check for duplicate IDs
    ids = [rsu.rsu_id for rsu in RSU_DEFINITIONS]
    if len(ids) != len(set(ids)):
        issues.append("Duplicate RSU IDs found")
    
    # Check for duplicate positions
    positions = [rsu.position for rsu in RSU_DEFINITIONS]
    if len(positions) != len(set(positions)):
        issues.append("Duplicate RSU positions found")
    
    # Check coverage (should have overlapping ranges)
    coverage_gaps = check_coverage_gaps()
    if coverage_gaps:
        issues.append(f"Coverage gaps detected: {coverage_gaps}")
    
    return {
        "valid": len(issues) == 0,
        "total_rsus": len(RSU_DEFINITIONS),
        "tier_distribution": get_tier_counts(),
        "issues": issues,
    }


def check_coverage_gaps() -> List[str]:
    """Check for potential coverage gaps in the network"""
    # Simplified check: just verify we have RSUs at key locations
    gaps = []
    
    junction_rsus = get_junction_rsus()
    if "J2" not in junction_rsus:
        gaps.append("Missing RSU at J2")
    if "J3" not in junction_rsus:
        gaps.append("Missing RSU at J3")
    
    return gaps


def print_rsu_summary():
    """Print human-readable RSU configuration summary"""
    print("\n" + "="*70)
    print("RSU CONFIGURATION SUMMARY")
    print("="*70)
    
    tier_counts = get_tier_counts()
    print(f"\nTotal RSUs: {get_rsu_count()}")
    print(f"  - Tier 1 (Intersections): {tier_counts['TIER1']}")
    print(f"  - Tier 2 (Road Segments): {tier_counts['TIER2']}")
    print(f"  - Tier 3 (Coverage):      {tier_counts['TIER3']}")
    
    print("\nRSU Details:")
    for tier in [RSUTier.TIER1, RSUTier.TIER2, RSUTier.TIER3]:
        rsus = get_rsus_by_tier(tier)
        if rsus:
            print(f"\n  {tier.value}:")
            for rsu in rsus:
                junc_str = f" (Junction: {rsu.junction_id})" if rsu.junction_id else ""
                print(f"    - {rsu.rsu_id:15s} @ {rsu.position}{junc_str}")
                print(f"      Range: {rsu.coverage_radius}m | {rsu.description}")
    
    validation = validate_rsu_config()
    print("\nValidation:")
    print(f"  Status: {'✓ VALID' if validation['valid'] else '✗ INVALID'}")
    if validation['issues']:
        print(f"  Issues: {', '.join(validation['issues'])}")
    
    print("="*70 + "\n")


if __name__ == "__main__":
    # Test the configuration
    print_rsu_summary()
    
    # Example usage
    print("\nExample API Usage:")
    print(f"  All RSU IDs: {get_rsu_ids()}")
    print(f"  Junction RSUs: {list(get_junction_rsus().keys())}")
    print(f"  RSU_J2 position: {get_rsu_by_id('RSU_J2').position}")
