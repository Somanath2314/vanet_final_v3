"""
V2V Communication Module with RSA Security Implementation
Implements secure vehicle-to-vehicle communication with performance metrics
"""

import time
import json
import threading
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import logging
from utils.logging_config import setup_logging
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.exceptions import InvalidSignature
import hashlib
import os
import random
import statistics
from collections import defaultdict, deque


@dataclass
class SecurityMetrics:
    """Security performance metrics for V2V communication"""
    encryption_overhead: float = 0.0  # Time taken for encryption (ms)
    decryption_overhead: float = 0.0  # Time taken for decryption (ms)
    key_exchange_latency: float = 0.0  # Key exchange latency (ms)
    security_processing_time: float = 0.0  # Total security processing time (ms)
    message_authentication_delay: float = 0.0  # Authentication delay (ms)
    signature_generation_time: float = 0.0  # Digital signature generation time (ms)
    signature_verification_time: float = 0.0  # Digital signature verification time (ms)
    total_messages_processed: int = 0
    successful_authentications: int = 0
    failed_authentications: int = 0


@dataclass
class VehicleIdentity:
    """Vehicle identity for authentication"""
    vehicle_id: str
    public_key: rsa.RSAPublicKey
    certificate_hash: str
    valid_from: float
    valid_until: float


@dataclass
class SecureMessage:
    """Secure V2V message with digital signature"""
    message_id: str
    sender_id: str
    receiver_id: str
    message_type: str  # 'safety', 'traffic_info', 'emergency', 'cooperative'
    payload: Dict
    timestamp: float
    signature: bytes
    encrypted_payload: bytes = b""
    session_key: bytes = b""


class RSASecurityManager:
    """RSA-based security manager for V2V communication"""

    def __init__(self, key_size: int = 2048):
        self.key_size = key_size
        self.vehicle_keys: Dict[str, Tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]] = {}
        self.vehicle_certificates: Dict[str, VehicleIdentity] = {}
        self.revoked_certificates: set = set()

        # Performance tracking
        self.metrics = SecurityMetrics()
        self.performance_history = deque(maxlen=1000)
        # Logger
        self.logger = setup_logging('v2v')

    def generate_vehicle_keys(self, vehicle_id: str) -> Tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
        """Generate RSA key pair for a vehicle"""
        start_time = time.time()

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self.key_size
        )
        public_key = private_key.public_key()

        # Store keys
        self.vehicle_keys[vehicle_id] = (private_key, public_key)

        generation_time = (time.time() - start_time) * 1000
        self.logger.info(f"Key generation completed", extra={'extra': {'vehicle_id': vehicle_id, 'generation_ms': generation_time}})

        return private_key, public_key

    def register_vehicle(self, vehicle_id: str, validity_hours: int = 24) -> VehicleIdentity:
        """Register a vehicle with certificate"""
        if vehicle_id not in self.vehicle_keys:
            self.generate_vehicle_keys(vehicle_id)

        private_key, public_key = self.vehicle_keys[vehicle_id]

        # Create certificate
        cert_data = f"{vehicle_id}:{public_key.public_bytes(encoding=serialization.Encoding.DER, format=serialization.PublicFormat.SubjectPublicKeyInfo).hex()}:{time.time()}"

        # Create certificate hash (simplified - in real implementation would use proper CA)
        certificate_hash = hashlib.sha256(cert_data.encode()).hexdigest()

        vehicle_cert = VehicleIdentity(
            vehicle_id=vehicle_id,
            public_key=public_key,
            certificate_hash=certificate_hash,
            valid_from=time.time(),
            valid_until=time.time() + (validity_hours * 3600)
        )

        self.vehicle_certificates[vehicle_id] = vehicle_cert
        self.logger.info("Registered vehicle certificate", extra={'extra': {'vehicle_id': vehicle_id, 'certificate_hash': certificate_hash[:16]}})
        return vehicle_cert

    def encrypt_message(self, message: bytes, recipient_public_key: rsa.RSAPublicKey) -> Tuple[bytes, float]:
        """Encrypt message using RSA"""
        start_time = time.time()

        # Generate session key for symmetric encryption (AES)
        session_key = os.urandom(32)  # 256-bit key

        # In a real implementation, you'd use AES here
        # For this demo, we'll simulate encryption with a simple XOR
        # (Note: This is NOT secure - just for demonstration)
        encrypted_payload = bytes([b ^ session_key[i % len(session_key)] for i, b in enumerate(message)])

        # Encrypt session key with RSA
        encrypted_session_key = recipient_public_key.encrypt(
            session_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        encryption_time = (time.time() - start_time) * 1000

        # Update metrics
        self.metrics.encryption_overhead = max(self.metrics.encryption_overhead, encryption_time)
        self.metrics.total_messages_processed += 1

        self.logger.debug("Message encrypted", extra={'extra': {'encryption_ms': encryption_time}})

        return encrypted_session_key + encrypted_payload, encryption_time

    def decrypt_message(self, encrypted_data: bytes, recipient_private_key: rsa.RSAPrivateKey) -> Tuple[bytes, float]:
        """Decrypt message using RSA"""
        start_time = time.time()

        # Split encrypted session key and payload
        encrypted_session_key = encrypted_data[:256]  # RSA-2048 encrypted key size
        encrypted_payload = encrypted_data[256:]

        # Decrypt session key
        session_key = recipient_private_key.decrypt(
            encrypted_session_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        # Decrypt payload (simplified XOR)
        decrypted_payload = bytes([b ^ session_key[i % len(session_key)] for i, b in enumerate(encrypted_payload)])

        decryption_time = (time.time() - start_time) * 1000

        # Update metrics
        self.metrics.decryption_overhead = max(self.metrics.decryption_overhead, decryption_time)

        self.logger.debug("Message decrypted", extra={'extra': {'decryption_ms': decryption_time}})

        return decrypted_payload, decryption_time

    def sign_message(self, message: bytes, sender_private_key: rsa.RSAPrivateKey) -> Tuple[bytes, float]:
        """Create digital signature for message"""
        start_time = time.time()

        signature = sender_private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )

        signature_time = (time.time() - start_time) * 1000

        # Update metrics
        self.metrics.signature_generation_time = max(self.metrics.signature_generation_time, signature_time)

        self.logger.debug("Signature generated", extra={'extra': {'signature_ms': signature_time}})

        return signature, signature_time

    def verify_signature(self, message: bytes, signature: bytes, sender_public_key: rsa.RSAPublicKey) -> Tuple[bool, float]:
        """Verify digital signature"""
        start_time = time.time()

        try:
            sender_public_key.verify(
                signature,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            is_valid = True
            self.metrics.successful_authentications += 1
        except InvalidSignature:
            is_valid = False
            self.metrics.failed_authentications += 1

        verification_time = (time.time() - start_time) * 1000

        # Update metrics
        self.metrics.signature_verification_time = max(self.metrics.signature_verification_time, verification_time)
        self.metrics.message_authentication_delay = max(self.metrics.message_authentication_delay, verification_time)

        self.logger.debug("Signature verification", extra={'extra': {'valid': is_valid, 'verification_ms': verification_time}})

        return is_valid, verification_time

    def authenticate_vehicle(self, vehicle_id: str) -> bool:
        """Authenticate a vehicle using its certificate"""
        if vehicle_id in self.revoked_certificates:
            return False

        if vehicle_id not in self.vehicle_certificates:
            return False

        cert = self.vehicle_certificates[vehicle_id]
        current_time = time.time()

        return current_time >= cert.valid_from and current_time <= cert.valid_until

    def get_security_metrics(self) -> Dict:
        """Get current security performance metrics"""
        return asdict(self.metrics)


class V2VCommunicationManager:
    """Main V2V Communication Manager with security"""

    def __init__(self, security_manager: RSASecurityManager):
        self.security_manager = security_manager
        self.message_history: List[SecureMessage] = []
        self.communication_range = 300  # meters
        self.message_queue: Dict[str, List[SecureMessage]] = defaultdict(list)
        self.broadcast_messages: List[SecureMessage] = []

        # Performance tracking
        self.latency_history = deque(maxlen=1000)
        self.throughput_history = deque(maxlen=1000)

    def send_secure_message(self, sender_id: str, receiver_id: str, message_type: str,
                          payload: Dict, broadcast: bool = False) -> Optional[SecureMessage]:
        """Send a secure V2V message"""
        start_time = time.time()

        # Authenticate sender
        if not self.security_manager.authenticate_vehicle(sender_id):
            self.security_manager.logger.warning("Authentication failed for sender", extra={'extra': {'sender_id': sender_id}})
            return None

        # Prepare message
        message_data = {
            'sender_id': sender_id,
            'receiver_id': receiver_id,
            'message_type': message_type,
            'payload': payload,
            'timestamp': time.time()
        }

        message_bytes = json.dumps(message_data, sort_keys=True).encode('utf-8')

        # Create digital signature
        sender_private_key = self.security_manager.vehicle_keys[sender_id][0]
        signature, sig_time = self.security_manager.sign_message(message_bytes, sender_private_key)

        # Encrypt message for specific receiver or broadcast
        if broadcast:
            # For broadcast, we don't encrypt (or use group key in real implementation)
            encrypted_payload = message_bytes
            enc_time = 0.0
        else:
            receiver_cert = self.security_manager.vehicle_certificates.get(receiver_id)
            if not receiver_cert:
                self.security_manager.logger.warning("No certificate for receiver", extra={'extra': {'receiver_id': receiver_id}})
                return None

            encrypted_data, enc_time = self.security_manager.encrypt_message(
                message_bytes, receiver_cert.public_key
            )
            encrypted_payload = encrypted_data

        # Create secure message
        secure_message = SecureMessage(
            message_id=f"msg_{int(time.time()*1000)}_{random.randint(1000, 9999)}",
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=message_type,
            payload=payload,
            timestamp=time.time(),
            signature=signature,
            encrypted_payload=encrypted_payload
        )

        # Simulate network latency
        network_latency = random.uniform(5, 50)  # 5-50ms network latency
        time.sleep(network_latency / 1000)

        # Store message
        self.message_history.append(secure_message)

        if broadcast:
            self.broadcast_messages.append(secure_message)
        else:
            self.message_queue[receiver_id].append(secure_message)

        # Update performance metrics
        total_time = (time.time() - start_time) * 1000
        self.security_manager.metrics.security_processing_time = max(
            self.security_manager.metrics.security_processing_time, total_time
        )

        # Track key exchange latency (simplified)
        self.security_manager.metrics.key_exchange_latency = max(
            self.security_manager.metrics.key_exchange_latency, network_latency
        )

        self.latency_history.append(total_time)
        self.throughput_history.append(1)  # Message count per time unit

        self.security_manager.logger.info(
            "Sent secure message",
            extra={'extra': {
                'sender_id': sender_id,
                'receiver_id': receiver_id,
                'message_type': message_type,
                'total_ms': total_time,
                'encryption_ms': enc_time
            }}
        )

        return secure_message

    def receive_message(self, receiver_id: str) -> List[SecureMessage]:
        """Receive messages for a vehicle"""
        # Get messages for this receiver
        messages = self.message_queue[receiver_id].copy()
        self.message_queue[receiver_id].clear()

        # Process each message
        valid_messages = []
        for message in messages:
            if self._verify_and_decrypt_message(message, receiver_id):
                valid_messages.append(message)

        self.security_manager.logger.debug("Messages received for vehicle", extra={'extra': {'receiver_id': receiver_id, 'count': len(valid_messages)}})

        return valid_messages

    def _verify_and_decrypt_message(self, message: SecureMessage, receiver_id: str) -> bool:
        """Verify signature and decrypt message"""
        start_time = time.time()

        try:
            # Verify digital signature
            sender_cert = self.security_manager.vehicle_certificates.get(message.sender_id)
            if not sender_cert:
                self.security_manager.logger.warning("No certificate for sender", extra={'extra': {'sender_id': message.sender_id}})
                return False

            # For broadcast messages, we need to reconstruct the original message data
            # that was signed (without the current timestamp)
            if message.receiver_id == 'BROADCAST':
                # For broadcast messages, reconstruct the original message data
                original_message_data = {
                    'sender_id': message.sender_id,
                    'receiver_id': message.receiver_id,
                    'message_type': message.message_type,
                    'payload': message.payload,
                    'timestamp': message.timestamp
                }
            else:
                # For direct messages, use the stored message data
                original_message_data = {
                    'sender_id': message.sender_id,
                    'receiver_id': message.receiver_id,
                    'message_type': message.message_type,
                    'payload': message.payload,
                    'timestamp': message.timestamp
                }

            message_bytes = json.dumps(original_message_data, sort_keys=True).encode('utf-8')

            # Verify signature
            is_valid_sig, sig_time = self.security_manager.verify_signature(
                message_bytes, message.signature, sender_cert.public_key
            )

            if not is_valid_sig:
                self.security_manager.logger.warning("Invalid signature", extra={'extra': {'message_id': message.message_id}})
                return False

            # Decrypt message if needed
            if message.encrypted_payload and message.encrypted_payload != message_bytes:
                receiver_private_key = self.security_manager.vehicle_keys[receiver_id][0]
                decrypted_data, dec_time = self.security_manager.decrypt_message(
                    message.encrypted_payload, receiver_private_key
                )

                # For encrypted messages, verify the decrypted data matches
                if decrypted_data != message_bytes:
                    self.security_manager.logger.warning("Decryption failed", extra={'extra': {'message_id': message.message_id}})
                    return False

            total_time = (time.time() - start_time) * 1000
            self.security_manager.logger.info("Verified message", extra={'extra': {'message_id': message.message_id, 'verification_ms': total_time}})

            return True

        except Exception as e:
            self.security_manager.logger.error(f"Error processing message {message.message_id}: {e}", extra={'extra': {'exception': str(e)}})
            return False

    def broadcast_safety_message(self, sender_id: str, location: Dict, speed: float,
                               emergency: bool = False) -> Optional[SecureMessage]:
        """Broadcast safety message to nearby vehicles"""
        payload = {
            'location': location,
            'speed': speed,
            'emergency': emergency,
            'message': 'Safety alert' if not emergency else 'EMERGENCY ALERT'
        }

        return self.send_secure_message(
            sender_id=sender_id,
            receiver_id='BROADCAST',
            message_type='safety',
            payload=payload,
            broadcast=True
        )

    def send_traffic_info(self, sender_id: str, receiver_id: str, traffic_data: Dict) -> Optional[SecureMessage]:
        """Send traffic information to another vehicle"""
        payload = {
            'traffic_condition': traffic_data.get('condition', 'unknown'),
            'congestion_level': traffic_data.get('congestion', 0.0),
            'recommended_action': traffic_data.get('action', 'proceed_normally')
        }

        return self.send_secure_message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type='traffic_info',
            payload=payload,
            broadcast=False
        )

    def get_performance_metrics(self) -> Dict:
        """Get V2V communication performance metrics"""
        metrics = self.security_manager.get_security_metrics()

        # Add communication-specific metrics
        if self.latency_history:
            metrics['average_latency'] = statistics.mean(self.latency_history)
            metrics['max_latency'] = max(self.latency_history)
            metrics['min_latency'] = min(self.latency_history)

        if self.throughput_history:
            metrics['messages_per_second'] = len(self.throughput_history) / max(1, len(self.latency_history))

        metrics['total_messages_sent'] = len(self.message_history)
        metrics['total_broadcasts'] = len(self.broadcast_messages)
        metrics['communication_range'] = self.communication_range

        return metrics


# Example usage and testing
if __name__ == "__main__":
    # Initialize security manager
    security_manager = RSASecurityManager()

    # Register vehicles
    vehicle1 = security_manager.register_vehicle("vehicle_001")
    vehicle2 = security_manager.register_vehicle("vehicle_002")

    security_manager.logger.info("Vehicle 1 Certificate", extra={'extra': {'certificate': vehicle1.certificate_hash[:16]}})
    security_manager.logger.info("Vehicle 2 Certificate", extra={'extra': {'certificate': vehicle2.certificate_hash[:16]}})

    # Initialize V2V manager
    v2v_manager = V2VCommunicationManager(security_manager)

    # Send a secure message
    message = v2v_manager.send_traffic_info(
        sender_id="vehicle_001",
        receiver_id="vehicle_002",
        traffic_data={
            'condition': 'heavy_traffic',
            'congestion': 0.8,
            'action': 'slow_down'
        }
    )

    if message:
        security_manager.logger.info("Message sent", extra={'extra': {'message_id': message.message_id}})

        # Receive message
        received_messages = v2v_manager.receive_message("vehicle_002")
        security_manager.logger.info("Received messages", extra={'extra': {'count': len(received_messages)}})

        # Get performance metrics
        metrics = v2v_manager.get_performance_metrics()
        security_manager.logger.info("Security metrics", extra={'extra': metrics})
