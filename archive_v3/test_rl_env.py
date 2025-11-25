#!/usr/bin/env python3
"""
Simple test to verify RL environment works without Ray/training.
This tests the emergency coordinator and basic RL functionality.
"""

import os
import sys

# Add paths
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import traci
from vanet_env import VANETTrafficEnv


def test_rl_environment():
    """Test the RL environment with SUMO"""
    
    print("=" * 70)
    print("Testing RL Environment with Emergency Coordinator")
    print("=" * 70)
    print()
    
    # SUMO configuration
    config_path = os.path.join(
        parent_dir,
        'sumo_simulation',
        'simulation.sumocfg'
    )
    
    if not os.path.exists(config_path):
        print(f"❌ Config not found: {config_path}")
        return False
    
    print(f"Using SUMO config: {config_path}")
    print()
    
    # Start SUMO (headless)
    sumo_binary = "sumo"
    sumo_cmd = [sumo_binary, "-c", config_path, "--start", "--step-length", "1"]
    
    try:
        traci.start(sumo_cmd)
        print("✓ Connected to SUMO")
    except Exception as e:
        print(f"❌ Error connecting to SUMO: {e}")
        return False
    
    # Get traffic lights for action spec
    tl_ids = traci.trafficlight.getIDList()
    print(f"✓ Found {len(tl_ids)} traffic lights: {tl_ids}")
    
    # Build action spec
    action_spec = {}
    for tl_id in tl_ids:
        try:
            logic = traci.trafficlight.getAllProgramLogics(tl_id)[0]
            phases = [phase.state for phase in logic.phases]
            action_spec[tl_id] = phases
            print(f"  {tl_id}: {len(phases)} phases")
        except Exception as e:
            print(f"  ⚠️  Error getting phases for {tl_id}: {e}")
    
    # Create environment config
    env_config = {
        'beta': 20,
        'action_spec': action_spec,
        'tl_constraint_min': 5,
        'tl_constraint_max': 60,
        'sim_step': 1.0,
        'algorithm': 'DQN',
        'horizon': 1000,
    }
    
    print()
    print("Creating RL environment...")
    
    try:
        env = VANETTrafficEnv(config=env_config)
        print("✓ Environment created")
    except Exception as e:
        print(f"❌ Error creating environment: {e}")
        import traceback
        traceback.print_exc()
        traci.close()
        return False
    
    print()
    print(f"Environment details:")
    print(f"  Observation space: {env.observation_space}")
    print(f"  Action space: {env.action_space}")
    print(f"  Traffic lights: {len(env.action_spec)}")
    
    # Reset environment
    print()
    print("Resetting environment...")
    try:
        state, info = env.reset()
        print(f"✓ Reset successful")
        print(f"  State shape: {state.shape}")
        print(f"  Info: {info}")
    except Exception as e:
        print(f"❌ Error resetting: {e}")
        import traceback
        traceback.print_exc()
        traci.close()
        return False
    
    # Run a few steps
    print()
    print("Running 100 simulation steps...")
    print("-" * 70)
    
    try:
        for step in range(100):
            # Take random action
            action = env.action_space.sample()
            
            # Step environment
            state, reward, terminated, truncated, info = env.step(action)
            
            # Print every 20 steps
            if step % 20 == 0:
                print(f"\nStep {step}:")
                print(f"  Reward: {reward:.2f}")
                print(f"  Mean speed: {info.get('mean_speed', 0):.2f} m/s")
                print(f"  Active emergencies: {info.get('active_emergencies', 0)}")
                print(f"  Completed vehicles: {info.get('completed_vehicles', 0)}")
                
                if info.get('active_emergencies', 0) > 0:
                    print(f"  🚨 Emergency vehicles active!")
                    print(f"  🟢 Greenwaves: {info.get('successful_greenwaves', 0)}")
            
            if terminated or truncated:
                print(f"\nEpisode ended at step {step}")
                break
        
        print()
        print("-" * 70)
        print("✅ TEST PASSED: Environment working correctly")
        
        # Print emergency coordinator stats
        if hasattr(env, 'emergency_coordinator'):
            stats = env.emergency_coordinator.get_statistics()
            print()
            print("Emergency Coordinator Statistics:")
            print(f"  Total detections: {stats.get('total_detections', 0)}")
            print(f"  Active emergencies: {stats.get('active_emergency_vehicles', 0)}")
            print(f"  Active greenwaves: {stats.get('active_greenwaves', 0)}")
            print(f"  RSU count: {stats.get('rsu_count', 0)}")
            print(f"  Junction count: {stats.get('junction_count', 0)}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during simulation: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            traci.close()
            print("\n✓ SUMO closed")
        except:
            pass


if __name__ == '__main__':
    success = test_rl_environment()
    sys.exit(0 if success else 1)
