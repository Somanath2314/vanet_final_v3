# Integrated SUMO + NS3 VANET with Hybrid RL Control

## Overview

The integrated system now supports **proximity-based hybrid RL control**, combining:
- **SUMO**: Traffic simulation with emergency vehicles
- **NS3**: Network simulation (WiFi 802.11p + WiMAX)
- **RL**: DQN-based traffic light control (proximity-activated)
- **Security**: RSA encryption for V2V/V2I communication
- **Edge Computing**: Smart RSUs with local processing

## 🚀 Quick Start

### 1. Basic Rule-Based Control (Original)
```bash
./run_integrated_sumo_ns3.sh --gui --steps 1000
```

### 2. Hybrid Proximity-Based RL Control (NEW!)
```bash
# With trained model
./run_integrated_sumo_ns3.sh --hybrid --gui --steps 1000 \
    --model ../rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip \
    --proximity 250

# Without model (random policy for testing)
./run_integrated_sumo_ns3.sh --hybrid --gui --steps 1000 --proximity 250
```

### 3. With Security + Edge Computing
```bash
./run_integrated_sumo_ns3.sh --hybrid --gui --steps 1000 \
    --security --edge \
    --model ../rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip \
    --proximity 250
```

## 🔧 Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--hybrid` | Enable proximity-based hybrid RL control | Off |
| `--rl` | Enable pure RL control (not recommended) | Off |
| `--model PATH` | Path to trained DQN model (.zip file) | None |
| `--proximity M` | Proximity threshold in meters | 250 |
| `--gui` | Use SUMO-GUI for visualization | Off |
| `--steps N` | Number of simulation steps | 1000 |
| `--security` | Enable RSA encryption | Off |
| `--edge` | Enable edge computing RSUs | Off |

## 🎯 How Hybrid Mode Works

### Control Strategy
1. **Default**: All junctions use **density-based adaptive control**
   - Low overhead, efficient for normal traffic
   - Green time: 10-45 seconds based on vehicle density
   - Thresholds: 3 vehicles (low), 10 vehicles (high)

2. **Emergency Activation**: When emergency vehicle detected within proximity threshold
   - Switches affected junctions to **RL-based control**
   - Uses trained DQN model for intelligent traffic management
   - Prioritizes emergency vehicle flow

3. **Per-Junction Switching**: Each junction independently switches modes
   - Only junctions near emergency use RL
   - Other junctions continue with density control
   - Automatic return to density mode when emergency passes

### Proximity Threshold Guidelines
- **150m**: Tighter control, later activation (more density-based)
- **250m**: Balanced (recommended default)
- **400m**: Wider activation, earlier RL engagement

## 📊 Performance Metrics

The system reports:
- **Total steps**: Simulation duration
- **Density-based control**: Number of steps in density mode
- **RL-based control**: Number of steps in RL mode
- **Mode switches**: Number of junction mode transitions
- **Network metrics**: WiFi/WiMAX PDR, delays, throughput

Example output:
```
🔀 Hybrid Control Statistics:
  Density-based control: 738 steps (73.8%)
  RL-based control: 262 steps (26.2%)
  Mode switches: 16
  Efficiency: 73.8% low-overhead, 26.2% emergency-focused
```

## 🎓 Training a Better Model

### Quick Training (10k steps, ~5 minutes)
```bash
cd rl_module
python3 train_dqn_model.py --timesteps 10000
```

### Production Training (100k steps, ~1 hour)
```bash
cd rl_module
python3 train_dqn_model.py --timesteps 100000
```

### Monitor Training
```bash
cd rl_module
tensorboard --logdir=trained_models/
# Open http://localhost:6006
```

## 🔍 Troubleshooting

### Issue: 0% RL activation in hybrid mode
**Cause**: No emergency vehicles or proximity threshold too small
**Solution**: 
- Check emergency vehicle flow rate in SUMO config
- Increase proximity threshold: `--proximity 400`
- Verify emergency vehicles spawn correctly

### Issue: Model not found
**Cause**: Model path incorrect or model not trained
**Solution**:
```bash
cd rl_module
# Train a model first
python3 train_dqn_model.py --timesteps 10000
# Use relative path from sumo_simulation directory
cd ../sumo_simulation
./run_integrated_sumo_ns3.sh --hybrid --model ../rl_module/trained_models/dqn_traffic_*/dqn_traffic_final.zip
```

### Issue: TraCI errors about unknown vehicles
**Cause**: Vehicle left simulation before query
**Solution**: Already handled in code with try-except blocks

### Issue: Security initialization slow (30-60 seconds)
**Cause**: RSA key generation is CPU-intensive
**Solution**: 
- Only use `--security` when needed
- Wait for "Security enabled" message
- Keys are generated once at startup

## 📁 Output Files

Results saved in `sumo_simulation/output/`:
- `integrated_simulation_results.json`: Network metrics (WiFi, WiMAX)
- `tripinfo.xml`: SUMO trip information
- `summary.xml`: SUMO summary statistics
- `v2i_packets.csv`: V2I communication packets
- `v2i_metrics.csv`: V2I performance metrics

## 🔬 Example Scenarios

### Scenario 1: Normal Traffic
```bash
./run_integrated_sumo_ns3.sh --gui --steps 1000
# Expected: Pure density-based control, efficient flow
```

### Scenario 2: Emergency Response Testing
```bash
./run_integrated_sumo_ns3.sh --hybrid --gui --steps 3600 \
    --model ../rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip \
    --proximity 250
# Expected: ~70-80% density, ~20-30% RL, 10-20 switches per 1000 steps
```

### Scenario 3: Full System with Security
```bash
./run_integrated_sumo_ns3.sh --hybrid --gui --steps 3600 \
    --security --edge \
    --model ../rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip \
    --proximity 250
# Expected: All features enabled, 60s startup time for security
```

### Scenario 4: Long-Duration Testing
```bash
./run_integrated_sumo_ns3.sh --hybrid --steps 7200 \
    --model ../rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip \
    --proximity 250
# Expected: 2 hours simulation time, comprehensive statistics
```

## 🎯 Best Practices

1. **Start Simple**: Test with rule-based mode first to verify setup
2. **Train Model**: Always train a model before using hybrid mode
3. **Tune Proximity**: Start with 250m, adjust based on results
4. **Monitor Performance**: Check control mode percentages (aim for 70-80% density)
5. **Use GUI Sparingly**: GUI slows simulation, use for debugging only
6. **Enable Security Last**: Add --security only after everything else works
7. **Check Logs**: Look for "Hybrid Control Statistics" in output

## 📈 Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Density mode % | 70-80% | Efficient baseline control |
| RL mode % | 20-30% | Emergency-focused activation |
| Mode switches | 10-20 per 1000 steps | Smooth transitions |
| WiFi PDR | >90% | V2V communication quality |
| WiMAX PDR | >95% | V2I emergency communication |
| Average delay | <100ms | Network responsiveness |

## 🚦 Traffic Light Control Details

### Density-Based (Default)
- **Low density** (<3 vehicles): 10s green time
- **Medium density** (3-10 vehicles): 10-45s scaled
- **High density** (>10 vehicles): 45s green time
- **Yellow phase**: 3s fixed

### RL-Based (Emergency)
- **State**: Vehicle counts per lane + current phase
- **Action**: Keep phase or switch to next phase
- **Model**: DQN with replay buffer
- **Update**: Every simulation step when active

## 📞 Support

For issues or questions:
1. Check this guide first
2. Review `DQN_TRAINING_GUIDE.md` for training details
3. Check `RL_QUICK_REFERENCE.md` for RL system overview
4. Look at logs in terminal output

## 🎉 Success Indicators

You know the system is working correctly when you see:
- ✅ "Connected to SUMO successfully"
- ✅ "DQN model loaded successfully"
- ✅ "X junctions mapped" (should be 2+ junctions)
- ✅ Progress updates every 5 seconds
- ✅ "Hybrid Control Statistics" showing ~70-80% density mode
- ✅ Mode switches happening (10-20 per 1000 steps)
- ✅ Emergency vehicles detected and processed

Happy simulating! 🚗💨
