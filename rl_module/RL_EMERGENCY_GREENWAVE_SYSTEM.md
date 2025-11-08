# RL Module Enhancement: Emergency Vehicle Greenwave System

## Overview

This update enhances the reinforcement learning module to properly handle emergency vehicles (ambulances) with RSU-based detection and greenwave coordination. It also fixes issues with short-distance vehicles that complete their routes during simulation.

## Key Changes

### 1. Emergency Vehicle Coordinator (`emergency_coordinator.py`)

**NEW FILE** - Core module for RSU-based emergency vehicle detection and greenwave management.

#### Features:
- **RSU-based Detection**: Uses roadside units (RSUs) positioned at junctions to detect emergency vehicles within 300m range
- **Greenwave Creation**: Coordinates traffic lights ahead of emergency vehicle's route (looks 3-5 junctions ahead)
- **Route Prediction**: Analyzes vehicle route to determine which junctions need green lights
- **Multi-RSU Relay**: RSUs communicate to maintain greenwave as vehicle moves through network

#### Key Classes:

```python
EmergencyVehicle
├─ vehicle_id: str           # Unique identifier
├─ current_edge: str          # Current road segment
├─ position: float            # Position on edge
├─ route: List[str]           # Planned route through network
├─ detected_by_rsu: str       # Which RSU detected it
└─ greenwave_active: bool     # Is greenwave currently active

EmergencyVehicleCoordinator
├─ detect_emergency_vehicles()    # Scan for ambulances via RSUs
├─ create_greenwave()             # Build greenwave path
├─ apply_greenwave()              # Set traffic lights to green
└─ get_statistics()               # Get performance metrics
```

#### Detection Logic:
1. Check all vehicles in simulation
2. Identify emergency vehicles by:
   - Vehicle ID contains: 'emergency', 'ambulance', 'fire', 'police'
   - Vehicle type is 'emergency'
3. Find nearest RSU within 300m range
4. Track vehicle position and route
5. Create greenwave along predicted path

### 2. Enhanced VANET Environment (`vanet_env.py`)

#### New Features:

**a) Vehicle Lifecycle Management**
```python
# Tracks all vehicles seen during simulation
self.all_seen_vehicles: set       # All vehicles ever observed
self.completed_vehicles: set       # Vehicles that finished routes

# Handles disappearing vehicles gracefully
def get_observable_veh_ids():
    # Updates tracking sets
    # Detects newly completed vehicles
    # Returns currently active vehicles only
```

**Problem Solved**: RL agent was crashing when vehicles with short routes disappeared from simulation. Now properly tracks vehicle lifecycle.

**b) RSU-Based Emergency Override**
```python
def emergency_override():
    # Initialize coordinator with network topology
    # Detect emergency vehicles via RSUs
    # Create greenwave for each emergency vehicle
    # Apply greenwave to traffic lights ahead
    # Force immediate phase change for emergencies
```

**Key Difference from Old System**:
- OLD: Simple distance-based detection, single junction response
- NEW: RSU network detection, multi-junction greenwave coordination

**c) Enhanced Reward Function**

The reward structure now heavily prioritizes emergency vehicles:

```python
Base Reward Components:
├─ Traffic flow metrics       (weight: 1.0 normal, 0.3 during emergency)
├─ Vehicle waiting times       (-50 penalty)
└─ Acceleration smoothness     (comfort)

Emergency Vehicle Rewards (HIGHEST PRIORITY):
├─ Moving fast (>10 m/s)      +200 reward (HUGE)
├─ Moving moderate (>5 m/s)   +100 reward
├─ Moving slow (<5 m/s)       -150 penalty (SEVERE)
├─ Waiting >5 seconds         -100 penalty (SEVERE)
└─ Active greenwave           +50 bonus

Queue Penalties:
├─ Congestion (<2 m/s)        -20 per lane
└─ Moderate congestion        -5 per lane
```

**Scaling During Emergency**:
When emergency vehicle is active:
- Base traffic rewards scaled to 30% (emergency is priority)
- Queue penalties scaled to 50% (secondary concern)
- Emergency rewards at 100% (absolute priority)

**Min/Max Rewards**:
- Normal operation: -200 to +200
- Emergency active: -300 to +350 (wider range for strong signal)

#### Emergency Statistics Tracking:
```python
info = {
    'active_emergencies': int          # Current emergency vehicles
    'successful_greenwaves': int       # Total greenwaves created
    'emergency_detections': int        # Total RSU detections
    'completed_vehicles': int          # Vehicles that finished routes
}
```

### 3. Updated RL Traffic Controller (`rl_traffic_controller.py`)

#### Enhanced Metrics:
Now returns emergency-related metrics in each step:
- `active_emergencies`: Number of emergency vehicles currently in system
- `successful_greenwaves`: Count of greenwaves successfully created
- `emergency_detections`: Total emergency vehicle detections by RSUs
- `completed_vehicles`: Vehicles that completed their routes

These metrics help monitor:
1. Emergency vehicle handling performance
2. Greenwave system effectiveness
3. Vehicle lifecycle management

## How It Works: Complete Flow

### Normal Traffic Operation:
```
1. RL Agent observes state (vehicle speeds, positions, traffic light states)
2. Agent selects action (traffic light phase changes)
3. Environment applies action
4. Vehicles move according to SUMO simulation
5. Reward computed based on traffic flow
6. Agent learns to optimize overall traffic flow
```

### Emergency Vehicle Detected:
```
1. RSU detects ambulance within 300m range
   └─> EmergencyVehicleCoordinator.detect_emergency_vehicles()

2. Coordinator analyzes vehicle route
   └─> Look ahead 3-5 junctions along route

3. Create greenwave path
   └─> Identify all traffic lights on path
   └─> Determine optimal phases for green path

4. Apply greenwave to traffic lights
   └─> Set phases to green ahead of vehicle
   └─> Force immediate change (override min green time)
   └─> Maintain greenwave as vehicle progresses

5. Compute massive reward
   └─> +200 if vehicle moving fast
   └─> -150 if vehicle delayed
   └─> +50 bonus for active greenwave

6. RSUs relay information
   └─> Next RSU detects vehicle
   └─> Greenwave extends forward
   └─> Previous lights return to normal RL control
```

## Configuration

### RSU Detection Range:
```python
EmergencyVehicleCoordinator(rsu_range=300.0)  # 300 meters
```

### Emergency Vehicle Identification:
- By ID: 'ambulance', 'emergency', 'fire', 'police'
- By Type: vType='emergency' in SUMO route file

### Traffic Light Constraints:
```python
tl_constraint_min = 5   # Minimum green time (can override for emergency)
tl_constraint_max = 60  # Maximum green time (forced change)
```

### Greenwave Lookahead:
```python
lookahead_edges = route_edges[current_idx:current_idx + 5]  # 5 junctions ahead
```

## Route File Configuration

Your routes file (`routes.rou.xml`) already has emergency vehicles:

```xml
<!-- Emergency vehicle type -->
<vType id="emergency" accel="3.0" decel="5.0" sigma="0.2" 
      length="6.0" minGap="2.0" maxSpeed="80.0" 
      guiShape="emergency" color="red"/>

<!-- Emergency vehicle -->
<vehicle id="emergency_1" type="emergency" route="route_east_west_full" depart="10"/>

<!-- Emergency flow -->
<flow id="emergency_flow" type="emergency" route="route_east_west_full" 
      begin="50" end="3600" vehsPerHour="10" departLane="best" departSpeed="max"/>
```

## Benefits of This Approach

### 1. **Realistic Emergency Response**
- RSU-based detection mimics real V2X infrastructure
- Greenwave coordination is how real emergency systems work
- Multi-junction coordination prevents stop-and-go for ambulances

### 2. **Handles Short-Distance Vehicles**
- Tracks vehicle lifecycle (creation → active → completed)
- Gracefully handles vehicles disappearing from simulation
- No more crashes when vehicles reach destination

### 3. **Strong Learning Signal**
- Huge reward differences (+200 vs -150) create strong gradient
- Agent learns emergency priority is critical
- Clear signal: delaying ambulance = very bad

### 4. **Scalable Design**
- Works with any network topology
- Automatically detects junctions and RSUs
- Can handle multiple simultaneous emergencies

### 5. **Observable Results**
- Metrics show emergency handling performance
- Can verify greenwave creation in logs
- Track delays and successful passages

## Usage Examples

### Running with RL:
```bash
cd /home/shreyasdk/capstone/vanet_final_v3/sumo_simulation
python3 run_rl_simulation.py
```

### Monitoring Emergency Handling:
Look for these log messages:
```
🚨 Emergency vehicle detected: emergency_1 by RSU_J2
🟢 Greenwave created for emergency_1: ['J2', 'J3']
🟢 Greenwave: J2 set to phase 2 for emergency_1
🚨 Emergency override: J3 forced to phase 1 for emergency_1
✓ Emergency vehicle emergency_1 completed route, greenwave deactivated
```

### Checking Metrics:
```python
metrics = rl_controller.step()
print(f"Active emergencies: {metrics['active_emergencies']}")
print(f"Greenwaves created: {metrics['successful_greenwaves']}")
print(f"Emergency detections: {metrics['emergency_detections']}")
```

## Testing Recommendations

### 1. **Test Emergency Detection**
- Run simulation and check for detection messages
- Verify RSU range (should detect at 300m)
- Confirm vehicle type recognition

### 2. **Test Greenwave Creation**
- Watch traffic lights turn green ahead of ambulance
- Verify multi-junction coordination
- Check that greenwave deactivates after passage

### 3. **Test Reward Signal**
- Monitor episode rewards during emergency
- Should see large positive rewards when ambulance flows smoothly
- Should see large negative rewards when ambulance stops

### 4. **Test Vehicle Lifecycle**
- Add vehicles with short routes
- Verify no crashes when vehicles complete
- Check `completed_vehicles` metric increases

### 5. **Test Multiple Emergencies**
- Add multiple ambulances simultaneously
- Verify each gets own greenwave
- Check system doesn't conflict

## Troubleshooting

### Issue: Emergency vehicles not detected
**Solution**: 
- Check vehicle ID contains 'ambulance' or 'emergency'
- Verify vehicle type is 'emergency' in SUMO
- Confirm RSUs initialized (see initialization logs)

### Issue: Greenwave not activating
**Solution**:
- Check network topology initialization
- Verify traffic lights are in action_spec
- Confirm vehicle route has valid edges

### Issue: RL agent ignoring emergencies
**Solution**:
- Verify reward signals in logs
- Check emergency_bonus vs base_reward magnitude
- May need to train longer to learn priority

### Issue: Crashes with short-distance vehicles
**Solution**:
- Already fixed with vehicle lifecycle tracking
- Check that `all_seen_vehicles` is being updated
- Verify `completed_vehicles` set is working

## Future Enhancements

1. **Predictive Greenwave**: Start greenwave before vehicle reaches RSU range
2. **Traffic Density Awareness**: Adapt greenwave based on congestion
3. **Multi-Vehicle Coordination**: Handle platoons of emergency vehicles
4. **Learning Emergency Patterns**: RL agent learns optimal emergency response
5. **Communication Delays**: Simulate realistic V2X communication latency

## Files Modified/Created

### Created:
- `rl_module/emergency_coordinator.py` - Emergency vehicle coordination system

### Modified:
- `rl_module/vanet_env.py` - Added emergency detection, vehicle tracking, enhanced rewards
- `rl_module/rl_traffic_controller.py` - Added emergency metrics to step returns

## References

- **Greenwave Systems**: Progressive signal timing for emergency vehicles
- **V2X Communication**: Vehicle-to-everything communication protocols
- **RSU Networks**: Roadside unit placement and detection ranges
- **Reinforcement Learning**: Reward shaping for priority handling

## Author Notes

This implementation addresses two critical issues:
1. Emergency vehicles (ambulances) now get proper priority through RSU-coordinated greenwave
2. Short-distance vehicles no longer cause crashes when they complete their routes

The system is designed to be realistic (based on real V2X infrastructure) while providing strong learning signals for the RL agent. The reward structure heavily incentivizes emergency vehicle passage, ensuring the agent learns this is the highest priority task.
