#!/usr/bin/env python3
"""
Integrated SUMO + NS3 VANET Simulation
Combines SUMO traffic simulation with NS3-based network simulation
- SUMO: Vehicle movements, traffic control, RL integration
- NS3 Bridge: WiFi (802.11p) for V2V, WiMAX for emergency V2I
- Full RL support with trained models
- Backend API server embedded for fog node communication
"""

import os
import sys
import time
import argparse
import traceback
import threading

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


def update_vehicle_cache():
    """
    Update vehicle data cache for backend API (thread-safe).
    Called by main simulation thread to avoid TraCI thread-safety issues.
    """
    import backend.app as backend_app
    import traci
    
    vehicle_ids = traci.vehicle.getIDList()
    vehicles_data = []
    
    for vehicle_id in vehicle_ids:
        try:
            pos = traci.vehicle.getPosition(vehicle_id)
            speed = traci.vehicle.getSpeed(vehicle_id)
            angle = traci.vehicle.getAngle(vehicle_id)
            lane = traci.vehicle.getLaneID(vehicle_id)
            vtype = traci.vehicle.getTypeID(vehicle_id)
            
            # Determine if emergency vehicle
            is_emergency = vehicle_id.startswith('emergency') or 'ambulance' in vehicle_id.lower()
            
            vehicles_data.append({
                "id": vehicle_id,
                "position": {"x": pos[0], "y": pos[1]},
                "speed": speed,
                "angle": angle,
                "lane": lane,
                "type": vtype,
                "is_emergency": is_emergency
            })
        except Exception:
            continue  # Vehicle left simulation
    
    # Update cache atomically
    backend_app.vehicles_data_cache = vehicles_data
    backend_app.last_vehicles_update = time.time()


def start_backend_server(traffic_controller, rl_controller):
    """
    Start Flask backend server in separate thread.
    Provides REST APIs for fog nodes to query state and send overrides.
    """
    # Import Flask app
    backend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend')
    sys.path.insert(0, backend_dir)
    
    import backend.app as backend_app
    
    # Inject traffic_controller and rl_controller into backend's global scope
    backend_app.traffic_controller = traffic_controller
    backend_app.rl_controller = rl_controller
    backend_app.simulation_running = True
    
    print("🌐 Starting Backend API Server on http://localhost:8000...")
    print("   Fog nodes can now query: GET /api/wimax/getSignalData")
    print("   Fog nodes can send overrides: POST /api/control/override")
    
    # Run Flask server (disable debug mode to avoid reloader in thread)
    backend_app.app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False, threaded=True)


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
    parser.add_argument('--no-backend', action='store_true',
                       help='Disable backend API server')
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
                # Priority order: ambulance model > general traffic models
                repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                models_dir = os.path.join(repo_root, 'rl_module', 'models')
                
                # Model candidates in priority order
                candidates = [
                    # Ambulance-aware models (highest priority)
                    (os.path.join(models_dir, 'ambulance_dqn_final.pth'), 'Ambulance-aware'),
                    (os.path.join(models_dir, 'ambulance_dqn_ep100.pth'), 'Ambulance-aware'),
                    (os.path.join(models_dir, 'ambulance_dqn_ep50.pth'), 'Ambulance-aware'),
                    # General traffic models (fallback)
                    (os.path.join(models_dir, 'dqn_traffic_final.pth'), 'General traffic'),
                    (os.path.join(models_dir, 'dqn_traffic_model.pth'), 'General traffic')
                ]

                loaded = False
                for model_path, model_type in candidates:
                    if os.path.exists(model_path):
                        print(f"🔍 Found {model_type} model: {os.path.basename(model_path)}")
                        if rl_controller.load_model(model_path):
                            print(f"✅ Loaded {model_type} RL model")
                            loaded = True
                            break
                        else:
                            print(f"⚠️  Failed to load model, trying next...")

                if not loaded:
                    print("⚠️  No trained model found in rl_module/models/")
                    print("   Available models should be:")
                    print("   - ambulance_dqn_final.pth (ambulance-aware)")
                    print("   - dqn_traffic_final.pth (general traffic)")
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

    # Start backend API server in separate thread (unless disabled)
    backend_thread = None
    backend_started = False
    if not args.no_backend:
        print()
        backend_thread = threading.Thread(
            target=start_backend_server,
            args=(traffic_controller, rl_controller),
            daemon=True
        )
        backend_thread.start()
        time.sleep(2)  # Give server time to start
        print("✅ Backend API server started on http://localhost:8000")
        backend_started = True

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
            
            # Advance SUMO one step
            traci.simulationStep()
            
            # Get current simulation time
            current_time = traci.simulation.getTime()
            
            # Edge Node Architecture: Each junction operates INDEPENDENTLY
            # - Each edge node uses LOCAL density sensors (N, S, E, W queue lengths)
            # - Makes INDEPENDENT decisions (no synchronization between J2 and J3)
            # - Only overridden by FOG node during emergencies via REST API
            
            # Local density-based control for EACH junction independently
            if not traffic_controller.update_traffic_lights():
                break
            
            # Update NS3 network simulation
            ns3_bridge.step(current_time)

            # Update sensor network (detect emergencies and update central pole color)
            try:
                sensor_network.detect_emergency_vehicles_and_update_pole()
            except Exception as e:
                print(f"⚠️  Sensor network update error: {e}")
            
            # Update vehicle cache for backend API (thread-safe)
            if backend_started:
                try:
                    update_vehicle_cache()
                except Exception as e:
                    pass  # Silently ignore cache update errors
            
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
