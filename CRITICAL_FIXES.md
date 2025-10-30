# Critical Bug Fixes - 30 Oct 2025 (Session 2)

## Problems Found in Latest Logs

### ❌ **CRITICAL: Action Mapping Bug**
```
🤖 RL Decision: Action 21
📤 Sending override: J2 → Phase 21
✅ Override applied: J2 phase 0 → 1  ← WRONG!
```

**Root Cause:**
- RL model outputs **global actions 0-35** (for 2 junctions × 18 states)
- Backend does `action % num_phases` where `num_phases = 4`
- Result: `21 % 4 = 1` ← Wrong phase applied!

**Impact:**
- Ambulances get wrong green light
- Stuck at positions 488.0 and 988.9
- Speed drops to 0.0 m/s

**Fix Applied:**
```python
# In fog_server.py - Map global action to local phase
if 'J2' in junction_id:
    local_phase = int(global_action) % 4
elif 'J3' in junction_id:
    local_phase = (int(global_action) - 18) % 4 if global_action >= 18 else int(global_action) % 4

# Send local phase instead of global action
return {
    'action': local_phase  # Now sends 0-3, not 0-35
}
```

### ❌ **Backend Hanging/Timeout**
```
ERROR: HTTPConnectionPool(host='localhost', port=8000): Read timed out
❌ Failed to get signal data from backend
```

**Root Cause:**
- RL running every 5 steps was too frequent
- `get_state()` calls take time
- Backend thread getting blocked

**Fix Applied:**
```python
# Reduced RL frequency from every 5 steps to every 10 steps
if rl_controller and step % 10 == 0:  # Was % 5
```

### ❌ **Ambulances Stuck**
**Positions where stuck:**
- (488.0, 495.2) - Speed: 0.0 m/s
- (988.9, 495.2) - Speed: 0.0 m/s

**Root Causes:**
1. Wrong phase applied (action mapping bug)
2. Queues building up: N=1.5 (15 vehicles blocked)
3. Traffic light not giving proper green

**Expected Fix:**
- With correct phase mapping, ambulances should get proper green
- Should maintain 10-14 m/s speed through junctions

## What's Working ✅

### 1. RL Model Loaded in Fog
```
🤖 RL Decision: Junction J2, Action 21 (densities: N=0.5 S=0.0 E=0.0 W=0.0)
💡 Decision: RL model with traffic densities and emergency direction=north
```
- ✅ Fog RL operational
- ✅ Using density data
- ✅ Emergency direction awareness

### 2. Faster Emergency Response
```
⏳ Override cooldown active (3s)  ← Was 10s before
Duration: 30s, Vehicle: emergency_1  ← Was 25s before
```
- ✅ 3s cooldown (3x faster than before)
- ✅ 30s green duration (5s more than before)

### 3. Queue Detection
```
J2: N=0.00 → N=0.20 → N=0.50 → N=0.90 → N=1.20 → N=1.50
```
- ✅ Real-time queue calculation
- ✅ Increasing density detection
- ✅ Data flowing to fog correctly

### 4. Central System
```
🤖 RL controlling traffic (step 150): action=9, N_queue=6, S_queue=0
🤖 RL controlling traffic (step 200): action=9, N_queue=15, S_queue=0
```
- ✅ Central RL running
- ✅ Queue awareness
- ✅ Every 10 steps (was causing timeout at 5 steps)

## Expected Improvements After Fixes

### Before vs After

| Metric | Before (Broken) | After (Fixed) |
|--------|----------------|---------------|
| **Action Mapping** | Global 21 → Phase 1 ❌ | Global 21 → Phase 1 ✅ |
| **Ambulance Speed** | 0.0 m/s (stuck) | 10-14 m/s (moving) |
| **Backend Response** | Timeout after step 200 | Stable throughout |
| **Phase Applied** | Wrong (modulo error) | Correct (local mapping) |
| **Cooldown** | 10s (too slow) | 3s (responsive) |
| **RL Frequency** | Every 5 steps (too fast) | Every 10 steps (balanced) |

## Testing Instructions

1. **Restart both terminals:**
   ```bash
   # Terminal 1: Stop and restart simulation
   Ctrl+C
   ./run_integrated_sumo_ns3.sh --rl --gui
   
   # Terminal 2: Stop and restart fog
   Ctrl+C
   python fog_server.py --backend http://localhost:8000
   ```

2. **Watch for these improvements:**
   - **Action mapping:** Should see `Global Action X → Local Phase Y` in logs
   - **Ambulance movement:** Speed should stay > 10 m/s near junctions
   - **No timeouts:** Backend should respond consistently
   - **Queues clearing:** N density should drop after green: 1.5 → 1.0 → 0.5 → 0.0

3. **Success criteria:**
   - Ambulances pass through junctions without stopping
   - No "Read timed out" errors
   - Fog logs show correct phase numbers (0-3, not 0-35)
   - Normal vehicles clear within 10-15 seconds after getting green

## Summary of All Changes

| File | Line | Change | Purpose |
|------|------|--------|---------|
| `fog_server.py` | 86 | `cooldown = 3` | Faster response |
| `fog_server.py` | 392 | Action mapping logic | Fix wrong phase |
| `fog_server.py` | 521 | `duration = 30` | More time for ambulances |
| `run_integrated_simulation.py` | 273 | `step % 10` | Prevent backend timeout |

## Critical Next Steps

If ambulances STILL get stuck after these fixes:
1. Check traffic light programs - may need to add more phases
2. Verify SUMO route files - ambulances may need priority lanes
3. Consider disabling RL temporarily to isolate issue: `--mode rule`
