"""
Unified RSU configuration.

This module keeps backward-compatible default RSU definitions for the simple map,
and can also load dynamic RSUs from a JSON file pointed to by the
VANET_RSU_CONFIG_FILE environment variable.
"""

from dataclasses import dataclass
from enum import Enum
import json
import os
from typing import Any, Dict, List, Optional, Tuple


class RSUTier(Enum):
    """RSU tier classifications for edge computing hierarchy."""

    TIER1 = "TIER1"  # High-capacity RSUs at major intersections
    TIER2 = "TIER2"  # Medium-capacity RSUs along roads
    TIER3 = "TIER3"  # Coverage RSUs for gaps


@dataclass
class RSUDefinition:
    """Complete RSU definition with metadata."""

    rsu_id: str
    position: Tuple[float, float]
    tier: RSUTier
    junction_id: Optional[str]
    coverage_radius: float
    description: str


# ============================================================================
# Built-in defaults (simple map)
# ============================================================================

DEFAULT_RSU_DEFINITIONS = [
    RSUDefinition(
        rsu_id="RSU_J2",
        position=(500.0, 500.0),
        tier=RSUTier.TIER1,
        junction_id="J2",
        coverage_radius=300.0,
        description="Primary RSU at J2 traffic light intersection",
    ),
    RSUDefinition(
        rsu_id="RSU_J3",
        position=(1000.0, 500.0),
        tier=RSUTier.TIER1,
        junction_id="J3",
        coverage_radius=300.0,
        description="Primary RSU at J3 traffic light intersection",
    ),
    RSUDefinition(
        rsu_id="RSU_E1_MID",
        position=(250.0, 500.0),
        tier=RSUTier.TIER2,
        junction_id=None,
        coverage_radius=250.0,
        description="Road RSU on E1 (between J0 and J2)",
    ),
    RSUDefinition(
        rsu_id="RSU_E2_MID",
        position=(750.0, 500.0),
        tier=RSUTier.TIER2,
        junction_id=None,
        coverage_radius=250.0,
        description="Road RSU on E2 (between J2 and J3)",
    ),
    RSUDefinition(
        rsu_id="RSU_E3_MID",
        position=(1250.0, 500.0),
        tier=RSUTier.TIER2,
        junction_id=None,
        coverage_radius=250.0,
        description="Road RSU on E3 (between J3 and J4)",
    ),
    RSUDefinition(
        rsu_id="RSU_E5_MID",
        position=(500.0, 250.0),
        tier=RSUTier.TIER2,
        junction_id=None,
        coverage_radius=250.0,
        description="Road RSU on E5 (between J5 and J2)",
    ),
    RSUDefinition(
        rsu_id="RSU_E6_MID",
        position=(500.0, 750.0),
        tier=RSUTier.TIER2,
        junction_id=None,
        coverage_radius=250.0,
        description="Road RSU on E6 (between J2 and J6)",
    ),
    RSUDefinition(
        rsu_id="RSU_E7_MID",
        position=(1000.0, 250.0),
        tier=RSUTier.TIER2,
        junction_id=None,
        coverage_radius=250.0,
        description="Road RSU on E7 (between J7 and J3)",
    ),
    RSUDefinition(
        rsu_id="RSU_E8_MID",
        position=(1000.0, 750.0),
        tier=RSUTier.TIER2,
        junction_id=None,
        coverage_radius=250.0,
        description="Road RSU on E8 (between J3 and J8)",
    ),
    RSUDefinition(
        rsu_id="RSU_SW",
        position=(250.0, 250.0),
        tier=RSUTier.TIER3,
        junction_id=None,
        coverage_radius=200.0,
        description="Southwest coverage RSU",
    ),
    RSUDefinition(
        rsu_id="RSU_NW",
        position=(250.0, 750.0),
        tier=RSUTier.TIER3,
        junction_id=None,
        coverage_radius=200.0,
        description="Northwest coverage RSU",
    ),
    RSUDefinition(
        rsu_id="RSU_SE",
        position=(1250.0, 250.0),
        tier=RSUTier.TIER3,
        junction_id=None,
        coverage_radius=200.0,
        description="Southeast coverage RSU",
    ),
    RSUDefinition(
        rsu_id="RSU_NE",
        position=(1250.0, 750.0),
        tier=RSUTier.TIER3,
        junction_id=None,
        coverage_radius=200.0,
        description="Northeast coverage RSU",
    ),
]

# Backward-compatible alias used by a few legacy scripts.
RSU_DEFINITIONS = DEFAULT_RSU_DEFINITIONS

_dynamic_cache_path: Optional[str] = None
_dynamic_cache_value: Optional[List[RSUDefinition]] = None


def _parse_position(entry: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """Parse position from either [x, y] or {x, y} fields."""
    position = entry.get("position")
    if isinstance(position, (list, tuple)) and len(position) >= 2:
        return float(position[0]), float(position[1])

    if isinstance(position, dict) and "x" in position and "y" in position:
        return float(position["x"]), float(position["y"])

    if "x" in entry and "y" in entry:
        return float(entry["x"]), float(entry["y"])

    return None


def _to_tier(value: str) -> RSUTier:
    normalized = (value or "").strip().upper()
    if normalized in ("TIER1", "1"):
        return RSUTier.TIER1
    if normalized in ("TIER2", "2"):
        return RSUTier.TIER2
    if normalized in ("TIER3", "3"):
        return RSUTier.TIER3
    return RSUTier.TIER2


def _load_dynamic_rsu_definitions() -> Optional[List[RSUDefinition]]:
    """Load RSUs from VANET_RSU_CONFIG_FILE if set and valid."""
    global _dynamic_cache_path
    global _dynamic_cache_value

    configured_path = os.environ.get("VANET_RSU_CONFIG_FILE")
    if not configured_path:
        _dynamic_cache_path = None
        _dynamic_cache_value = None
        return None

    absolute_path = os.path.abspath(configured_path)
    if _dynamic_cache_path == absolute_path:
        return _dynamic_cache_value

    _dynamic_cache_path = absolute_path
    _dynamic_cache_value = None

    if not os.path.exists(absolute_path):
        print(f"[rsu_config] dynamic RSU file not found: {absolute_path}")
        return None

    try:
        with open(absolute_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        print(f"[rsu_config] failed to read dynamic RSU file ({absolute_path}): {exc}")
        return None

    entries = payload.get("rsus") if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        print(f"[rsu_config] invalid dynamic RSU file format: {absolute_path}")
        return None

    dynamic_defs: List[RSUDefinition] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue

        rsu_id = entry.get("rsu_id") or entry.get("id")
        position = _parse_position(entry)
        if not rsu_id or position is None:
            print(f"[rsu_config] skipping invalid RSU entry at index {index}")
            continue

        dynamic_defs.append(
            RSUDefinition(
                rsu_id=str(rsu_id),
                position=position,
                tier=_to_tier(str(entry.get("tier", "TIER2"))),
                junction_id=entry.get("junction_id"),
                coverage_radius=float(entry.get("coverage_radius", 300.0)),
                description=str(entry.get("description", f"Dynamic RSU {rsu_id}")),
            )
        )

    if not dynamic_defs:
        print(f"[rsu_config] no valid RSU entries found in {absolute_path}")
        return None

    _dynamic_cache_value = dynamic_defs
    return _dynamic_cache_value


def _get_active_rsu_definitions() -> List[RSUDefinition]:
    dynamic_defs = _load_dynamic_rsu_definitions()
    if dynamic_defs:
        return dynamic_defs
    return DEFAULT_RSU_DEFINITIONS


# ============================================================================
# Convenience accessors
# ============================================================================


def get_all_rsus() -> List[RSUDefinition]:
    return _get_active_rsu_definitions().copy()


def get_rsus_by_tier(tier: RSUTier) -> List[RSUDefinition]:
    return [rsu for rsu in _get_active_rsu_definitions() if rsu.tier == tier]


def get_rsu_by_id(rsu_id: str) -> Optional[RSUDefinition]:
    for rsu in _get_active_rsu_definitions():
        if rsu.rsu_id == rsu_id:
            return rsu
    return None


def get_rsu_positions() -> Dict[str, Tuple[float, float]]:
    return {rsu.rsu_id: rsu.position for rsu in _get_active_rsu_definitions()}


def get_junction_rsus() -> Dict[str, RSUDefinition]:
    return {
        rsu.junction_id: rsu
        for rsu in _get_active_rsu_definitions()
        if rsu.junction_id is not None
    }


def get_rsu_ids() -> List[str]:
    return [rsu.rsu_id for rsu in _get_active_rsu_definitions()]


def get_rsu_count() -> int:
    return len(_get_active_rsu_definitions())


def get_tier_counts() -> Dict[str, int]:
    return {
        "TIER1": len(get_rsus_by_tier(RSUTier.TIER1)),
        "TIER2": len(get_rsus_by_tier(RSUTier.TIER2)),
        "TIER3": len(get_rsus_by_tier(RSUTier.TIER3)),
    }


# ============================================================================
# NS3 integration helpers
# ============================================================================


def get_ns3_rsu_positions() -> List[Tuple[float, float]]:
    return [rsu.position for rsu in _get_active_rsu_definitions()]


def get_ns3_rsu_mapping() -> Dict[int, str]:
    return {idx: rsu.rsu_id for idx, rsu in enumerate(_get_active_rsu_definitions())}


# ============================================================================
# Validation and debugging
# ============================================================================


def validate_rsu_config() -> Dict[str, Any]:
    issues = []
    active_defs = _get_active_rsu_definitions()

    ids = [rsu.rsu_id for rsu in active_defs]
    if len(ids) != len(set(ids)):
        issues.append("Duplicate RSU IDs found")

    positions = [rsu.position for rsu in active_defs]
    if len(positions) != len(set(positions)):
        issues.append("Duplicate RSU positions found")

    coverage_gaps = check_coverage_gaps()
    if coverage_gaps:
        issues.append(f"Coverage gaps detected: {coverage_gaps}")

    return {
        "valid": len(issues) == 0,
        "total_rsus": len(active_defs),
        "tier_distribution": get_tier_counts(),
        "issues": issues,
    }


def check_coverage_gaps() -> List[str]:
    gaps = []
    if not get_junction_rsus():
        gaps.append("No junction RSUs available")
    return gaps


def print_rsu_summary() -> None:
    print("\n" + "=" * 70)
    print("RSU CONFIGURATION SUMMARY")
    print("=" * 70)

    source = os.environ.get("VANET_RSU_CONFIG_FILE") or "built-in defaults"
    print(f"\nSource: {source}")

    tier_counts = get_tier_counts()
    print(f"Total RSUs: {get_rsu_count()}")
    print(f"  - Tier 1 (Intersections): {tier_counts['TIER1']}")
    print(f"  - Tier 2 (Road Segments): {tier_counts['TIER2']}")
    print(f"  - Tier 3 (Coverage):      {tier_counts['TIER3']}")

    print("\nRSU Details:")
    for tier in [RSUTier.TIER1, RSUTier.TIER2, RSUTier.TIER3]:
        rsus = get_rsus_by_tier(tier)
        if not rsus:
            continue
        print(f"\n  {tier.value}:")
        for rsu in rsus:
            junction = f" (Junction: {rsu.junction_id})" if rsu.junction_id else ""
            print(f"    - {rsu.rsu_id:20s} @ {rsu.position}{junction}")
            print(f"      Range: {rsu.coverage_radius}m | {rsu.description}")

    validation = validate_rsu_config()
    print("\nValidation:")
    print(f"  Status: {'VALID' if validation['valid'] else 'INVALID'}")
    if validation["issues"]:
        print(f"  Issues: {', '.join(validation['issues'])}")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    print_rsu_summary()
    junction_rsus = get_junction_rsus()
    print("Example API usage:")
    print(f"  All RSU IDs: {get_rsu_ids()}")
    print(f"  Junction RSUs: {list(junction_rsus.keys())}")
    if junction_rsus:
        first_key = sorted(junction_rsus.keys())[0]
        print(f"  First junction RSU ({first_key}): {junction_rsus[first_key].position}")
