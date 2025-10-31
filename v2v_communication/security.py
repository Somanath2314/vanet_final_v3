#!/usr/bin/env python3
"""
VANET Security Module
Implements RSA encryption, hybrid encryption (RSA+AES), and digital signatures
for secure V2V and V2I communication.
"""

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature
import os
import json
import time
from typing import Dict, Tuple, Optional
from dataclasses import dataclass, asdict
import base64


@dataclass
class SecureMessage:
    """Encrypted message with metadata"""
    sender_id: str
    timestamp: float
    nonce: str
    encrypted_data: str  # Base64 encoded
    encrypted_session_key: str  # Base64 encoded (RSA encrypted AES key)
    signature: str  # Base64 encoded digital signature
    message_type: str = "data"
    
    def to_dict(self):
        return asdict(self)
    
    @staticmethod
    def from_dict(data: dict):
        return SecureMessage(**data)


class RSAKeyPair:
    """Manages RSA key pair for an entity"""
    
    def __init__(self, entity_id: str, key_size: int = 2048):
        self.entity_id = entity_id
        self.key_size = key_size
        self.private_key = None
        self.public_key = None
        self.generate_keys()
    
    def generate_keys(self):
        """Generate new RSA key pair"""
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self.key_size,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()
        print(f"[RSA] Generated {self.key_size}-bit key pair for {self.entity_id}")
    
    def get_public_key_pem(self) -> bytes:
        """Export public key as PEM format"""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    
    def get_private_key_pem(self) -> bytes:
        """Export private key as PEM format (use with caution)"""
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
    
    @staticmethod
    def load_public_key_from_pem(pem_data: bytes):
        """Load public key from PEM format"""
        return serialization.load_pem_public_key(pem_data, backend=default_backend())


class HybridEncryption:
    """
    Hybrid encryption using RSA for key exchange and AES for data encryption.
    This is much faster than pure RSA for large messages.
    """
    
    AES_KEY_SIZE = 32  # 256 bits
    
    @staticmethod
    def generate_session_key() -> bytes:
        """Generate random AES session key"""
        return os.urandom(HybridEncryption.AES_KEY_SIZE)
    
    @staticmethod
    def encrypt_with_aes(data: bytes, session_key: bytes) -> Tuple[bytes, bytes]:
        """
        Encrypt data with AES-256-GCM
        Returns: (encrypted_data, iv)
        """
        iv = os.urandom(16)
        cipher = Cipher(
            algorithms.AES(session_key),
            modes.GCM(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(data) + encryptor.finalize()
        # Return encrypted data with authentication tag
        return encrypted_data + encryptor.tag, iv
    
    @staticmethod
    def decrypt_with_aes(encrypted_data_with_tag: bytes, session_key: bytes, iv: bytes) -> bytes:
        """
        Decrypt data with AES-256-GCM
        """
        # Split encrypted data and tag (last 16 bytes)
        encrypted_data = encrypted_data_with_tag[:-16]
        tag = encrypted_data_with_tag[-16:]
        
        cipher = Cipher(
            algorithms.AES(session_key),
            modes.GCM(iv, tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        return decryptor.update(encrypted_data) + decryptor.finalize()
    
    @staticmethod
    def encrypt_session_key_with_rsa(session_key: bytes, public_key) -> bytes:
        """Encrypt AES session key with RSA public key"""
        return public_key.encrypt(
            session_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
    
    @staticmethod
    def decrypt_session_key_with_rsa(encrypted_session_key: bytes, private_key) -> bytes:
        """Decrypt AES session key with RSA private key"""
        return private_key.decrypt(
            encrypted_session_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )


class DigitalSignature:
    """Digital signature for message authentication and integrity"""
    
    @staticmethod
    def sign_message(message: bytes, private_key) -> bytes:
        """Sign message with RSA private key"""
        return private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
    
    @staticmethod
    def verify_signature(message: bytes, signature: bytes, public_key) -> bool:
        """Verify message signature with RSA public key"""
        try:
            public_key.verify(
                signature,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except InvalidSignature:
            return False


class SecureMessageHandler:
    """
    High-level interface for secure message handling.
    Combines hybrid encryption and digital signatures.
    """
    
    def __init__(self, entity_id: str, key_size: int = 2048):
        self.entity_id = entity_id
        self.key_pair = RSAKeyPair(entity_id, key_size)
        self.peer_public_keys: Dict[str, any] = {}  # peer_id -> public_key
        self.session_keys_cache: Dict[str, bytes] = {}  # peer_id -> session_key
        self.message_history: Dict[str, float] = {}  # nonce -> timestamp (for replay protection)
        
    def register_peer_public_key(self, peer_id: str, public_key_pem: bytes):
        """Register a peer's public key"""
        public_key = RSAKeyPair.load_public_key_from_pem(public_key_pem)
        self.peer_public_keys[peer_id] = public_key
        print(f"[Security] Registered public key for {peer_id}")
    
    def get_public_key_pem(self) -> bytes:
        """Get this entity's public key for sharing"""
        return self.key_pair.get_public_key_pem()
    
    def encrypt_message(self, recipient_id: str, message_data: dict, message_type: str = "data") -> Optional[SecureMessage]:
        """
        Encrypt a message for a specific recipient
        Returns SecureMessage object or None if recipient public key not found
        """
        if recipient_id not in self.peer_public_keys:
            print(f"[Security] ERROR: Public key for {recipient_id} not found")
            return None
        
        # Generate nonce and timestamp for replay protection
        nonce = base64.b64encode(os.urandom(16)).decode('utf-8')
        timestamp = time.time()
        
        # Serialize message data
        message_json = json.dumps(message_data)
        message_bytes = message_json.encode('utf-8')
        
        # Generate or reuse session key
        if recipient_id not in self.session_keys_cache:
            session_key = HybridEncryption.generate_session_key()
            self.session_keys_cache[recipient_id] = session_key
        else:
            session_key = self.session_keys_cache[recipient_id]
        
        # Encrypt data with AES
        encrypted_data, iv = HybridEncryption.encrypt_with_aes(message_bytes, session_key)
        
        # Combine IV and encrypted data
        encrypted_payload = iv + encrypted_data
        
        # Encrypt session key with recipient's RSA public key
        recipient_public_key = self.peer_public_keys[recipient_id]
        encrypted_session_key = HybridEncryption.encrypt_session_key_with_rsa(
            session_key, recipient_public_key
        )
        
        # Sign the message (encrypt payload + nonce + timestamp)
        signature_data = encrypted_payload + nonce.encode('utf-8') + str(timestamp).encode('utf-8')
        signature = DigitalSignature.sign_message(signature_data, self.key_pair.private_key)
        
        # Create secure message
        secure_msg = SecureMessage(
            sender_id=self.entity_id,
            timestamp=timestamp,
            nonce=nonce,
            encrypted_data=base64.b64encode(encrypted_payload).decode('utf-8'),
            encrypted_session_key=base64.b64encode(encrypted_session_key).decode('utf-8'),
            signature=base64.b64encode(signature).decode('utf-8'),
            message_type=message_type
        )
        
        return secure_msg
    
    def decrypt_message(self, secure_msg: SecureMessage, max_age_seconds: float = 30.0) -> Optional[dict]:
        """
        Decrypt and verify a received secure message
        Returns decrypted message data or None if verification fails
        """
        # Check message age (replay protection)
        message_age = time.time() - secure_msg.timestamp
        if message_age > max_age_seconds:
            print(f"[Security] Message rejected: too old ({message_age:.1f}s)")
            return None
        
        # Check for duplicate nonce (replay protection)
        if secure_msg.nonce in self.message_history:
            print(f"[Security] Message rejected: duplicate nonce (replay attack)")
            return None
        
        # Get sender's public key
        if secure_msg.sender_id not in self.peer_public_keys:
            print(f"[Security] ERROR: Public key for sender {secure_msg.sender_id} not found")
            return None
        
        sender_public_key = self.peer_public_keys[secure_msg.sender_id]
        
        # Decode base64 data
        encrypted_payload = base64.b64decode(secure_msg.encrypted_data)
        encrypted_session_key = base64.b64decode(secure_msg.encrypted_session_key)
        signature = base64.b64decode(secure_msg.signature)
        
        # Verify signature
        signature_data = encrypted_payload + secure_msg.nonce.encode('utf-8') + str(secure_msg.timestamp).encode('utf-8')
        if not DigitalSignature.verify_signature(signature_data, signature, sender_public_key):
            print(f"[Security] Message rejected: invalid signature from {secure_msg.sender_id}")
            return None
        
        # Decrypt session key with our private key
        try:
            session_key = HybridEncryption.decrypt_session_key_with_rsa(
                encrypted_session_key, self.key_pair.private_key
            )
        except Exception as e:
            print(f"[Security] ERROR: Failed to decrypt session key: {e}")
            return None
        
        # Split IV and encrypted data
        iv = encrypted_payload[:16]
        encrypted_data = encrypted_payload[16:]
        
        # Decrypt message data with AES
        try:
            decrypted_bytes = HybridEncryption.decrypt_with_aes(encrypted_data, session_key, iv)
            message_json = decrypted_bytes.decode('utf-8')
            message_data = json.loads(message_json)
        except Exception as e:
            print(f"[Security] ERROR: Failed to decrypt message: {e}")
            return None
        
        # Record nonce to prevent replay
        self.message_history[secure_msg.nonce] = secure_msg.timestamp
        
        # Clean old nonces (older than max_age_seconds)
        current_time = time.time()
        self.message_history = {
            n: t for n, t in self.message_history.items() 
            if current_time - t < max_age_seconds
        }
        
        return message_data
    
    def clear_session_key(self, peer_id: str):
        """Clear cached session key for a peer (forces new key generation)"""
        if peer_id in self.session_keys_cache:
            del self.session_keys_cache[peer_id]


# Utility functions for easy integration

def create_secure_handler(entity_id: str) -> SecureMessageHandler:
    """Create a secure message handler for an entity"""
    return SecureMessageHandler(entity_id)


def exchange_public_keys(handler1: SecureMessageHandler, handler2: SecureMessageHandler):
    """Exchange public keys between two handlers"""
    handler1.register_peer_public_key(handler2.entity_id, handler2.get_public_key_pem())
    handler2.register_peer_public_key(handler1.entity_id, handler1.get_public_key_pem())
    print(f"[Security] Key exchange completed between {handler1.entity_id} and {handler2.entity_id}")


if __name__ == "__main__":
    # Demo usage
    print("=== VANET Security Module Demo ===\n")
    
    # Create handlers for RSU and vehicle
    rsu_handler = create_secure_handler("RSU_1")
    vehicle_handler = create_secure_handler("Vehicle_123")
    
    # Exchange public keys
    exchange_public_keys(rsu_handler, vehicle_handler)
    
    # Vehicle sends encrypted message to RSU
    print("\n--- Vehicle -> RSU Communication ---")
    vehicle_message = {
        "type": "emergency",
        "location": {"x": 500.0, "y": 500.0},
        "speed": 80.5,
        "timestamp": time.time()
    }
    
    encrypted_msg = vehicle_handler.encrypt_message("RSU_1", vehicle_message, "emergency")
    print(f"Encrypted message size: {len(encrypted_msg.encrypted_data)} bytes")
    
    # RSU receives and decrypts message
    decrypted_msg = rsu_handler.decrypt_message(encrypted_msg)
    print(f"Decrypted message: {decrypted_msg}")
    
    # RSU responds to vehicle
    print("\n--- RSU -> Vehicle Communication ---")
    rsu_response = {
        "type": "acknowledgement",
        "priority_granted": True,
        "route_recommendation": "E1-E2-E3"
    }
    
    encrypted_response = rsu_handler.encrypt_message("Vehicle_123", rsu_response, "response")
    decrypted_response = vehicle_handler.decrypt_message(encrypted_response)
    print(f"Decrypted response: {decrypted_response}")
    
    print("\n=== Demo Complete ===")
