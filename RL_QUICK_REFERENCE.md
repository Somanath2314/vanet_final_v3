# Quick RL Commands Reference

## Training Commands

**Note**: Edge computing and security are ENABLED BY DEFAULT. Use `--no-edge` or `--no-security` to disable.

```bash
# Quick test (10 episodes, ~10 minutes) - edge & security enabled
python train_rl_agent.py --episodes 10

# Full training with edge + security (default, ~5 days CPU)
python train_rl_agent.py

# Disable edge computing
python train_rl_agent.py --episodes 10 --no-edge

# Disable security
python train_rl_agent.py --episodes 10 --no-security

# Disable both
python train_rl_agent.py --episodes 10 --no-edge --no-security
```

## Evaluation Commands

```bash
# Basic evaluation (10 episodes)
python evaluate_rl_agent.py

# Test specific model
python evaluate_rl_agent.py --model rl_module/models/dqn_best.pth

# Compare with rule-based controller
python evaluate_rl_agent.py --compare --episodes 20

# Visualize with SUMO GUI
python evaluate_rl_agent.py --gui --episodes 5
```

## Integration Commands

```bash
# Use trained RL model in simulation
./run_integrated_sumo_ns3.sh --rl --edge --gui

# RL with security
./run_integrated_sumo_ns3.sh --rl --edge --security --gui

# Fast simulation (no GUI)
./run_integrated_sumo_ns3.sh --rl --edge --steps 1800
```

## Long Training Session

```bash
# Use screen to avoid interruption
screen -S rl_training
cd /home/shreyasdk/capstone/vanet_final_v3
python train_rl_agent.py --edge

# Detach: Press Ctrl+A, then D
# Reattach later: screen -r rl_training
```

## Check Progress

```bash
# View latest training curves
ls -lht rl_module/logs/training_curves_*.png | head -1

# View latest checkpoint
ls -lht rl_module/models/ | head -5

# Check training summary
cat rl_module/logs/training_summary.json | python -m json.tool
```

## File Locations

- **Training Script**: `train_rl_agent.py`
- **Evaluation Script**: `evaluate_rl_agent.py`
- **Configuration**: `rl_module/config.yaml`
- **Best Model**: `rl_module/models/dqn_best.pth`
- **Checkpoints**: `rl_module/models/dqn_episode_*.pth`
- **Training Curves**: `rl_module/logs/training_curves_*.png`
- **Evaluation Results**: `rl_module/logs/evaluation_results.json`

## Documentation

- **Full Guide**: `docs/RL_TRAINING.md`
- **Summary**: `RL_IMPLEMENTATION_SUMMARY.md`
- **Main README**: `README.md` (see RL section)
- **Edge Computing**: `docs/EDGE_COMPUTING.md`

## Expected Timeline

| Task | Duration | Command |
|------|----------|---------|
| Quick test | 10 min | `python train_rl_agent.py --episodes 10 --edge` |
| Full training (CPU) | 4 days | `python train_rl_agent.py --edge` |
| Full training (GPU) | 1.5 days | `python train_rl_agent.py --edge` |
| Evaluation | 10 min | `python evaluate_rl_agent.py --compare` |

## Expected Performance

- **Waiting Time**: 30-35s (vs 45-50s rule-based) = **~30% improvement**
- **Collision Warnings**: 20-25 (vs 30-35 rule-based) = **~30% reduction**
- **Training Episodes**: 5000 recommended (minimum 1000)
