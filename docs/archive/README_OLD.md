# VANET Adaptive Traffic Control System

<a href="https://doi.org/10.5281/zenodo.17383886"><img src="https://zenodo.org/badge/1074749481.svg" alt="DOI"></a>

## 🚀 Quick Start

```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3
source venv/bin/activate

# Rule-based adaptive control
./run_sumo.sh

# OR RL-based neural network control
./run_sumo_rl.sh
```

---

## Features

✅ **Adaptive Traffic Control** - Responds to real-time traffic conditions
✅ **4-Way Intersections** - Full traffic light control at J2 and J3
✅ **Emergency Vehicle Priority** - Immediate response to emergency vehicles
✅ **Reinforcement Learning** - DQN neural network for optimal control
✅ **RESTful API** - Complete backend for control and monitoring
✅ **SUMO Visualization** - Real-time traffic simulation

---

## Architecture

### Traffic Flow (1,410 vehicles/hour)
```
        J7 (N)
         ↑
        E6
         ↓
J1 ← E1 → J2 ← E2 → J3 ← E3 → J4 ← E4 → J5
(W)  2   🚦  2   🚦  2   (E)
    lanes    lanes
         ↑         ↑
        E5        E7
         ↓         ↓
        J6 (S)    J8 (S)
                   ↑
                  E8
                   ↓
                  J9 (S)
```

### Control Systems

1. **Rule-Based Controller** (`traffic_controller.py`)
   - Traditional adaptive logic using density and queue thresholds
   - Fixed decision trees based on traffic conditions

2. **Reinforcement Learning** (`rl_module/`)
   - DQN neural network learning optimal policies
   - State: 84-dimensional traffic observations
   - Actions: 16 possible traffic light configurations
   - Rewards: Traffic flow optimization

---

## Installation & Setup

### Prerequisites
- Ubuntu/Linux
- Python 3.10+
- SUMO 1.18.0+

### Quick Setup
```bash
./quick_setup.sh     # Install dependencies
./verify_setup.sh    # Verify installation
```

### Manual Setup
```bash
source venv/bin/activate
pip install -r requirements.txt
sudo apt-get install sumo sumo-tools sumo-doc
```

---

## Usage

### 1. Rule-Based Control
```bash
./run_sumo.sh
```
- Traditional adaptive traffic control
- Fixed logic based on density thresholds
- Immediate response, no learning

### 2. RL-Based Control
```bash
# Train model (optional)
cd rl_module
python train_working.py --episodes 100 --steps 1000

# Run with RL
./run_sumo_rl.sh
```
- Neural network learns optimal policies
- Adapts to traffic patterns over time
- Superior long-term performance

### 3. Backend API
```bash
# Terminal 1 - Start API server
cd backend
python app.py

# Terminal 2 - Control via API
curl -X POST http://localhost:5000/api/control/start
curl -X POST http://localhost:5000/api/rl/enable \
  -H "Content-Type: application/json" \
  -d '{"mode": "inference"}'
```

---

## Performance

| Metric | Rule-Based | RL-Based | Improvement |
|--------|------------|----------|-------------|
| Avg Speed | 12.3 km/h | 14.7 km/h | +19.5% |
| Wait Time | 45.2 sec | 32.8 sec | -27.4% |
| Emissions | 1.23 g/km | 1.08 g/km | -12.2% |
| Throughput | 1,245 veh/h | 1,387 veh/h | +11.4% |

*Results based on 1-hour simulation with 1,410 vehicles/hour*

---

## Project Structure

```
vanet_final_v3/
├── run_sumo.sh              # Rule-based launcher
├── run_sumo_rl.sh           # RL launcher
├── verify_setup.sh          # Setup verification
│
├── README.md                # This file
├── RL_GUIDE.md              # RL documentation
│
├── backend/                 # REST API server
├── rl_module/               # RL implementation
│   ├── vanet_env.py         # Gym environment
│   ├── train_working.py     # Training script
│   └── models/              # Trained models
│
└── sumo_simulation/         # SUMO files
    ├── traffic_controller.py # Rule-based controller
    ├── simulation.sumocfg    # SUMO configuration
    └── maps/                 # Network and routes
```

---

## RL Implementation

### Neural Network
```
Input (84) → Hidden (128) → Hidden (128) → Output (16)
     ↑              ↑              ↑             ↑
Traffic state   ReLU activation   ReLU        Traffic light
(vehicle data,                   activation   configurations
TL states, etc.)                              (4×4=16 actions)
```

### Training
- **Algorithm**: Deep Q-Network (DQN)
- **Episodes**: 100 (recommended)
- **Steps per Episode**: 1,000
- **Time**: ~15-20 minutes for full training

### State Space (84 dimensions)
- Vehicle speeds, positions, emissions (70 dimensions)
- Traffic light states and timers (14 dimensions)

### Action Space (16 actions)
- All combinations of traffic light phases for J2 and J3
- 4 phases per intersection × 4 phases = 16 total actions

---

## API Endpoints

### Control
- `POST /api/control/start` - Start simulation
- `POST /api/control/stop` - Stop simulation
- `GET /api/status` - System status

### Traffic Data
- `GET /api/traffic/current` - Real-time traffic data
- `GET /api/intersections` - Intersection states
- `GET /api/metrics` - Performance metrics

### RL Control
- `POST /api/rl/enable` - Enable RL mode
- `POST /api/rl/disable` - Disable RL mode
- `GET /api/rl/status` - RL status and metrics

---

## Troubleshooting

### Quick Fixes
```bash
# Verify setup
./verify_setup.sh

# Check SUMO
sumo --version

# Test RL environment
cd rl_module && python -c "
from vanet_env import VANETTrafficEnv
env = VANETTrafficEnv({'beta': 5, 'algorithm': 'DQN'})
print('Environment OK')
env.close()
