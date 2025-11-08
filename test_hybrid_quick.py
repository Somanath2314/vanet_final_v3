#!/usr/bin/env python3
"""
Quick test of hybrid control - runs automatically without user input.
"""

import os
import sys
import traci

# Add paths
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("HYBRID TRAFFIC CONTROL - QUICK TEST")
print("=" * 80)

try:
    from sumo_simulation.traffic_controller import AdaptiveTrafficController
    from rl_module.rl_traffic_controller import RLTrafficController
    
    # Use simulation_headless config (has emergency vehicles + traffic lights)
    sumo_config = "sumo_simulation/simulation_headless.sumocfg"
    
    if not os.path.exists(sumo_config):
        print(f"❌ Config not found: {sumo_config}")
        sys.exit(1)
    
    print(f"✓ Using: {sumo_config}")
    
    # Start SUMO
    print("✓ Starting SUMO...")
    sumo_cmd = ["sumo", "-c", sumo_config, "--start", "--quit-on-end", "--no-warnings"]
    traci.start(sumo_cmd)
    
    # Initialize controllers
    print("✓ Initializing traffic controller...")
    controller = AdaptiveTrafficController(
        output_dir="./output_hybrid_test",
        mode="rule"
    )
    
    print("✓ Initializing RL controller...")
    rl_controller = RLTrafficController(
        mode='inference',
        model_path=None,
        config={}
    )
    
    if not rl_controller.initialize(sumo_connected=True):
        print("❌ RL controller initialization failed")
        traci.close()
        sys.exit(1)
    
    print("\n" + "=" * 80)
    print("Running HYBRID control (100 steps)...")
    print("=" * 80)
    
    # Run hybrid control
    controller.run_simulation_with_rl(rl_controller, steps=100)
    
    print("\n" + "=" * 80)
    print("✅ HYBRID CONTROL TEST PASSED!")
    print("=" * 80)
    
except KeyboardInterrupt:
    print("\n⚠️  Interrupted by user")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    try:
        traci.close()
    except:
        pass
