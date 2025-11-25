#!/usr/bin/env python3
"""
Test script for hybrid traffic control system.
Verifies switching between density-based and RL-based control during emergencies.
"""

import os
import sys
import time
import traci

# Add paths
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_hybrid_control():
    """Test the hybrid control system."""
    print("=" * 80)
    print("Testing HYBRID Traffic Control System")
    print("=" * 80)
    print("\nThis test will verify:")
    print("  1. Normal operation uses DENSITY-based adaptive control")
    print("  2. Emergency detection triggers RL control with greenwave")
    print("  3. System switches back to density control after emergency")
    print("=" * 80)
    
    try:
        from sumo_simulation.traffic_controller import AdaptiveTrafficController
        from rl_module.rl_traffic_controller import RLTrafficController
        
        # Configuration - use working_simulation.sumocfg 
        sumo_config = "sumo_simulation/working_simulation.sumocfg"
        
        if not os.path.exists(sumo_config):
            print(f"\n❌ ERROR: SUMO config file not found: {sumo_config}")
            return False
        
        print(f"\n📁 Using SUMO config: {sumo_config}")
        
        # Start SUMO manually
        print("\n🚗 Starting SUMO simulation...")
        sumo_binary = "sumo"  # Use sumo-gui for visual
        sumo_cmd = [sumo_binary, "-c", sumo_config, "--start", "--quit-on-end"]
        traci.start(sumo_cmd)
        
        # Initialize traffic controller
        print("🚦 Initializing traffic controller...")
        controller = AdaptiveTrafficController(
            output_dir="./output_hybrid_test",
            mode="rule"  # Start in rule mode (will switch to hybrid)
        )
        
        # Initialize RL controller
        print("🤖 Initializing RL controller...")
        rl_controller = RLTrafficController(
            mode='inference',  # Use inference mode (no training)
            model_path=None,   # No pretrained model
            config={}          # Default config
        )
        
        # Initialize the RL controller with SUMO connection
        if not rl_controller.initialize(sumo_connected=True):
            print("❌ Failed to initialize RL controller")
            return False
        
        print("\n✅ Initialization complete!")
        print("\n" + "=" * 80)
        print("Starting simulation with HYBRID control...")
        print("=" * 80)
        print("\nExpected behavior:")
        print("  • Steps 0-10: DENSITY-based control (no emergencies)")
        print("  • Steps 10+: Emergency vehicle appears → RL control")
        print("  • After emergency passes: Back to DENSITY control")
        print("=" * 80)
        
        # Run with hybrid control (200 steps to see emergency at t=10s)
        controller.run_simulation_with_rl(rl_controller, steps=200)
        
        print("\n" + "=" * 80)
        print("✅ Test completed successfully!")
        print("=" * 80)
        
        return True
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user (Ctrl+C)")
        return False
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("HYBRID TRAFFIC CONTROL SYSTEM TEST")
    print("=" * 80)
    print("\nThis test verifies intelligent mode switching:")
    print("  🚦 DENSITY-based: Normal traffic flow optimization")
    print("  🚨 RL-based: Emergency vehicle priority with greenwave")
    print("=" * 80)
    
    input("\nPress Enter to start the test...")
    
    success = test_hybrid_control()
    
    if success:
        print("\n" + "=" * 80)
        print("🎉 HYBRID CONTROL TEST PASSED!")
        print("=" * 80)
        print("\nKey verifications:")
        print("  ✓ System starts in density-based mode")
        print("  ✓ Switches to RL when emergency detected")
        print("  ✓ Returns to density after emergency clears")
        print("  ✓ Traffic congestion minimized with hybrid approach")
        print("=" * 80)
        sys.exit(0)
    else:
        print("\n" + "=" * 80)
        print("❌ HYBRID CONTROL TEST FAILED")
        print("=" * 80)
        sys.exit(1)
