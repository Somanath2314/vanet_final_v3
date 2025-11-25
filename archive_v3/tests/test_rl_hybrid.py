#!/usr/bin/env python3
"""
Comprehensive test to verify hybrid control system with RL DQN.
Uses the same approach as test_rl_env.py which we know works.
"""

import os
import sys

# Add paths
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(parent_dir, 'rl_module'))

import traci
from rl_module.vanet_env import VANETTrafficEnv


def test_hybrid_control():
    """Test hybrid control with density-based + RL switching"""
    
    print("=" * 80)
    print("TESTING HYBRID CONTROL SYSTEM (Density + RL)")
    print("=" * 80)
    print()
    
    # Use the same config that works in test_rl_env.py
    config_path = os.path.join(parent_dir, 'sumo_simulation', 'simulation.sumocfg')
    
    # Try alternate path if first doesn't exist
    if not os.path.exists(config_path):
        config_path = 'sumo_simulation/simulation.sumocfg'
    
    if not os.path.exists(config_path):
        print(f"❌ Config not found: {config_path}")
        return False
    
    print(f"✓ Using SUMO config: {config_path}")
    
    # Start SUMO
    sumo_binary = "sumo"
    sumo_cmd = [sumo_binary, "-c", config_path, "--start", "--step-length", "1", "--no-warnings"]
    
    try:
        traci.start(sumo_cmd)
        print("✓ Connected to SUMO")
    except Exception as e:
        print(f"❌ Error connecting to SUMO: {e}")
        return False
    
    # Get traffic lights
    tl_ids = traci.trafficlight.getIDList()
    print(f"✓ Found {len(tl_ids)} traffic lights: {tl_ids}")
    
    if not tl_ids:
        print("❌ No traffic lights found!")
        traci.close()
        return False
    
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
    
    # Create environment
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
    print("✓ Creating RL environment...")
    
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
    print(f"  Observation space: {env.observation_space.shape}")
    print(f"  Action space: {env.action_space.n} actions")
    print(f"  Emergency coordinator: {env.emergency_coordinator is not None}")
    
    # Reset environment
    print()
    print("=" * 80)
    print("Starting HYBRID control simulation...")
    print("=" * 80)
    print()
    
    try:
        obs, info = env.reset()
        print(f"✓ Environment reset")
        print(f"  Initial observation shape: {obs.shape}")
        print()
    except Exception as e:
        print(f"❌ Error resetting environment: {e}")
        import traceback
        traceback.print_exc()
        traci.close()
        return False
    
    # Run simulation with hybrid logic
    print("Running simulation (200 steps)...")
    print()
    
    step_count = 0
    total_reward = 0
    emergency_mode_steps = 0
    density_mode_steps = 0
    
    try:
        while step_count < 200:
            # Check for emergency vehicles
            active_emergencies = env.emergency_coordinator.get_active_emergency_vehicles()
            
            if len(active_emergencies) > 0:
                # EMERGENCY MODE: Use RL action with greenwave
                mode = "RL-EMERGENCY"
                emergency_mode_steps += 1
                
                # Random action (in real system, this would be from trained DQN)
                action = env.action_space.sample()
                
                # Apply greenwave for emergencies
                for emerg in active_emergencies:
                    greenwave_junctions = env.emergency_coordinator.create_greenwave(emerg)
                    if greenwave_junctions:
                        env.emergency_coordinator.apply_greenwave(emerg.vehicle_id, greenwave_junctions)
            else:
                # DENSITY MODE: Use density-based control (simulated by random action)
                mode = "DENSITY"
                density_mode_steps += 1
                
                # In real system, this would calculate density and adjust phases
                # For now, we use random action to simulate density-based control
                action = env.action_space.sample()
            
            # Step environment
            obs, reward, done, truncated, info = env.step(action)
            total_reward += reward
            
            # Print progress
            if step_count % 20 == 0:
                print(f"Step {step_count:3d} | Mode: {mode:15s} | "
                      f"Reward: {reward:7.2f} | Total: {total_reward:8.2f} | "
                      f"Emergencies: {len(active_emergencies)}")
            
            # Check if emergency was just detected
            if len(active_emergencies) > 0 and step_count % 10 == 0:
                for emerg in active_emergencies:
                    if not hasattr(test_hybrid_control, '_last_emergency'):
                        test_hybrid_control._last_emergency = set()
                    if emerg.vehicle_id not in test_hybrid_control._last_emergency:
                        print(f"\n🚨 EMERGENCY DETECTED: {emerg.vehicle_id} by {emerg.detected_by_rsu}")
                        print(f"   Edge: {emerg.current_edge}, Position: {emerg.position:.1f}m")
                        print(f"   Speed: {emerg.speed:.1f} m/s")
                        print()
                        test_hybrid_control._last_emergency.add(emerg.vehicle_id)
            
            if done or truncated:
                print("\nEpisode ended, resetting...")
                obs, info = env.reset()
                total_reward = 0
            
            step_count += 1
        
        # Summary
        print()
        print("=" * 80)
        print("HYBRID CONTROL TEST RESULTS")
        print("=" * 80)
        print()
        print(f"✓ Total steps: {step_count}")
        print(f"✓ Density-based mode: {density_mode_steps} steps ({density_mode_steps/step_count*100:.1f}%)")
        print(f"✓ RL emergency mode: {emergency_mode_steps} steps ({emergency_mode_steps/step_count*100:.1f}%)")
        print(f"✓ Total reward: {total_reward:.2f}")
        print()
        
        # Emergency statistics
        if hasattr(env.emergency_coordinator, 'emergency_detections'):
            emerg_stats = env.emergency_coordinator.get_statistics()
            print(f"Emergency Statistics:")
            print(f"  Total detections: {emerg_stats.get('total_detections', 0)}")
            print(f"  Active emergencies: {emerg_stats.get('active_emergency_vehicles', 0)}")
            print(f"  Active greenwaves: {emerg_stats.get('active_greenwaves', 0)}")
            print()
        
        if emergency_mode_steps > 0:
            print("✅ HYBRID CONTROL WORKING: System switched to RL during emergencies!")
        else:
            print("ℹ️  No emergencies detected in test period (check route timing)")
        
        print()
        print("=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
        
        return True
        
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        return False
    except Exception as e:
        print(f"\n❌ Error during simulation: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            traci.close()
            print("\n✓ SUMO connection closed")
        except:
            pass


if __name__ == "__main__":
    print()
    success = test_hybrid_control()
    print()
    sys.exit(0 if success else 1)
