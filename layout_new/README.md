New Layout Runbook

This folder contains an OSM-derived SUMO network and generated assets for VANET runs.

Prerequisites
- SUMO installed and available on PATH (sumo, sumo-gui)
- Python virtual environment at .venv with project dependencies installed

Generate layout assets
- From repo root:
  .venv\Scripts\python.exe layout_new\generate_layout_assets.py

Generate denser, map-wide tier-2 RSU coverage (300m directional + short-road midpoint fallback)
- From repo root:
  .venv\Scripts\python.exe layout_new\generate_layout_assets.py --rsu-interval 300 --ensure-short-road-coverage --short-road-min-length 120

Generated files
- layout_new\routes_new.rou.xml
- layout_new\rsu.add.xml
- layout_new\rsu_config.json
- layout_new\simulation_new.sumocfg

Headless proximity run
- From repo root:
  .venv\Scripts\python.exe sumo_simulation\run_complete_integrated.py --mode proximity --model rl_module\trained_models\dqn_traffic_20260304_221440\dqn_traffic_final.zip --config layout_new\simulation_new.sumocfg --steps 420 --seed 42

GUI proximity run
- From repo root:
  .venv\Scripts\python.exe sumo_simulation\run_complete_integrated.py --mode proximity --model rl_module\trained_models\dqn_traffic_20260304_221440\dqn_traffic_final.zip --config layout_new\simulation_new.sumocfg --steps 1200 --seed 42 --gui

Notes
- The runner auto-loads layout_new\rsu_config.json when --config points to layout_new\simulation_new.sumocfg.
- If you regenerate map.net.xml, rerun generate_layout_assets.py before simulation.
