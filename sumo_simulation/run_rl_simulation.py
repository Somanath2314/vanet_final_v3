#!/usr/bin/env python3
"""
RL-based SUMO simulation with GUI
Combines RL control with SUMO-GUI visualization
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sumo_simulation.traffic_controller import AdaptiveTrafficController
from sumo_simulation.sensors.sensor_network import SensorNetwork

def main():
    """Run RL-based simulation with GUI"""
    print("=" * 60)
    print("VANET RL Traffic Control - SUMO Simulation with GUI")
    print("=" * 60)
    print()

    # Create output directory if it doesn't exist
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)

    # Create controller
    controller = AdaptiveTrafficController()

    # Configuration file path
    config_path = os.path.join(os.path.dirname(__file__), "simulation.sumocfg")

    if not os.path.exists(config_path):
        print(f"Error: Configuration file not found: {config_path}")
        return

    print(f"Using configuration: {config_path}")
    print()

    # Connect to SUMO (this launches SUMO-GUI)
    if controller.connect_to_sumo(config_path):
        print("✓ Connected to SUMO successfully")
        print("✓ SUMO-GUI window should be open")
        print()
        print("Controls:")
        print("  - Space: Play/Pause")
        print("  - +/-: Speed up/slow down")
        print("  - Ctrl+C: Stop simulation")
        print()

        # Import and initialize RL controller
        try:
            from rl_module.rl_traffic_controller import RLTrafficController

            # Create RL controller
            rl_controller = RLTrafficController(mode='inference')

            if rl_controller.initialize(sumo_connected=True):
                print("✓ RL Controller initialized")

                # Load trained model if available
                model_path = os.path.join(os.path.dirname(__file__), '..', 'rl_module', 'models', 'dqn_traffic_model.pth')
                if os.path.exists(model_path):
                    rl_controller.load_model(model_path)
                    print(f"✓ Loaded trained RL model")
                else:
                    print("⚠ No trained model found, using random policy")

                print()
                print("Starting RL-based traffic control simulation...")
                print("-" * 60)

                # Initialize sensor network and central pole
                sensor_network = SensorNetwork()
                sensor_network.initialize_central_pole()

                try:
                    # Run simulation with RL control for 1000 steps (about 16 minutes)
                    controller.run_simulation_with_rl(rl_controller, 1000)
                except KeyboardInterrupt:
                    print("\n\nRL simulation stopped by user")
                except Exception as e:
                    print(f"\n\nRL simulation error: {e}")
                    import traceback
                    traceback.print_exc()
                finally:
                    controller.stop_simulation()
                    print("\n✓ RL Simulation ended")
            else:
                print("✗ Failed to initialize RL controller")
                print("Falling back to rule-based control...")
                controller.run_simulation(1000)

        except ImportError as e:
            print(f"✗ RL module not available: {e}")
            print("Falling back to rule-based control...")
            controller.run_simulation(1000)

    else:
        print("✗ Failed to connect to SUMO")
        print("\nTroubleshooting:")
        print("1. Make sure SUMO-GUI is installed: sumo-gui --version")
        print("2. Check if config file exists")
        print("3. Make sure no other SUMO instance is running")
        print("4. Try: killall sumo-gui")

if __name__ == "__main__":
    main()
