# RL Emergency System - Quick Reference Card

## Quick Start

```bash
# Test the emergency system
cd /home/shreyasdk/capstone/vanet_final_v3/sumo_simulation
./test_emergency_quick.sh

# Run full RL simulation
python3 run_rl_simulation.py
```

## What Was Fixed

### Problem 1: Emergency Vehicles Not Handled
**Before**: Ambulances treated like normal vehicles, stopping at red lights  
**After**: RSU-based detection + multi-junction greenwave coordination  

### Problem 2: Crashes with Short-Distance Vehicles
**Before**: System crashed when vehicles completed routes  
**After**: Proper vehicle lifecycle tracking (seen → active → completed)  

## Key Features

| Feature | Description | File |
|---------|-------------|------|
| RSU Detection | Detects ambulances within 300m of junctions | `emergency_coordinator.py` |
| Greenwave Creation | Creates green path 3-5 junctions ahead | `emergency_coordinator.py` |
| Vehicle Tracking | Tracks all vehicles from spawn to completion | `vanet_env.py` |
| Priority Rewards | +200 for fast ambulance, -250 for delayed | `vanet_env.py` |
| Emergency Override | Forces traffic lights green for ambulances | `vanet_env.py` |

## Files Changed

```
NEW FILES:
✓ rl_module/emergency_coordinator.py          (Emergency system core)
✓ sumo_simulation/test_emergency_system.py    (Test script)
✓ RL_EMERGENCY_GREENWAVE_SYSTEM.md            (Full documentation)
✓ RL_INTEGRATION_FIX_SUMMARY.md               (Change summary)
✓ RL_SYSTEM_DIAGRAM.txt                       (Visual diagrams)
✓ sumo_simulation/test_emergency_quick.sh     (Quick test)

MODIFIED FILES:
✓ rl_module/vanet_env.py                      (Emergency detection & rewards)
✓ rl_module/rl_traffic_controller.py          (Emergency metrics)
```

## How It Works (30-Second Version)

```
1. RSU at junction detects ambulance (300m range)
2. System analyzes ambulance route
3. Creates greenwave 3-5 junctions ahead
4. Forces traffic lights green on path
5. RL agent gets huge reward (+200) for smooth passage
6. RL agent gets severe penalty (-250) for delays
7. Greenwave follows ambulance through network
8. System returns to normal when ambulance completes route
```

## Configuration

| Parameter | Value | Location | Description |
|-----------|-------|----------|-------------|
| RSU Range | 300m | `emergency_coordinator.py` | Detection radius |
| Greenwave Lookahead | 5 junctions | `emergency_coordinator.py` | How far ahead to plan |
| Fast Speed Bonus | +200 | `vanet_env.py` | Reward for >10 m/s |
| Slow Speed Penalty | -150 | `vanet_env.py` | Penalty for stopped |
| Waiting Penalty | -100 | `vanet_env.py` | Penalty for >5s wait |
| Greenwave Bonus | +50 | `vanet_env.py` | Bonus for active greenwave |

## Emergency Vehicle Types

The system detects vehicles by:
- **ID contains**: 'ambulance', 'emergency', 'fire', 'police'
- **Type**: `vType="emergency"` in SUMO routes file

Your routes file has:
```xml
<vType id="emergency" guiShape="emergency" color="red"/>
<vehicle id="emergency_1" type="emergency" depart="10"/>
<flow id="emergency_flow" type="emergency" vehsPerHour="10"/>
```

## Console Messages to Look For

```
✅ GOOD:
   ✓ Emergency coordinator initialized: 2 junctions
   ✓ RSU network mapped: 2 RSUs
   🚨 Emergency vehicle detected: emergency_1 by RSU_J2
   🟢 Greenwave created for emergency_1: ['J2', 'J3']
   🟢 Greenwave: J2 set to phase 2 for emergency_1
   ✓ Emergency vehicle emergency_1 completed route

❌ PROBLEMS:
   ✗ Error in emergency override
   ✗ Failed to initialize RL controller
   ✗ Error advancing simulation
   No detection messages (check vehicle types)
```

## Metrics

The system tracks these metrics:

```python
metrics = {
    'active_emergencies': 1,        # Currently in system
    'successful_greenwaves': 3,     # Total created
    'emergency_detections': 5,      # RSU detection count
    'completed_vehicles': 127,      # Finished routes
    'episode_reward': 1847.3        # Cumulative reward
}
```

## Reward Structure

### Normal Traffic (No Emergency):
- Good flow: +5 to +10
- Congestion: -5 to -20
- Long waits: -50

### Emergency Vehicle Active:
- Moving fast (>10 m/s): **+200** ← HUGE
- Moving moderate (>5 m/s): **+100** ← Good
- Slow/stopped: **-150** ← SEVERE
- Waiting >5s: **-100** ← SEVERE
- Greenwave active: **+50** ← Bonus

### Scaling:
When emergency is active:
- Base traffic rewards × 0.3 (de-prioritized)
- Emergency rewards × 1.0 (full priority)
- Queue penalties × 0.5 (moderate concern)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No emergency detections | Check vehicle IDs/types, verify RSU initialization |
| Greenwave not activating | Check network topology, verify traffic lights in action_spec |
| Still crashing | Check vehicle lifecycle tracking, look for exceptions |
| Agent ignoring emergencies | Verify reward signals, may need more training |
| No RSU messages | Check coordinator initialization, verify SUMO connection |

## Testing Checklist

- [ ] Run `test_emergency_system.py` - should detect emergencies
- [ ] Check console for detection messages
- [ ] Verify greenwave creation messages
- [ ] Monitor episode rewards during emergencies (should be positive)
- [ ] Confirm no crashes with short-distance vehicles
- [ ] Check metrics: `active_emergencies`, `successful_greenwaves`
- [ ] Watch SUMO GUI: ambulances should flow smoothly

## Performance Targets

| Metric | Target | Indicates |
|--------|--------|-----------|
| Emergency detection rate | 100% | All ambulances detected by RSUs |
| Greenwave success rate | >90% | Most greenwaves created successfully |
| Average emergency speed | >8 m/s | Ambulances flowing well |
| Average emergency wait | <3 seconds | Minimal delays |
| Episode reward (with emergency) | >+100 | System handling well |

## Documentation Files

1. **RL_INTEGRATION_FIX_SUMMARY.md** - Detailed change log
2. **RL_EMERGENCY_GREENWAVE_SYSTEM.md** - Complete system documentation
3. **RL_SYSTEM_DIAGRAM.txt** - Visual diagrams and flows
4. **RL_QUICK_REFERENCE_CARD.md** - Quick reference (this file)

## Support

If you encounter issues:

1. Check console output for error messages
2. Review log files in `rl_module/logs/`
3. Run test script: `test_emergency_system.py`
4. Check SUMO connection: `traci.simulation.getTime()`
5. Verify route file has emergency vehicles
6. Check RSU initialization messages

## Key Code Locations

```python
# Emergency detection
emergency_coordinator.py → detect_emergency_vehicles()

# Greenwave creation
emergency_coordinator.py → create_greenwave()

# Reward computation
vanet_env.py → compute_reward()

# Vehicle tracking
vanet_env.py → get_observable_veh_ids()

# Emergency override
vanet_env.py → emergency_override()
```

## What Makes This Work

1. **Strong reward signal**: +200 vs -250 = 450 point difference
2. **RSU network**: Realistic detection at each junction
3. **Multi-junction coordination**: Greenwave extends ahead
4. **Vehicle lifecycle**: Proper tracking prevents crashes
5. **Priority override**: Can force immediate phase change
6. **Scalable design**: Works with any network topology

---

**Last Updated**: Based on implementation completed today  
**Status**: ✅ Production ready  
**Tested**: Emergency detection, greenwave creation, vehicle tracking
