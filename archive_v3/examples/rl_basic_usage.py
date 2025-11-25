#!/usr/bin/env python3
"""
Basic RL Usage Example
Demonstrates how to use the RL traffic controller with SUMO
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import traci
from rl_module.rl_traffic_controller import RLTrafficController


def main():
    """Run basic RL traffic control example"""
    
    # SUMO configuration
    sumo_config = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'sumo_simulation', 
        'simulation.sumocfg'
    )
    
    # Start SUMO
    print("Starting SUMO simulation...")
    sumo_cmd = [
        "sumo-gui",  # Use sumo-gui for visualization, or "sumo" for headless
        "-c", sumo_config,
        "--start",
        "--quit-on-end"
    ]
    
    try:
        traci.start(sumo_cmd)
        print("✓ SUMO started successfully")
    except Exception as e:
        print(f"✗ Failed to start SUMO: {e}")
        return
    
    # Configure RL controller
    rl_config = {
        'beta': 20,                    # Observe 20 vehicles
        'algorithm': 'DQN',            # Use DQN algorithm
        'tl_constraint_min': 5,        # Min 5 seconds before light change
        'tl_constraint_max': 60,       # Max 60 seconds before forced change
        'horizon': 1000,               # Episode length
    }
    
    # Create RL controller
    print("\nInitializing RL controller...")
    rl_controller = RLTrafficController(mode='inference', config=rl_config)
    
    if not rl_controller.initialize(sumo_connected=True):
        print("✗ Failed to initialize RL controller")
        traci.close()
        return
    
    print("✓ RL controller initialized")
    print(f"  Controlling {len(rl_controller.config['action_spec'])} traffic lights")
    
    # Run simulation with RL control
    print("\nRunning simulation with RL control...")
    print("Press Ctrl+C to stop\n")
    
    try:
        step = 0
        total_reward = 0
        
        while step < 1000:  # Run for 1000 steps
            # Execute RL step
            metrics = rl_controller.step()
            
            if 'error' in metrics:
                print(f"Error: {metrics['error']}")
                break
            
            # Update statistics
            total_reward += metrics.get('reward', 0)
            
            # Print progress every 100 steps
            if step % 100 == 0:
                print(f"Step {step:4d} | "
                      f"Reward: {metrics.get('reward', 0):7.2f} | "
                      f"Avg Speed: {metrics.get('mean_speed', 0):6.2f} km/h | "
                      f"Avg Emission: {metrics.get('mean_emission', 0):8.2f} mg")
            
            step += 1
        
        # Final statistics
        print("\n" + "=" * 60)
        print("Simulation Complete")
        print("=" * 60)
        print(f"Total steps: {step}")
        print(f"Total reward: {total_reward:.2f}")
        print(f"Average reward per step: {total_reward/step:.2f}")
        
        # Get final metrics
        final_metrics = rl_controller.get_metrics()
        print(f"\nRL Controller Metrics:")
        print(f"  Total episodes: {final_metrics['total_episodes']}")
        print(f"  Avg episode reward: {final_metrics['avg_episode_reward']:.2f}")
        print(f"  Avg episode length: {final_metrics['avg_episode_length']:.0f}")
        
    except KeyboardInterrupt:
        print("\n\nSimulation interrupted by user")
    except Exception as e:
        print(f"\n✗ Simulation error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        print("\nCleaning up...")
        rl_controller.close()
        traci.close()
        print("✓ Done")


if __name__ == '__main__':
    main()
