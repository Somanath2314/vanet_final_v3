# Training and Using DQN Model for Hybrid Traffic Control

## Overview

This guide shows how to train a proper DQN (Deep Q-Network) model for your hybrid traffic control system and integrate it with your existing infrastructure.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              HYBRID TRAFFIC CONTROL SYSTEM              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐         ┌──────────────────┐        │
│  │   NORMAL     │         │   EMERGENCY       │        │
│  │   TRAFFIC    │         │   SITUATION       │        │
│  └──────┬───────┘         └────────┬──────────┘        │
│         │                          │                   │
│         ▼                          ▼                   │
│  ┌──────────────┐         ┌──────────────────┐        │
│  │  Density-    │         │  Trained DQN     │        │
│  │  Based       │         │  Model           │        │
│  │  Control     │         │  (Neural Net)    │        │
│  └──────────────┘         └──────────────────┘        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Step 1: Install Requirements

### Option A: Automatic Setup (Recommended)
```bash
cd /home/shreyasdk/capstone/vanet_final_v3
./setup_dqn_training.sh
```

### Option B: Manual Setup
```bash
cd /home/shreyasdk/capstone/vanet_final_v3
source venv/bin/activate
pip install -r rl_dqn_requirements.txt
```

**Packages installed:**
- `stable-baselines3==2.2.1` - DQN algorithm implementation
- `torch>=2.0.0` - Neural network backend
- `gymnasium>=0.28.0` - RL environment interface
- `tensorboard>=2.11.0` - Training monitoring

## Step 2: Train DQN Model

### Quick Training (Testing - 10k steps, ~5 minutes)
```bash
cd rl_module
python3 train_dqn_model.py --timesteps 10000
```

### Standard Training (100k steps, ~1 hour)
```bash
python3 train_dqn_model.py --timesteps 100000
```

### Full Training (1M steps, ~10 hours)
```bash
python3 train_dqn_model.py \
    --timesteps 1000000 \
    --lr 0.0001 \
    --buffer-size 100000 \
    --batch-size 64 \
    --save-freq 10000
```

### Training Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--timesteps` | 100000 | Total training steps |
| `--lr` | 0.0001 | Learning rate |
| `--buffer-size` | 50000 | Replay buffer size |
| `--batch-size` | 32 | Training batch size |
| `--gamma` | 0.99 | Discount factor |
| `--exploration` | 0.3 | Exploration fraction |
| `--save-freq` | 10000 | Checkpoint frequency |
| `--config` | simulation.sumocfg | SUMO configuration |
| `--output` | ./trained_models | Output directory |

### Training Output

The training script creates:
```
trained_models/
└── dqn_traffic_YYYYMMDD_HHMMSS/
    ├── dqn_traffic_final.zip          # Final trained model
    ├── config.txt                      # Training configuration
    ├── checkpoints/                    # Intermediate checkpoints
    │   ├── dqn_traffic_10000_steps.zip
    │   ├── dqn_traffic_20000_steps.zip
    │   └── ...
    └── tensorboard/                    # Training logs
        └── DQN_1/
```

### Monitor Training with TensorBoard

```bash
tensorboard --logdir=trained_models/dqn_traffic_*/tensorboard
```

Open browser to: `http://localhost:6006`

**Metrics to watch:**
- `rollout/ep_rew_mean` - Average episode reward (should increase)
- `train/loss` - Training loss (should decrease)
- `rollout/ep_len_mean` - Episode length

## Step 3: Run Hybrid Control with Trained Model

### Using Latest Trained Model
```bash
cd rl_module

# Find the latest model
MODEL=$(ls -t ../trained_models/dqn_traffic_*/dqn_traffic_final.zip | head -1)

# Run hybrid control
python3 run_hybrid_dqn.py --model $MODEL --steps 3600
```

### Using Specific Model
```bash
python3 run_hybrid_dqn.py \
    --model ../trained_models/dqn_traffic_20241108_143022/dqn_traffic_final.zip \
    --config ../sumo_simulation/simulation.sumocfg \
    --steps 3600
```

### Expected Output

```
================================================================================
INITIALIZING HYBRID DQN CONTROLLER
================================================================================

Loading trained DQN model...
  Model: trained_models/dqn_traffic_20241108_143022/dqn_traffic_final.zip
✓ Model loaded successfully

Starting SUMO simulation...
  Config: sumo_simulation/simulation.sumocfg
✓ SUMO started
✓ Found 2 traffic lights: ('J2', 'J3')
  J2: 4 phases
  J3: 4 phases

Creating environment...
✓ Environment created
  Observation space: (154,)
  Action space: 16 actions

Resetting environment...
✓ Environment reset

================================================================================
✅ INITIALIZATION COMPLETE
================================================================================

================================================================================
RUNNING HYBRID CONTROL WITH TRAINED DQN
================================================================================

Control Strategy:
  • Normal traffic: Density-based adaptive control
  • Emergency detected: Trained DQN model with greenwave

================================================================================

Step    0/3600 | Mode: DENSITY         | Reward:    0.45 | Avg:    0.45 | Emergencies: 0
Step   50/3600 | Mode: DENSITY         | Reward:    3.21 | Avg:    2.87 | Emergencies: 0

🚨 EMERGENCY DETECTED at step 100!
   • emergency_1 detected by RSU_J2
   Switching to TRAINED DQN control...

Step  100/3600 | Mode: RL-EMERGENCY    | Reward:  215.33 | Avg:   45.12 | Emergencies: 1
Step  150/3600 | Mode: RL-EMERGENCY    | Reward:  398.21 | Avg:   67.89 | Emergencies: 1

✅ EMERGENCY CLEARED at step 180
   Switching back to density-based control...

Step  200/3600 | Mode: DENSITY         | Reward:    4.56 | Avg:   52.34 | Emergencies: 0
...

================================================================================
HYBRID CONTROL SIMULATION STATISTICS
================================================================================

Total steps: 3600
Density-based mode: 3200 steps (88.9%)
RL emergency mode: 400 steps (11.1%)
Emergency detections: 3
Total reward: 185423.45
Average reward: 51.51

Emergency Coordinator Statistics:
  Total detections: 3
  Active emergencies: 0
  Active greenwaves: 0

✅ HYBRID CONTROL WITH TRAINED DQN WORKING!
   System successfully used trained model during emergencies

================================================================================
```

## Step 4: Integrate with Existing Traffic Controller

To use the trained model in your existing `traffic_controller.py`:

```python
from stable_baselines3 import DQN

# In your initialization
class AdaptiveTrafficController:
    def __init__(self, ...):
        # ... existing code ...
        
        # Load trained DQN model
        self.dqn_model = None
        if os.path.exists('trained_models/latest/dqn_traffic_final.zip'):
            self.dqn_model = DQN.load('trained_models/latest/dqn_traffic_final.zip')
            print("✓ Loaded trained DQN model")

# In your run_simulation_with_rl method
def run_simulation_with_rl(self, rl_controller, steps=3600):
    # ... existing emergency detection code ...
    
    if emergency_active:
        if self.dqn_model:
            # Use trained DQN model
            action, _states = self.dqn_model.predict(obs, deterministic=True)
        else:
            # Fallback to random policy
            action = rl_controller.env.action_space.sample()
```

## Model Performance Expectations

### Training Progress

| Timesteps | Expected Reward | Description |
|-----------|----------------|-------------|
| 0-10k | -50 to 0 | Random exploration, poor performance |
| 10k-50k | 0 to +50 | Learning basic patterns |
| 50k-100k | +50 to +150 | Good traffic flow |
| 100k-500k | +150 to +300 | Excellent traffic flow |
| 500k-1M | +300 to +500 | Near-optimal performance |

### Reward Breakdown

```python
# Normal traffic
base_reward = -waiting_time - stopped_vehicles * 10

# Emergency bonuses
if emergency_moving_fast:
    reward += 200  # Fast ambulance transit
elif emergency_stopped:
    reward -= 150  # Ambulance blocked (bad!)

# Traffic flow
reward += mean_speed * 0.1
reward -= queue_length * 5
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'stable_baselines3'"
**Solution**: Run `./setup_dqn_training.sh` to install requirements

### Issue: Training is very slow
**Solutions**:
1. Reduce `--timesteps` for testing (e.g., 10000)
2. Increase `--batch-size` if you have GPU (e.g., 128)
3. Use fewer vehicles in SUMO config for faster simulation

### Issue: Model performance not improving
**Solutions**:
1. Train longer (try 500k-1M timesteps)
2. Adjust learning rate: `--lr 0.00005` (lower) or `--lr 0.0005` (higher)
3. Increase replay buffer: `--buffer-size 100000`
4. Check TensorBoard graphs for learning issues

### Issue: Model works well in training but poorly in hybrid system
**Solution**: The environment might be different. Ensure:
- Same SUMO configuration used for training and testing
- Same emergency vehicle routes
- Same traffic patterns

## Advanced: Hyperparameter Tuning

### Conservative (Stable but Slower)
```bash
python3 train_dqn_model.py \
    --timesteps 500000 \
    --lr 0.00005 \
    --buffer-size 100000 \
    --batch-size 64 \
    --exploration 0.5 \
    --gamma 0.995
```

### Aggressive (Faster but Less Stable)
```bash
python3 train_dqn_model.py \
    --timesteps 200000 \
    --lr 0.001 \
    --buffer-size 30000 \
    --batch-size 128 \
    --exploration 0.2 \
    --gamma 0.98
```

### GPU-Optimized (If Available)
```bash
python3 train_dqn_model.py \
    --timesteps 1000000 \
    --lr 0.0001 \
    --buffer-size 200000 \
    --batch-size 256 \
    --save-freq 20000
```

## Files Created

1. **`rl_module/train_dqn_model.py`** - Training script
2. **`rl_module/run_hybrid_dqn.py`** - Inference script with hybrid control
3. **`rl_dqn_requirements.txt`** - Python dependencies
4. **`setup_dqn_training.sh`** - Automated setup script
5. **`DQN_TRAINING_GUIDE.md`** - This guide

## Quick Start Commands

```bash
# 1. Setup environment
./setup_dqn_training.sh

# 2. Quick training test (5 min)
cd rl_module
python3 train_dqn_model.py --timesteps 10000

# 3. Run with trained model
MODEL=$(ls -t ../trained_models/dqn_traffic_*/dqn_traffic_final.zip | head -1)
python3 run_hybrid_dqn.py --model $MODEL --steps 1000

# 4. For production training (overnight)
nohup python3 train_dqn_model.py --timesteps 1000000 > training.log 2>&1 &
```

## Next Steps

1. **Train initial model**: Start with 100k timesteps
2. **Evaluate performance**: Run hybrid control and check statistics
3. **Tune hyperparameters**: Adjust learning rate, buffer size based on results
4. **Long training**: Train 500k-1M timesteps for production model
5. **Deploy**: Integrate best model into your traffic controller

## Summary

✅ **Created:**
- Complete DQN training pipeline with stable-baselines3
- Hybrid controller that uses trained model for emergencies
- Automated setup and training scripts
- Comprehensive documentation

✅ **Features:**
- Proper neural network (not random actions)
- Checkpointing every 10k steps
- TensorBoard monitoring
- Easy integration with your existing system
- Hybrid control: density-based + trained DQN

✅ **Ready to use!** Just run the setup script and start training.
