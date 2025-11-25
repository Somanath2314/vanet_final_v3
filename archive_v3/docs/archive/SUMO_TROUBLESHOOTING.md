# SUMO Simulation Troubleshooting Guide

## Issues Fixed ✅

### 1. Module Import Error ✅ FIXED
**Error**: `ModuleNotFoundError: No module named 'sensor_network'`

**Cause**: Incorrect path in import statement

**Solution**: Updated `traffic_controller.py` line 16:
```python
# OLD (incorrect)
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'sensors'))

# NEW (correct)
sys.path.append(os.path.join(os.path.dirname(__file__), 'sensors'))
```

### 2. SUMO Port Conflict ✅ FIXED
**Error**: `Error: A value for the option 'remote-port' was already set`

**Cause**: Multiple SUMO instances or conflicting port specifications

**Solution**: 
1. Removed `--remote-port` argument (TraCI assigns automatically)
2. Added cleanup of existing connections before starting new one

**Updated code**:
```python
def connect_to_sumo(self, config_path: str = None):
    try:
        # Close any existing connections
        try:
            traci.close()
        except:
            pass
        
        # Start SUMO without explicit port
        traci.start(["sumo-gui", "-c", config_path])
```

---

## How to Run (3 Methods)

### ✅ Method 1: Quick Launch Script (EASIEST)

```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3
source venv/bin/activate
./run_sumo.sh
```

This script:
- Activates virtual environment
- Kills existing SUMO processes
- Checks SUMO installation
- Launches simulation with GUI

### ✅ Method 2: Python Script

```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3
source venv/bin/activate
cd sumo_simulation
python run_simulation.py
```

### ✅ Method 3: Direct Controller

```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3
source venv/bin/activate
cd sumo_simulation
python traffic_controller.py
```

---

## Common Errors & Solutions

### Error: "Command 'python' not found"
**Solution**: Use `python3` or activate venv
```bash
source venv/bin/activate
```

### Error: "SUMO not found"
**Solution**: Install SUMO
```bash
sudo apt-get update
sudo apt-get install sumo sumo-tools sumo-doc
```

**Verify installation**:
```bash
sumo --version
# Should show: Eclipse SUMO sumo Version 1.18.0
```

### Error: "Could not connect to TraCI server"
**Solution**: Kill existing SUMO processes
```bash
killall sumo-gui
killall sumo
# Wait 2 seconds
sleep 2
# Then retry
```

### Error: "Config file not found"
**Solution**: Make sure you're in the right directory
```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3/sumo_simulation
ls -la *.sumocfg
# Should show simulation.sumocfg
```

### Error: "Empty reply from server" (API)
**Solution**: Backend not running. Start it first:
```bash
# Terminal 1
cd /home/mahesh/Desktop/capstone/vanet_final_v3
source venv/bin/activate
cd backend
python app.py
```

### Error: Port already in use
**Solution**: 
```bash
# Find process using port
lsof -i :8813

# Kill it
kill -9 <PID>

# Or kill all SUMO
killall sumo-gui sumo
```

---

## Step-by-Step Verification

### 1. Check Environment
```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3
source venv/bin/activate
python --version  # Should show Python 3.10.x
```

### 2. Check SUMO
```bash
which sumo-gui
# Should show: /usr/bin/sumo-gui

sumo --version
# Should show: Eclipse SUMO sumo Version 1.18.0
```

### 3. Check Files
```bash
cd sumo_simulation
ls -la
# Should see:
#   - traffic_controller.py
#   - simulation.sumocfg
#   - sensors/ directory
#   - run_simulation.py
```

### 4. Test Import
```bash
python -c "from traffic_controller import AdaptiveTrafficController; print('OK')"
# Should print: OK
```

### 5. Run Simulation
```bash
python run_simulation.py
# SUMO-GUI should open
```

---

## What You Should See

### Console Output
```
==========================================
VANET Adaptive Traffic Control - SUMO Simulation
==========================================

Using configuration: /path/to/simulation.sumocfg

✓ Connected to SUMO successfully
✓ SUMO-GUI window should be open

Controls:
  - Space: Play/Pause
  - +/-: Speed up/slow down
  - Ctrl+C: Stop simulation

Starting simulation...
------------------------------------------------------------
Connected to SUMO simulation
Found traffic lights: ['J2', 'J3']
Starting adaptive traffic control simulation for 3600 steps

--- Simulation Step 0 ---
J2: Phase 0 (East-West Green) - 0/30s
J3: Phase 0 (East-West Green) - 0/30s
Vehicles detected: 0, Emergency: 0
```

### SUMO-GUI Window
- Network visualization with roads and intersections
- Vehicles (if any in route file)
- Traffic lights changing colors
- Playback controls at bottom

---

## Quick Fixes Checklist

Before running, always:

```bash
# 1. Kill existing SUMO
killall sumo-gui sumo 2>/dev/null || true

# 2. Activate venv
cd /home/mahesh/Desktop/capstone/vanet_final_v3
source venv/bin/activate

# 3. Navigate to correct directory
cd sumo_simulation

# 4. Run
python run_simulation.py
```

---

## Alternative: Headless Mode (No GUI)

If you don't need visualization:

```python
# Edit traffic_controller.py line 82
# Change:
traci.start(["sumo-gui", "-c", config_path])

# To:
traci.start(["sumo", "-c", config_path])
```

Or use the headless config:
```bash
python run_simulation.py simulation_headless.sumocfg
```

---

## Testing Without Full Simulation

### Test 1: Import Check
```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3
source venv/bin/activate
python -c "
import sys
sys.path.insert(0, 'sumo_simulation')
from traffic_controller import AdaptiveTrafficController
print('✓ Import successful')
"
```

### Test 2: SUMO Connection
```bash
cd sumo_simulation
python -c "
import traci
traci.start(['sumo-gui', '-c', 'simulation.sumocfg'])
print('✓ SUMO connected')
traci.close()
"
```

---

## File Structure Verification

Your directory should look like this:

```
vanet_final_v3/
├── venv/                          # Virtual environment
├── run_sumo.sh                    # ✅ NEW: Quick launcher
├── sumo_simulation/
│   ├── traffic_controller.py      # ✅ FIXED: Import path
│   ├── run_simulation.py          # ✅ NEW: Standalone runner
│   ├── simulation.sumocfg         # SUMO config
│   └── sensors/
│       └── sensor_network.py      # Sensor module
└── backend/
    └── app.py                     # Flask API
```

---

## Summary of Changes

### Files Modified:
1. **`traffic_controller.py`** (Line 16)
   - Fixed import path for sensor_network
   - Removed hardcoded port specification
   - Added connection cleanup

### Files Created:
1. **`run_sumo.sh`** - Bash launcher script
2. **`sumo_simulation/run_simulation.py`** - Python runner
3. **`SUMO_TROUBLESHOOTING.md`** - This guide

---

## Ready to Run!

Everything is now fixed. Run with:

```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3
source venv/bin/activate
./run_sumo.sh
```

**Expected Result**: SUMO-GUI opens showing the traffic network with adaptive signal control active.

Press `Ctrl+C` to stop when done.
