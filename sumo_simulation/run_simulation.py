#!/usr/bin/env python3
import sys
import os
import argparse

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from traffic_controller import AdaptiveTrafficController

def main():
    parser = argparse.ArgumentParser(description="Run VANET Traffic Simulation")
    parser.add_argument("--mode", choices=["rule", "rl"], default="rule", help="Simulation mode")
    parser.add_argument("--out", default="./output_rule", help="Output folder")
    parser.add_argument("--steps", type=int, default=3600, help="Number of simulation steps")
    args = parser.parse_args()

    output_dir = os.path.abspath(args.out)
    os.makedirs(output_dir, exist_ok=True)

    controller = AdaptiveTrafficController(output_dir=output_dir, mode=args.mode)

    # SUMO config file
    config_path = os.path.join(os.path.dirname(__file__), "simulation.sumocfg")
    if not os.path.exists(config_path):
        print(f"Error: SUMO config not found: {config_path}")
        return

    if controller.connect_to_sumo(config_path):
        print(f"Starting {args.mode}-based simulation for {args.steps} steps...")
        controller.run_simulation(args.steps)
    else:
        print("Failed to start SUMO simulation")

if __name__ == "__main__":
    main()
