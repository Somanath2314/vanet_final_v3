#!/usr/bin/env python3
"""
Main Simulation Runner
Supports Rule-Based or RL-Based Traffic Control
Automatically writes all required outputs:
 - tripinfo.xml
 - summary.xml
 - v2i_packets.csv
 - v2i_metrics.csv
"""

import os
import sys
import traceback

# Add parent folder for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sumo_simulation.traffic_controller import AdaptiveTrafficController
from sumo_simulation.sensors.sensor_network import SensorNetwork

# RL module (optional)
try:
    from rl_module.rl_traffic_controller import RLTrafficController
    RL_AVAILABLE = True
except ImportError:
    RL_AVAILABLE = False


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["rule", "rl"], default="rule", help="Simulation mode")
    ap.add_argument("--out", default="./output", help="Output directory")
    ap.add_argument("--steps", type=int, default=1000, help="Simulation steps")
    args = ap.parse_args()

    output_dir = os.path.abspath(args.out)
    os.makedirs(output_dir, exist_ok=True)

    print("="*60)
    print(f"VANET SUMO Simulation ({args.mode}-based)")
    print(f"Outputs will be saved to: {output_dir}")
    print("="*60)

    # Initialize controller
    controller = AdaptiveTrafficController()
    sensor_network = SensorNetwork()
    sensor_network.initialize_central_pole()

    # SUMO config
    config_path = os.path.join(os.path.dirname(__file__), "simulation.sumocfg")
    if not os.path.exists(config_path):
        print(f"Error: SUMO config not found: {config_path}")
        return

    if not controller.connect_to_sumo(config_path):
        print("Error: Could not connect to SUMO")
        return

    try:
        if args.mode == "rl" and RL_AVAILABLE:
            rl_controller = RLTrafficController(mode='inference')
            rl_controller.initialize(sumo_connected=True)
            model_path = os.path.join(os.path.dirname(__file__), '..', 'rl_module', 'models', 'dqn_traffic_model.pth')
            if os.path.exists(model_path):
                rl_controller.load_model(model_path)
                print("Loaded RL model")
            else:
                print("No RL model found, using random policy")

            controller.run_simulation_with_rl(rl_controller, args.steps)
        else:
            print("Running Rule-Based simulation")
            controller.run_simulation(args.steps)

    except KeyboardInterrupt:
        print("\nSimulation interrupted by user")
    except Exception as e:
        print("Simulation error:", e)
        traceback.print_exc()
    finally:
        # Stop simulation
        controller.stop_simulation()

        # Save SUMO outputs
        sumo_output_files = ["tripinfo.xml", "summary.xml"]
        for fname in sumo_output_files:
            src = os.path.join(os.path.dirname(__file__), fname)
            if os.path.exists(src):
                dst = os.path.join(output_dir, fname)
                os.replace(src, dst)

        # Save VANET outputs
        if hasattr(controller, "packets_df"):
            controller.packets_df.to_csv(os.path.join(output_dir, "v2i_packets.csv"), index=False)
        if hasattr(controller, "metrics_df"):
            controller.metrics_df.to_csv(os.path.join(output_dir, "v2i_metrics.csv"), index=False)

        print(f"\n✓ Simulation finished. Outputs saved in {output_dir}")
        print("Files should include: tripinfo.xml, summary.xml, v2i_packets.csv, v2i_metrics.csv")


if __name__ == "__main__":
    main()
