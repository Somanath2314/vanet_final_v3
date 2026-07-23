# Green Corridor Tuning Playbook

## Purpose
This document records the emergency-priority tuning work done in this repository, why it was needed, what changed in code, and how to retrain/benchmark on another device.

## Problem Observed
Emergency vehicles were not consistently getting lower wait than normal vehicles.

Example from baseline density run:
- emergency_avg_wait: 6.625 s
- normal_avg_wait: 5.7226 s

This means local preemption was not enough to guarantee a route-level green corridor.

## Root Cause
The previous logic was mostly reactive and local:
- prioritize a junction when emergency is nearby
- no strong route-ahead preemption horizon across upcoming junctions

So emergencies could still face downstream red waves and accumulate wait.

## Code Changes Implemented

### 1) Proactive Green Corridor in Traffic Controller
File: sumo_simulation/traffic_controller.py

What was added:
- Edge-to-traffic-light mapping for route-ahead preemption.
- Emergency-priority configuration API:
  - detection_range
  - pass_through_range
  - corridor_depth
  - corridor_max_distance
- Corridor control parameters:
  - emergency_pass_through_range
  - green_corridor_enabled
  - green_corridor_max_distance
  - green_corridor_junction_lookahead
  - green_corridor_edge_lookahead
  - emergency_green_hold_time
- Improved _check_emergency_priority():
  - keeps reactive nearby preemption
  - adds proactive route-ahead preemption over upcoming route edges
  - deduplicates candidates per vehicle per junction
  - prioritizes by corridor rank then distance
- Holds emergency green for a short duration after preemption.

### 2) Runtime Knobs Exposed in Integrated Runner
File: sumo_simulation/run_complete_integrated.py

New CLI options:
- --emergency-priority {auto,on,off}
- --emergency-range <meters>
- --corridor-depth <junctions>
- --corridor-distance <meters>
- --pass-through-range <meters>

Behavior:
- Applies emergency-priority settings to controller at startup.
- Persists active emergency-priority config into benchmark_metrics.json.

### 3) Benchmark Runner Support for New Knobs
File: run_benchmark.py

Added forwarding of new emergency-priority options to each simulation run:
- emergency_priority
- emergency_range
- corridor_depth
- corridor_distance
- pass_through_range

### 4) Proximity PPO Inference Wiring (Earlier Critical Fix)
Files:
- sumo_simulation/run_complete_integrated.py
- sumo_simulation/traffic_controller.py

What changed:
- Proximity mode now applies PPO-inferred phase actions to emergency-adjacent traffic lights.
- Externally controlled traffic lights are protected from density overwrite.

### 5) Reward Shaping for Training
File: rl_module/vanet_env.py

Added explicit emergency-vs-normal wait-gap pressure in reward:
- penalize when emergency wait > normal wait
- bonus when emergency wait < normal wait

## Validation Snapshots (Seed 42)

### A) Density baseline (no forced emergency mode)
Output file:
- sumo_simulation/output_validation_density_420/benchmark_metrics.json

Key values:
- emergency_avg_wait: 6.625
- normal_avg_wait: 5.7226

### B) Density + emergency priority ON (corridor depth 3, distance 450)
Output file:
- sumo_simulation/output_validation_density_green_corridor_420/benchmark_metrics.json

Key values:
- emergency_avg_wait: 4.8
- normal_avg_wait: 4.0503

### C) Density + emergency priority ON tuned (depth 5, distance 700)
Output file:
- sumo_simulation/output_validation_density_green_corridor_tuned_420/benchmark_metrics.json

Key values:
- emergency_avg_wait: 5.3
- normal_avg_wait: 3.6871

Interpretation:
- Overall waits improved with corridor controls.
- Emergency wait is still slightly higher than normal in heavy mixed traffic.
- Remaining gap is policy/training quality and parameter balancing, not missing control hooks.

## Recommended Default Knob Set Before Retraining
Start with this (more stable than aggressive horizon):
- emergency-priority: on (for corridor-focused experiments)
- emergency-range: 250
- corridor-depth: 3
- corridor-distance: 450
- pass-through-range: 30

## Cross-Device Workflow

### 1) Commit and push code changes on current device
Run from repo root:

```powershell
git add sumo_simulation/traffic_controller.py sumo_simulation/run_complete_integrated.py run_benchmark.py rl_module/vanet_env.py layout_new/routes_new.rou.xml GREEN_CORRIDOR_TUNING_PLAYBOOK.md
git commit -m "Add proactive green-corridor control and emergency-priority tuning knobs"
git push origin purge-largefile
git push upstream purge-largefile
```

### 2) Pull on another device

```powershell
git checkout purge-largefile
git pull origin purge-largefile
```

## Training Commands (Run on Other Device)

### A) Main PPO retraining run

```powershell
c:/SAPDevelop/Myproject/capstone/vanet/.venv/Scripts/python.exe rl_module/train.py --algo ppo --config layout_new/simulation_new.sumocfg --timesteps 500000 --output rl_module/trained_models --heartbeat-steps 500 --scenario-randomization --scenario-scales 0.7,0.9,1.0,1.2,1.4 --route-randomization --route-rate-min 0.6 --route-rate-max 1.4
```

### B) Quick sanity retrain (short)

```powershell
c:/SAPDevelop/Myproject/capstone/vanet/.venv/Scripts/python.exe rl_module/train.py --algo ppo --config layout_new/simulation_new.sumocfg --timesteps 50000 --output rl_module/trained_models --heartbeat-steps 250
```

## Post-Training Evaluation Commands
Replace <MODEL_ZIP_PATH> with the produced ppo_traffic_final.zip path.

### A) Single validation with emergency-priority knobs

```powershell
c:/SAPDevelop/Myproject/capstone/vanet/.venv/Scripts/python.exe sumo_simulation/run_complete_integrated.py --mode proximity --model <MODEL_ZIP_PATH> --proximity 250 --emergency-priority on --emergency-range 250 --corridor-depth 3 --corridor-distance 450 --pass-through-range 30 --config layout_new/simulation_new.sumocfg --steps 700 --seed 42 --output sumo_simulation/output_validation_retrained
```

### B) Full benchmark

```powershell
c:/SAPDevelop/Myproject/capstone/vanet/.venv/Scripts/python.exe run_benchmark.py --seeds 30 --seed-start 42 --steps 1000 --config layout_new/simulation_new.sumocfg --modes fixed,density,proximity --model <MODEL_ZIP_PATH> --proximity 250 --emergency-priority on --emergency-range 250 --corridor-depth 3 --corridor-distance 450 --pass-through-range 30
```

### C) Export paper tables/graphs

```powershell
c:/SAPDevelop/Myproject/capstone/vanet/.venv/Scripts/python.exe export_paper_metrics.py --results-dir benchmark_results --seed-start 42 --seed-count 30
```

## Documentation Update Rule
After each tuning batch, append:
- Model path and commit hash
- Knob values used
- Emergency/normal wait means and std
- 1-line conclusion

This keeps experiments reproducible and publication-ready.
