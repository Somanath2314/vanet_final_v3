#!/usr/bin/env python3
"""
Verification script for architectural fixes:
1. RSU position/naming unification
2. Emergency coordinator state reset
3. Junction position verification
"""

import sys
import os

# Add rl_module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'rl_module'))

from rsu_config import (
    print_rsu_summary, 
    validate_rsu_config,
    get_junction_rsus,
    get_rsu_by_id,
    get_rsu_positions,
    get_rsu_count,
    get_tier_counts
)

def test_rsu_unification():
    """Test that RSU configuration is properly unified"""
    print("\n" + "="*70)
    print("TEST 1: RSU POSITION/NAMING UNIFICATION")
    print("="*70)
    
    # Print full summary
    print_rsu_summary()
    
    # Validate configuration
    validation = validate_rsu_config()
    
    # Check specific requirements
    checks = []
    
    # 1. RSU_J2 and RSU_J3 must exist at correct positions
    rsu_j2 = get_rsu_by_id("RSU_J2")
    rsu_j3 = get_rsu_by_id("RSU_J3")
    
    if rsu_j2 and rsu_j2.position == (500.0, 500.0):
        checks.append(("✓", "RSU_J2 at correct position (500, 500)"))
    else:
        checks.append(("✗", f"RSU_J2 position wrong: {rsu_j2.position if rsu_j2 else 'NOT FOUND'}"))
    
    if rsu_j3 and rsu_j3.position == (1000.0, 500.0):
        checks.append(("✓", "RSU_J3 at correct position (1000, 500)"))
    else:
        checks.append(("✗", f"RSU_J3 position wrong: {rsu_j3.position if rsu_j3 else 'NOT FOUND'}"))
    
    # 2. Check junction RSUs
    junction_rsus = get_junction_rsus()
    if "J2" in junction_rsus and "J3" in junction_rsus:
        checks.append(("✓", f"Junction RSUs mapped correctly: {list(junction_rsus.keys())}"))
    else:
        checks.append(("✗", f"Junction RSUs incomplete: {list(junction_rsus.keys())}"))
    
    # 3. Check total RSU count
    rsu_count = get_rsu_count()
    if rsu_count == 13:
        checks.append(("✓", f"Total RSU count: {rsu_count} (Tier1: 2, Tier2: 7, Tier3: 4)"))
    else:
        checks.append(("⚠", f"Total RSU count: {rsu_count} (expected 13)"))
    
    # 4. Check tier distribution
    tier_counts = get_tier_counts()
    expected = {"TIER1": 2, "TIER2": 7, "TIER3": 4}
    if tier_counts["TIER1"] == 2 and tier_counts["TIER2"] == 7:
        checks.append(("✓", f"Tier distribution: {tier_counts}"))
    else:
        checks.append(("⚠", f"Tier distribution: {tier_counts} (expected {expected})"))
    
    # 5. No duplicate IDs
    rsu_positions = get_rsu_positions()
    if len(rsu_positions) == rsu_count:
        checks.append(("✓", "No duplicate RSU IDs"))
    else:
        checks.append(("✗", f"Duplicate IDs: {rsu_count} RSUs but {len(rsu_positions)} unique IDs"))
    
    print("\nVerification Results:")
    for status, message in checks:
        print(f"  {status} {message}")
    
    overall_pass = all(check[0] == "✓" for check in checks)
    print(f"\n{'✅ PASS' if overall_pass else '❌ FAIL'}: RSU Unification")
    
    return overall_pass


def test_emergency_coordinator_reset():
    """Test that emergency coordinator has proper reset method"""
    print("\n" + "="*70)
    print("TEST 2: EMERGENCY COORDINATOR STATE RESET")
    print("="*70)
    
    try:
        from emergency_coordinator import EmergencyVehicleCoordinator
        
        # Create coordinator
        coordinator = EmergencyVehicleCoordinator()
        
        # Check if reset method exists
        if not hasattr(coordinator, 'reset'):
            print("  ✗ reset() method not found")
            print("❌ FAIL: Emergency Coordinator Reset")
            return False
        
        print("  ✓ reset() method exists")
        
        # Verify state variables exist
        state_vars = [
            'emergency_vehicles',
            'active_greenwaves',
            'emergency_detections'
        ]
        
        missing_vars = []
        for var in state_vars:
            if not hasattr(coordinator, var):
                missing_vars.append(var)
        
        if missing_vars:
            print(f"  ✗ Missing state variables: {missing_vars}")
            print("❌ FAIL: Emergency Coordinator Reset")
            return False
        
        print(f"  ✓ All state variables present: {state_vars}")
        
        # Test reset functionality
        # Simulate adding some state
        coordinator.emergency_vehicles['test'] = None
        coordinator.active_greenwaves['test'] = []
        coordinator.emergency_detections.append((0, 'test', 'rsu'))
        
        print(f"  ℹ Before reset: {len(coordinator.emergency_vehicles)} vehicles, "
              f"{len(coordinator.active_greenwaves)} greenwaves, "
              f"{len(coordinator.emergency_detections)} detections")
        
        # Call reset
        coordinator.reset()
        
        print(f"  ℹ After reset: {len(coordinator.emergency_vehicles)} vehicles, "
              f"{len(coordinator.active_greenwaves)} greenwaves, "
              f"{len(coordinator.emergency_detections)} detections")
        
        # Verify all cleared
        if (len(coordinator.emergency_vehicles) == 0 and
            len(coordinator.active_greenwaves) == 0 and
            len(coordinator.emergency_detections) == 0):
            print("  ✓ State properly cleared after reset()")
            print("✅ PASS: Emergency Coordinator Reset")
            return True
        else:
            print("  ✗ State not fully cleared after reset()")
            print("❌ FAIL: Emergency Coordinator Reset")
            return False
            
    except Exception as e:
        print(f"  ✗ Error testing reset: {e}")
        import traceback
        traceback.print_exc()
        print("❌ FAIL: Emergency Coordinator Reset")
        return False


def test_junction_positions():
    """Test that junction positions match SUMO network"""
    print("\n" + "="*70)
    print("TEST 3: JUNCTION POSITION VERIFICATION")
    print("="*70)
    
    # Expected positions from SUMO network file
    expected_positions = {
        "J2": (500.0, 500.0),
        "J3": (1000.0, 1000.0)
    }
    
    print("\nExpected junction positions from SUMO network:")
    print("  J2: (500.0, 500.0)")
    print("  J3: (1000.0, 500.0)")
    
    # Check RSU config matches
    print("\nRSU Configuration positions:")
    rsu_j2 = get_rsu_by_id("RSU_J2")
    rsu_j3 = get_rsu_by_id("RSU_J3")
    
    checks = []
    
    if rsu_j2:
        print(f"  RSU_J2: {rsu_j2.position}")
        if rsu_j2.position == (500.0, 500.0):
            checks.append(("✓", "J2 position matches"))
        else:
            checks.append(("✗", f"J2 mismatch: {rsu_j2.position} != (500.0, 500.0)"))
    else:
        checks.append(("✗", "RSU_J2 not found"))
    
    if rsu_j3:
        print(f"  RSU_J3: {rsu_j3.position}")
        if rsu_j3.position == (1000.0, 500.0):
            checks.append(("✓", "J3 position matches"))
        else:
            checks.append(("✗", f"J3 mismatch: {rsu_j3.position} != (1000.0, 500.0)"))
    else:
        checks.append(("✗", "RSU_J3 not found"))
    
    print("\nVerification Results:")
    for status, message in checks:
        print(f"  {status} {message}")
    
    overall_pass = all(check[0] == "✓" for check in checks)
    print(f"\n{'✅ PASS' if overall_pass else '❌ FAIL'}: Junction Position Verification")
    
    return overall_pass


def test_integration_imports():
    """Test that integrated scripts can import unified RSU config"""
    print("\n" + "="*70)
    print("TEST 4: INTEGRATION IMPORTS")
    print("="*70)
    
    tests = []
    
    # Test emergency coordinator imports
    try:
        from emergency_coordinator import EmergencyVehicleCoordinator, get_junction_rsus, get_rsu_positions
        tests.append(("✓", "emergency_coordinator imports rsu_config"))
    except ImportError as e:
        tests.append(("✗", f"emergency_coordinator import error: {e}"))
    
    # Test that vanet_env calls reset
    try:
        import re
        env_file = os.path.join(os.path.dirname(__file__), 'rl_module/vanet_env.py')
        with open(env_file, 'r') as f:
            content = f.read()
            if 'emergency_coordinator.reset()' in content:
                tests.append(("✓", "vanet_env.py calls emergency_coordinator.reset()"))
            else:
                tests.append(("✗", "vanet_env.py doesn't call emergency_coordinator.reset()"))
    except Exception as e:
        tests.append(("✗", f"Error checking vanet_env.py: {e}"))
    
    # Test run_complete_integrated imports
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'sumo_simulation'))
        # Just check the file contains the imports (don't actually import to avoid SUMO dependency)
        integrated_file = os.path.join(os.path.dirname(__file__), 'sumo_simulation/run_complete_integrated.py')
        with open(integrated_file, 'r') as f:
            content = f.read()
            if 'from rsu_config import' in content:
                tests.append(("✓", "run_complete_integrated.py imports rsu_config"))
            else:
                tests.append(("✗", "run_complete_integrated.py missing rsu_config import"))
            
            if 'get_rsu_ids()' in content:
                tests.append(("✓", "run_complete_integrated.py uses get_rsu_ids()"))
            else:
                tests.append(("✗", "run_complete_integrated.py doesn't use unified config"))
    except Exception as e:
        tests.append(("✗", f"Error checking run_complete_integrated.py: {e}"))
    
    print("\nIntegration Test Results:")
    for status, message in tests:
        print(f"  {status} {message}")
    
    overall_pass = all(test[0] == "✓" for test in tests)
    print(f"\n{'✅ PASS' if overall_pass else '❌ FAIL'}: Integration Imports")
    
    return overall_pass


def main():
    """Run all verification tests"""
    print("\n" + "="*70)
    print("VANET PROJECT ARCHITECTURAL FIXES VERIFICATION")
    print("="*70)
    print("\nRunning comprehensive verification tests...")
    
    results = []
    
    # Run all tests
    results.append(("RSU Unification", test_rsu_unification()))
    results.append(("Emergency Reset", test_emergency_coordinator_reset()))
    results.append(("Junction Positions", test_junction_positions()))
    results.append(("Integration", test_integration_imports()))
    
    # Summary
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "="*70)
    if all_passed:
        print("🎉 ALL TESTS PASSED - Fixes verified successfully!")
        print("="*70)
        return 0
    else:
        failed = [name for name, passed in results if not passed]
        print(f"⚠️  SOME TESTS FAILED: {', '.join(failed)}")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
