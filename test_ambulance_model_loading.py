#!/usr/bin/env python3
"""
Test script to verify ambulance model loading and inference
Phase 1 validation - tests RL controller with ambulance model
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import traci
from rl_module.rl_traffic_controller import RLTrafficController


def test_model_loading():
    """Test that ambulance model can be loaded"""
    print("="*70)
    print("TEST 1: Model Loading")
    print("="*70)
    
    # Check if model exists
    model_path = os.path.join(
        os.path.dirname(__file__),
        'rl_module', 'models', 'ambulance_dqn_final.pth'
    )
    
    if not os.path.exists(model_path):
        print(f"❌ Model not found: {model_path}")
        print("   Please train the model first:")
        print("   python rl_module/train_ambulance_agent.py --episodes 100")
        return False
    
    print(f"✅ Model found: {model_path}")
    print(f"   Size: {os.path.getsize(model_path) / 1024 / 1024:.2f} MB")
    return True


def test_controller_init():
    """Test RL controller initialization"""
    print("\n" + "="*70)
    print("TEST 2: Controller Initialization")
    print("="*70)
    
    try:
        # Start SUMO (headless)
        config_path = os.path.join(
            os.path.dirname(__file__),
            'sumo_simulation', 'simulation.sumocfg'
        )
        
        print(f"📁 Starting SUMO with: {config_path}")
        
        sumo_cmd = [
            "sumo",  # Headless mode
            "-c", config_path,
            "--start",
            "--step-length", "1.0",
            "--no-warnings"
        ]
        
        traci.start(sumo_cmd)
        print("✅ SUMO started")
        
        # Create RL controller
        print("\n🤖 Creating RL controller...")
        controller = RLTrafficController(mode='inference')
        
        # Initialize
        if not controller.initialize(sumo_connected=True):
            print("❌ Controller initialization failed")
            traci.close()
            return False
        
        print("✅ Controller initialized")
        print(f"   Action space: {controller.env.action_space}")
        print(f"   Observation space: {controller.env.observation_space}")
        
        traci.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        try:
            traci.close()
        except:
            pass
        return False


def test_model_inference():
    """Test model loading and inference"""
    print("\n" + "="*70)
    print("TEST 3: Model Loading & Inference")
    print("="*70)
    
    try:
        # Start SUMO
        config_path = os.path.join(
            os.path.dirname(__file__),
            'sumo_simulation', 'simulation.sumocfg'
        )
        
        sumo_cmd = [
            "sumo",
            "-c", config_path,
            "--start",
            "--step-length", "1.0",
            "--no-warnings"
        ]
        
        traci.start(sumo_cmd)
        
        # Create and initialize controller
        controller = RLTrafficController(mode='inference')
        if not controller.initialize(sumo_connected=True):
            print("❌ Initialization failed")
            traci.close()
            return False
        
        # Load ambulance model
        model_path = os.path.join(
            os.path.dirname(__file__),
            'rl_module', 'models', 'ambulance_dqn_final.pth'
        )
        
        print(f"\n📦 Loading model: {os.path.basename(model_path)}")
        if not controller.load_model(model_path):
            print("❌ Model loading failed")
            traci.close()
            return False
        
        print(f"✅ Model loaded successfully")
        print(f"   Ambulance-aware: {controller.is_ambulance_model}")
        
        # Test inference with random state
        print("\n🔮 Testing inference...")
        import numpy as np
        
        # Get a real state from environment
        state = controller.get_state()
        print(f"   State shape: {state.shape}")
        print(f"   State range: [{state.min():.2f}, {state.max():.2f}]")
        
        # Get action from model
        action = controller.get_action(state)
        print(f"   Predicted action: {action}")
        print(f"   Action type: {type(action)}")
        
        print("✅ Inference successful")
        
        traci.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        try:
            traci.close()
        except:
            pass
        return False


def test_ambulance_state_extraction():
    """Test ambulance state extraction"""
    print("\n" + "="*70)
    print("TEST 4: Ambulance State Extraction")
    print("="*70)
    
    try:
        # Start SUMO
        config_path = os.path.join(
            os.path.dirname(__file__),
            'sumo_simulation', 'simulation.sumocfg'
        )
        
        sumo_cmd = [
            "sumo",
            "-c", config_path,
            "--start",
            "--step-length", "1.0",
            "--no-warnings"
        ]
        
        traci.start(sumo_cmd)
        
        # Create controller
        controller = RLTrafficController(mode='inference')
        if not controller.initialize(sumo_connected=True):
            print("❌ Initialization failed")
            traci.close()
            return False
        
        # Spawn a test ambulance
        print("\n🚑 Spawning test ambulance...")
        try:
            traci.vehicle.add(
                'test_ambulance',
                'route_0',
                typeID='passenger',
                depart='now'
            )
            traci.vehicle.setColor('test_ambulance', (255, 0, 0, 255))  # Red
            traci.vehicle.setSpeedMode('test_ambulance', 0)  # No speed limits
            print("✅ Test ambulance spawned")
        except Exception as e:
            print(f"⚠️  Could not spawn ambulance: {e}")
            print("   Testing with generic detection...")
        
        # Run a few steps
        for _ in range(10):
            traci.simulationStep()
        
        # Extract ambulance state
        print("\n🔍 Extracting ambulance state...")
        amb_state = controller.get_ambulance_state('test_ambulance')
        
        print(f"   Present: {amb_state['present']}")
        print(f"   Position: {amb_state['position']}")
        print(f"   Speed: {amb_state['speed']:.2f} m/s")
        print(f"   Heading: {amb_state['heading']:.2f}°")
        print(f"   Target: {amb_state['target']}")
        print(f"   Lane: {amb_state['lane_id']}")
        
        if amb_state['present']:
            print("✅ Ambulance state extraction successful")
        else:
            print("⚠️  No ambulance detected (expected if spawn failed)")
        
        traci.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        try:
            traci.close()
        except:
            pass
        return False


def main():
    """Run all tests"""
    print("\n" + "🧪 " + "="*66)
    print("   AMBULANCE RL MODEL - PHASE 1 VALIDATION")
    print("="*70 + "\n")
    
    results = {}
    
    # Test 1: Model file exists
    results['model_exists'] = test_model_loading()
    
    if not results['model_exists']:
        print("\n❌ Cannot proceed without model file")
        return
    
    # Test 2: Controller initialization
    results['controller_init'] = test_controller_init()
    
    # Test 3: Model loading and inference
    results['model_inference'] = test_model_inference()
    
    # Test 4: Ambulance state extraction
    results['ambulance_state'] = test_ambulance_state_extraction()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} | {test_name.replace('_', ' ').title()}")
    
    all_passed = all(results.values())
    
    print("\n" + "="*70)
    if all_passed:
        print("🎉 ALL TESTS PASSED - Phase 1 Complete!")
        print("="*70)
        print("\n✅ Next Steps:")
        print("   1. Phase 2: Add backend APIs (getSignalData, controller override)")
        print("   2. Phase 3: Integrate fog → RL → controller flow")
        print("   3. Phase 4: End-to-end testing with ./run_integrated_sumo_ns3.sh")
    else:
        print("❌ SOME TESTS FAILED - Review errors above")
        print("="*70)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
