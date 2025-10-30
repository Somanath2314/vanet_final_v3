#!/usr/bin/env python3
"""Quick test to verify queue length logic"""

# Simulate controlled lanes
controlled_lanes = [
    "E5_0", "E5_1", "E5_2",  # South approach (north-bound) - should be 'N'
    "E6_0", "E6_1", "E6_2",  # North approach (south-bound) - should be 'S'
    "E2_0", "E2_1", "E2_2",  # East approach (west-bound) - should be 'W'
    "E4_0", "E4_1", "E4_2",  # West approach (east-bound) - should be 'E'
]

queue_lengths = {"N": 0, "S": 0, "E": 0, "W": 0}

for lane in controlled_lanes:
    halting = 5  # Simulate 5 vehicles
    if "_0" in lane or "E5_" in lane or "E7_" in lane:  # South approach
        queue_lengths["N"] += halting
        print(f"{lane} -> N (halting={halting})")
    elif "_1" in lane or "E6_" in lane or "E8_" in lane:  # North approach
        queue_lengths["S"] += halting
        print(f"{lane} -> S (halting={halting})")
    elif "_2" in lane or "E4_" in lane:  # West approach
        queue_lengths["E"] += halting
        print(f"{lane} -> E (halting={halting})")
    elif "_3" in lane or "E2_" in lane:  # East approach
        queue_lengths["W"] += halting
        print(f"{lane} -> W (halting={halting})")

print(f"\nQueue lengths: {queue_lengths}")
