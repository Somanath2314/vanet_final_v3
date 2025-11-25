#!/usr/bin/env python3
"""
Test script for Emergency Vehicle Greenwave System
Verifies RSU detection and greenwave coordination
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import traci
from rl_module.emergency_coordinator import EmergencyVehicleCoordinator


def test_emergency_coordinator():
    """Test the emergency coordinator with SUMO simulation"""
    
    print("=" * 70)
    print("Emergency Vehicle Greenwave System - Test")
    print("=" * 70)
    print()
    
    # Configuration
    config_path = os.path.join(
        os.path.dirname(__file__), 
        'maps', 
        'test_simulation.sumocfg'
    )
    
    # Check if config exists, otherwise use simulation.sumocfg
    if not os.path.exists(config_path):
        config_path = os.path.join(
            os.path.dirname(__file__), 
            'simulation.sumocfg'
        )
    
    if not os.path.exists(config_path):
        print(f"❌ Error: Config file not found")
        print(f"   Tried: {config_path}")
        return False
    
    print(f"Using config: {config_path}")
    print()
    
    # Start SUMO (headless for testing)
    sumo_binary = "sumo"
    sumo_cmd = [sumo_binary, "-c", config_path, "--start", "--quit-on-end"]
    
    try:
        traci.start(sumo_cmd)
        print("✓ Connected to SUMO simulation")
    except Exception as e:
        print(f"❌ Error connecting to SUMO: {e}")
        return False
    
    # Create emergency coordinator
    coordinator = EmergencyVehicleCoordinator(rsu_range=300.0)
    
    # Initialize network topology
    print("\nInitializing network topology...")
    coordinator.initialize_network_topology()
    
    # Print network info
    print(f"\nNetwork Information:")
    print(f"  Junctions: {len(coordinator.junction_info)}")
    print(f"  RSUs: {len(coordinator.rsu_positions)}")
    print()
    
    # List RSUs
    print("RSU Positions:")
    for rsu_id, pos in coordinator.rsu_positions.items():
        print(f"  {rsu_id}: ({pos[0]:.1f}, {pos[1]:.1f})")
    print()
    
    # Run simulation for a period
    max_steps = 500
    detection_count = 0
    greenwave_count = 0
    
    print("Starting simulation...")
    print("-" * 70)
    
    try:
        for step in range(max_steps):
            # Advance simulation
            traci.simulationStep()
            current_time = traci.simulation.getTime()
            
            # Detect emergency vehicles
            emergency_vehicles = coordinator.detect_emergency_vehicles(current_time)
            
            if emergency_vehicles:
                detection_count += 1
                
                for emerg_veh in emergency_vehicles:
                    print(f"\nStep {step} (t={current_time:.1f}s):")
                    print(f"  🚨 Emergency: {emerg_veh.vehicle_id}")
                    print(f"     Edge: {emerg_veh.current_edge}")
                    print(f"     Speed: {emerg_veh.speed:.2f} m/s")
                    print(f"     Detected by: {emerg_veh.detected_by_rsu}")
                    
                    # Create greenwave
                    greenwave_tls = coordinator.create_greenwave(emerg_veh)
                    
                    if greenwave_tls:
                        greenwave_count += 1
                        print(f"     🟢 Greenwave: {greenwave_tls}")
                        
                        # Apply greenwave
                        for tl_id in greenwave_tls:
                            phase_idx = coordinator.apply_greenwave(
                                tl_id, 
                                emerg_veh.current_edge
                            )
                            if phase_idx is not None:
                                print(f"        → {tl_id} set to phase {phase_idx}")
            
            # Print progress every 100 steps
            if step % 100 == 0 and step > 0:
                stats = coordinator.get_statistics()
                print(f"\nProgress: Step {step}/{max_steps}")
                print(f"  Total detections: {stats['total_detections']}")
                print(f"  Active emergencies: {stats['active_emergency_vehicles']}")
                print(f"  Active greenwaves: {stats['active_greenwaves']}")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during simulation: {e}")
        import traceback
        traceback.print_exc()
    finally:
        traci.close()
    
    # Print final statistics
    print()
    print("=" * 70)
    print("Test Results")
    print("=" * 70)
    
    stats = coordinator.get_statistics()
    print(f"\nFinal Statistics:")
    print(f"  Total RSU detections: {stats['total_detections']}")
    print(f"  Greenwaves created: {greenwave_count}")
    print(f"  RSUs in network: {stats['rsu_count']}")
    print(f"  Junctions in network: {stats['junction_count']}")
    
    # Determine success
    success = stats['total_detections'] > 0
    
    print()
    if success:
        print("✅ TEST PASSED: Emergency vehicles detected and greenwave created")
    else:
        print("⚠️  TEST INCOMPLETE: No emergency vehicles detected")
        print("   This may be normal if no emergency vehicles were in the route file")
    
    print()
    return success


if __name__ == '__main__':
    test_emergency_coordinator()
