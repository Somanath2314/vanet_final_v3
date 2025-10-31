# 🚗 Integrated SUMO + NS3 VANET System with Security

**Status**: ✅ FULLY OPERATIONAL | **Modes**: Rule-Based + RL | **Security**: RSA Encryption | **PDR**: 95%+

Complete Vehicular Ad-Hoc Network (VANET) simulation combining **SUMO traffic simulation** with **NS3-based network protocols** and **optional RSA encryption**.

---

## 🎯 System Overview

This system provides a complete VANET simulation environment with:

- **🚦 Traffic Simulation**: Real vehicle movements, intersections, emergency vehicles (SUMO)
- **📡 Network Protocols**: WiFi 802.11p (V2V) + WiMAX (V2I for emergency)
- **🤖 Traffic Control**: Rule-based (density) OR Reinforcement Learning (DQN)
- **🔐 Security**: Optional RSA-2048/4096 encryption with Certificate Authority
- **🚑 Emergency Priority**: Automatic detection and encrypted messaging

---

## 🚀 Quick Start

### Basic Usage (No Security)

```bash
# Rule-based traffic control with GUI
./run_integrated_sumo_ns3.sh --gui --steps 100

# RL-based traffic control with GUI
./run_integrated_sumo_ns3.sh --rl --gui --steps 100

# Fast testing without GUI
./run_integrated_sumo_ns3.sh --steps 50
```

### With Security (RSA Encryption)

```bash
# Rule-based + RSA encryption (45-60s startup)
./run_integrated_sumo_ns3.sh --gui --steps 100 --security

# RL + RSA encryption
./run_integrated_sumo_ns3.sh --rl --gui --steps 100 --security
```

### All Options

```bash
./run_integrated_sumo_ns3.sh [OPTIONS]

Options:
  --rl          Use RL-based traffic control (default: rule-based)
  --gui         Use SUMO-GUI for visualization
  --steps N     Number of simulation steps (default: 1000)
  --security    Enable RSA encryption (adds 30-60s startup time)
```

---

## ✨ Key Features

### 📡 Communication Protocols

| Protocol | Type | Range | PDR | Delay | Use Case |
|----------|------|-------|-----|-------|----------|
| **WiFi 802.11p** | V2V | 300m | 92-98% | 20-50ms | Vehicle-to-vehicle |
| **WiMAX** | V2I | 1000m | 95-99% | 15-30ms | Emergency → RSU |
| **WiFi** | V2I | 300m | 90-95% | 25-40ms | Normal → RSU |

### 🚦 Traffic Control Modes

#### Rule-Based (Default)
- Density-based traffic light switching
- Min green: 15s, Max green: 60s, Yellow: 5s
- Emergency vehicle detection and priority
- Fast, deterministic, simple

#### RL-Based (`--rl` flag)
- Deep Q-Network (DQN) agent
- State: Traffic density, queue lengths, emergency status
- Action: Traffic light phase selection
- Trained model: `rl_module/models/dqn_traffic_model.pth`
- Adaptive to traffic patterns

### 🔐 Security Features (`--security` flag)

- **Certificate Authority**: RSA-4096 keys, issues certificates
- **Vehicle Keys**: RSA-2048 per vehicle, dynamic registration
- **RSU Keys**: RSA-2048 per Road-Side Unit
- **Encryption**: Hybrid RSA + AES-256-GCM
- **Signatures**: RSA-PSS with SHA256 for message authentication
- **Key Management**: Automatic key exchange and distribution

**Security Startup Time**: 30-60 seconds (one-time key generation)
- CA: ~20s, RSUs: ~10s, Vehicles: ~10s, Key exchange: ~5s

---

## 🔧 System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│              Integrated VANET System                          │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐         ┌─────────────────┐               │
│  │     SUMO     │◄───────►│  NS3 Bridge     │               │
│  │   Traffic    │  TraCI  │  Network Sim    │               │
│  │  Simulation  │         │  WiFi + WiMAX   │               │
│  └──────┬───────┘         └────────┬────────┘               │
│         │                          │                         │
│         │                          │                         │
│  ┌──────▼───────┐         ┌───────▼─────────┐               │
│  │   Traffic    │         │  V2V/V2I Comm   │               │
│  │  Controller  │         │  4 RSUs         │               │
│  │  Rule/RL     │         │  802.11p/WiMAX  │               │
│  └──────────────┘         └─────────────────┘               │
│                                                               │
│  Optional Security Layer (--security):                       │
│  ┌───────────────────────────────────────────────────┐      │
│  │  Certificate Authority → RSUs → Vehicles          │      │
│  │  RSA Encryption → Digital Signatures → Key Mgmt   │      │
│  └───────────────────────────────────────────────────┘      │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
vanet_final_v3/
├── sumo_simulation/              # SUMO traffic simulation
│   ├── run_integrated_simulation.py   # Main simulation runner
│   ├── traffic_controller.py          # Traffic light control
│   ├── sumo_ns3_bridge.py             # SUMO ↔ NS3 bridge
│   ├── simulation.sumocfg             # SUMO configuration
│   ├── intersection.net.xml           # Road network
│   ├── intersection.rou.xml           # Vehicle routes
│   ├── wimax/                         # WiMAX implementation
│   │   ├── wimax.py                   # Base WiMAX protocol
│   │   └── secure_wimax.py            # Secure WiMAX with encryption
│   └── output/                        # Simulation results
│
├── v2v_communication/            # V2V/V2I protocols
│   ├── security.py               # RSA encryption, AES, signatures
│   ├── key_management.py         # CA, certificates, key distribution
│   └── protocols.py              # Communication protocols
│
├── rl_module/                    # Reinforcement Learning
│   ├── rl_traffic_controller.py  # RL agent implementation
│   ├── dqn_agent.py              # Deep Q-Network
│   └── models/                   # Trained models
│       └── dqn_traffic_model.pth # Pre-trained DQN model
│
├── tests/                        # Unit tests
│   └── test_security.py          # Security tests (22 tests)
│
├── examples/                     # Example scripts
│   └── secure_communication_example.py  # 5 security demos
│
├── docs/archive/                 # Detailed documentation
│   ├── FIXES_EXPLAINED.md        # Bug fixes and solutions
│   ├── COMMANDS.md               # All commands reference
│   ├── OUTPUT_EXPLAINED.md       # Understanding output
│   └── ...                       # More detailed guides
│
├── run_integrated_sumo_ns3.sh    # Main launcher ⭐
└── README.md                     # This file
```

---

## 🛠️ Installation

### Prerequisites

```bash
# Install SUMO (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install sumo sumo-tools sumo-doc

# Verify installation
sumo --version
# Expected: Eclipse SUMO sumo Version 1.12.0 or higher
```

### Python Setup

```bash
# Create virtual environment (if not exists)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r rl_requirements.txt

# Key packages: traci, pandas, numpy, torch, cryptography
```

### Verify Installation

```bash
# Quick test (30 steps, no GUI, fast)
./run_integrated_sumo_ns3.sh --steps 30

# Should complete in ~2 seconds
# Output: "✅ Simulation Completed Successfully"
```

---

## 📊 View Results

### Output Files Location

All results are saved to: `sumo_simulation/output/`

```bash
ls -lh sumo_simulation/output/

# Files created:
# - integrated_simulation_results.json  (Network metrics)
# - v2i_packets.csv                     (V2I communication log)
# - v2i_metrics.csv                     (WiMAX performance)
# - tripinfo.xml                        (SUMO trip data)
# - summary.xml                         (SUMO summary)
```

### View Network Metrics

```bash
# Pretty-print JSON results
cat sumo_simulation/output/integrated_simulation_results.json | python3 -m json.tool | less

# Quick summary
python3 << 'EOF'
import json
with open('sumo_simulation/output/integrated_simulation_results.json') as f:
    data = json.load(f)
    metrics = data['metrics']
    
    print("="*60)
    print("SIMULATION RESULTS SUMMARY")
    print("="*60)
    print(f"Total Vehicles: {data['vehicles']['total']}")
    print(f"Emergency Vehicles: {data['vehicles']['emergency']}")
    print(f"\nOverall PDR: {metrics['combined']['overall_pdr']*100:.2f}%")
    print(f"Average Delay: {metrics['combined']['average_delay_ms']:.1f} ms")
    print(f"Throughput: {metrics['combined']['throughput_mbps']:.2f} Mbps")
    print(f"\nEmergency Success Rate: {metrics['emergency']['success_rate']*100:.2f}%")
    print("="*60)
EOF
```

### View Packet Logs

```bash
# View V2I packets (with encryption info if --security used)
head -20 sumo_simulation/output/v2i_packets.csv

# View WiMAX metrics
head -20 sumo_simulation/output/v2i_metrics.csv
```

---

## 🎓 Usage Examples

### Example 1: Quick Test (Rule-Based, No Security)

```bash
./run_integrated_sumo_ns3.sh --steps 50

# Time: ~2 seconds
# Use: Fast testing, development
```

### Example 2: Full Demo with GUI (Rule-Based)

```bash
./run_integrated_sumo_ns3.sh --gui --steps 200

# Time: ~20 seconds
# Use: Visual demonstration, debugging
```

### Example 3: RL Traffic Control with Security

```bash
./run_integrated_sumo_ns3.sh --rl --gui --steps 100 --security

# Time: ~60 seconds (45s security init + 15s simulation)
# Use: Full system demonstration with encryption
```

### Example 4: Long Simulation for Research

```bash
./run_integrated_sumo_ns3.sh --rl --steps 5000 --security

# Time: ~60s security + ~5 minutes simulation
# Use: Data collection, performance analysis
```

### Example 5: Batch Testing

```bash
#!/bin/bash
# Test all 4 combinations
for mode in "" "--rl"; do
    for security in "" "--security"; do
        echo "Testing: mode=$mode security=$security"
        ./run_integrated_sumo_ns3.sh $mode $security --steps 100
        mv sumo_simulation/output/integrated_simulation_results.json \
           results_${mode}_${security}.json
    done
done
```

---

## 🔬 Testing

### Unit Tests

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run security tests only (22 tests)
python3 -m pytest tests/test_security.py -v

# Expected: All 22 tests PASSED
```

### Example Scripts

```bash
# Run all security examples (5 demos)
python3 examples/secure_communication_example.py

# Demos included:
# 1. RSA key generation and encryption
# 2. Hybrid encryption (RSA + AES)
# 3. Digital signatures
# 4. Certificate Authority
# 5. Complete secure communication flow
```

---

## 📈 Expected Output

### Rule-Based Mode (No Security)

```
==========================================
🚗 Integrated SUMO + NS3 VANET System
==========================================
...
Mode: rule
Steps: 100
GUI: Yes
Security: Disabled
...
✅ Connected to SUMO successfully
⚠️  Security disabled (use --security flag to enable RSA encryption)

🚀 Starting integrated simulation...
----------------------------------------------------------------------
Step 50/100 | Vehicles: 17 (Emergency: 2) | WiFi PDR: 94.5% | 
WiMAX PDR: 97.2% | Avg Delay: 28.3ms
...
✅ Simulation completed in 2.1 seconds
...
📊 Combined Performance:
  Overall PDR: 95.65%
  Average Delay: 28.34 ms
...
✅ Simulation Completed Successfully
```

### With Security Enabled

```
==========================================
🚗 Integrated SUMO + NS3 VANET System
==========================================
...
Security: Enabled (RSA)
...
✅ Connected to SUMO successfully

🔐 Initializing VANET Security Infrastructure...
  - Certificate Authority (CA)
  - RSU key managers
  - Vehicle key managers
  ⏳ Generating keys (this takes 30-60 seconds)...
  💡 SUMO is paused during key generation
  
  ✅ CA initialized: CA_VANET
  ✅ RSU managers: 4
  ✅ Vehicle managers: 5 (more added dynamically)
  🔄 Re-initializing RSUs with encryption...
  ✅ Security enabled: RSA encryption + CA authentication

🚀 Starting integrated simulation...
----------------------------------------------------------------------
Step 50/100 | Vehicles: 17 (Emergency: 2) | WiFi PDR: 94.5% | 
WiMAX PDR: 97.2% | Avg Delay: 28.3ms
...
🔐 Secure RSU initialized: RSU_J2 at (500.0, 500.0)
🔐 Secure RSU initialized: RSU_J3 at (1000.0, 500.0)
[Security] Registered public key for Vehicle_0
[Security] Registered public key for ambulance_0
...
✅ Simulation Completed Successfully
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. SUMO Not Found

```bash
# Install SUMO
sudo apt-get install sumo sumo-tools sumo-doc

# Set SUMO_HOME
export SUMO_HOME=/usr/share/sumo
echo 'export SUMO_HOME=/usr/share/sumo' >> ~/.bashrc
```

#### 2. Simulation Stops Immediately

```bash
# Check SUMO configuration
cat sumo_simulation/simulation.sumocfg

# Verify route file has vehicles
grep -c "vehicle" sumo_simulation/intersection.rou.xml
```

#### 3. RL Module Not Available

```
⚠️  RL module not available, using rule-based control
```

**Solution**: Install PyTorch
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

System automatically falls back to rule-based mode if RL unavailable.

#### 4. Security Initialization Slow

**This is normal!** RSA key generation takes time:
- CA (4096-bit): ~20 seconds
- Each RSU (2048-bit): ~3 seconds
- Each vehicle (2048-bit): ~2 seconds

**Tip**: Reduce pre-generated vehicles in `run_integrated_simulation.py` line 111 (currently 5, can reduce to 2-3).

#### 5. Kill Stuck SUMO Processes

```bash
# Force kill all SUMO instances
killall sumo-gui sumo

# Verify
ps aux | grep sumo
```

---

## 📚 Documentation

### Quick References

- **Main README**: This file - comprehensive guide
- **Archive**: `docs/archive/` - detailed documentation

### Documentation Archive (`docs/archive/`)

- **COMMANDS.md** - All commands and examples
- **FIXES_EXPLAINED.md** - Bug fixes and solutions
- **OUTPUT_EXPLAINED.md** - Understanding system output
- **QUICK_START.md** - Getting started guide
- **SECURITY_WORKING.md** - Security implementation details
- **RL_GUIDE.md** - Reinforcement learning guide
- And more...

---

## 🎯 Use Cases

### Research
- VANET protocol performance analysis
- Emergency vehicle priority algorithms
- Security impact on network performance
- Traffic optimization with RL

### Education
- Understanding V2V/V2I communication
- Learning RSA encryption in practice
- Studying traffic control algorithms
- SUMO and NS3 integration

### Development
- Testing new traffic control strategies
- Prototyping security features
- Evaluating network protocols
- Algorithm benchmarking

---

## 🔑 How It Works

### 1. SUMO Traffic Simulation
- Generates realistic vehicle movements on road network
- Manages traffic lights at intersections (J2, J3, etc.)
- Spawns emergency vehicles (ambulances) randomly
- Provides real-time vehicle positions via TraCI API

### 2. NS3 Bridge
- Connects to SUMO using TraCI (Python interface)
- Reads vehicle positions every simulation step
- Detects emergency vehicles automatically
- Calculates distances between vehicles and RSUs

### 3. Network Simulation
- **V2V (WiFi 802.11p)**: Vehicles communicate with nearby vehicles (<300m)
- **V2I Emergency (WiMAX)**: Emergency vehicles → RSU (<1000m)
- **V2I Normal (WiFi)**: Normal vehicles → RSU (<300m)
- Distance-based PDR and delay models

### 4. Traffic Control

**Rule-Based**:
- Monitor traffic density at each intersection
- Adjust green light duration (15-60s)
- Detect emergency vehicles and give priority
- Simple, fast, deterministic

**RL-Based**:
- DQN agent observes traffic state
- Selects optimal traffic light phase
- Learns from experience (trained model)
- Adapts to traffic patterns

### 5. Security (Optional)

**Initialization**:
1. Create Certificate Authority with 4096-bit keys
2. Generate keys for 4 RSUs (2048-bit each)
3. Pre-generate keys for initial vehicles
4. Distribute public keys and certificates

**Runtime**:
1. New vehicles register and get keys dynamically
2. Emergency messages encrypted with hybrid RSA+AES
3. Digital signatures verify message authenticity
4. Secure WiMAX protocol for V2I communication

---

## 📊 Performance Metrics

### Without Security (Fast)
- **Startup**: 2 seconds
- **50 steps**: 2 seconds total
- **1000 steps**: 10-15 seconds
- **Use**: Quick testing, development

### With Security (Slower Startup)
- **Startup**: 45-60 seconds (one-time)
- **50 steps**: ~50 seconds total (45s init + 5s sim)
- **1000 steps**: ~60 seconds (45s init + 15s sim)
- **After init**: Normal speed (encryption overhead minimal)

### Network Performance (Typical)
- **V2V PDR**: 92-98%
- **V2I PDR**: 95-99%
- **Average Delay**: 20-50ms
- **Throughput**: 15-25 Mbps

---

## 🎉 System Status

✅ **All Features Working:**
- Rule-based traffic control
- RL-based traffic control
- V2V communication (WiFi 802.11p)
- V2I communication (WiMAX + WiFi)
- Emergency vehicle detection
- RSA encryption (optional)
- Certificate Authority
- Dynamic vehicle registration
- All 4 combinations tested:
  - Rule + No Security ✅
  - Rule + Security ✅
  - RL + No Security ✅
  - RL + Security ✅

---

## 🔮 Future Enhancements

- Multiprocessing for parallel RSU key generation
- Attack simulation (malicious vehicles, replay attacks)
- Security analytics dashboard
- More traffic control algorithms (A*, Genetic Algorithm)
- Multiple intersection coordination
- Real-world map integration (OpenStreetMap)

---

## 📞 Support

**Issues?**
1. Check troubleshooting section above
2. Review `docs/archive/` for detailed guides
3. Run tests: `python3 -m pytest tests/ -v`
4. Check output logs in `sumo_simulation/output/`

**For detailed information:**
- See `docs/archive/COMMANDS.md` for all commands
- See `docs/archive/OUTPUT_EXPLAINED.md` for output interpretation
- See `docs/archive/FIXES_EXPLAINED.md` for known issues and fixes

---

## 📜 License

Academic/Research Use

---

## 👥 Credits

**VANET Simulation System**
- SUMO: Eclipse Foundation
- NS3: NS-3 Project
- Integration: Custom implementation

---

**Version**: 3.2 - Security Update  
**Status**: ✅ Production Ready  
**Last Updated**: 2025-11-01

**Quick Start**: `./run_integrated_sumo_ns3.sh --gui --steps 100`

**Full Demo**: `./run_integrated_sumo_ns3.sh --rl --gui --steps 100 --security`

---
