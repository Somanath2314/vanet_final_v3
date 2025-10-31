#!/usr/bin/env python3
"""
Secure WiMAX Communication Module
Integrates RSA encryption with WiMAX Base Station and Mobile Station communications
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from typing import Dict, Optional
import json
from v2v_communication.security import SecureMessage, SecureMessageHandler
from v2v_communication.key_management import KeyManager


class SecureWiMAXNode:
    """
    Wraps WiMAX nodes with encryption capabilities
    Handles secure message exchange between BS and MS
    """
    
    def __init__(self, node_id: str, entity_type: str = "rsu", key_manager: Optional[KeyManager] = None):
        self.node_id = node_id
        self.entity_type = entity_type
        
        # Use provided key manager or create new one
        if key_manager:
            self.key_manager = key_manager
            self.secure_handler = key_manager.handler
        else:
            from v2v_communication.security import SecureMessageHandler
            self.secure_handler = SecureMessageHandler(node_id)
        
        self.encrypted_messages_sent = 0
        self.encrypted_messages_received = 0
        self.decryption_failures = 0
        
    def send_secure_message(self, recipient_id: str, message_data: dict, message_type: str = "data") -> Optional[dict]:
        """
        Encrypt and prepare a message for transmission
        Returns serialized encrypted message or None if encryption fails
        """
        encrypted_msg = self.secure_handler.encrypt_message(recipient_id, message_data, message_type)
        
        if encrypted_msg:
            self.encrypted_messages_sent += 1
            # Convert SecureMessage to dict for transmission
            return encrypted_msg.to_dict()
        else:
            print(f"[SecureWiMAX] Failed to encrypt message from {self.node_id} to {recipient_id}")
            return None
    
    def receive_secure_message(self, encrypted_message_dict: dict) -> Optional[dict]:
        """
        Receive and decrypt an encrypted message
        Returns decrypted message data or None if decryption/verification fails
        """
        try:
            # Convert dict back to SecureMessage object
            secure_msg = SecureMessage.from_dict(encrypted_message_dict)
            
            # Decrypt and verify
            decrypted_data = self.secure_handler.decrypt_message(secure_msg)
            
            if decrypted_data:
                self.encrypted_messages_received += 1
                return decrypted_data
            else:
                self.decryption_failures += 1
                print(f"[SecureWiMAX] Decryption failed for message to {self.node_id}")
                return None
                
        except Exception as e:
            self.decryption_failures += 1
            print(f"[SecureWiMAX] Error processing encrypted message: {e}")
            return None
    
    def register_peer(self, peer_id: str, public_key_pem: bytes):
        """Register a peer's public key for secure communication"""
        self.secure_handler.register_peer_public_key(peer_id, public_key_pem)
    
    def get_security_stats(self) -> dict:
        """Get security statistics"""
        return {
            "node_id": self.node_id,
            "messages_sent": self.encrypted_messages_sent,
            "messages_received": self.encrypted_messages_received,
            "decryption_failures": self.decryption_failures,
            "registered_peers": len(self.secure_handler.peer_public_keys)
        }


class SecureWiMAXBaseStation(SecureWiMAXNode):
    """
    Secure WiMAX Base Station with encryption
    Extends base WiMAXBaseStation with security features
    """
    
    def __init__(self, bs_id: str, x: float, y: float, config, key_manager: Optional[KeyManager] = None):
        super().__init__(bs_id, entity_type="rsu", key_manager=key_manager)
        
        # Import here to avoid circular dependency
        from sumo_simulation.wimax.node import WiMAXBaseStation
        self.base_station = WiMAXBaseStation(bs_id, x, y, config)
        
        self.x = x
        self.y = y
        self.config = config
        
    def attach(self, ms_id: str, x: float, y: float):
        """Attach a mobile station"""
        from sumo_simulation.wimax.node import WiMAXMobileStation
        ms = WiMAXMobileStation(ms_id, x, y)
        self.base_station.attach(ms)
    
    def detach(self, ms_id: str):
        """Detach a mobile station"""
        self.base_station.detach(ms_id)
    
    def send_encrypted_beacon(self, ms_id: str, beacon_data: dict) -> bool:
        """
        Send encrypted beacon to mobile station
        Returns True if encryption and queueing succeeded
        """
        encrypted_msg = self.send_secure_message(ms_id, beacon_data, "beacon")
        
        if encrypted_msg:
            # Convert encrypted message to bytes for transmission
            encrypted_json = json.dumps(encrypted_msg)
            payload_bytes = len(encrypted_json.encode('utf-8'))
            
            # Enqueue in WiMAX base station
            self.base_station.enqueue_beacon(ms_id, payload_bytes)
            return True
        
        return False
    
    def send_encrypted_data(self, ms_id: str, data: dict, message_type: str = "data") -> bool:
        """
        Send encrypted data message to mobile station
        Returns True if encryption and queueing succeeded
        """
        encrypted_msg = self.send_secure_message(ms_id, data, message_type)
        
        if encrypted_msg:
            # Convert encrypted message to bytes for transmission
            encrypted_json = json.dumps(encrypted_msg)
            payload_bytes = len(encrypted_json.encode('utf-8'))
            
            # Enqueue in WiMAX MAC layer
            self.base_station.mac.enqueue(ms_id, payload_bytes)
            return True
        
        return False
    
    def step(self):
        """Step the base station (handles transmission)"""
        self.base_station.step()
    
    def get_metrics(self) -> dict:
        """Get combined metrics (WiMAX + security)"""
        wimax_metrics = self.base_station.metrics
        security_stats = self.get_security_stats()
        
        return {
            **wimax_metrics,
            "security": security_stats
        }


class SecureWiMAXMobileStation(SecureWiMAXNode):
    """
    Secure WiMAX Mobile Station with encryption
    Represents a vehicle or mobile entity
    """
    
    def __init__(self, ms_id: str, x: float, y: float, key_manager: Optional[KeyManager] = None):
        super().__init__(ms_id, entity_type="vehicle", key_manager=key_manager)
        self.x = x
        self.y = y
        self.last_beacon_time = 0.0
    
    def update_position(self, x: float, y: float):
        """Update mobile station position"""
        self.x = x
        self.y = y
    
    def send_encrypted_request(self, bs_id: str, request_data: dict) -> Optional[dict]:
        """
        Send encrypted request to base station
        Returns encrypted message dict for transmission
        """
        return self.send_secure_message(bs_id, request_data, "request")
    
    def receive_encrypted_beacon(self, encrypted_beacon: dict) -> Optional[dict]:
        """
        Receive and decrypt beacon from base station
        Returns decrypted beacon data
        """
        return self.receive_secure_message(encrypted_beacon)


# Integration helpers

def create_secure_wimax_infrastructure(rsu_positions: dict, vehicle_ids: list, 
                                      config, ca=None) -> tuple:
    """
    Create secure WiMAX infrastructure with encryption
    
    Args:
        rsu_positions: dict of {rsu_id: (x, y)}
        vehicle_ids: list of vehicle IDs
        config: WiMAXConfig instance
        ca: Optional CertificateAuthority for key management
    
    Returns:
        (secure_base_stations, secure_mobile_stations, key_managers)
    """
    from v2v_communication.key_management import KeyManager
    
    secure_base_stations = {}
    secure_mobile_stations = {}
    key_managers = {}
    
    print("[SecureWiMAX] Initializing secure WiMAX infrastructure...")
    
    # Create secure base stations (RSUs)
    for rsu_id, (x, y) in rsu_positions.items():
        key_mgr = KeyManager(rsu_id, entity_type="rsu", ca=ca)
        secure_bs = SecureWiMAXBaseStation(rsu_id, x, y, config, key_manager=key_mgr)
        secure_base_stations[rsu_id] = secure_bs
        key_managers[rsu_id] = key_mgr
        print(f"  Created secure BS: {rsu_id} at ({x}, {y})")
    
    # Create secure mobile stations (vehicles)
    for vehicle_id in vehicle_ids:
        key_mgr = KeyManager(vehicle_id, entity_type="vehicle", ca=ca)
        secure_ms = SecureWiMAXMobileStation(vehicle_id, 0.0, 0.0, key_manager=key_mgr)
        secure_mobile_stations[vehicle_id] = secure_ms
        key_managers[vehicle_id] = key_mgr
    
    print(f"  Created {len(secure_mobile_stations)} secure mobile stations")
    
    # Exchange keys between all entities
    print("[SecureWiMAX] Exchanging keys...")
    
    # RSUs register all vehicles
    for rsu_id, rsu in secure_base_stations.items():
        for vehicle_id in vehicle_ids:
            vehicle_key_mgr = key_managers[vehicle_id]
            if vehicle_key_mgr.certificate:
                key_managers[rsu_id].register_peer_from_certificate(vehicle_key_mgr.certificate)
    
    # Vehicles register all RSUs
    for vehicle_id, vehicle in secure_mobile_stations.items():
        for rsu_id in rsu_positions.keys():
            rsu_key_mgr = key_managers[rsu_id]
            if rsu_key_mgr.certificate:
                key_managers[vehicle_id].register_peer_from_certificate(rsu_key_mgr.certificate)
    
    print("[SecureWiMAX] Secure infrastructure ready")
    
    return secure_base_stations, secure_mobile_stations, key_managers


if __name__ == "__main__":
    # Demo
    print("=== Secure WiMAX Communication Demo ===\n")
    
    from sumo_simulation.wimax.config import WiMAXConfig
    from v2v_communication.key_management import CertificateAuthority
    
    # Create CA
    ca = CertificateAuthority()
    
    # Create WiMAX config
    config = WiMAXConfig()
    
    # Create secure infrastructure
    rsu_positions = {
        "RSU_1": (500.0, 500.0),
        "RSU_2": (1000.0, 500.0)
    }
    
    vehicle_ids = ["Vehicle_0", "Vehicle_1", "Vehicle_2"]
    
    secure_bs, secure_ms, key_mgrs = create_secure_wimax_infrastructure(
        rsu_positions, vehicle_ids, config, ca
    )
    
    # Test encrypted communication
    print("\n--- Testing Encrypted V2I Communication ---\n")
    
    vehicle_0 = secure_ms["Vehicle_0"]
    rsu_1 = secure_bs["RSU_1"]
    
    # Vehicle sends encrypted request
    request_data = {
        "type": "emergency",
        "location": {"x": 250.0, "y": 500.0},
        "speed": 85.0,
        "request": "priority_access"
    }
    
    encrypted_request = vehicle_0.send_encrypted_request("RSU_1", request_data)
    print(f"Vehicle_0 sent encrypted request to RSU_1")
    print(f"  Encrypted payload size: {len(json.dumps(encrypted_request))} bytes")
    
    # RSU receives and decrypts
    decrypted_request = rsu_1.receive_secure_message(encrypted_request)
    print(f"\nRSU_1 decrypted request: {decrypted_request}")
    
    # RSU sends encrypted response
    response_data = {
        "type": "response",
        "priority_granted": True,
        "recommended_route": "E1-E2-E3",
        "timestamp": time.time()
    }
    
    encrypted_response = rsu_1.send_secure_message("Vehicle_0", response_data, "response")
    print(f"\nRSU_1 sent encrypted response")
    
    # Vehicle decrypts response
    decrypted_response = vehicle_0.receive_secure_message(encrypted_response)
    print(f"Vehicle_0 decrypted response: {decrypted_response}")
    
    # Show security stats
    print("\n--- Security Statistics ---")
    print(f"RSU_1: {rsu_1.get_security_stats()}")
    print(f"Vehicle_0: {vehicle_0.get_security_stats()}")
    
    print("\n=== Demo Complete ===")
