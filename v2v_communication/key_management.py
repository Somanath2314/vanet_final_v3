#!/usr/bin/env python3
"""
Key Management System for VANET
Handles key distribution, certificate management, and key rotation
"""

import json
import os
from typing import Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
from v2v_communication.security import SecureMessageHandler


class KeyStore:
    """Persistent storage for keys and certificates"""
    
    def __init__(self, storage_dir: str = "./keys"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
    def save_private_key(self, entity_id: str, pem_data: bytes):
        """Save private key (use with caution - should be encrypted in production)"""
        key_file = self.storage_dir / f"{entity_id}_private.pem"
        with open(key_file, 'wb') as f:
            f.write(pem_data)
        # Set restrictive permissions
        os.chmod(key_file, 0o600)
        
    def save_public_key(self, entity_id: str, pem_data: bytes):
        """Save public key"""
        key_file = self.storage_dir / f"{entity_id}_public.pem"
        with open(key_file, 'wb') as f:
            f.write(pem_data)
            
    def load_private_key(self, entity_id: str) -> Optional[bytes]:
        """Load private key"""
        key_file = self.storage_dir / f"{entity_id}_private.pem"
        if key_file.exists():
            with open(key_file, 'rb') as f:
                return f.read()
        return None
        
    def load_public_key(self, entity_id: str) -> Optional[bytes]:
        """Load public key"""
        key_file = self.storage_dir / f"{entity_id}_public.pem"
        if key_file.exists():
            with open(key_file, 'rb') as f:
                return f.read()
        return None
    
    def list_entities(self) -> list:
        """List all entities with stored keys"""
        public_keys = list(self.storage_dir.glob("*_public.pem"))
        return [k.stem.replace("_public", "") for k in public_keys]


class CertificateAuthority:
    """
    Simple Certificate Authority for VANET
    In production, use a proper PKI infrastructure
    """
    
    def __init__(self, ca_id: str = "VANET_CA"):
        self.ca_id = ca_id
        self.ca_handler = SecureMessageHandler(ca_id, key_size=4096)  # CA uses 4096-bit key
        self.certificates: Dict[str, dict] = {}
        self.key_store = KeyStore()
        
        # Save CA keys
        self.key_store.save_private_key(ca_id, self.ca_handler.key_pair.get_private_key_pem())
        self.key_store.save_public_key(ca_id, self.ca_handler.get_public_key_pem())
        
    def issue_certificate(self, entity_id: str, public_key_pem: bytes, 
                         entity_type: str = "vehicle", validity_days: int = 365) -> dict:
        """
        Issue a certificate for an entity
        Returns certificate dictionary
        """
        issue_date = datetime.now()
        expiry_date = issue_date + timedelta(days=validity_days)
        
        certificate = {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "public_key": public_key_pem.decode('utf-8'),
            "issuer": self.ca_id,
            "issue_date": issue_date.isoformat(),
            "expiry_date": expiry_date.isoformat(),
            "serial_number": os.urandom(16).hex()
        }
        
        # Sign certificate with CA's private key
        cert_data = json.dumps(certificate, sort_keys=True).encode('utf-8')
        from v2v_communication.security import DigitalSignature
        signature = DigitalSignature.sign_message(cert_data, self.ca_handler.key_pair.private_key)
        
        certificate["signature"] = signature.hex()
        self.certificates[entity_id] = certificate
        
        # Save public key
        self.key_store.save_public_key(entity_id, public_key_pem)
        
        print(f"[CA] Issued certificate for {entity_id} (valid until {expiry_date.date()})")
        return certificate
    
    def verify_certificate(self, certificate: dict) -> bool:
        """Verify a certificate's signature and validity"""
        # Check expiry
        expiry_date = datetime.fromisoformat(certificate["expiry_date"])
        if datetime.now() > expiry_date:
            print(f"[CA] Certificate for {certificate['entity_id']} has expired")
            return False
        
        # Verify signature
        cert_copy = certificate.copy()
        signature_hex = cert_copy.pop("signature")
        cert_data = json.dumps(cert_copy, sort_keys=True).encode('utf-8')
        
        from v2v_communication.security import DigitalSignature
        signature = bytes.fromhex(signature_hex)
        
        return DigitalSignature.verify_signature(
            cert_data, signature, self.ca_handler.key_pair.public_key
        )
    
    def get_ca_public_key(self) -> bytes:
        """Get CA's public key for distribution"""
        return self.ca_handler.get_public_key_pem()
    
    def revoke_certificate(self, entity_id: str):
        """Revoke a certificate"""
        if entity_id in self.certificates:
            del self.certificates[entity_id]
            print(f"[CA] Revoked certificate for {entity_id}")


class KeyManager:
    """
    High-level key management for VANET entities
    Handles key generation, registration with CA, and peer key distribution
    """
    
    def __init__(self, entity_id: str, entity_type: str = "vehicle", ca: Optional[CertificateAuthority] = None):
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.ca = ca
        self.key_store = KeyStore()
        
        # Create secure message handler
        self.handler = SecureMessageHandler(entity_id)
        
        # Save keys
        self.key_store.save_private_key(entity_id, self.handler.key_pair.get_private_key_pem())
        self.key_store.save_public_key(entity_id, self.handler.get_public_key_pem())
        
        # Get certificate from CA if available
        self.certificate = None
        if ca:
            self.certificate = ca.issue_certificate(
                entity_id, 
                self.handler.get_public_key_pem(), 
                entity_type
            )
    
    def register_peer(self, peer_id: str, peer_public_key_pem: bytes):
        """Register a peer's public key"""
        self.handler.register_peer_public_key(peer_id, peer_public_key_pem)
        
    def register_peer_from_certificate(self, certificate: dict):
        """Register a peer using their certificate"""
        if self.ca and self.ca.verify_certificate(certificate):
            peer_id = certificate["entity_id"]
            public_key_pem = certificate["public_key"].encode('utf-8')
            self.register_peer(peer_id, public_key_pem)
            print(f"[KeyMgr] Registered {peer_id} from verified certificate")
            return True
        else:
            print(f"[KeyMgr] Failed to verify certificate for {certificate.get('entity_id')}")
            return False
    
    def get_certificate(self) -> Optional[dict]:
        """Get this entity's certificate"""
        return self.certificate
    
    def rotate_keys(self):
        """Generate new key pair and get new certificate"""
        print(f"[KeyMgr] Rotating keys for {self.entity_id}")
        old_handler = self.handler
        
        # Generate new keys
        self.handler = SecureMessageHandler(self.entity_id)
        
        # Save new keys
        self.key_store.save_private_key(self.entity_id, self.handler.key_pair.get_private_key_pem())
        self.key_store.save_public_key(self.entity_id, self.handler.get_public_key_pem())
        
        # Get new certificate
        if self.ca:
            self.certificate = self.ca.issue_certificate(
                self.entity_id,
                self.handler.get_public_key_pem(),
                self.entity_type
            )
        
        # Transfer peer public keys to new handler
        self.handler.peer_public_keys = old_handler.peer_public_keys.copy()
        
        print(f"[KeyMgr] Key rotation completed for {self.entity_id}")


# Convenience functions for VANET setup

def initialize_vanet_security(rsu_ids: list, num_vehicles: int = 10) -> tuple:
    """
    Initialize security infrastructure for a VANET simulation
    Returns: (ca, rsu_key_managers, vehicle_key_managers)
    """
    print("=== Initializing VANET Security Infrastructure ===\n")
    
    # Create Certificate Authority
    ca = CertificateAuthority()
    print(f"Certificate Authority '{ca.ca_id}' initialized\n")
    
    # Create key managers for RSUs
    rsu_managers = {}
    for rsu_id in rsu_ids:
        manager = KeyManager(rsu_id, entity_type="rsu", ca=ca)
        rsu_managers[rsu_id] = manager
        print(f"RSU {rsu_id} registered")
    
    print()
    
    # Create key managers for vehicles
    vehicle_managers = {}
    for i in range(num_vehicles):
        vehicle_id = f"Vehicle_{i}"
        manager = KeyManager(vehicle_id, entity_type="vehicle", ca=ca)
        vehicle_managers[vehicle_id] = manager
    
    print(f"{num_vehicles} vehicles registered\n")
    
    # Exchange keys between RSUs and vehicles
    print("Exchanging public keys...")
    
    # RSUs register all vehicles
    for rsu_id, rsu_mgr in rsu_managers.items():
        for vehicle_id, vehicle_mgr in vehicle_managers.items():
            cert = vehicle_mgr.get_certificate()
            if cert:
                rsu_mgr.register_peer_from_certificate(cert)
    
    # Vehicles register all RSUs
    for vehicle_id, vehicle_mgr in vehicle_managers.items():
        for rsu_id, rsu_mgr in rsu_managers.items():
            cert = rsu_mgr.get_certificate()
            if cert:
                vehicle_mgr.register_peer_from_certificate(cert)
    
    # Vehicles register other vehicles (for V2V)
    for vehicle_id, vehicle_mgr in vehicle_managers.items():
        for other_vehicle_id, other_vehicle_mgr in vehicle_managers.items():
            if vehicle_id != other_vehicle_id:
                cert = other_vehicle_mgr.get_certificate()
                if cert:
                    vehicle_mgr.register_peer_from_certificate(cert)
    
    print("Key exchange completed\n")
    print("=== Security Infrastructure Ready ===\n")
    
    return ca, rsu_managers, vehicle_managers


if __name__ == "__main__":
    # Demo
    print("=== VANET Key Management Demo ===\n")
    
    # Initialize security for 2 RSUs and 5 vehicles
    ca, rsu_mgrs, vehicle_mgrs = initialize_vanet_security(
        rsu_ids=["RSU_EW_1", "RSU_EW_2"],
        num_vehicles=5
    )
    
    # Test encrypted communication
    print("--- Testing Encrypted Communication ---\n")
    
    vehicle_0_mgr = vehicle_mgrs["Vehicle_0"]
    rsu_1_mgr = rsu_mgrs["RSU_EW_1"]
    
    # Vehicle sends encrypted emergency message
    message_data = {
        "type": "emergency",
        "location": {"x": 250.0, "y": 500.0},
        "speed": 85.0
    }
    
    encrypted_msg = vehicle_0_mgr.handler.encrypt_message("RSU_EW_1", message_data, "emergency")
    print(f"Vehicle_0 sent encrypted message to RSU_EW_1")
    
    # RSU decrypts message
    decrypted = rsu_1_mgr.handler.decrypt_message(encrypted_msg)
    print(f"RSU_EW_1 decrypted: {decrypted}\n")
    
    # Test key rotation
    print("--- Testing Key Rotation ---\n")
    vehicle_0_mgr.rotate_keys()
    
    print("\n=== Demo Complete ===")
