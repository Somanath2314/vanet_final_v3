# 🚀 How to Run VANET SUMO Simulation

## ✅ All Errors Fixed!

The following issues have been resolved:
1. ✅ Module import error (`sensor_network`)
2. ✅ SUMO port conflict
3. ✅ TraCI connection issues

---

## Quick Start (Recommended)

### Single Command Launch

```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3
source venv/bin/activate
./run_sumo.sh
```

**That's it!** SUMO-GUI will open automatically.

---

## What You'll See

### 1. Console Output
```
==========================================
VANET SUMO Simulation Launcher
==========================================

✓ SUMO found: Eclipse SUMO sumo Version 1.18.0
✓ Configuration file found

Starting simulation...
SUMO-GUI will open in a moment...

Controls:
  Space    - Play/Pause
  +/-      - Speed up/slow down
  Ctrl+C   - Stop simulation

==========================================

Connected to SUMO simulation
Found traffic lights: ['J2', 'J3']
Starting adaptive traffic control simulation for 3600 steps
```

### 2. SUMO-GUI Window
- **Network**: Roads and intersections displayed
- **Traffic Lights**: Changing colors (red/yellow/green)
- **Vehicles**: Moving through the network (if route file has vehicles)
- **Controls**: Play/pause, speed controls at bottom

### 3. Adaptive Control Messages
```
--- Simulation Step 60 ---
J2: Phase 0 (East-West Green) - 30/30s
J3: Phase 2 (North-South Green) - 15/30s
Vehicles detected: 12, Emergency: 0
  E1_0: MEDIUM density (0.35), Queue: 45.2m
  E2_0: LOW density (0.15), Queue: 12.1m

J2: Phase 1 (East-West Yellow) - 0/5s
Emergency vehicle detected at J2 - switching phase
J2: Phase 2 (North-South Green) - 0/35s  # Extended due to emergency
```

---

## Alternative Methods

### Method 2: Python Script
```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3
source venv/bin/activate
cd sumo_simulation
python run_simulation.py
```

### Method 3: Direct Import
```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3
source venv/bin/activate
cd sumo_simulation
python traffic_controller.py
```

---

## SUMO-GUI Controls

Once the window opens:

| Key/Button | Action |
|------------|--------|
| **Space** | Play/Pause simulation |
| **+** | Speed up |
| **-** | Slow down |
| **Ctrl+C** (terminal) | Stop simulation |
| **Mouse Wheel** | Zoom in/out |
| **Right-click + Drag** | Pan view |
| **Step button** | Advance one step |

---

## Viewing Options in SUMO-GUI

### Enable Useful Visualizations

1. **View → Show Vehicle Names** - See vehicle IDs
2. **View → Show Traffic Light States** - See signal phases
3. **View → Color by Speed** - Color-code vehicles by speed
   - Green = Fast
   - Yellow = Medium
   - Red = Slow/stopped

### Adjust View
- **Edit → Edit Visualization** - Customize colors, sizes
- **View → Zoom** - Fit network to screen

---

## Monitoring Adaptive Behavior

Watch the console for adaptive decisions:

### Normal Operation
```
J2: Phase 0 (East-West Green) - 30s
```

### Extended Green (High Demand)
```
J2: Phase 0 (East-West Green) - 45s  # Extended by 15s
```

### Early Termination (Low Demand)
```
J2: Phase 0 (East-West Green) - 20s  # Ended early
```

### Emergency Response
```
Emergency vehicle detected at J2 - switching phase
J2: Phase 2 (North-South Green) - 5s  # Immediate switch
```

---

## Stopping the Simulation

Press `Ctrl+C` in the terminal:

```
^C
Simulation stopped by user

Simulation ended
SUMO simulation closed
✓ Simulation completed
```

---

## Troubleshooting

### Issue: "SUMO not found"
```bash
sudo apt-get install sumo sumo-tools sumo-doc
```

### Issue: "Port conflict"
```bash
killall sumo-gui sumo
sleep 2
./run_sumo.sh
```

### Issue: "Module not found"
```bash
source venv/bin/activate
cd sumo_simulation
python run_simulation.py
```

### Issue: "Config file not found"
```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3/sumo_simulation
ls -la simulation.sumocfg  # Verify file exists
```

---

## Running with RL Control

### Option 1: Via API

**Terminal 1** - Start Backend:
```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3
source venv/bin/activate
cd backend
python app.py
```

**Terminal 2** - Start Simulation:
```bash
curl -X POST http://localhost:5000/api/control/start \
  -H "Content-Type: application/json" \
  -d '{"config_path": "../sumo_simulation/simulation.sumocfg"}'
```

**Terminal 3** - Enable RL:
```bash
curl -X POST http://localhost:5000/api/rl/enable \
  -H "Content-Type: application/json" \
  -d '{"mode": "inference", "config": {"algorithm": "DQN"}}'
```

### Option 2: Standalone RL

```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3
source venv/bin/activate
cd rl_module
python train_rl_agent.py --algorithm DQN --iterations 100
```

---

## Verification Checklist

Before running, verify:

- [x] Virtual environment activated (`source venv/bin/activate`)
- [x] SUMO installed (`sumo --version`)
- [x] In correct directory (`cd sumo_simulation`)
- [x] No existing SUMO processes (`killall sumo-gui`)
- [x] Config file exists (`ls simulation.sumocfg`)

---

## Quick Test

Test everything works:

```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3
source venv/bin/activate

# Test 1: Import
python -c "from sumo_simulation.traffic_controller import AdaptiveTrafficController; print('✓ OK')"

# Test 2: SUMO
sumo --version

# Test 3: Run
./run_sumo.sh
```

---

## Expected Results

✅ **Success looks like:**
- Console shows "Connected to SUMO simulation"
- SUMO-GUI window opens
- Network is visible
- Traffic lights are present
- Console shows adaptive control messages
- No error messages

❌ **Failure looks like:**
- Error messages in console
- SUMO-GUI doesn't open
- "Module not found" errors
- "Connection refused" errors

If you see failures, check `SUMO_TROUBLESHOOTING.md`

---

## Summary

### Files Created/Fixed:
1. ✅ `traffic_controller.py` - Fixed import path
2. ✅ `run_sumo.sh` - Quick launcher script
3. ✅ `run_simulation.py` - Standalone runner
4. ✅ `RUN_INSTRUCTIONS.md` - This guide
5. ✅ `SUMO_TROUBLESHOOTING.md` - Detailed troubleshooting

### Ready to Run:
```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3
source venv/bin/activate
./run_sumo.sh
```

**Enjoy your adaptive traffic simulation! 🚦🚗**
