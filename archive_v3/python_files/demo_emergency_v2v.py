#!/usr/bin/env python3
"""
VANET Emergency Vehicle V2V Communication Demo
Demonstrates real V2V communication with RSA security for emergency vehicles
"""

import sys
import os
import time
import json
import requests
from datetime import datetime

# Add paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'v2v_communication'))

def demo_emergency_v2v_communication():
    """Demonstrate emergency vehicle V2V communication with real RSA security"""

    print("🚨 VANET Emergency Vehicle V2V Communication Demo")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Backend API base URL
    API_BASE = "http://localhost:5000"

    def check_backend():
        """Check if backend is running"""
        try:
            response = requests.get(f"{API_BASE}/api/status")
            return response.status_code == 200
        except:
            return False

    if not check_backend():
        print("❌ Backend server not running")
        print("   Start backend with: cd backend && python3 app.py")
        return False

    print("✅ Backend server connected")
    print()

    # Step 1: Register emergency vehicle
    print("📡 Step 1: Registering Emergency Vehicle")
    print("-" * 40)

    try:
        response = requests.post(f"{API_BASE}/api/v2v/register",
                                json={"vehicle_id": "emergency_vehicle_001"},
                                headers={"Content-Type": "application/json"})

        if response.status_code == 200:
            result = response.json()
            print(f"✅ Emergency vehicle registered: {result['vehicle_id']}")
            print(f"   Communication range: {result['communication_range']}m")
        else:
            print(f"❌ Registration failed: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Registration error: {e}")
        return False

    print()

    # Step 2: Register nearby vehicles
    print("📡 Step 2: Registering Nearby Vehicles")
    print("-" * 40)

    nearby_vehicles = ["nearby_vehicle_001", "nearby_vehicle_002", "traffic_vehicle_001"]

    for vehicle_id in nearby_vehicles:
        try:
            response = requests.post(f"{API_BASE}/api/v2v/register",
                                    json={"vehicle_id": vehicle_id},
                                    headers={"Content-Type": "application/json"})

            if response.status_code == 200:
                print(f"✅ {vehicle_id} registered")
            else:
                print(f"⚠️  {vehicle_id} registration failed: {response.text}")

        except Exception as e:
            print(f"❌ {vehicle_id} registration error: {e}")

    print()

    # Step 3: Simulate emergency scenario
    print("🚨 Step 3: Emergency Scenario Simulation")
    print("-" * 40)

    # Update emergency vehicle position (simulating movement)
    print("🚗 Moving emergency vehicle to intersection...")

    position_updates = [
        {"x": 100, "y": 100, "speed": 60, "lane": "E1_0"},
        {"x": 200, "y": 100, "speed": 70, "lane": "E1_0"},
        {"x": 300, "y": 100, "speed": 80, "lane": "E1_0"},
        {"x": 400, "y": 100, "speed": 80, "lane": "E1_0"},
        {"x": 500, "y": 100, "speed": 80, "lane": "E1_0"}
    ]

    for i, position in enumerate(position_updates):
        try:
            response = requests.post(f"{API_BASE}/api/v2v/update",
                                    json={
                                        "vehicle_id": "emergency_vehicle_001",
                                        **position
                                    },
                                    headers={"Content-Type": "application/json"})

            if response.status_code == 200:
                result = response.json()
                print(f"   Position {i+1}: ({position['x']}, {position['y']}) - Speed: {position['speed']} km/h")

                # Check for received messages
                if result.get('messages_received', 0) > 0:
                    print(f"   📨 Received {result['messages_received']} V2V messages")

            time.sleep(1)  # Simulate time passing

        except Exception as e:
            print(f"❌ Position update error: {e}")

    print()

    # Step 4: Send emergency broadcast
    print("🚨 Step 4: Broadcasting Emergency Message")
    print("-" * 40)

    emergency_broadcasts = [
        {
            "location": {"x": 500, "y": 100},
            "speed": 80,
            "emergency": True,
            "message": "🚨 EMERGENCY VEHICLE APPROACHING - CLEAR PATH"
        },
        {
            "location": {"x": 600, "y": 100},
            "speed": 75,
            "emergency": True,
            "message": "🚨 HIGH PRIORITY EMERGENCY - EVACUATE INTERSECTION"
        }
    ]

    for i, broadcast in enumerate(emergency_broadcasts):
        try:
            response = requests.post(f"{API_BASE}/api/v2v/send",
                                    json={
                                        "sender_id": "emergency_vehicle_001",
                                        "receiver_id": "BROADCAST",
                                        "message_type": "safety",
                                        "payload": broadcast
                                    },
                                    headers={"Content-Type": "application/json"})

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Emergency broadcast {i+1} sent")
                print(f"   Message ID: {result['message_id']}")
                print(f"   Message: {broadcast['message']}")

                # Wait a moment for processing
                time.sleep(2)

                # Show updated security metrics
                show_security_metrics()

            else:
                print(f"❌ Broadcast failed: {response.text}")

        except Exception as e:
            print(f"❌ Broadcast error: {e}")

    print()

    # Step 5: Show final security metrics
    print("📊 Step 5: Final Security Metrics Summary")
    print("-" * 40)

    show_detailed_security_metrics()

    print()
    print("🎉 Emergency V2V Communication Demo Complete!")
    print()
    print("💡 Next Steps:")
    print("   • Monitor real-time logs: ./dynamic_security_monitor.sh")
    print("   • View API data: http://localhost:5000/api/v2v/security")
    print("   • Run full simulation: ./run_sumo_rl.sh")

    return True

def show_security_metrics():
    """Show current V2V security metrics"""
    API_BASE = "http://localhost:5000"

    try:
        response = requests.get(f"{API_BASE}/api/v2v/security")
        if response.status_code == 200:
            metrics = response.json()

            print("   🔐 RSA Security Metrics:")
            print(f"      • Encryption overhead: {metrics.get('encryption_overhead', 0):.2f}ms")
            print(f"      • Decryption overhead: {metrics.get('decryption_overhead', 0):.2f}ms")
            print(f"      • Key exchange latency: {metrics.get('key_exchange_latency', 0):.2f}ms")
            print(f"      • Security processing time: {metrics.get('security_processing_time', 0):.2f}ms")
            print(f"      • Message authentication delay: {metrics.get('message_authentication_delay', 0):.2f}ms")
            print(f"      • Successful authentications: {metrics.get('successful_authentications', 0)}")
            print(f"      • Failed authentications: {metrics.get('failed_authentications', 0)}")
            print(f"      • Total messages processed: {metrics.get('total_messages_processed', 0)}")

    except Exception as e:
        print(f"   ❌ Could not retrieve security metrics: {e}")

def show_detailed_security_metrics():
    """Show comprehensive security metrics"""
    API_BASE = "http://localhost:5000"

    try:
        # Get V2V security metrics
        v2v_response = requests.get(f"{API_BASE}/api/v2v/security")
        if v2v_response.status_code == 200:
            v2v_metrics = v2v_response.json()

            print("🔐 COMPREHENSIVE SECURITY METRICS:")
            print("=" * 50)

            print("📊 RSA Cryptography Performance:")
            print(f"   • Encryption overhead: {v2v_metrics.get('encryption_overhead', 0):.2f}ms")
            print(f"   • Decryption overhead: {v2v_metrics.get('decryption_overhead', 0):.2f}ms")
            print(f"   • Key exchange latency: {v2v_metrics.get('key_exchange_latency', 0):.2f}ms")
            print(f"   • Security processing time: {v2v_metrics.get('security_processing_time', 0):.2f}ms")

            print("\n🔑 Authentication & Verification:")
            print(f"   • Message authentication delay: {v2v_metrics.get('message_authentication_delay', 0):.2f}ms")
            print(f"   • Signature generation time: {v2v_metrics.get('signature_generation_time', 0):.2f}ms")
            print(f"   • Signature verification time: {v2v_metrics.get('signature_verification_time', 0):.2f}ms")
            print(f"   • Successful authentications: {v2v_metrics.get('successful_authentications', 0)}")
            print(f"   • Failed authentications: {v2v_metrics.get('failed_authentications', 0)}")

            print("\n📡 Communication Metrics:")
            print(f"   • Total messages processed: {v2v_metrics.get('total_messages_processed', 0)}")
            print(f"   • Average latency: {v2v_metrics.get('average_latency', 0):.2f}ms")
            print(f"   • Messages per second: {v2v_metrics.get('messages_per_second', 0):.2f}")

            if 'total_messages_sent' in v2v_metrics:
                print(f"   • Total messages sent: {v2v_metrics['total_messages_sent']}")
            if 'total_broadcasts' in v2v_metrics:
                print(f"   • Emergency broadcasts: {v2v_metrics['total_broadcasts']}")

    except Exception as e:
        print(f"❌ Could not retrieve detailed security metrics: {e}")

def main():
    """Main demo function"""
    success = demo_emergency_v2v_communication()
    exit(0 if success else 1)

if __name__ == "__main__":
    main()
