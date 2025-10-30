#!/usr/bin/env python3
"""
Test script for Phase 2 - Backend APIs
Tests GET /api/wimax/getSignalData and POST /api/control/override
"""

import requests
import json
import time


def test_get_signal_data(base_url="http://localhost:8000"):
    """Test GET /api/wimax/getSignalData endpoint"""
    print("\n" + "="*70)
    print("TEST 1: GET /api/wimax/getSignalData")
    print("="*70)
    
    # Test with various parameters
    test_cases = [
        {"x": 500, "y": 500, "radius": 1000, "desc": "Center of network"},
        {"x": 0, "y": 0, "radius": 2000, "desc": "Origin with large radius"},
        {"x": 350, "y": 420, "radius": 500, "desc": "Near ambulance position"},
    ]
    
    for case in test_cases:
        print(f"\n📍 Query: {case['desc']}")
        print(f"   Coordinates: ({case['x']}, {case['y']}), Radius: {case['radius']}m")
        
        try:
            response = requests.get(
                f"{base_url}/api/wimax/getSignalData",
                params={"x": case['x'], "y": case['y'], "radius": case['radius']},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Status: {response.status_code}")
                print(f"   📊 Junctions found: {len(data.get('junctions', []))}")
                
                for junction in data.get('junctions', [])[:2]:  # Show first 2
                    print(f"      - {junction['poleId']}: "
                          f"({junction['coords']['x']:.1f}, {junction['coords']['y']:.1f}), "
                          f"Distance: {junction['distance_from_query']:.1f}m, "
                          f"Phase: {junction['phase_info']['current_phase']}")
                
                if data.get('ambulance', {}).get('detected'):
                    amb = data['ambulance']
                    print(f"   🚑 Ambulance detected: {amb.get('vehicle_id', 'unknown')}")
                    print(f"      Position: ({amb['position']['x']:.1f}, {amb['position']['y']:.1f})")
                    print(f"      Target: ({amb['target']['x']:.1f}, {amb['target']['y']:.1f})")
                    print(f"      Speed: {amb['speed']:.1f} m/s, Direction: {amb['direction']}")
                else:
                    print(f"   ℹ️  No ambulance detected")
                    
            else:
                print(f"   ❌ Status: {response.status_code}")
                print(f"   Error: {response.json()}")
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection failed - Is backend running?")
            return False
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False
    
    return True


def test_control_override(base_url="http://localhost:8000"):
    """Test POST /api/control/override endpoint"""
    print("\n" + "="*70)
    print("TEST 2: POST /api/control/override")
    print("="*70)
    
    # Test cases
    test_cases = [
        {
            "desc": "Emergency preemption for Junction J2",
            "payload": {
                "vehicle_id": "emergency_test_1",
                "poleId": "J2",
                "action": 0,
                "duration_s": 15,
                "priority": 1
            }
        },
        {
            "desc": "Manual override for Junction J3",
            "payload": {
                "poleId": "J3",
                "action": 1,  # Use phase 1 (valid for J3 which has phases 0-3)
                "duration_s": 20,
                "priority": 3
            }
        }
    ]
    
    for case in test_cases:
        print(f"\n🔧 Test: {case['desc']}")
        payload = case['payload']
        print(f"   Junction: {payload['poleId']}, Action: {payload['action']}, Duration: {payload['duration_s']}s")
        
        try:
            response = requests.post(
                f"{base_url}/api/control/override",
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Status: {response.status_code} - {data.get('status', 'unknown')}")
                print(f"   📊 Junction: {data.get('junction')}")
                print(f"   🔄 Phase change: {data.get('previous_phase')} → {data.get('new_phase')}")
                print(f"   ⏱️  Duration: {data.get('duration_s')}s")
                if data.get('vehicle_id'):
                    print(f"   🚑 Vehicle: {data.get('vehicle_id')}")
            else:
                print(f"   ❌ Status: {response.status_code}")
                print(f"   Error: {response.json()}")
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection failed - Is backend running?")
            return False
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False
        
        # Small delay between requests
        time.sleep(1)
    
    return True


def test_invalid_requests(base_url="http://localhost:8000"):
    """Test error handling with invalid requests"""
    print("\n" + "="*70)
    print("TEST 3: Error Handling")
    print("="*70)
    
    test_cases = [
        {
            "desc": "Missing parameters in override",
            "endpoint": "/api/control/override",
            "method": "POST",
            "payload": {"poleId": "J2"},  # Missing action
            "expected_status": 400
        },
        {
            "desc": "Invalid junction ID",
            "endpoint": "/api/control/override",
            "method": "POST",
            "payload": {"poleId": "INVALID_ID", "action": 0},
            "expected_status": 404
        },
        {
            "desc": "Invalid coordinates in getSignalData",
            "endpoint": "/api/wimax/getSignalData",
            "method": "GET",
            "params": {"x": "invalid", "y": 500},
            "expected_status": 400
        }
    ]
    
    passed = 0
    for case in test_cases:
        print(f"\n🧪 Test: {case['desc']}")
        
        try:
            if case['method'] == 'POST':
                response = requests.post(
                    f"{base_url}{case['endpoint']}",
                    json=case.get('payload', {}),
                    timeout=5
                )
            else:
                response = requests.get(
                    f"{base_url}{case['endpoint']}",
                    params=case.get('params', {}),
                    timeout=5
                )
            
            if response.status_code == case['expected_status']:
                print(f"   ✅ Correct error handling: {response.status_code}")
                passed += 1
            else:
                print(f"   ❌ Unexpected status: {response.status_code} (expected {case['expected_status']})")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print(f"\n   Passed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def main():
    """Run all API tests"""
    print("\n" + "🧪 " + "="*66)
    print("   BACKEND APIs - PHASE 2 VALIDATION")
    print("="*70 + "\n")
    
    print("⚠️  Prerequisites:")
    print("   1. Run integrated simulation: ./run_integrated_sumo_ns3.sh --rl --gui")
    print("      (This starts SUMO + Backend on port 8000 automatically)")
    print("   2. Wait for simulation to start and backend to initialize")
    print()
    
    input("Press Enter when you see 'Backend API server started', or Ctrl+C to cancel...")
    
    results = {}
    
    # Test 1: getSignalData
    results['getSignalData'] = test_get_signal_data()
    
    # Test 2: control/override  
    results['control_override'] = test_control_override()
    
    # Test 3: Error handling
    results['error_handling'] = test_invalid_requests()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} | {test_name.replace('_', ' ').title()}")
    
    all_passed = all(results.values())
    
    print("\n" + "="*70)
    if all_passed:
        print("🎉 ALL TESTS PASSED - Phase 2 Complete!")
        print("="*70)
        print("\n✅ Backend APIs ready for:")
        print("   - Fog nodes to query junction states")
        print("   - Fog nodes to send RL-based overrides")
        print("   - Emergency vehicle preemption")
        print("\n📋 Next: Phase 3 - Integrate sensor network with RL")
    else:
        print("❌ SOME TESTS FAILED - Check logs above")
        print("="*70)
    
    return all_passed


if __name__ == "__main__":
    import sys
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests cancelled by user")
        sys.exit(1)
