#!/usr/bin/env python3
"""
Example demonstrating secure V2V and V2I communication using RSA encryption

This example shows:
1. Setting up Certificate Authority (CA)
2. Creating RSUs and vehicles with key management
3. Exchanging public keys between entities
4. Sending encrypted messages (V2I and V2V)
5. Verifying message authentication and integrity
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from v2v_communication.key_management import initialize_vanet_security
from v2v_communication.security import SecureMessage


def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def example_v2i_emergency_message():
    """Example: Vehicle sends emergency message to RSU"""
    print_section("V2I Communication - Emergency Message")
    
    # Initialize security infrastructure
    ca, rsu_mgrs, vehicle_mgrs = initialize_vanet_security(
        rsu_ids=["RSU_Junction1", "RSU_Junction2"],
        num_vehicles=5
    )
    
    # Get vehicle and RSU
    vehicle = vehicle_mgrs["Vehicle_0"]
    rsu = rsu_mgrs["RSU_Junction1"]
    
    print("\n[SCENARIO] Emergency vehicle approaching junction")
    print(f"  Vehicle: {vehicle.entity_id}")
    print(f"  RSU: {rsu.entity_id}")
    
    # Emergency message
    emergency_data = {
        "type": "emergency",
        "priority": "HIGH",
        "vehicle_id": "Vehicle_0",
        "location": {"x": 500.0, "y": 250.0},
        "speed": 90.0,
        "destination": "hospital",
        "request": "clear_path"
    }
    
    print(f"\n[Vehicle_0] Sending emergency message to RSU_Junction1...")
    print(f"  Message: {emergency_data}")
    
    # Encrypt and send
    encrypted_msg = vehicle.handler.encrypt_message(
        "RSU_Junction1", 
        emergency_data, 
        message_type="emergency"
    )
    
    if encrypted_msg:
        print(f"\n[Vehicle_0] ✓ Message encrypted successfully")
        print(f"  Encrypted data size: {len(encrypted_msg.encrypted_data)} bytes")
        print(f"  Signature size: {len(encrypted_msg.signature)} bytes")
        print(f"  Timestamp: {encrypted_msg.timestamp:.2f}")
        
        # RSU receives and decrypts
        print(f"\n[RSU_Junction1] Receiving encrypted message...")
        decrypted_data = rsu.handler.decrypt_message(encrypted_msg)
        
        if decrypted_data:
            print(f"[RSU_Junction1] ✓ Message decrypted and verified successfully")
            print(f"  Decrypted message: {decrypted_data}")
            print(f"  Sender authenticated: Vehicle_0")
            print(f"  Message integrity verified: ✓")
            
            # RSU processes emergency
            print(f"\n[RSU_Junction1] Processing emergency request...")
            print(f"  Priority: {decrypted_data['priority']}")
            print(f"  Action: Adjust traffic lights for emergency vehicle")
            return True
        else:
            print(f"[RSU_Junction1] ✗ Failed to decrypt message")
            return False
    else:
        print(f"[Vehicle_0] ✗ Failed to encrypt message")
        return False


def example_v2v_hazard_warning():
    """Example: Vehicle broadcasts hazard warning to nearby vehicles"""
    print_section("V2V Communication - Hazard Warning")
    
    # Initialize with multiple vehicles
    ca, rsu_mgrs, vehicle_mgrs = initialize_vanet_security(
        rsu_ids=["RSU_1"],
        num_vehicles=4
    )
    
    sender = vehicle_mgrs["Vehicle_0"]
    receivers = [vehicle_mgrs[f"Vehicle_{i}"] for i in range(1, 4)]
    
    print("\n[SCENARIO] Vehicle detects hazard and warns nearby vehicles")
    print(f"  Sender: {sender.entity_id}")
    print(f"  Receivers: {[v.entity_id for v in receivers]}")
    
    # Hazard warning message
    hazard_data = {
        "type": "hazard_warning",
        "hazard_type": "accident",
        "location": {"x": 800.0, "y": 500.0},
        "severity": "high",
        "description": "Multi-vehicle accident blocking 2 lanes",
        "recommended_action": "reduce_speed",
        "alternate_route": "use_detour_via_east"
    }
    
    print(f"\n[Vehicle_0] Broadcasting hazard warning...")
    print(f"  Hazard: {hazard_data['hazard_type']}")
    print(f"  Location: {hazard_data['location']}")
    
    # Send to each nearby vehicle
    success_count = 0
    for receiver in receivers:
        print(f"\n  → Sending to {receiver.entity_id}...")
        
        encrypted_msg = sender.handler.encrypt_message(
            receiver.entity_id,
            hazard_data,
            message_type="hazard_warning"
        )
        
        if encrypted_msg:
            decrypted = receiver.handler.decrypt_message(encrypted_msg)
            if decrypted:
                print(f"    [{receiver.entity_id}] ✓ Received and verified")
                print(f"    [{receiver.entity_id}] Action: {decrypted['recommended_action']}")
                success_count += 1
            else:
                print(f"    [{receiver.entity_id}] ✗ Decryption failed")
        else:
            print(f"    [Vehicle_0] ✗ Encryption failed for {receiver.entity_id}")
    
    print(f"\n[RESULT] Successfully delivered to {success_count}/3 vehicles")
    return success_count == 3


def example_replay_attack_prevention():
    """Example: Demonstrating replay attack prevention"""
    print_section("Security Feature - Replay Attack Prevention")
    
    ca, rsu_mgrs, vehicle_mgrs = initialize_vanet_security(
        rsu_ids=["RSU_1"],
        num_vehicles=2
    )
    
    vehicle1 = vehicle_mgrs["Vehicle_0"]
    vehicle2 = vehicle_mgrs["Vehicle_1"]
    
    print("\n[SCENARIO] Attacker attempts to replay captured message")
    
    # Vehicle 1 sends legitimate message
    message_data = {"type": "status", "speed": 60.0}
    print(f"\n[Vehicle_0] Sending legitimate message to Vehicle_1...")
    
    encrypted_msg = vehicle1.handler.encrypt_message("Vehicle_1", message_data)
    
    # Vehicle 2 receives first time (legitimate)
    print(f"[Vehicle_1] Receiving message (1st time)...")
    decrypted1 = vehicle2.handler.decrypt_message(encrypted_msg)
    
    if decrypted1:
        print(f"  ✓ Message accepted (legitimate)")
    
    # Attacker tries to replay the same message
    print(f"\n[ATTACKER] Replaying captured message...")
    print(f"[Vehicle_1] Receiving message (2nd time - REPLAY)...")
    decrypted2 = vehicle2.handler.decrypt_message(encrypted_msg)
    
    if decrypted2 is None:
        print(f"  ✓ Message REJECTED - Duplicate nonce detected (replay attack prevented)")
        return True
    else:
        print(f"  ✗ SECURITY FAILURE - Replay attack succeeded")
        return False


def example_message_tampering_detection():
    """Example: Detecting tampered messages"""
    print_section("Security Feature - Tampering Detection")
    
    ca, rsu_mgrs, vehicle_mgrs = initialize_vanet_security(
        rsu_ids=["RSU_1"],
        num_vehicles=2
    )
    
    sender = vehicle_mgrs["Vehicle_0"]
    receiver = vehicle_mgrs["Vehicle_1"]
    
    print("\n[SCENARIO] Attacker tampers with encrypted message")
    
    # Send legitimate message
    original_data = {"type": "status", "speed": 50.0}
    print(f"\n[Vehicle_0] Sending message: speed={original_data['speed']}")
    
    encrypted_msg = sender.handler.encrypt_message("Vehicle_1", original_data)
    
    # Attacker tampers with encrypted data
    print(f"\n[ATTACKER] Tampering with encrypted data...")
    # Decode and modify encrypted data
    import base64
    encrypted_bytes = base64.b64decode(encrypted_msg.encrypted_data)
    tampered_bytes = encrypted_bytes[::-1]  # Reverse bytes
    tampered_data = base64.b64encode(tampered_bytes).decode('utf-8')
    
    tampered_msg = SecureMessage(
        sender_id=encrypted_msg.sender_id,
        timestamp=encrypted_msg.timestamp,
        nonce=encrypted_msg.nonce,
        encrypted_data=tampered_data,  # Tampered data
        encrypted_session_key=encrypted_msg.encrypted_session_key,
        signature=encrypted_msg.signature,
        message_type=encrypted_msg.message_type
    )
    
    # Receiver tries to decrypt tampered message
    print(f"[Vehicle_1] Receiving tampered message...")
    decrypted = receiver.handler.decrypt_message(tampered_msg)
    
    if decrypted is None:
        print(f"  ✓ Message REJECTED - Decryption failed (tampering detected)")
        return True
    else:
        print(f"  ✗ SECURITY FAILURE - Tampered message accepted")
        return False


def example_certificate_verification():
    """Example: Certificate-based authentication"""
    print_section("Security Feature - Certificate-Based Authentication")
    
    ca, rsu_mgrs, vehicle_mgrs = initialize_vanet_security(
        rsu_ids=["RSU_1"],
        num_vehicles=1
    )
    
    vehicle = vehicle_mgrs["Vehicle_0"]
    rsu = rsu_mgrs["RSU_1"]
    
    print("\n[SCENARIO] Vehicle presents certificate to RSU")
    
    # Get vehicle certificate
    vehicle_cert = vehicle.get_certificate()
    
    print(f"\n[Vehicle_0] Certificate details:")
    print(f"  Entity ID: {vehicle_cert['entity_id']}")
    print(f"  Entity Type: {vehicle_cert['entity_type']}")
    print(f"  Serial Number: {vehicle_cert['serial_number']}")
    print(f"  Issued: {vehicle_cert['issue_date']}")
    print(f"  Expires: {vehicle_cert['expiry_date']}")
    
    # RSU verifies certificate
    print(f"\n[RSU_1] Verifying certificate...")
    is_valid = ca.verify_certificate(vehicle_cert)
    
    if is_valid:
        print(f"  ✓ Certificate is VALID")
        print(f"  ✓ Issued by trusted CA")
        print(f"  ✓ Not expired")
        print(f"  ✓ Signature verified")
        return True
    else:
        print(f"  ✗ Certificate verification FAILED")
        return False


def main():
    """Run all examples"""
    print("\n" + "=" * 70)
    print("  VANET Secure Communication Examples")
    print("  RSA-2048 Encryption + AES-256 Hybrid System")
    print("=" * 70)
    
    results = {}
    
    # Run examples
    try:
        results['V2I Emergency'] = example_v2i_emergency_message()
        results['V2V Hazard Warning'] = example_v2v_hazard_warning()
        results['Replay Prevention'] = example_replay_attack_prevention()
        results['Tampering Detection'] = example_message_tampering_detection()
        results['Certificate Verification'] = example_certificate_verification()
        
    except Exception as e:
        print(f"\n✗ Error during examples: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Print summary
    print_section("SUMMARY")
    
    all_passed = True
    for example_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {example_name:30s} {status}")
        if not result:
            all_passed = False
    
    print()
    if all_passed:
        print("  All examples completed successfully! ✓")
    else:
        print("  Some examples failed! ✗")
    
    print("\n" + "=" * 70)
    print("  Key Features Demonstrated:")
    print("  • RSA-2048 encryption for key exchange")
    print("  • AES-256-GCM for efficient data encryption")
    print("  • Digital signatures for authentication")
    print("  • Replay attack prevention (nonce + timestamp)")
    print("  • Message tampering detection")
    print("  • Certificate-based trust (CA)")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
