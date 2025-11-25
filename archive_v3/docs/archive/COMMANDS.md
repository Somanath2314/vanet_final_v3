# VANET Security - Command Cheat Sheet

## 🚀 Quick Commands

### Run Simulation (Choose One)

```bash
# 1. FASTEST - No security, for testing (DEFAULT)
./run_integrated_sumo_ns3.sh --gui --steps 1000

# 2. WITH SECURITY - Full encryption (use this!)
./run_integrated_sumo_ns3.sh --gui --steps 1000 --security

# 3. RL MODE - Reinforcement learning + security
./run_integrated_sumo_ns3.sh --rl --gui --steps 1000 --security

# 4. BACKGROUND - No GUI, faster
./run_integrated_sumo_ns3.sh --steps 1000 --security
```

## 📋 All Options

```
./run_integrated_sumo_ns3.sh [OPTIONS]

--rl         Use RL traffic control (default: rule-based)
--gui        Show SUMO visualization
--steps N    Simulation duration (default: 1000)
--security   Enable RSA encryption (adds 45s startup)
```

## ⚡ Quick Tests

```bash
# 30 second test
./run_integrated_sumo_ns3.sh --gui --steps 50

# 1 minute test with security
./run_integrated_sumo_ns3.sh --gui --steps 50 --security

# Full featured test
./run_integrated_sumo_ns3.sh --rl --gui --steps 100 --security
```

## 📊 Check Results

```bash
# View output files
ls -lh sumo_simulation/output/

# View encrypted packets
cat sumo_simulation/output/v2i_packets.csv | grep emergency

# View JSON results
cat sumo_simulation/output/integrated_simulation_results.json | python3 -m json.tool | less
```

## 🧪 Run Tests

```bash
# Security unit tests (22 tests)
python3 tests/test_security.py

# Integration tests
./test_security_integration.sh

# Security examples
python3 examples/secure_communication_example.py
```

## 🔍 What to Look For

### With `--security` flag:

```
✅ Connected to SUMO successfully
🔐 Initializing VANET Security Infrastructure...
[RSA] Generated 4096-bit key pair for VANET_CA
✅ CA initialized: VANET_CA
✅ RSU managers: 4
🔐 Secure RSU initialized: RSU_J2 at (500, 500)
🔐 Secure RSU initialized: RSU_J3 at (1000, 500)
✅ Security enabled: RSA encryption + CA authentication
🚑 Emergency vehicle registered: emergency_1 (encrypted)
```

### Without `--security` flag:

```
⚠️  Security disabled (use --security flag to enable RSA encryption)
⚠️  Security disabled: Running without encryption
```

## ⏱️ Timing

| Mode | Startup | Per Step | Total (1000 steps) |
|------|---------|----------|-------------------|
| **No security** | 3s | <1ms | ~1 minute |
| **With security** | 45s | ~1ms | ~2 minutes |

## 🆘 Troubleshooting

### SUMO won't start
```bash
# Check SUMO installation
sumo-gui --version

# Kill any stuck processes
killall sumo-gui sumo
```

### Security takes too long
```bash
# Edit run_integrated_simulation.py line 111
# Change num_vehicles=5 to num_vehicles=3
```

### Want to see verbose output
```bash
# Remove grep/head filters
./run_integrated_sumo_ns3.sh --gui --steps 100 --security 2>&1 | less
```

## 📚 Documentation

- `SECURITY_WORKING.md` - How it works (this file)
- `QUICK_START.md` - Detailed guide
- `SECURITY_README.md` - API reference
- `SECURITY_INTEGRATION_GUIDE.md` - Integration details

## ✨ Recommended Commands

### For Daily Development
```bash
./run_integrated_sumo_ns3.sh --gui --steps 100
```

### For Demonstrations
```bash
./run_integrated_sumo_ns3.sh --gui --steps 500 --security
```

### For Final Results
```bash
./run_integrated_sumo_ns3.sh --rl --gui --steps 3600 --security
```

## 🎯 One-Liner Tests

```bash
# Quick sanity check (30 sec)
./run_integrated_sumo_ns3.sh --gui --steps 30

# Security demo (2 min)
./run_integrated_sumo_ns3.sh --gui --steps 100 --security

# Full test (5 min)
./run_integrated_sumo_ns3.sh --rl --gui --steps 500 --security
```

---

**TL;DR**: Use `./run_integrated_sumo_ns3.sh --gui --steps 1000 --security` for full features! 🎉
