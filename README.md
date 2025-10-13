# VANET Adaptive Traffic Control System

## 🚀 Quick Start

```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3
source venv/bin/activate
./run_sumo.sh
```

---

## Features

✅ **Adaptive Traffic Control** - Responds to real-time traffic conditions  
✅ **4-Way Intersections** - Full traffic light control at J2 and J3  
✅ **Emergency Vehicle Priority** - Immediate response to emergency vehicles  
✅ **RL Integration** - DQN and PPO reinforcement learning agents  
✅ **RESTful API** - Complete backend for control and monitoring  
✅ **SUMO Visualization** - Real-time traffic simulation  

---

## Traffic Flow

### Intersection J2 (4-way)
- **East-West**: E1 → J2 → E2 (300 veh/hr)
- **West-East**: E2 → J2 → E1 (250 veh/hr)
- **North-South**: E5 → J2 → E6 (200 veh/hr)
- **South-North**: E6 → J2 → E5 (180 veh/hr)

### Intersection J3 (4-way)
- **East-West**: E2 → J3 → E3 (via J2 flow)
- **West-East**: E3 → J3 → E2 (250 veh/hr)
- **North-South**: E7 → J3 → E8 (220 veh/hr)
- **South-North**: E8 → J3 → E7 (190 veh/hr)

---

## Project Structure

```
vanet_final_v3/
├── run_sumo.sh              # Quick launcher
├── verify_setup.sh          # Setup verification
├── README.md                # This file
├── START_HERE.md            # Quick reference
│
├── backend/
│   ├── app.py               # Flask API (16 endpoints)
│   └── requirements.txt     # Dependencies
│
├── rl_module/
│   ├── vanet_env.py         # RL environment
│   ├── train_rl_agent.py    # Training script
│   ├── rl_traffic_controller.py
│   ├── states.py            # State management
│   └── rewards.py           # Reward functions
│
├── sumo_simulation/
│   ├── traffic_controller.py # Adaptive control
│   ├── simulation.sumocfg    # SUMO config
│   ├── maps/
│   │   ├── simple_network.net.xml
│   │   ├── routes.rou.xml    # 4-way traffic routes
│   │   └── gui-settings.cfg
│   └── output/               # Simulation results
│
└── docs/
    ├── COMPREHENSIVE_ANALYSIS.md
    ├── REQUIREMENTS_CHECKLIST.md
    ├── RL_INTEGRATION_README.md
    └── archive/              # Old documentation
```

---

## Documentation

### Essential Docs (Read These)
1. **START_HERE.md** - Quick launch guide
2. **REQUIREMENTS_CHECKLIST.md** - Requirements verification
3. **RL_INTEGRATION_README.md** - RL usage guide
4. **COMPREHENSIVE_ANALYSIS.md** - Full technical analysis

### Reference Docs
- **INSTALLATION_GUIDE.md** - Detailed installation
- **RUN_INSTRUCTIONS.md** - Running instructions
- **INTEGRATION_SUMMARY.md** - Integration overview

### Archived (Historical)
- `docs/archive/` - Old troubleshooting guides

---

## Running the System

### 1. SUMO Simulation
```bash
./run_sumo.sh
```

### 2. With Backend API
```bash
# Terminal 1
cd backend
python app.py

# Terminal 2
curl -X POST http://localhost:5000/api/control/start
```

### 3. With RL Control
```bash
# Start backend first, then:
curl -X POST http://localhost:5000/api/rl/enable \
  -H "Content-Type: application/json" \
  -d '{"mode": "inference"}'
```

### 4. Train RL Agent
```bash
cd rl_module
python train_rl_agent.py --algorithm DQN --iterations 100
```

---

## Adaptive Control Features

### Normal Operation
- East-West Green: 30 seconds
- Yellow transition: 5 seconds
- North-South Green: 30 seconds
- Yellow transition: 5 seconds

### Adaptive Adjustments
- **High Demand**: Extend green up to 60 seconds
- **Low Demand**: Early termination (minimum 15 seconds)
- **Emergency**: Immediate phase switch (< 5 seconds)

---

## API Endpoints

### Traffic Control
- `POST /api/control/start` - Start simulation
- `POST /api/control/stop` - Stop simulation
- `GET /api/status` - System status
- `GET /api/traffic/current` - Current traffic data
- `GET /api/intersections` - Intersection states

### RL Control
- `POST /api/rl/enable` - Enable RL mode
- `POST /api/rl/disable` - Disable RL mode
- `GET /api/rl/status` - RL status
- `GET /api/rl/metrics` - RL metrics

---

## Requirements Met

✅ **RL Agents**: DQN and PPO fully implemented  
✅ **Traffic State Management**: Density, queue length, waiting time  
✅ **Adaptive Signal Control**: Rule-based and RL-based  
✅ **RESTful API**: 16 endpoints  
✅ **Performance Metrics**: Comprehensive collection  
✅ **Adaptive Response**: 5 response mechanisms  

---

## System Status

✅ All errors resolved  
✅ All dependencies installed  
✅ All tests passing (7/7)  
✅ Production ready  

---

## Support

- **Quick Help**: Read `START_HERE.md`
- **Troubleshooting**: Check `docs/archive/`
- **API Usage**: Read `RL_INTEGRATION_README.md`
- **Full Analysis**: Read `COMPREHENSIVE_ANALYSIS.md`

---

## Version

**Version**: 3.0  
**Status**: Production Ready  
**Last Updated**: October 2025  

---

**Ready to run!** Execute `./run_sumo.sh` to start the simulation.
