# 📚 Documentation Index

## 🚀 Getting Started

1. **[README.md](README.md)** ⭐ **START HERE**
   - Complete system overview
   - Installation & setup
   - RL model parameters
   - Quick start commands
   - Configuration guide

2. **[START_HERE.md](START_HERE.md)** - Quick Start Guide
   - Ready-to-use commands
   - Basic usage examples
   - Copy-paste commands
   - Troubleshooting basics

3. **[QUICK_COMMANDS.sh](QUICK_COMMANDS.sh)** - Command Helper
   - Executable script with all commands
   - Auto-detects available models
   - Usage examples

## 📖 Detailed Guides

### System Architecture
- **[SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)** - Architecture Diagrams
  - Detailed system flow
  - Component interaction
  - Control flow diagrams
  - Visual representations

- **[COMPLETE_SYSTEM_GUIDE.md](COMPLETE_SYSTEM_GUIDE.md)** - Comprehensive Guide
  - All features explained
  - Advanced usage
  - Configuration options
  - Output analysis

### RL & Training
- **[RL_QUICK_REFERENCE.md](RL_QUICK_REFERENCE.md)** - RL Overview
  - RL system design
  - Model architecture
  - Reward structure
  - Performance metrics

- **[DQN_TRAINING_GUIDE.md](DQN_TRAINING_GUIDE.md)** - Training Instructions
  - Step-by-step training
  - Hyperparameter tuning
  - TensorBoard monitoring
  - Model deployment

## 📁 Archived Documentation

Older documentation moved to [docs/archive/](docs/archive/):
- Previous implementation notes
- Integration fix summaries
- Historical development docs
- System evolution history

## 🎯 Quick Reference

### I want to...

**Run the system NOW**:
```bash
./run_integrated_sumo_ns3.sh --gui --steps 500
```

**Use RL control with GUI**:
```bash
./run_integrated_sumo_ns3.sh \
    --proximity 250 \
    --model rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip \
    --gui --edge --steps 1000
```

**Train a new RL model**:
```bash
cd rl_module
python3 train_dqn_model.py --timesteps 100000
```

**See all available commands**:
```bash
./QUICK_COMMANDS.sh
```

**Get help on options**:
```bash
./run_integrated_sumo_ns3.sh --help
```

## 📊 Documentation Structure

```
vanet_final_v3/
├── README.md ⭐                    # Main documentation
├── START_HERE.md                   # Quick start
├── QUICK_COMMANDS.sh               # Command helper
│
├── SYSTEM_ARCHITECTURE.md          # Architecture details
├── COMPLETE_SYSTEM_GUIDE.md        # Comprehensive guide
│
├── RL_QUICK_REFERENCE.md           # RL overview
├── DQN_TRAINING_GUIDE.md           # Training guide
│
└── docs/
    ├── archive/                    # Historical docs
    └── [other documentation]
```

## 🔗 Quick Links

| Document | Purpose | When to Use |
|----------|---------|-------------|
| [README.md](README.md) | Main documentation | Always start here |
| [START_HERE.md](START_HERE.md) | Quick start | First time users |
| [QUICK_COMMANDS.sh](QUICK_COMMANDS.sh) | Commands | Need copy-paste commands |
| [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | Architecture | Understanding system design |
| [COMPLETE_SYSTEM_GUIDE.md](COMPLETE_SYSTEM_GUIDE.md) | Full guide | Advanced usage |
| [RL_QUICK_REFERENCE.md](RL_QUICK_REFERENCE.md) | RL overview | Understanding RL system |
| [DQN_TRAINING_GUIDE.md](DQN_TRAINING_GUIDE.md) | Training | Training new models |

---

**Tip**: Start with [README.md](README.md), then use other guides as needed!
