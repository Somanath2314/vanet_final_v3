#!/usr/bin/env python3
"""
Generate SUMO assets for the OSM-derived layout in this folder.

Outputs:
- routes_new.rou.xml
- rsu.add.xml
- rsu_config.json
- simulation_new.sumocfg
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
from datetime import datetime, timezone
import json
from pathlib import Path
import random
from typing import Dict, List, Optional, Sequence, Tuple
import xml.etree.ElementTree as ET


def is_drivable_edge(edge_elem: ET.Element) -> bool:
    """Return True when at least one lane can carry passenger traffic."""
    lanes = edge_elem.findall("lane")
    if not lanes:
        return False

    for lane in lanes:
        allow = (lane.get("allow") or "").split()
        disallow = (lane.get("disallow") or "").split()

        if allow:
            if "passenger" in allow or "private" in allow or "authority" in allow:
                return True
        else:
            if "passenger" not in disallow:
                return True

    return False


def parse_shape_endpoints(shape_text: str) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Parse first/last points from a SUMO shape string."""
    if not shape_text:
        return None

    points = []
    for token in shape_text.split():
        if "," not in token:
            continue
        x_text, y_text = token.split(",", 1)
        points.append((float(x_text), float(y_text)))

    if len(points) < 2:
        return None
    return points[0], points[-1]


def bfs_path(start: str, target: str, adjacency: Dict[str, Sequence[str]], max_hops: int = 80) -> Optional[List[str]]:
    """Find a feasible edge path from start to target."""
    queue = deque([(start, [start])])
    visited = {start}

    while queue:
        current, path = queue.popleft()
        if current == target:
            return path

        if len(path) >= max_hops:
            continue

        for nxt in adjacency.get(current, []):
            if nxt in visited:
                continue
            visited.add(nxt)
            queue.append((nxt, path + [nxt]))

    return None


def position_too_close(position: Tuple[float, float], existing: Sequence[Tuple[float, float]], min_distance: float) -> bool:
    for ex, ey in existing:
        dx = position[0] - ex
        dy = position[1] - ey
        if (dx * dx + dy * dy) ** 0.5 < min_distance:
            return True
    return False


def build_routes(
    edge_data: Dict[str, Dict[str, object]],
    adjacency: Dict[str, List[str]],
    traffic_light_junctions: set,
    seed: int,
) -> List[List[str]]:
    """Create map-compatible route templates."""
    rng = random.Random(seed)

    in_degree = defaultdict(int)
    out_degree = defaultdict(int)
    for src, dsts in adjacency.items():
        out_degree[src] = len(dsts)
        for dst in dsts:
            in_degree[dst] += 1

    edges = list(edge_data.keys())
    if not edges:
        return []

    origins = [edge_id for edge_id in edges if in_degree[edge_id] == 0 and out_degree[edge_id] > 0]
    if len(origins) < 10:
        origins = sorted(edges, key=lambda e: (in_degree[e], -float(edge_data[e]["length"])))[:80]

    destinations = [edge_id for edge_id in edges if out_degree[edge_id] == 0 and in_degree[edge_id] > 0]
    if len(destinations) < 10:
        destinations = sorted(edges, key=lambda e: (out_degree[e], -float(edge_data[e]["length"])))[:80]

    candidate_pairs = [(o, d) for o in origins for d in destinations if o != d]
    rng.shuffle(candidate_pairs)

    routes: List[List[str]] = []
    seen = set()

    for origin, destination in candidate_pairs:
        if len(routes) >= 16:
            break
        path = bfs_path(origin, destination, adjacency)
        if not path or len(path) < 2:
            continue
        key = tuple(path)
        if key in seen:
            continue
        seen.add(key)
        routes.append(path)

    # Fallback random walks if BFS combinations are sparse.
    if len(routes) < 10:
        shuffled_edges = edges[:]
        rng.shuffle(shuffled_edges)
        for start in shuffled_edges:
            if len(routes) >= 10:
                break
            if out_degree[start] == 0:
                continue
            path = [start]
            hop_count = rng.randint(4, 10)
            for _ in range(hop_count):
                nxt_candidates = adjacency.get(path[-1], [])
                if not nxt_candidates:
                    break
                path.append(rng.choice(nxt_candidates))
            if len(path) < 2:
                continue
            key = tuple(path)
            if key in seen:
                continue
            seen.add(key)
            routes.append(path)

    # Prefer routes that traverse traffic-light areas for emergency scenarios.
    def route_score(path: List[str]) -> Tuple[int, int]:
        tl_hits = 0
        for edge_id in path:
            from_j = edge_data[edge_id].get("from")
            to_j = edge_data[edge_id].get("to")
            if from_j in traffic_light_junctions or to_j in traffic_light_junctions:
                tl_hits += 1
        return tl_hits, len(path)

    routes.sort(key=route_score, reverse=True)
    return routes[:16]


def write_routes_file(layout_dir: Path, routes: List[List[str]], route_scores: List[int]) -> None:
    output_path = layout_dir / "routes_new.rou.xml"

    lines: List[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">')
    lines.append('  <vType id="passenger" accel="2.6" decel="4.5" sigma="0.5" length="5.0" minGap="2.5" maxSpeed="20.0" guiShape="passenger"/>')
    lines.append('  <vType id="emergency" accel="3.0" decel="5.0" sigma="0.2" length="6.0" minGap="2.0" maxSpeed="25.0" guiShape="emergency" color="red"/>')
    lines.append("")

    for idx, edges in enumerate(routes, start=1):
        lines.append(f'  <route id="route_{idx}" edges="{" ".join(edges)}"/>')

    lines.append("")

    depart_time = 10
    for idx in range(min(8, len(routes))):
        lines.append(
            f'  <vehicle id="warmup_{idx + 1}" type="passenger" route="route_{idx + 1}" depart="{depart_time}"/>'
        )
        depart_time += 6

    lines.append("")

    passenger_flow_begin = 60
    passenger_flow_end = 3600
    passenger_uniform_vehs_per_hour = 300
    for idx in range(len(routes)):
        lines.append(
            f'  <flow id="flow_passenger_{idx + 1}" type="passenger" route="route_{idx + 1}" begin="{passenger_flow_begin}" end="{passenger_flow_end}" vehsPerHour="{passenger_uniform_vehs_per_hour}" departLane="best" departSpeed="max"/>'
        )

    lines.append("")

    ranked_indices = sorted(range(len(routes)), key=lambda i: (route_scores[i], len(routes[i])), reverse=True)

    emergency_depart = 320
    for idx in range(min(10, len(ranked_indices))):
        route_idx = ranked_indices[idx] + 1
        lines.append(
            f'  <vehicle id="emergency_{idx + 1}" type="emergency" route="route_{route_idx}" depart="{emergency_depart}"/>'
        )
        emergency_depart += 45

    lines.append("")

    emergency_flow_begin = 900
    for idx in range(min(4, len(ranked_indices))):
        route_idx = ranked_indices[idx] + 1
        vehs_per_hour = 12 + (idx * 4)
        lines.append(
            f'  <flow id="flow_emergency_{idx + 1}" type="emergency" route="route_{route_idx}" begin="{emergency_flow_begin}" end="3600" vehsPerHour="{vehs_per_hour}" departLane="best" departSpeed="max"/>'
        )
        emergency_flow_begin += 120

    lines.append("</routes>")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_rsu_config_files(
    layout_dir: Path,
    traffic_light_positions: Dict[str, Tuple[float, float]],
    edge_data: Dict[str, Dict[str, object]],
    tier2_interval_m: float = 300.0,
) -> int:
    """Write rsu_config.json and rsu.add.xml."""
    rsus = []

    for junction_id in sorted(traffic_light_positions.keys()):
        x, y = traffic_light_positions[junction_id]
        rsus.append(
            {
                "rsu_id": f"RSU_{junction_id}",
                "position": [x, y],
                "tier": "TIER1",
                "junction_id": junction_id,
                "coverage_radius": 300.0,
                "description": f"Primary RSU at traffic light {junction_id}",
            }
        )

    # Place tier-2 road RSUs at regular spacing along drivable edges.
    placed = [tuple(item["position"]) for item in rsus]
    sorted_edges = sorted(edge_data.items(), key=lambda item: item[0])
    tier2_added = 0
    for edge_id, info in sorted_edges:
        start = info.get("start")
        end = info.get("end")
        length = float(info.get("length", 0.0))
        if start is None or end is None:
            continue
        if length <= 0:
            continue

        num_points = int(length // tier2_interval_m)
        if num_points <= 0:
            continue

        # Center the first/last RSU on each edge while keeping interval spacing.
        first_offset = (length - (num_points - 1) * tier2_interval_m) / 2.0

        for idx in range(num_points):
            offset = first_offset + idx * tier2_interval_m
            ratio = max(0.0, min(1.0, offset / length))

            midpoint = (
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio,
            )

            # Keep only a tiny de-dup distance to avoid overlapping markers.
            if position_too_close(midpoint, placed, min_distance=35.0):
                continue

            rsus.append(
                {
                    "rsu_id": f"RSU_EDGE_{tier2_added + 1}",
                    "position": [midpoint[0], midpoint[1]],
                    "tier": "TIER2",
                    "junction_id": None,
                    "coverage_radius": tier2_interval_m,
                    "description": f"Road RSU at {tier2_interval_m:.0f}m spacing on edge {edge_id}",
                }
            )
            placed.append(midpoint)
            tier2_added += 1

    config_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_net": "map.net.xml",
        "rsus": rsus,
    }
    (layout_dir / "rsu_config.json").write_text(json.dumps(config_payload, indent=2), encoding="utf-8")

    add_lines = []
    add_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    add_lines.append('<additional xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/additional_file.xsd">')

    def diamond_shape(x: float, y: float, size: float) -> str:
        top = (x, y + size)
        right = (x + size, y)
        bottom = (x, y - size)
        left = (x - size, y)
        return (
            f"{top[0]:.2f},{top[1]:.2f} "
            f"{right[0]:.2f},{right[1]:.2f} "
            f"{bottom[0]:.2f},{bottom[1]:.2f} "
            f"{left[0]:.2f},{left[1]:.2f} "
            f"{top[0]:.2f},{top[1]:.2f}"
        )

    for rsu in rsus:
        x, y = rsu["position"]
        color = "0,0,1" if rsu["tier"] == "TIER1" else "0,0.6,0.2"
        rsu_type = "tier1_rsu" if rsu["tier"] == "TIER1" else "tier2_rsu"
        marker_size = 16.0 if rsu["tier"] == "TIER1" else 12.0
        marker_width = 2.0 if rsu["tier"] == "TIER1" else 1.4
        add_lines.append(
            f'  <poi id="{rsu["rsu_id"]}" type="{rsu_type}" x="{x:.2f}" y="{y:.2f}" color="{color}" layer="10"/>'
        )
        add_lines.append(
            f'  <poly id="{rsu["rsu_id"]}_SYMBOL" type="rsu_symbol" color="{color}" fill="false" lineWidth="{marker_width:.1f}" layer="11" shape="{diamond_shape(x, y, marker_size)}"/>'
        )
    add_lines.append("</additional>")
    (layout_dir / "rsu.add.xml").write_text("\n".join(add_lines) + "\n", encoding="utf-8")

    return len(rsus)


def write_sumocfg(layout_dir: Path) -> None:
    cfg_lines = []
    cfg_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    cfg_lines.append('<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">')
    cfg_lines.append("  <input>")
    cfg_lines.append('    <net-file value="map.net.xml"/>')
    cfg_lines.append('    <route-files value="routes_new.rou.xml"/>')
    cfg_lines.append('    <additional-files value="rsu.add.xml"/>')
    cfg_lines.append("  </input>")
    cfg_lines.append("")
    cfg_lines.append("  <output>")
    cfg_lines.append('    <summary-output value="output/summary_new.xml"/>')
    cfg_lines.append('    <tripinfo-output value="output/tripinfo_new.xml"/>')
    cfg_lines.append("  </output>")
    cfg_lines.append("")
    cfg_lines.append("  <time>")
    cfg_lines.append('    <begin value="0"/>')
    cfg_lines.append('    <end value="3600"/>')
    cfg_lines.append('    <step-length value="1"/>')
    cfg_lines.append("  </time>")
    cfg_lines.append("")
    cfg_lines.append("  <processing>")
    cfg_lines.append('    <time-to-teleport value="300"/>')
    cfg_lines.append("  </processing>")
    cfg_lines.append("")
    cfg_lines.append("  <gui_only>")
    cfg_lines.append('    <gui-settings-file value="../sumo_simulation/maps/gui-settings.cfg"/>')
    cfg_lines.append('    <start value="true"/>')
    cfg_lines.append('    <quit-on-end value="false"/>')
    cfg_lines.append("  </gui_only>")
    cfg_lines.append("</configuration>")

    (layout_dir / "simulation_new.sumocfg").write_text("\n".join(cfg_lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate layout_new SUMO assets")
    parser.add_argument("--layout-dir", default=str(Path(__file__).resolve().parent), help="Directory containing map.net.xml")
    parser.add_argument("--net-file", default="map.net.xml", help="SUMO network file name")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for route generation")
    parser.add_argument("--rsu-interval", type=float, default=300.0, help="Tier-2 RSU spacing along roads in meters")
    args = parser.parse_args()

    if args.rsu_interval <= 0:
        raise ValueError("--rsu-interval must be positive")

    layout_dir = Path(args.layout_dir).resolve()
    net_path = layout_dir / args.net_file
    if not net_path.exists():
        raise FileNotFoundError(f"Net file not found: {net_path}")

    tree = ET.parse(net_path)
    root = tree.getroot()

    edge_data: Dict[str, Dict[str, object]] = {}
    for edge in root.findall("edge"):
        edge_id = edge.get("id")
        if not edge_id:
            continue
        if edge.get("function") == "internal" or edge_id.startswith(":"):
            continue
        if not is_drivable_edge(edge):
            continue

        lane = edge.find("lane")
        if lane is None:
            continue

        shape_points = parse_shape_endpoints(lane.get("shape", ""))
        start, end = (None, None)
        if shape_points is not None:
            start, end = shape_points

        edge_data[edge_id] = {
            "from": edge.get("from"),
            "to": edge.get("to"),
            "length": float(lane.get("length", "0")),
            "start": start,
            "end": end,
        }

    adjacency: Dict[str, List[str]] = defaultdict(list)
    for connection in root.findall("connection"):
        src = connection.get("from")
        dst = connection.get("to")
        if src in edge_data and dst in edge_data and dst not in adjacency[src]:
            adjacency[src].append(dst)

    traffic_light_positions: Dict[str, Tuple[float, float]] = {}
    for junction in root.findall("junction"):
        if junction.get("type") != "traffic_light":
            continue
        junction_id = junction.get("id")
        if not junction_id:
            continue
        x = float(junction.get("x", "0"))
        y = float(junction.get("y", "0"))
        traffic_light_positions[junction_id] = (x, y)

    routes = build_routes(edge_data, adjacency, set(traffic_light_positions.keys()), seed=args.seed)
    if not routes:
        raise RuntimeError("Could not generate any valid routes from map.net.xml")

    route_scores = []
    for path in routes:
        score = 0
        for edge_id in path:
            from_j = edge_data[edge_id].get("from")
            to_j = edge_data[edge_id].get("to")
            if from_j in traffic_light_positions or to_j in traffic_light_positions:
                score += 1
        route_scores.append(score)

    write_routes_file(layout_dir, routes, route_scores)
    rsu_count = write_rsu_config_files(
        layout_dir,
        traffic_light_positions,
        edge_data,
        tier2_interval_m=args.rsu_interval,
    )
    write_sumocfg(layout_dir)

    (layout_dir / "output").mkdir(exist_ok=True)

    print("Generated layout assets:")
    print(f"  - Net file: {net_path}")
    print(f"  - Routes:   {layout_dir / 'routes_new.rou.xml'}")
    print(f"  - RSU add:  {layout_dir / 'rsu.add.xml'}")
    print(f"  - RSU cfg:  {layout_dir / 'rsu_config.json'}")
    print(f"  - SUMO cfg: {layout_dir / 'simulation_new.sumocfg'}")
    print(f"  - Routes generated: {len(routes)}")
    print(f"  - RSUs generated:   {rsu_count}")


if __name__ == "__main__":
    main()
