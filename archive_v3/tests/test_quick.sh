#!/bin/bash
# Quick test - 50 steps only

echo "Quick test: 50 steps without GUI"
cd /home/shreyasdk/capstone/vanet_final_v3

source venv/bin/activate 2>/dev/null || true

cd sumo_simulation
python3 run_integrated_simulation.py --mode rule --steps 50 --output ./output

echo ""
echo "Check results:"
ls -lh output/integrated_simulation_results.json 2>/dev/null && echo "✅ Results file created" || echo "❌ No results file"
