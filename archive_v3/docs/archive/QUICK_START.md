# VANET Security - Quick Start Guide

## 🚀 Running the Simulation

### Without Security (Faster - Recommended for Testing)

```bash
cd /home/shreyasdk/capstone/vanet_final_v3

# Rule-based with GUI (default)
./run_integrated_sumo_ns3.sh --gui --steps 1000

# RL-based with GUI
./run_integrated_sumo_ns3.sh --rl --gui --steps 1000

# Background mode (no GUI, faster)
./run_integrated_sumo_ns3.sh --steps 1000
```

### With Security Enabled (RSA Encryption)

**Note**: Security adds 30-60 seconds startup time for key generation

```bash
# Rule-based with security
./run_integrated_sumo_ns3.sh --gui --steps 1000 --security

# RL-based with security
./run_integrated_sumo_ns3.sh --rl --gui --steps 1000 --security
```

## 📋 Command Line Options

```
./run_integrated_sumo_ns3.sh [OPTIONS]

Options:
  --rl         Use RL-based traffic control (default: rule-based)
  --gui        Use SUMO-GUI for visualization
  --steps N    Number of simulation steps (default: 1000)
  --security   Enable RSA encryption for V2V/V2I communications
```

## 🔐 What `--security` Does

When you add the `--security` flag:

### Startup (30-60 seconds):
1. **Certificate Authority**: Generates 4096-bit RSA key
2. **RSU Keys**: Generates 2048-bit RSA keys for 4 RSUs
3. **Vehicle Keys**: Pre-generates 2048-bit RSA keys for 20 vehicles
4. **Key Exchange**: All entities exchange public keys

### During Simulation:
- **Secure RSUs**: RSU_J2 and RSU_J3 use `SecureWiMAXBaseStation`
- **Dynamic Registration**: New vehicles get RSA keys automatically
- **Encrypted Messages**: All V2I/V2V use RSA-2048 + AES-256-GCM
- **Digital Signatures**: Every message is signed and verified
- **Emergency Vehicles**: Ambulances send encrypted priority requests

### Security Features:
- ✅ Hybrid encryption (RSA + AES-256-GCM)
- ✅ Digital signatures (RSA-PSS with SHA256)
- ✅ Replay attack prevention (nonce + timestamp)
- ✅ Certificate-based authentication (CA)
- ✅ Message tampering detection

## 📊 Performance Comparison

| Mode | Startup Time | Per-Message Overhead | Message Size |
|------|--------------|---------------------|--------------|
| **Without Security** | <5 seconds | 0ms | ~100 bytes |
| **With Security** | 30-60 seconds | ~20ms | ~700 bytes |

## 🎯 Examples

### Quick Test (No Security)
```bash
# Fast startup, good for testing traffic control
./run_integrated_sumo_ns3.sh --gui --steps 100
```

### Full Simulation with RL (No Security)
```bash
# Use for RL training/testing
./run_integrated_sumo_ns3.sh --rl --gui --steps 3600
```

### Security Demonstration (With Security)
```bash
# Show encrypted emergency vehicle communications
./run_integrated_sumo_ns3.sh --gui --steps 500 --security
```

### Production Simulation (With Security + RL)
```bash
# Full featured: RL control + encryption
./run_integrated_sumo_ns3.sh --rl --gui --steps 3600 --security
```

## 📁 Output Files

Results are saved to `sumo_simulation/output/`:

- `integrated_simulation_results.json` - Full metrics
- `v2i_packets.csv` - V2I packet log (includes encrypted packets if --security used)
- `v2i_metrics.csv` - WiMAX metrics
- `summary.xml` - SUMO summary
- `tripinfo.xml` - Vehicle trip information

## 🔍 What You'll See

### Without `--security`:
```
⚠️  Security disabled (use --security flag to enable RSA encryption)
🔧 Initializing simulation components...
⚠️  Security disabled: Running without encryption
✅ Connected to SUMO successfully
🚀 Starting integrated simulation...
```

### With `--security`:
```
🔐 Initializing VANET Security Infrastructure...
  ⏳ This may take 30-60 seconds for key generation...
[RSA] Generated 4096-bit key pair for VANET_CA
Certificate Authority 'VANET_CA' initialized
[RSA] Generated 2048-bit key pair for RSU_J2
...
  ✅ CA initialized: VANET_CA
  ✅ RSU managers: 4
  ✅ Vehicle managers: 20

🔧 Initializing simulation components...
🔐 Security enabled: RSA encryption + CA authentication
🔐 Secure RSU initialized: RSU_J2 at (500, 500)
🔐 Secure RSU initialized: RSU_J3 at (1000, 500)
✅ Connected to SUMO successfully
🚀 Starting integrated simulation...
🚑 Emergency vehicle registered: emergency_1 (encrypted)
```

## 🧪 Testing

### Test Without Security (Fast)
```bash
# Should complete in <1 minute
./run_integrated_sumo_ns3.sh --gui --steps 50
```

### Test With Security
```bash
# Takes ~1 minute (30s startup + 30s simulation)
./run_integrated_sumo_ns3.sh --gui --steps 50 --security
```

### Run Security Unit Tests
```bash
# All tests should pass
python3 tests/test_security.py
```

### Run Integration Tests
```bash
# Verify security modules work
./test_security_integration.sh
```

## 💡 Recommendations

### For Development/Testing:
**Don't use `--security`** - Faster iteration, same traffic behavior

```bash
./run_integrated_sumo_ns3.sh --gui --steps 100
```

### For Demonstrations:
**Use `--security`** - Show encrypted communications

```bash
./run_integrated_sumo_ns3.sh --gui --steps 500 --security
```

### For Production/Final Results:
**Use `--security`** with longer simulation

```bash
./run_integrated_sumo_ns3.sh --rl --steps 3600 --security
```

## 🆘 Troubleshooting

### SUMO Crashes on Startup

**Problem**: TraCI timeout due to slow security initialization

**Solution**: Don't use `--security` flag, or increase pre-generated vehicles:

Edit `sumo_simulation/run_integrated_simulation.py` line 78:
```python
num_vehicles=5  # Reduce from 20 to 5 for faster startup
```

### Want Security But Faster Startup

**Solution**: Reduce pre-generated vehicles to 5:

```python
# In run_integrated_simulation.py line 78
ca, rsu_managers, vehicle_managers = initialize_vanet_security(
    rsu_ids=rsu_ids,
    num_vehicles=5  # Changed from 20
)
```

Vehicles will still be registered dynamically as they appear.

## 📚 Documentation

- **`SECURITY_README.md`** - Complete security API reference
- **`SECURITY_INTEGRATION_GUIDE.md`** - Detailed integration guide
- **`INTEGRATION_SUMMARY.md`** - Full integration summary
- **`examples/secure_communication_example.py`** - Security demonstrations

## ✨ Summary

**Default (No Security)**: Fast, good for testing
```bash
./run_integrated_sumo_ns3.sh --gui
```

**With Security**: Encrypted, good for demonstrations
```bash
./run_integrated_sumo_ns3.sh --gui --security
```

Both modes work perfectly - choose based on your needs! 🎉
