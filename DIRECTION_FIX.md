# Direction Detection Fix - 30 Oct 2025

## Problem Identified
1. **Wrong direction detection**: Ambulances moving **EAST** (X: 76→370→494, Y: constant 495.2) were detected as moving **NORTH**
2. **Root cause**: On first detection, no previous position exists, so system fell back to SUMO angle which was incorrect
3. **Trigger distance**: Was 200m, user wanted 500m for earlier warning

## Solution Applied

### 1. Movement-Based Direction (Primary)
```python
# Calculate from actual position changes (dx, dy)
if abs(dx) > 5 or abs(dy) > 5:  # Require 5m minimum movement
    if abs(dx) > abs(dy):
        direction = 'east' if dx > 0 else 'west'
    else:
        direction = 'north' if dy > 0 else 'south'
```

**Advantages:**
- Most accurate - based on actual vehicle movement
- Works after first detection cycle
- Immune to SUMO angle errors

### 2. Lane ID Fallback (Secondary)
```python
if '_E' in lane_id or 'toE' in lane_id or 'East' in lane_id:
    direction = 'east'
# Similar for north, south, west
```

**Advantages:**
- Works on first detection
- Reliable if lane names follow convention

### 3. Angle Fallback (Tertiary)
```python
# SUMO angle: 0=East, 90=North, 180=West, 270=South
if 45 <= angle < 135:
    direction = 'north'
# etc.
```

**Last resort only!**

### 4. Trigger Distance
- Changed from **200m** back to **500m**
- Gives ~36 seconds advance warning at 14 m/s
- Allows proper green wave setup

### 5. Enhanced Logging
```python
fog_logger.debug(f"   {vehicle_id} direction from movement: dx={dx:.1f}m, dy={dy:.1f}m → {direction}")
fog_logger.debug(f"   Lane: {lane_id}, Angle: {angle:.1f}°")
```

## Expected Behavior Now

1. **First detection**: Uses lane ID or angle (may be slightly wrong)
2. **Second detection** (1 second later): Uses actual movement (highly accurate!)
3. **Approach check**: Only triggers if ambulance APPROACHING junction:
   - East-bound: ambulance must be WEST of junction (amb_x < junc_x)
   - North-bound: ambulance must be SOUTH of junction (amb_y < junc_y)
4. **Distance check**: Must be within 500m
5. **Cooldown**: 3 seconds global cooldown between any overrides

## Test Verification

Watch for logs:
```
🚑 Ambulance detected: emergency_1 at (76.0, 495.2), heading east, speed 14.2 m/s
   emergency_1 direction from movement: dx=294.5m, dy=0.0m → east
🚨 Processing emergency: emergency_1
   Position: (370.5, 495.2)
   Distance to junction: 129.6m
   Direction: east, Speed: 14.2 m/s
🎯 Target junction: J2
📤 Sending override: J2 → Phase 0 for emergency_1
```

**Success criteria:**
- Direction matches actual movement (east if X increasing, north if Y increasing)
- Override triggers when 130-500m from junction
- NO overrides after ambulance passes junction
- Each ambulance gets ONE override per junction

## Files Modified
- `fog_server.py` lines 227-280: Direction detection from movement
- `fog_server.py` lines 574-576: Trigger distance 200m → 500m
- `fog_server.py` line 287: Added debug logging for lane/angle
