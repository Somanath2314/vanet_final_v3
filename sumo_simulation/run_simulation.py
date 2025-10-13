#!/usr/bin/env python3
"""
Simple script to run SUMO simulation with adaptive traffic control
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sumo_simulation.traffic_controller import AdaptiveTrafficController

def main():
    """Run the simulation"""
    print("=" * 60)
    print("VANET Adaptive Traffic Control - SUMO Simulation")
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
        print("\nAvailable config files:")
        for f in os.listdir(os.path.dirname(__file__)):
            if f.endswith('.sumocfg'):
                print(f"  - {f}")
        return
    
    print(f"Using configuration: {config_path}")
    print()
    
    # Connect to SUMO
    if controller.connect_to_sumo(config_path):
        print("✓ Connected to SUMO successfully")
        print("✓ SUMO-GUI window should be open")
        print()
        print("Controls:")
        print("  - Space: Play/Pause")
        print("  - +/-: Speed up/slow down")
        print("  - Ctrl+C: Stop simulation")
        print()
        print("Starting simulation...")
        print("-" * 60)
        
        try:
            # Run for 3600 simulation seconds (1 hour)
            controller.run_simulation(3600)
        except KeyboardInterrupt:
            print("\n\nSimulation stopped by user")
        finally:
            controller.stop_simulation()
            print("\n✓ Simulation ended")
    else:
        print("✗ Failed to connect to SUMO")
        print("\nTroubleshooting:")
        print("1. Make sure SUMO is installed: sumo --version")
        print("2. Check if config file exists")
        print("3. Make sure no other SUMO instance is running")
        print("4. Try: killall sumo-gui")

if __name__ == "__main__":
    main()
