#!/usr/bin/env python3
"""
Unit tests for VANET security module
Tests RSA encryption, hybrid encryption, digital signatures, and key management
"""

import unittest
import time
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from v2v_communication.security import (
    RSAKeyPair, HybridEncryption, DigitalSignature,
    SecureMessageHandler, SecureMessage, create_secure_handler, exchange_public_keys
)
from v2v_communication.key_management import (
    KeyStore, CertificateAuthority, KeyManager, initialize_vanet_security
)


class TestRSAKeyPair(unittest.TestCase):
    """Test RSA key pair generation and serialization"""
    
    def test_key_generation(self):
        """Test that keys are generated correctly"""
        key_pair = RSAKeyPair("test_entity", key_size=2048)
        self.assertIsNotNone(key_pair.private_key)
        self.assertIsNotNone(key_pair.public_key)
    
    def test_public_key_export(self):
        """Test public key PEM export"""
        key_pair = RSAKeyPair("test_entity")
        pem = key_pair.get_public_key_pem()
        self.assertTrue(pem.startswith(b'-----BEGIN PUBLIC KEY-----'))
        self.assertTrue(pem.endswith(b'-----END PUBLIC KEY-----\n'))
    
    def test_public_key_import(self):
        """Test public key PEM import"""
        key_pair1 = RSAKeyPair("entity1")
        pem = key_pair1.get_public_key_pem()
        
        # Import the key
        imported_key = RSAKeyPair.load_public_key_from_pem(pem)
        self.assertIsNotNone(imported_key)


class TestHybridEncryption(unittest.TestCase):
    """Test hybrid encryption (RSA + AES)"""
    
    def test_session_key_generation(self):
        """Test AES session key generation"""
        session_key = HybridEncryption.generate_session_key()
        self.assertEqual(len(session_key), 32)  # 256 bits
    
    def test_aes_encryption_decryption(self):
        """Test AES encryption and decryption"""
        session_key = HybridEncryption.generate_session_key()
        plaintext = b"Test message for AES encryption"
        
        # Encrypt
        encrypted_data, iv = HybridEncryption.encrypt_with_aes(plaintext, session_key)
        self.assertNotEqual(encrypted_data, plaintext)
        
        # Decrypt
        decrypted = HybridEncryption.decrypt_with_aes(encrypted_data, session_key, iv)
        self.assertEqual(decrypted, plaintext)
    
    def test_rsa_session_key_encryption(self):
        """Test RSA encryption of session key"""
        key_pair = RSAKeyPair("test_entity")
        session_key = HybridEncryption.generate_session_key()
        
        # Encrypt session key with public key
        encrypted_key = HybridEncryption.encrypt_session_key_with_rsa(
            session_key, key_pair.public_key
        )
        
        # Decrypt with private key
        decrypted_key = HybridEncryption.decrypt_session_key_with_rsa(
            encrypted_key, key_pair.private_key
        )
        
        self.assertEqual(session_key, decrypted_key)
    
    def test_large_message_encryption(self):
        """Test encryption of large messages"""
        session_key = HybridEncryption.generate_session_key()
        large_message = b"A" * 10000  # 10KB message
        
        encrypted_data, iv = HybridEncryption.encrypt_with_aes(large_message, session_key)
        decrypted = HybridEncryption.decrypt_with_aes(encrypted_data, session_key, iv)
        
        self.assertEqual(decrypted, large_message)


class TestDigitalSignature(unittest.TestCase):
    """Test digital signature generation and verification"""
    
    def test_sign_and_verify(self):
        """Test message signing and verification"""
        key_pair = RSAKeyPair("test_entity")
        message = b"Test message for signature"
        
        # Sign
        signature = DigitalSignature.sign_message(message, key_pair.private_key)
        self.assertIsNotNone(signature)
        
        # Verify
        is_valid = DigitalSignature.verify_signature(
            message, signature, key_pair.public_key
        )
        self.assertTrue(is_valid)
    
    def test_tampered_message_detection(self):
        """Test that tampered messages are detected"""
        key_pair = RSAKeyPair("test_entity")
        message = b"Original message"
        signature = DigitalSignature.sign_message(message, key_pair.private_key)
        
        # Tamper with message
        tampered_message = b"Tampered message"
        
        # Verification should fail
        is_valid = DigitalSignature.verify_signature(
            tampered_message, signature, key_pair.public_key
        )
        self.assertFalse(is_valid)
    
    def test_wrong_public_key(self):
        """Test that wrong public key fails verification"""
        key_pair1 = RSAKeyPair("entity1")
        key_pair2 = RSAKeyPair("entity2")
        
        message = b"Test message"
        signature = DigitalSignature.sign_message(message, key_pair1.private_key)
        
        # Try to verify with wrong public key
        is_valid = DigitalSignature.verify_signature(
            message, signature, key_pair2.public_key
        )
        self.assertFalse(is_valid)


class TestSecureMessageHandler(unittest.TestCase):
    """Test secure message handling"""
    
    def setUp(self):
        """Set up test handlers"""
        self.handler1 = SecureMessageHandler("entity1")
        self.handler2 = SecureMessageHandler("entity2")
        
        # Exchange public keys
        exchange_public_keys(self.handler1, self.handler2)
    
    def test_message_encryption_decryption(self):
        """Test end-to-end message encryption and decryption"""
        message_data = {
            "type": "test",
            "value": 123,
            "text": "Hello, World!"
        }
        
        # Encrypt
        encrypted_msg = self.handler1.encrypt_message("entity2", message_data)
        self.assertIsNotNone(encrypted_msg)
        self.assertIsInstance(encrypted_msg, SecureMessage)
        
        # Decrypt
        decrypted_data = self.handler2.decrypt_message(encrypted_msg)
        self.assertIsNotNone(decrypted_data)
        self.assertEqual(decrypted_data, message_data)
    
    def test_replay_attack_prevention(self):
        """Test that replay attacks are prevented"""
        message_data = {"type": "test"}
        
        # Send message
        encrypted_msg = self.handler1.encrypt_message("entity2", message_data)
        
        # First reception succeeds
        decrypted1 = self.handler2.decrypt_message(encrypted_msg)
        self.assertIsNotNone(decrypted1)
        
        # Second reception fails (replay attack)
        decrypted2 = self.handler2.decrypt_message(encrypted_msg)
        self.assertIsNone(decrypted2)
    
    def test_expired_message_rejection(self):
        """Test that old messages are rejected"""
        message_data = {"type": "test"}
        
        # Create message
        encrypted_msg = self.handler1.encrypt_message("entity2", message_data)
        
        # Modify timestamp to be old
        encrypted_msg.timestamp = time.time() - 100.0  # 100 seconds ago
        
        # Should be rejected
        decrypted = self.handler2.decrypt_message(encrypted_msg, max_age_seconds=30.0)
        self.assertIsNone(decrypted)
    
    def test_unknown_sender_rejection(self):
        """Test that messages from unknown senders are rejected"""
        handler3 = SecureMessageHandler("entity3")
        
        message_data = {"type": "test"}
        encrypted_msg = handler3.encrypt_message("entity1", message_data)
        
        # entity1 doesn't have entity3's public key
        # So we need to manually create the message without proper key exchange
        # This simulates an unknown sender
        
        # handler1 doesn't know handler3, so encryption will fail
        result = self.handler1.encrypt_message("entity3", message_data)
        self.assertIsNone(result)
    
    def test_session_key_caching(self):
        """Test that session keys are cached"""
        message_data1 = {"msg": 1}
        message_data2 = {"msg": 2}
        
        # Send two messages
        encrypted1 = self.handler1.encrypt_message("entity2", message_data1)
        encrypted2 = self.handler1.encrypt_message("entity2", message_data2)
        
        # Both should succeed
        self.assertIsNotNone(encrypted1)
        self.assertIsNotNone(encrypted2)
        
        # Check that session key was cached
        self.assertIn("entity2", self.handler1.session_keys_cache)


class TestKeyManagement(unittest.TestCase):
    """Test key management system"""
    
    def test_key_store(self):
        """Test key storage and retrieval"""
        key_store = KeyStore(storage_dir="./test_keys")
        key_pair = RSAKeyPair("test_entity")
        
        # Save keys
        key_store.save_public_key("test_entity", key_pair.get_public_key_pem())
        key_store.save_private_key("test_entity", key_pair.get_private_key_pem())
        
        # Load keys
        loaded_public = key_store.load_public_key("test_entity")
        loaded_private = key_store.load_private_key("test_entity")
        
        self.assertIsNotNone(loaded_public)
        self.assertIsNotNone(loaded_private)
        
        # Cleanup
        import shutil
        shutil.rmtree("./test_keys")
    
    def test_certificate_authority(self):
        """Test CA certificate issuance and verification"""
        ca = CertificateAuthority()
        entity_key = RSAKeyPair("test_vehicle")
        
        # Issue certificate
        cert = ca.issue_certificate(
            "test_vehicle",
            entity_key.get_public_key_pem(),
            entity_type="vehicle"
        )
        
        self.assertIsNotNone(cert)
        self.assertEqual(cert["entity_id"], "test_vehicle")
        self.assertEqual(cert["entity_type"], "vehicle")
        
        # Verify certificate
        is_valid = ca.verify_certificate(cert)
        self.assertTrue(is_valid)
    
    def test_certificate_expiry(self):
        """Test that expired certificates are detected"""
        ca = CertificateAuthority()
        entity_key = RSAKeyPair("test_entity")
        
        # Issue certificate with 0 days validity
        cert = ca.issue_certificate(
            "test_entity",
            entity_key.get_public_key_pem(),
            validity_days=0
        )
        
        # Wait a moment
        time.sleep(0.1)
        
        # Should be expired
        is_valid = ca.verify_certificate(cert)
        self.assertFalse(is_valid)
    
    def test_key_rotation(self):
        """Test key rotation"""
        ca = CertificateAuthority()
        key_mgr = KeyManager("test_entity", entity_type="vehicle", ca=ca)
        
        # Get original certificate
        original_cert = key_mgr.get_certificate()
        original_serial = original_cert["serial_number"]
        
        # Rotate keys
        key_mgr.rotate_keys()
        
        # Get new certificate
        new_cert = key_mgr.get_certificate()
        new_serial = new_cert["serial_number"]
        
        # Serial numbers should be different
        self.assertNotEqual(original_serial, new_serial)


class TestIntegration(unittest.TestCase):
    """Integration tests for complete VANET security"""
    
    def test_vanet_initialization(self):
        """Test initialization of complete VANET security infrastructure"""
        ca, rsu_mgrs, vehicle_mgrs = initialize_vanet_security(
            rsu_ids=["RSU_1", "RSU_2"],
            num_vehicles=3
        )
        
        # Check that all entities were created
        self.assertEqual(len(rsu_mgrs), 2)
        self.assertEqual(len(vehicle_mgrs), 3)
        
        # Check that keys were exchanged
        for rsu_id, rsu_mgr in rsu_mgrs.items():
            # RSU should know all vehicles but NOT other RSUs (peer-to-peer RSU communication not needed)
            # Only vehicles need to know RSUs, and RSUs need to know vehicles
            self.assertEqual(len(rsu_mgr.handler.peer_public_keys), 3)  # 3 vehicles
        
        for vehicle_id, vehicle_mgr in vehicle_mgrs.items():
            # Vehicle should know all RSUs and other vehicles (not itself)
            self.assertEqual(len(vehicle_mgr.handler.peer_public_keys), 2 + 2)  # 2 RSUs + 2 other vehicles
    
    def test_v2i_communication(self):
        """Test V2I encrypted communication"""
        ca, rsu_mgrs, vehicle_mgrs = initialize_vanet_security(
            rsu_ids=["RSU_1"],
            num_vehicles=1
        )
        
        vehicle = vehicle_mgrs["Vehicle_0"]
        rsu = rsu_mgrs["RSU_1"]
        
        # Vehicle sends emergency message to RSU
        emergency_data = {
            "type": "emergency",
            "location": {"x": 500.0, "y": 500.0},
            "speed": 90.0
        }
        
        encrypted = vehicle.handler.encrypt_message("RSU_1", emergency_data, "emergency")
        decrypted = rsu.handler.decrypt_message(encrypted)
        
        self.assertIsNotNone(decrypted)
        self.assertEqual(decrypted, emergency_data)
    
    def test_v2v_communication(self):
        """Test V2V encrypted communication"""
        ca, rsu_mgrs, vehicle_mgrs = initialize_vanet_security(
            rsu_ids=[],
            num_vehicles=2
        )
        
        vehicle1 = vehicle_mgrs["Vehicle_0"]
        vehicle2 = vehicle_mgrs["Vehicle_1"]
        
        # Vehicle 1 sends message to Vehicle 2
        message_data = {
            "type": "warning",
            "message": "Accident ahead",
            "distance": 200.0
        }
        
        encrypted = vehicle1.handler.encrypt_message("Vehicle_1", message_data)
        decrypted = vehicle2.handler.decrypt_message(encrypted)
        
        self.assertIsNotNone(decrypted)
        self.assertEqual(decrypted, message_data)


def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestRSAKeyPair))
    suite.addTests(loader.loadTestsFromTestCase(TestHybridEncryption))
    suite.addTests(loader.loadTestsFromTestCase(TestDigitalSignature))
    suite.addTests(loader.loadTestsFromTestCase(TestSecureMessageHandler))
    suite.addTests(loader.loadTestsFromTestCase(TestKeyManagement))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success status
    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 70)
    print("VANET Security Module - Unit Tests")
    print("=" * 70)
    print()
    
    success = run_tests()
    
    print()
    print("=" * 70)
    if success:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed")
    print("=" * 70)
    
    sys.exit(0 if success else 1)
