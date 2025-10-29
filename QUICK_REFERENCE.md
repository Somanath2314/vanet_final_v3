# VANET System - Quick Reference Card

## 🚀 Run the System

### Option 1: Integrated SUMO + NS3 (RECOMMENDED) ⭐
```bash
cd /home/shreyasdk/capstone/vanet_final_v3
./run_integrated_sumo_ns3.sh                    # Basic
./run_integrated_sumo_ns3.sh --gui              # With GUI
./run_integrated_sumo_ns3.sh --rl --gui         # With RL control
./run_integrated_sumo_ns3.sh --gui --steps 2000 # Custom duration
```

**Features:**
- ✅ Real SUMO traffic simulation
- ✅ WiFi (802.11p) for V2V
- ✅ WiMAX for emergency vehicles
- ✅ Actual vehicle positions

### Option 2: Standalone NS3 Simulation
```bash
python3 run_vanet_system.py [vehicles] [duration]
```

**Examples:**
```bash
python3 run_vanet_system.py          # Default: 20 vehicles, 60s
python3 run_vanet_system.py 30 120   # 30 vehicles, 2 minutes
python3 run_vanet_system.py 50 300   # 50 vehicles, 5 minutes
```

### Option 3: SUMO Only (Traffic Simulation)
```bash
./run_sumo_rl.sh                     # With RL control
./run_sumo.sh                        # Rule-based control
```

## 📊 View Results

### Integrated SUMO + NS3 Results
```bash
# View integrated results
cat sumo_simulation/output/integrated_simulation_results.json | python3 -m json.tool

# Quick metrics
python3 << 'EOF'
import json
with open('sumo_simulation/output/integrated_simulation_results.json') as f:
    d = json.load(f)['metrics']
    print(f"PDR: {d['combined']['overall_pdr']:.2%}, Delay: {d['combined']['average_delay_ms']:.1f}ms")
    print(f"Emergency Success: {d['emergency']['success_rate']:.2%}")
EOF

# List all outputs
ls -lh sumo_simulation/output/
```

### Standalone NS3 Results
```bash
# List results
ls -lt output_metrics/

# View latest result
cat output_metrics/vanet_results_*.json | tail -1 | python3 -m json.tool

# Quick stats
python3 -c "import json; d=json.load(open(sorted(__import__('glob').glob('output_metrics/*.json'))[-1])); print(f\"PDR: {d['combined']['overall_pdr']:.2%}, Delay: {d['combined']['overall_delay_ms']:.1f}ms\")"
```

## 🧪 Test System

```bash
python3 test_ns3_integration.py      # Full test suite
cat ns3_integration_test_report.md   # View test report
```

## 📖 Documentation

- **`HOW_TO_RUN.md`** - Quick start guide
- **`NS3_INTEGRATION_GUIDE.md`** - Complete documentation
- **`ERRORS_FIXED_SUMMARY.md`** - What was fixed

## 🔧 Alternative Methods

```bash
./run_sumo_rl.sh                     # With SUMO traffic simulation
./launch_complete_system.sh          # Complete system with GUI
```

## 📈 Key Metrics

- **PDR**: Packet Delivery Ratio (92-98% good)
- **Delay**: End-to-end delay (20-50ms good)
- **Throughput**: Data rate (15-27 Mbps good)
- **Emergency Response**: <20ms critical

## ✅ System Status

- **NS3 Integration**: ✅ Operational (with simulated metrics)
- **Metrics Generation**: ✅ Working
- **Result Storage**: ✅ Working
- **Documentation**: ✅ Complete

---
**Last Updated**: 2025-10-29 | **Version**: v3.0
