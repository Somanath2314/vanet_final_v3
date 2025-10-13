# RL Traffic Optimization Integration

This document describes the integration of Reinforcement Learning (RL) traffic optimization functionality from the RL-Traffic-optimization_CIL4sys repository into the VANET final v3 project.

## Overview

The RL module provides intelligent traffic light control using Deep Q-Networks (DQN) or Proximal Policy Optimization (PPO) algorithms. It learns optimal traffic signal timing to minimize congestion, reduce emissions, and improve traffic flow.

## Architecture

### Components

1. **RL Module** (`rl_module/`)
   - `vanet_env.py`: Gym-compatible RL environment
   - `rewards.py`: Reward function definitions
   - `states.py`: State representation for vehicles and traffic lights
   - `helpers.py`: Utility functions
   - `rl_traffic_controller.py`: Integration with SUMO traffic controller
   - `train_rl_agent.py`: Training script for RL agents

2. **Backend Integration** (`backend/app.py`)
   - New API endpoints for RL control
   - Integration with existing traffic controller
   - Metrics tracking for RL performance

## Installation

### 1. Install Dependencies

```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3
pip install -r backend/requirements.txt
```

### 2. Verify Installation

```bash
python -c "import gymnasium; import ray; import torch; print('RL dependencies installed successfully')"
```

## Usage

### Starting the Simulation with RL

#### Option 1: Via API

1. **Start the backend server:**
```bash
cd backend
python app.py
```

2. **Start the simulation:**
```bash
curl -X POST http://localhost:5000/api/control/start \
  -H "Content-Type: application/json" \
  -d '{"config_path": "../sumo_simulation/simulation.sumocfg", "steps": 3600}'
```

3. **Enable RL mode:**
```bash
curl -X POST http://localhost:5000/api/rl/enable \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "inference",
    "config": {
      "beta": 20,
      "algorithm": "DQN",
      "tl_constraint_min": 5,
      "tl_constraint_max": 60
    }
  }'
```

4. **Check RL status:**
```bash
curl http://localhost:5000/api/rl/status
```

5. **Get RL metrics:**
```bash
curl http://localhost:5000/api/rl/metrics
```

#### Option 2: Direct Python Usage

```python
from rl_module.rl_traffic_controller import RLTrafficController
import traci

# Start SUMO
sumo_cmd = ["sumo", "-c", "simulation.sumocfg"]
traci.start(sumo_cmd)

# Create RL controller
config = {
    'beta': 20,
    'algorithm': 'DQN',
    'tl_constraint_min': 5,
    'tl_constraint_max': 60,
    'horizon': 1000
}

rl_controller = RLTrafficController(mode='inference', config=config)
rl_controller.initialize(sumo_connected=True)

# Run simulation with RL control
for step in range(1000):
    metrics = rl_controller.step()
    print(f"Step {step}: Reward={metrics['reward']:.2f}")

rl_controller.close()
traci.close()
```

## Training a New RL Agent

### Using the Training Script

```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3/rl_module

# Train DQN agent
python train_rl_agent.py \
  --algorithm DQN \
  --iterations 100 \
  --beta 20 \
  --horizon 1000 \
  --output-dir ../rl_models

# Train PPO agent
python train_rl_agent.py \
  --algorithm PPO \
  --iterations 100 \
  --beta 20 \
  --horizon 1000 \
  --output-dir ../rl_models
```

### Training Parameters

- `--algorithm`: RL algorithm (DQN or PPO)
- `--iterations`: Number of training iterations
- `--beta`: Number of observable vehicles
- `--horizon`: Episode length in steps
- `--tl-min`: Minimum time before traffic light change (seconds)
- `--tl-max`: Maximum time before forced change (seconds)
- `--checkpoint-freq`: Save checkpoint every N iterations
- `--output-dir`: Directory to save trained models

### Using Trained Models

```bash
curl -X POST http://localhost:5000/api/rl/enable \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "inference",
    "model_path": "/path/to/trained/model",
    "config": {"beta": 20, "algorithm": "DQN"}
  }'
```

## API Endpoints

### RL-Specific Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/rl/status` | GET | Get RL controller status and metrics |
| `/api/rl/enable` | POST | Enable RL-based traffic control |
| `/api/rl/disable` | POST | Disable RL mode |
| `/api/rl/metrics` | GET | Get RL training/inference metrics |
| `/api/rl/step` | POST | Execute one RL control step |

### Request/Response Examples

#### Enable RL Mode
**Request:**
```json
POST /api/rl/enable
{
  "mode": "inference",
  "model_path": null,
  "config": {
    "beta": 20,
    "algorithm": "DQN",
    "tl_constraint_min": 5,
    "tl_constraint_max": 60,
    "horizon": 1000
  }
}
```

**Response:**
```json
{
  "message": "RL mode enabled successfully",
  "mode": "inference",
  "config": {
    "beta": 20,
    "algorithm": "DQN",
    "action_spec": {
      "tl_1": ["GGGGrrrr", "rrrrGGGG"],
      "tl_2": ["GGrr", "rrGG"]
    }
  }
}
```

#### Get RL Metrics
**Response:**
```json
{
  "current": {
    "mode": "inference",
    "current_episode_reward": 125.5,
    "current_episode_length": 450,
    "total_episodes": 5,
    "avg_episode_reward": 110.2,
    "avg_episode_length": 480
  },
  "history": [...],
  "total_records": 150
}
```

## Configuration

### Environment Configuration

The RL environment can be configured with the following parameters:

```python
config = {
    'beta': 20,                    # Number of observable vehicles
    'action_spec': {},             # Auto-detected from SUMO
    'tl_constraint_min': 5,        # Min seconds before light change
    'tl_constraint_max': 60,       # Max seconds before forced change
    'sim_step': 1.0,               # Simulation step size (seconds)
    'algorithm': 'DQN',            # 'DQN' or 'PPO'
    'horizon': 1000,               # Episode length
}
```

### Reward Function

The default reward function optimizes for:
- **Speed**: Rewards vehicles traveling above minimum speed (10 km/h)
- **Wait time**: Penalizes vehicles idled for more than 80 steps
- **Acceleration**: Penalizes harsh accelerations (> 0.15 m/s²)

Customize in `rl_module/vanet_env.py`:

```python
def compute_reward(self, rl_actions):
    min_speed = 10        # km/h
    idled_max_steps = 80  # steps
    max_abs_acc = 0.15    # m/s^2
    c = 0.001
    
    reward = c * (
        self.rewards.penalize_min_speed(min_speed) +
        self.rewards.penalize_max_wait(self.obs_veh_wait_steps, idled_max_steps, 0, -10) +
        self.rewards.penalize_max_acc(self.obs_veh_acc, max_abs_acc, 1, 0)
    )
    
    return reward
```

## State Space

The RL agent observes:
- Vehicle speeds (beta vehicles)
- Vehicle orientations (x, y, angle)
- CO2 emissions
- Wait steps (time idled)
- Accelerations
- Traffic light states (binary encoding)
- Traffic light timers

**Total state dimension:** `7 * beta + num_traffic_lights + num_intersections`

## Action Space

### DQN
- Discrete action space
- Each action represents a combination of traffic light phases
- Size: Product of all possible phase combinations

### PPO
- Continuous action space
- One action per intersection
- Range: [0, 1] mapped to phase selection

## Performance Metrics

The RL controller tracks:
- Episode rewards
- Mean vehicle speed
- Mean CO2 emissions
- Episode length
- Traffic flow metrics

Access via `/api/rl/metrics` endpoint.

## Troubleshooting

### Common Issues

1. **Import errors**
   ```bash
   # Ensure all dependencies are installed
   pip install -r backend/requirements.txt
   ```

2. **SUMO connection issues**
   ```bash
   # Verify SUMO is installed and in PATH
   sumo --version
   ```

3. **Ray initialization errors**
   ```bash
   # Ray may need to be restarted
   ray stop
   ray start --head
   ```

4. **Memory issues during training**
   ```bash
   # Reduce batch size or number of workers
   python train_rl_agent.py --num-workers 1
   ```

## Integration with Existing Features

The RL module integrates seamlessly with:
- **Sensor Network**: Uses sensor data for state observation
- **Emergency Vehicle Detection**: Can prioritize emergency vehicles
- **Traffic Metrics**: Provides additional performance metrics
- **API**: Full REST API support for control and monitoring

## Future Enhancements

Planned improvements:
1. Multi-agent RL for coordinated intersection control
2. Transfer learning from pre-trained models
3. Real-time adaptation to traffic patterns
4. Integration with V2X communication
5. Advanced reward shaping for specific objectives

## References

- Original CIL4SYS Project: [RL-Traffic-optimization_CIL4sys](https://github.com/cyrilhokage/RL-Traffic-optimization_CIL4sys)
- Ray RLlib Documentation: https://docs.ray.io/en/latest/rllib/index.html
- SUMO Documentation: https://sumo.dlr.de/docs/
- OpenAI Gym: https://gym.openai.com/

## License

This integration maintains compatibility with both the original VANET project and the CIL4SYS RL traffic optimization project.
