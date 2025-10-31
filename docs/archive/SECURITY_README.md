# VANET Security System

## Overview

This is a complete RSA-based encryption and security system for Vehicular Ad Hoc Networks (VANET) implementing secure Vehicle-to-Vehicle (V2V) and Vehicle-to-Infrastructure (V2I) communication.

## Architecture

### Components

1. **Security Module** (`v2v_communication/security.py`)
   - RSA key pair generation and management
   - Hybrid encryption (RSA + AES-256-GCM)
   - Digital signatures (RSA-PSS with SHA256)
   - Replay attack prevention (nonce + timestamp)
   - Message tampering detection

2. **Key Management** (`v2v_communication/key_management.py`)
   - Certificate Authority (CA) with 4096-bit keys
   - Key storage and retrieval
   - Certificate issuance and verification
   - Key rotation
   - Peer registration

3. **Secure WiMAX** (`sumo_simulation/wimax/secure_wimax.py`)
   - Integration with existing WiMAX protocol
   - Secure base station (RSU)
   - Secure mobile station (Vehicle)
   - Encrypted beacons and data transmission

## Security Features

### 1. Hybrid Encryption
- **RSA-2048** for asymmetric key exchange
- **AES-256-GCM** for efficient symmetric data encryption
- Session key caching for improved performance
- Each message uses a unique AES key for forward secrecy

### 2. Authentication & Integrity
- **Digital Signatures**: RSA-PSS with SHA256
- **Certificate-based Trust**: CA issues and verifies certificates
- **Message Authentication**: Every message is signed by sender
- **Integrity Verification**: Signatures prevent tampering

### 3. Attack Prevention
- **Replay Attacks**: Unique nonce per message, 30-second message validity window
- **Tampering**: Signature verification detects any modification
- **Man-in-the-Middle**: Public key exchange validated through CA certificates
- **Unknown Senders**: Only messages from registered entities are accepted

### 4. Key Management
- **Certificate Authority**: 4096-bit RSA keys for CA
- **Entity Keys**: 2048-bit RSA keys for vehicles and RSUs
- **Key Rotation**: Periodic key updates supported
- **Key Storage**: Secure persistent storage with proper permissions

## Usage

### Basic Setup

```python
from v2v_communication.key_management import initialize_vanet_security

# Initialize complete security infrastructure
ca, rsu_managers, vehicle_managers = initialize_vanet_security(
    rsu_ids=["RSU_1", "RSU_2"],
    num_vehicles=10
)

# Get a specific entity manager
vehicle = vehicle_managers["Vehicle_0"]
rsu = rsu_managers["RSU_1"]
```

### Sending Secure Messages

```python
# Vehicle sends emergency message to RSU
emergency_data = {
    "type": "emergency",
    "priority": "HIGH",
    "location": {"x": 500.0, "y": 250.0},
    "speed": 90.0
}

# Encrypt the message
encrypted_msg = vehicle.handler.encrypt_message(
    recipient_id="RSU_1",
    message_data=emergency_data,
    message_type="emergency"
)

# RSU receives and decrypts
decrypted_data = rsu.handler.decrypt_message(encrypted_msg)
```

### V2V Communication

```python
# Vehicle-to-Vehicle hazard warning
hazard_data = {
    "type": "hazard_warning",
    "hazard_type": "accident",
    "location": {"x": 800.0, "y": 500.0},
    "severity": "high"
}

# Sender encrypts
encrypted = sender.handler.encrypt_message("Vehicle_5", hazard_data)

# Receiver decrypts
decrypted = receiver.handler.decrypt_message(encrypted)
```

### Certificate Verification

```python
# Get entity certificate
cert = vehicle.get_certificate()

# CA verifies certificate
is_valid = ca.verify_certificate(cert)

if is_valid:
    print("Certificate is valid and trusted")
```

### Key Rotation

```python
# Rotate keys for a vehicle
vehicle_mgr.rotate_keys()

# Old certificate is revoked, new certificate issued
# Peer keys must be re-exchanged
```

## Integration with WiMAX

### Secure Base Station (RSU)

```python
from sumo_simulation.wimax.secure_wimax import SecureWiMAXBaseStation

# Create secure RSU
rsu_key_manager = rsu_managers["RSU_1"]
secure_rsu = SecureWiMAXBaseStation(
    station_id="RSU_1",
    position=(500.0, 500.0),
    key_manager=rsu_key_manager
)

# Send encrypted beacon
secure_rsu.send_encrypted_beacon({
    "type": "beacon",
    "timestamp": time.time(),
    "traffic_conditions": "normal"
})

# Send encrypted data to vehicle
secure_rsu.send_encrypted_data("Vehicle_0", {
    "type": "traffic_update",
    "green_time_remaining": 15
})
```

### Secure Mobile Station (Vehicle)

```python
from sumo_simulation.wimax.secure_wimax import SecureWiMAXMobileStation

# Create secure vehicle
vehicle_key_manager = vehicle_managers["Vehicle_0"]
secure_vehicle = SecureWiMAXMobileStation(
    station_id="Vehicle_0",
    key_manager=vehicle_key_manager
)

# Attach to RSU with encryption
secure_vehicle.attach_to_base_station("RSU_1")

# Send encrypted request
secure_vehicle.send_encrypted_request("RSU_1", {
    "type": "emergency_request",
    "priority": "HIGH"
})
```

## Message Format

### SecureMessage Structure

```python
@dataclass
class SecureMessage:
    sender_id: str              # Entity ID of sender
    timestamp: float            # Unix timestamp
    nonce: str                  # Unique message identifier
    encrypted_data: str         # Base64 encoded encrypted data
    encrypted_session_key: str  # Base64 encoded RSA-encrypted AES key
    signature: str              # Base64 encoded digital signature
    message_type: str          # "data", "emergency", "beacon", etc.
```

### Encryption Process

1. **Generate Session Key**: Random 256-bit AES key
2. **Encrypt Data**: Encrypt message data with AES-256-GCM
3. **Encrypt Session Key**: Encrypt AES key with recipient's RSA public key
4. **Sign Message**: Sign encrypted data with sender's RSA private key
5. **Package**: Combine all components into SecureMessage

### Decryption Process

1. **Verify Signature**: Verify message signature with sender's public key
2. **Check Replay**: Verify nonce is unique and timestamp is recent
3. **Decrypt Session Key**: Decrypt AES key with recipient's RSA private key
4. **Decrypt Data**: Decrypt message data with AES key
5. **Return**: Deserialize and return original message data

## Performance Considerations

### Encryption Overhead
- **RSA encryption**: ~5-10ms per message (session key only)
- **AES encryption**: <1ms per message (bulk data)
- **Digital signature**: ~5-10ms per message
- **Total overhead**: ~10-20ms per message

### Optimization Strategies
- **Session key caching**: Reuse session keys for same sender-receiver pair
- **Batch processing**: Process multiple messages together
- **Async encryption**: Use threading/asyncio for parallel processing
- **Hardware acceleration**: Use AES-NI CPU instructions when available

### Memory Usage
- **RSA keys**: ~2KB per entity (2048-bit keys)
- **CA key**: ~4KB (4096-bit key)
- **Certificates**: ~1KB per entity
- **Total for 100 vehicles + 10 RSUs**: ~220KB

## Security Analysis

### Threat Model

**Protected Against:**
- ✓ Eavesdropping (AES-256 encryption)
- ✓ Message tampering (Digital signatures)
- ✓ Replay attacks (Nonce + timestamp)
- ✓ Impersonation (Certificate-based authentication)
- ✓ Man-in-the-middle (CA-verified public keys)

**Not Protected Against:**
- ✗ Denial of Service (DoS) attacks
- ✗ Compromised CA (trust anchor)
- ✗ Side-channel attacks (timing, power analysis)
- ✗ Quantum computing (RSA will be vulnerable)

### Recommended Practices

1. **Key Rotation**: Rotate keys every 30-90 days
2. **Certificate Expiry**: Use short validity periods (1 year)
3. **Secure Storage**: Store private keys with restricted permissions
4. **Revocation**: Maintain Certificate Revocation List (CRL)
5. **Monitoring**: Log all security events and anomalies

## Testing

### Run Unit Tests

```bash
python3 tests/test_security.py
```

**Test Coverage:**
- RSA key generation and serialization
- AES encryption/decryption
- RSA session key encryption
- Digital signatures
- Message tampering detection
- Replay attack prevention
- Certificate issuance and verification
- Key rotation
- V2I and V2V communication

### Run Examples

```bash
python3 examples/secure_communication_example.py
```

**Examples Demonstrated:**
- V2I emergency message
- V2V hazard warning
- Replay attack prevention
- Message tampering detection
- Certificate verification

## File Structure

```
v2v_communication/
├── security.py              # Core encryption and security primitives
├── key_management.py        # CA, key storage, and certificates
└── __init__.py

sumo_simulation/wimax/
├── secure_wimax.py          # Secure WiMAX wrapper
├── node.py                  # Original WiMAX implementation
├── mac.py
├── phy.py
└── config.py

tests/
└── test_security.py         # Unit tests

examples/
└── secure_communication_example.py  # Usage examples
```

## Dependencies

```bash
pip install cryptography
```

**Required:**
- `cryptography>=41.0.0` - RSA, AES, and signature algorithms

**Optional:**
- `pycryptodome>=3.19.0` - Alternative crypto library (not used currently)

## API Reference

### RSAKeyPair
- `__init__(entity_id, key_size=2048)` - Generate new key pair
- `get_public_key_pem()` - Export public key as PEM
- `get_private_key_pem()` - Export private key as PEM
- `load_public_key_from_pem(pem_data)` - Import public key

### HybridEncryption
- `generate_session_key()` - Generate 256-bit AES key
- `encrypt_with_aes(data, key)` - Encrypt data with AES-GCM
- `decrypt_with_aes(encrypted, key, iv)` - Decrypt AES-GCM data
- `encrypt_session_key_with_rsa(key, public_key)` - Encrypt AES key
- `decrypt_session_key_with_rsa(encrypted, private_key)` - Decrypt AES key

### DigitalSignature
- `sign_message(message, private_key)` - Sign message with RSA-PSS
- `verify_signature(message, signature, public_key)` - Verify signature

### SecureMessageHandler
- `__init__(entity_id)` - Create handler for entity
- `register_peer_public_key(peer_id, public_key)` - Register peer
- `encrypt_message(recipient_id, data, message_type)` - Encrypt and sign
- `decrypt_message(secure_msg, max_age_seconds)` - Decrypt and verify

### KeyManager
- `__init__(entity_id, entity_type, ca)` - Create key manager
- `get_certificate()` - Get entity certificate
- `register_peer(peer_id, peer_cert)` - Register peer with certificate
- `rotate_keys()` - Generate new keys and certificate

### CertificateAuthority
- `__init__(ca_id="VANET_CA")` - Initialize CA
- `issue_certificate(entity_id, public_key, entity_type, validity_days)` - Issue cert
- `verify_certificate(cert)` - Verify certificate validity

## Future Enhancements

1. **Elliptic Curve Cryptography (ECC)**: Smaller keys, faster operations
2. **Quantum-Resistant Algorithms**: Prepare for post-quantum era
3. **Hardware Security Modules (HSM)**: Secure key storage
4. **Certificate Revocation Lists (CRL)**: Real-time revocation checking
5. **Group Signatures**: Anonymous authentication for privacy
6. **Blockchain Integration**: Decentralized certificate management

## License

This security module is part of the VANET simulation system.

## Authors

Developed as part of the VANET capstone project.

## References

1. IEEE 1609.2 - Security Services for Applications and Management Messages
2. NIST SP 800-57 - Recommendation for Key Management
3. RFC 5280 - Internet X.509 Public Key Infrastructure Certificate
4. ETSI TS 103 097 - Security header and certificate formats
