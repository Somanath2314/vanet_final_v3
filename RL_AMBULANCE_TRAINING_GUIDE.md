# Ambulance-Aware RL Training Guide

## Overview

This system trains a **Deep Q-Network (DQN)** agent that learns optimal traffic light control strategies to **prioritize ambulances while minimizing overall traffic disruption**.

---

## How the RL Agent Learns

### **What the Agent Sees (Observation Space)**

Every simulation step, the RL agent receives a rich state vector containing:

#### **1. Standard Traffic Features (per junction)**
- Queue lengths on each approach (north, south, east, west)
- Traffic density (vehicles per meter)
- Current traffic light phase (0-3)
- Time remaining in current phase

#### **2. Ambulance Routing Features (CRITICAL - your question!)**
```python
# Global ambulance state:
- ambulance_present: bool              # Is there an ambulance in the network?
- ambulance_x, ambulance_y: float      # Current position (meters)
- ambulance_target_x, target_y: float  # Destination coordinates
- ambulance_speed: float               # Current speed (m/s)
- ambulance_heading: float             # Direction angle (0-360°)
- ambulance_direction: [N,S,E,W]       # One-hot: which cardinal direction

# Per-junction ambulance features:
For each junction (J2, J3, ...):
  - distance_to_junction: float        # Euclidean distance (meters)
  - eta_to_junction: float             # Estimated time of arrival (seconds)
  - is_target_junction: bool           # Is ambulance heading here?
  - direction_match: float             # Does ambulance need this junction? (0-1)
```

**Example state when ambulance is detected:**
```
Ambulance at (450, 520), moving east to target (1200, 500)
→ direction = [0, 0, 1, 0]  # East
→ distance_to_J2 = 50m, eta = 3s
→ distance_to_J3 = 550m, eta = 22s
→ J2 is target junction, direction_match = 1.0
```

### **What the Agent Does (Action Space)**

For each junction, the agent chooses one action:
- **Actions 0-3**: Switch to traffic light phase 0, 1, 2, or 3 (normal control)
- **Action 4**: **PREEMPT FOR AMBULANCE** (green for ambulance lane, red for cross-traffic)
- **Action 5**: Hold current phase (do nothing)

The **preempt action** automatically:
1. Detects which lane the ambulance is on
2. Sets that lane to GREEN
3. Sets cross-traffic to RED
4. Holds this configuration until ambulance passes

### **How the Agent Learns (Reward Function)**

The reward function teaches the agent what's important:

```python
reward = 0

# 🚨 HUGE PENALTY: Ambulance stopped near junction
if ambulance_present and ambulance_speed < 1.0 and distance < 100m:
    reward -= 50,000  # This is BAD!

# 🚨 MODERATE PENALTY: Ambulance slowing down
if ambulance_present and ambulance_speed < 5.0 and distance < 200m:
    reward -= 5,000

# ✅ BIG REWARD: Ambulance cleared junction quickly
if ambulance_cleared and clearance_time < 200 steps:
    reward += 1000 / clearance_time  # Faster = better

# ✅ SMALL REWARD: Ambulance moving fast
if ambulance_present and ambulance_speed > 15.0:
    reward += 10

# ⚠️ MODERATE PENALTY: Normal traffic delay
reward -= 0.1 * sum(queue_lengths)
reward -= 0.05 * sum(vehicle_waiting_times)

# ✅ SMALL BONUS: Maintaining traffic flow
reward += 0.01 * average_network_speed
```

**What this teaches:**
- **Never** let the ambulance stop (massive penalty)
- Clear ambulances **as fast as possible** (reward scales with speed)
- Minimize side effects on normal traffic (smaller penalties)
- The agent learns to **preempt at the right time** (not too early, not too late)

---

## Training Process

### **Step 1: Ambulance Spawning**

During training, ambulances are spawned randomly:
```python
# 30% of episodes will have an ambulance
if random() < 0.30:
    # Spawn ambulance after 50-150 steps
    # Random start edge (E1, E2, E5, E7)
    # Random target edge (E3, E4, E6, E8)
    # Speed: 15-25 m/s (~54-90 km/h)
```

The agent sees episodes **with and without** ambulances, learning:
- Normal traffic optimization (70% of time)
- Emergency response (30% of time)

### **Step 2: Training Loop**

```python
for episode in 1..500:
    state = env.reset()  # Start SUMO, maybe spawn ambulance
    
    for step in 1..1000:
        # Agent decides actions for all junctions
        action = agent.select_action(state)
        
        # Environment applies actions, simulates 1 second
        next_state, reward, done = env.step(action)
        
        # Store experience for learning
        agent.remember(state, action, reward, next_state)
        
        # Learn from past experiences
        if len(replay_buffer) > 64:
            agent.train_on_batch()
        
        state = next_state
```

### **Step 3: What the Neural Network Learns**

Over thousands of episodes, the network learns patterns like:

**Pattern 1: Preempt Early for Fast Ambulances**
```
IF ambulance_speed > 20 m/s AND distance_to_junction < 200m
THEN action = PREEMPT (at junction in ambulance's path)
```

**Pattern 2: Hold Preemption Until Ambulance Clears**
```
IF preemption_active AND ambulance_distance_to_junction < 50m
THEN action = HOLD (keep green for ambulance)
```

**Pattern 3: Resume Normal Control After Clearance**
```
IF ambulance_cleared OR ambulance_distance > 300m
THEN action = NORMAL_PHASE (optimize for density)
```

**Pattern 4: Coordinate Multi-Junction Preemption**
```
IF ambulance_target_is_J3 AND currently_at_J2
THEN preempt_J2_now AND prepare_J3_preemption
```

These patterns emerge naturally from the reward signal — **you don't code them explicitly**.

---

## Running the Training

### **Quick Start (Prototype Training)**

```bash
cd /Users/apple/Desktop/vanet_29_oct/vanet_final_v3

# Train for 500 episodes (~2-3 hours)
python rl_module/train_ambulance_agent.py \
    --episodes 500 \
    --steps 1000 \
    --save-freq 50
```

### **Production Training (Longer, Better)**

```bash
# Train for 2000 episodes with GUI visualization every 50 episodes
python rl_module/train_ambulance_agent.py \
    --episodes 2000 \
    --steps 1500 \
    --save-freq 100 \
    --gui
```

### **Training Output**

The script saves:
- **`rl_module/models/ambulance_dqn_final.pth`** — Final trained model
- **`rl_module/models/ambulance_dqn_ep{N}.pth`** — Checkpoints every 50 episodes
- **`rl_module/models/ambulance_training_metrics.json`** — Training curves and statistics

---

## Answering Your Questions Directly

### **Q1: "Are you taking into account ambulance direction?"**
✅ **YES!** The observation space includes:
- `ambulance_direction`: One-hot encoded [north, south, east, west]
- `direction_match` per junction: Does the ambulance need this junction?
- Heading angle and target coordinates

The agent **sees** which direction the ambulance is traveling and learns to preempt **only junctions in its path**.

### **Q2: "There will be target X/Y coordinates?"**
✅ **YES!** The state includes:
- `ambulance_x, ambulance_y`: Current position
- `ambulance_target_x, ambulance_target_y`: Destination
- `eta_to_junction`: Calculated as `distance / speed`

The agent uses this to predict **when** the ambulance will reach each junction.

### **Q3: "Do we need all this to train the model?"**
✅ **ABSOLUTELY!** Without ambulance routing info, the agent would:
- Preempt **random** junctions (wastes green time)
- Preempt too early or too late (ambulance stops anyway)
- Not coordinate multi-junction paths

With routing info, the agent learns **spatially-aware** policies.

### **Q4: "Is RL the right method?"**
✅ **YES, RL is IDEAL** because:

| Approach | Pros | Cons |
|----------|------|------|
| **Rule-based** | Simple, predictable | Can't optimize timing, causes excessive congestion, fails in edge cases |
| **Supervised Learning** | Fast inference | Needs labeled data (who labels "optimal" actions?), no sequential reasoning |
| **RL (DQN/PPO)** | Learns from simulation, optimizes long-term outcomes, handles uncertainty | Requires training time, needs tuning |

**RL is the state-of-the-art** for traffic optimization with dynamic events (like ambulances).

---

## Integration with Fog System

After training, the fog uses the model like this:

```python
# 1. Fog detects ambulance
ambulance = sensor_network.detect_emergency_vehicles()[0]

# 2. Fog gets junction data
junctions = requests.get('/api/wimax/getSignalData?x=450&y=500&radius=1000').json()

# 3. Fog constructs RL observation
state = [
    # Junction densities, phases, times...
    junctions['J2']['density']['north'], junctions['J2']['density']['south'], ...,
    
    # Ambulance routing (from TraCI):
    1,  # ambulance_present
    ambulance.x / 1000, ambulance.y / 1000,  # position
    ambulance.target_x / 1000, ambulance.target_y / 1000,  # target
    ambulance.speed / 25,  # speed
    ambulance.heading / 360,  # heading
    1, 0, 0, 0,  # direction: [east, -, -, -]
    distance_to_J2 / 1000, eta_to_J2 / 60, ...  # per-junction features
]

# 4. Fog runs RL inference
action = policy_net(torch.FloatTensor(state)).argmax().item()

# 5. Fog decodes action to override
if action == 4:  # Preempt J2
    override = {
        "poleId": "J2",
        "direction": "east",  # from ambulance direction
        "duration_s": 25,
        ...
    }
    requests.post('/api/controller/override', json=override)
```

---

## Expected Training Results

After 500 episodes:
- **Ambulance clearance time**: ~30-50 steps (30-50 seconds)
- **Normal traffic delay**: Similar to baseline (slight increase acceptable)
- **Ambulance stop events**: Near zero (agent learns to prevent stops)

After 2000 episodes:
- **Ambulance clearance time**: ~20-30 steps (20-30 seconds) ✨
- **Coordination**: Agent preempts multiple junctions in sequence
- **Robustness**: Handles varying ambulance speeds, traffic densities

---

## Next Steps

1. **Run prototype training** (500 episodes, ~2-3 hours)
2. **Validate model** with test scenarios
3. **Integrate into fog** (`sensor_network.py` loads the `.pth`)
4. **Run production training** (2000 episodes) for paper results

---

## Summary

**Yes, the RL model FULLY accounts for:**
✅ Ambulance position (x, y)  
✅ Ambulance target (target_x, target_y)  
✅ Ambulance direction (north/south/east/west)  
✅ Ambulance speed and heading  
✅ Distance and ETA to each junction  
✅ Junction densities and phases  

**The agent learns to:**
🎯 Preempt the RIGHT junction (in ambulance's path)  
🎯 Preempt at the RIGHT time (just before arrival)  
🎯 Coordinate multi-junction preemption  
🎯 Balance ambulance priority with normal traffic  

**RL is the RIGHT approach** because it learns optimal policies that rule-based systems cannot achieve.
