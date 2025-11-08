# Complete VANET System - Quick Start Guide

## 🚀 One-Command Launch

### Basic Usage (Rule-based with GUI)
```bash
./run_integrated_sumo_ns3.sh --gui --steps 1000
```

### 🎯 **RECOMMENDED: Proximity-Based RL with All Features**
```bash
./run_integrated_sumo_ns3.sh \
    --proximity 250 \
    --model rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip \
    --gui \
    --security \
    --edge \
    --steps 1000
```

## 📋 Available Modes

### 1. **Rule-Based (Default)**
Uses density-based adaptive traffic control
```bash
./run_integrated_sumo_ns3.sh --gui --steps 1000
```

### 2. **Hybrid Mode**
Globally switches to RL when emergencies detected
```bash
./run_integrated_sumo_ns3.sh --hybrid --gui --steps 1000
```

### 3. **Proximity-Based RL (⭐ BEST)**
Junction-specific RL activation based on emergency vehicle distance
```bash
./run_integrated_sumo_ns3.sh \
    --proximity 250 \
    --model rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip \
    --gui \
    --steps 1000
```

## 🎛️ Command-Line Options

### Control Modes
- `--rl` - Pure RL-based control (requires --model)
- `--hybrid` - Global switching between density and RL
- `--proximity DIST` - Proximity-based switching (default: 250m)

### Model Options
- `--model PATH` - Path to trained DQN model (.zip file)
  - Required for `--rl` and `--proximity` modes
  - Example: `--model rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip`

### Simulation Options
- `--gui` - Enable SUMO-GUI visualization
- `--steps N` - Number of simulation steps (default: 1000)
- `--security` - Enable RSA encryption (adds 30-60s startup)
- `--edge` - Enable edge computing RSUs

### Help
- `--help` or `-h` - Show detailed usage information

## 📊 Features Included

### ✅ Traffic Simulation (SUMO)
- Real vehicle movements and traffic dynamics
- Emergency vehicle priority routing
- Multiple junctions with traffic lights
- GUI visualization with real-time metrics

### ✅ Network Simulation (NS3)
- **V2V Communication**: WiFi 802.11p (300m range)
- **V2I Communication**: WiMAX for emergencies (500m range)
- Packet delivery ratio (PDR) tracking
- Latency and throughput metrics

### ✅ RL Traffic Control
- **Trained DQN Model**: Deep Q-Network from stable-baselines3
- **Proximity-Based Switching**: Only activates RL near emergencies
- **Efficient**: 70-75% density mode, 25-30% RL mode
- **Responsive**: Switches immediately when emergency passes

### ✅ Edge Computing
- Smart RSU processing at intersections
- Local traffic analytics
- Collision avoidance services
- Emergency vehicle support
- Data aggregation and caching

### ✅ Security
- RSA encryption for V2V/V2I messages
- Certificate Authority (CA) authentication
- Key management for RSUs and vehicles
- Secure emergency communications

## 🎮 SUMO-GUI Controls

When running with `--gui`:
- **Space**: Play/Pause simulation
- **+/-**: Speed up/slow down
- **Click vehicle**: View details
- **Right-click**: Vehicle tracking
- **Ctrl+C**: Stop simulation

## 📈 Real-Time Metrics

During simulation, you'll see:
```
Step  500/1000 | RL Junctions: 1/2 (50%) | Vehicles: 45 (Emerg: 1) | WiFi PDR: 95.2% | WiMAX PDR: 98.5%
```

### Metrics Explained:
- **Step**: Current/Total simulation steps
- **RL Junctions**: How many junctions using RL control
- **Vehicles**: Total vehicles (emergency count)
- **WiFi PDR**: V2V packet delivery rate
- **WiMAX PDR**: V2I emergency packet delivery rate

## 📁 Output Files

Results saved in `sumo_simulation/output/`:
- `integrated_simulation_results.json` - Network metrics
- `v2i_packets.csv` - V2I communication packets
- `v2i_metrics.csv` - V2I performance metrics
- `tripinfo.xml` - SUMO trip information
- `summary.xml` - SUMO summary statistics

## 🔍 Examples

### 1. Quick Test with Visualization
```bash
./run_integrated_sumo_ns3.sh --gui --steps 500
```

### 2. Full System Test (1000 steps)
```bash
./run_integrated_sumo_ns3.sh \
    --proximity 250 \
    --model rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip \
    --gui \
    --edge \
    --steps 1000
```

### 3. Production Run with Security
```bash
./run_integrated_sumo_ns3.sh \
    --proximity 250 \
    --model rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip \
    --gui \
    --security \
    --edge \
    --steps 3600
```

### 4. Tighter Proximity Threshold (150m)
```bash
./run_integrated_sumo_ns3.sh \
    --proximity 150 \
    --model rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip \
    --gui \
    --steps 1000
```

## 🐛 Troubleshooting

### Issue: "Model not found"
```bash
# Check available models
find rl_module/trained_models -name "*.zip"

# Use correct path
./run_integrated_sumo_ns3.sh --proximity 250 --model rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip --gui
```

### Issue: "RL module not available"
```bash
# Install RL dependencies
pip install stable-baselines3 torch gymnasium tensorboard
```

### Issue: GUI not showing
```bash
# Make sure you use --gui flag
./run_integrated_sumo_ns3.sh --gui --steps 1000

# Check SUMO installation
sumo-gui --version
```

### Issue: Slow startup with security
- First run takes 30-60 seconds to generate RSA keys
- Subsequent runs use cached keys (faster)
- Use `--security` only when testing security features

## 🎯 Performance Tips

### For Fast Testing
```bash
./run_integrated_sumo_ns3.sh --gui --steps 500
# No security, no edge computing, short run
```

### For Visualization
```bash
./run_integrated_sumo_ns3.sh --proximity 250 --model rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip --gui --steps 1000
# GUI enabled, RL control, moderate length
```

### For Complete System Demo
```bash
./run_integrated_sumo_ns3.sh --proximity 250 --model rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip --gui --security --edge --steps 1000
# All features enabled
```

## 📚 Related Documentation

- `DQN_TRAINING_GUIDE.md` - How to train new RL models
- `RL_QUICK_REFERENCE.md` - RL system architecture
- `HYBRID_CONTROL_GUIDE.md` - Control mode details
- `INTEGRATED_HYBRID_GUIDE.md` - Integration architecture

## ✨ What Makes This System Special

### 🎯 Proximity-Based RL Control
- **Smart**: Only uses RL where needed (near emergencies)
- **Efficient**: 70-75% uses lightweight density control
- **Responsive**: Switches per-junction, not globally
- **Results**: 16 switches per 1000 steps, ~40 steps RL per junction

### 🔄 Multi-Modal Integration
- **SUMO**: Realistic traffic simulation
- **NS3**: Network simulation with WiFi/WiMAX
- **RL**: Trained DQN for intelligent control
- **Edge**: Smart RSU processing
- **Security**: End-to-end encryption

### 📊 Real-Time Monitoring
- Live metrics during simulation
- Network performance tracking
- RL activation monitoring
- Emergency handling verification

## 🚀 Next Steps

1. **Run the basic demo**:
   ```bash
   ./run_integrated_sumo_ns3.sh --gui --steps 1000
   ```

2. **Try proximity-based RL**:
   ```bash
   ./run_integrated_sumo_ns3.sh --proximity 250 --model rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip --gui --steps 1000
   ```

3. **Enable all features**:
   ```bash
   ./run_integrated_sumo_ns3.sh --proximity 250 --model rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip --gui --security --edge --steps 1000
   ```

4. **Train better model** (optional):
   ```bash
   cd rl_module
   python3 train_dqn_model.py --timesteps 100000
   ```

5. **Analyze results**:
   ```bash
   cat sumo_simulation/output/integrated_simulation_results.json | python3 -m json.tool
   ```

---

**Enjoy your complete VANET simulation system! 🚗🌐🤖**
