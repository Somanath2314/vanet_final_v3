#!/usr/bin/env python3
"""
Integrated SUMO + NS3 VANET Simulation
Combines SUMO traffic simulation with NS3-based network simulation
- SUMO: Vehicle movements, traffic control, RL integration
- NS3 Bridge: WiFi (802.11p) for V2V, WiMAX for emergency V2I
- Full RL support with trained models
"""

import os
import sys
import time
import argparse
import traceback

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sumo_simulation.traffic_controller import AdaptiveTrafficController
from sumo_simulation.sensors.sensor_network import SensorNetwork
from sumo_simulation.sumo_ns3_bridge import SUMONS3Bridge

# RL module (optional)
try:
    from rl_module.rl_traffic_controller import RLTrafficController
    RL_AVAILABLE = True
except ImportError:
    RL_AVAILABLE = False
    print("⚠️  RL module not available")


def main():
    parser = argparse.ArgumentParser(description='Integrated SUMO + NS3 VANET Simulation')
    parser.add_argument('--mode', choices=['rule', 'rl'], default='rule',
                       help='Traffic control mode: rule-based or RL-based')
    parser.add_argument('--steps', type=int, default=1000,
                       help='Number of simulation steps')
    parser.add_argument('--gui', action='store_true',
                       help='Use SUMO-GUI instead of SUMO')
    parser.add_argument('--output', default='./output',
                       help='Output directory for results')
    args = parser.parse_args()

    # Create output directory
    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)

    print("="*70)
    print("🚗 INTEGRATED SUMO + NS3 VANET SIMULATION")
    print("="*70)
    print(f"Mode: {args.mode.upper()}-based traffic control")
    print(f"Steps: {args.steps}")
    print(f"GUI: {'Yes' if args.gui else 'No'}")
    print(f"Output: {output_dir}")
    print("="*70)
    print()

    # Initialize components
    print("🔧 Initializing simulation components...")
    traffic_controller = AdaptiveTrafficController()
    sensor_network = SensorNetwork()
    ns3_bridge = SUMONS3Bridge()
    
    # Initialize RSUs at intersection positions
    # These are typical intersection positions in the SUMO network
    rsu_positions = [
        (500.0, 500.0),   # Intersection 1
        (1500.0, 500.0),  # Intersection 2
        (500.0, 1500.0),  # Intersection 3
        (1500.0, 1500.0)  # Intersection 4
    ]
    ns3_bridge.initialize_rsus(rsu_positions)
    
    # Connect to SUMO
    config_path = os.path.join(os.path.dirname(__file__), "simulation.sumocfg")
    if not os.path.exists(config_path):
        print(f"❌ Error: SUMO config not found: {config_path}")
        return

    print(f"📁 Using SUMO config: {config_path}")
    
    # Connect to SUMO with appropriate binary
    if not traffic_controller.connect_to_sumo(config_path, use_gui=args.gui):
        print("❌ Error: Could not connect to SUMO")
        return

    print("✅ Connected to SUMO successfully")
    
    # Initialize sensor network after SUMO connection
    try:
        sensor_network.initialize_central_pole()
        print("✅ Sensor network initialized")
    except Exception as e:
        print(f"⚠️  Sensor network initialization warning: {e}")
        print("   Continuing without sensor network...")
    
    if args.gui:
        print("\n🖥️  SUMO-GUI Controls:")
        print("  Space: Play/Pause")
        print("  +/-: Speed up/slow down")
        print("  Ctrl+C: Stop simulation")
    
    print()
    print("🌐 Network Simulation:")
    print(f"  V2V Protocol: WiFi 802.11p (Range: {ns3_bridge.wifi_range}m)")
    print(f"  V2I Protocol: WiMAX for emergency, WiFi for normal (Range: {ns3_bridge.wimax_range}m)")
    print(f"  RSUs: {len(rsu_positions)} at intersections")
    print()

    # Initialize RL controller if needed
    rl_controller = None
    if args.mode == 'rl' and RL_AVAILABLE:
        print("🤖 Initializing RL controller...")
        try:
            rl_controller = RLTrafficController(mode='inference')
            if rl_controller.initialize(sumo_connected=True):
                model_path = os.path.join(os.path.dirname(__file__), '..', 
                                         'rl_module', 'models', 'dqn_traffic_model.pth')
                if os.path.exists(model_path):
                    rl_controller.load_model(model_path)
                    print("✅ Loaded trained RL model from:", model_path)
                else:
                    print("⚠️  No trained model found at:", model_path)
                    print("   Using random policy for exploration")
                print("✅ RL controller ready")
            else:
                print("❌ Failed to initialize RL controller")
                rl_controller = None
        except Exception as e:
            print(f"❌ RL initialization error: {e}")
            rl_controller = None
    
    if args.mode == 'rl' and not RL_AVAILABLE:
        print("⚠️  RL module not available, using rule-based control")
    
    if args.mode == 'rl' and rl_controller is None:
        print("⚠️  Falling back to rule-based control")
        args.mode = 'rule'

    print()
    print("🚀 Starting integrated simulation...")
    print("-"*70)
    
    try:
        step = 0
        start_time = time.time()
        last_print_time = start_time
        
        import traci
        
        while step < args.steps:
            # Check if simulation should continue
            if traci.simulation.getMinExpectedNumber() <= 0:
                print("\n⚠️  No more vehicles in simulation")
                break
            
            # Advance SUMO simulation
            if rl_controller:
                # RL-based control
                traci.simulationStep()
                current_time = traci.simulation.getTime()
                
                # RL control logic every 10 steps
                if step % 10 == 0:
                    try:
                        # Get state from traffic controller
                        state = rl_controller.get_state()
                        # Get action from RL agent
                        action = rl_controller.get_action(state)
                        # Apply action to traffic lights
                        rl_controller.apply_action(action)
                    except Exception as e:
                        print(f"⚠️  RL control error: {e}")
                
                # Update NS3 network simulation
                ns3_bridge.step(current_time)
            else:
                # Rule-based control - use traffic controller's built-in step
                if not traffic_controller.run_simulation_step():
                    break
                
                # Get current simulation time
                current_time = traci.simulation.getTime()
                
                # Update NS3 network simulation
                ns3_bridge.step(current_time)
            
            # Print progress every 5 seconds
            if time.time() - last_print_time >= 5.0:
                metrics = ns3_bridge.get_metrics()
                print(f"Step {step}/{args.steps} | "
                      f"Vehicles: {metrics['vehicles']['total']} "
                      f"(Emergency: {metrics['vehicles']['emergency']}) | "
                      f"WiFi PDR: {metrics['v2v_wifi']['pdr']*100:.1f}% | "
                      f"WiMAX PDR: {metrics['v2i_wimax']['pdr']*100:.1f}% | "
                      f"Avg Delay: {metrics['combined']['average_delay_ms']:.1f}ms")
                last_print_time = time.time()
            
            step += 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Simulation interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Simulation error: {e}")
        traceback.print_exc()
    finally:
        # Stop SUMO
        traffic_controller.stop_simulation()
        
        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        
        print()
        print("-"*70)
        print(f"✅ Simulation completed in {elapsed_time:.1f} seconds")
        
        # Print network metrics summary
        ns3_bridge.print_summary()
        
        # Save results
        results_file = os.path.join(output_dir, 'integrated_simulation_results.json')
        ns3_bridge.save_results(results_file)
        
        # Save SUMO outputs
        print(f"\n📁 Saving outputs to {output_dir}...")
        sumo_output_files = ["tripinfo.xml", "summary.xml"]
        for fname in sumo_output_files:
            src = os.path.join(os.path.dirname(__file__), fname)
            if os.path.exists(src):
                import shutil
                dst = os.path.join(output_dir, fname)
                shutil.copy2(src, dst)
                print(f"  ✅ Saved {fname}")
        
        # Save traffic controller outputs
        if hasattr(traffic_controller, "packets_df") and traffic_controller.packets_df is not None:
            packets_file = os.path.join(output_dir, "v2i_packets.csv")
            traffic_controller.packets_df.to_csv(packets_file, index=False)
            print(f"  ✅ Saved v2i_packets.csv")
        
        if hasattr(traffic_controller, "metrics_df") and traffic_controller.metrics_df is not None:
            metrics_file = os.path.join(output_dir, "v2i_metrics.csv")
            traffic_controller.metrics_df.to_csv(metrics_file, index=False)
            print(f"  ✅ Saved v2i_metrics.csv")
        
        print(f"\n✅ All results saved to: {output_dir}")
        print(f"📊 Main results file: {results_file}")


if __name__ == "__main__":
    main()
