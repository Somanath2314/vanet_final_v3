#!/bin/bash

# VANET SYSTEM - QUICK COMMANDS
# Copy and paste these commands to run the system

echo "=========================================="
echo "🚗 VANET System - Quick Commands"
echo "=========================================="
echo ""

# Find the trained model path
MODEL_PATH=$(find rl_module/trained_models -name "dqn_traffic_final.zip" -type f 2>/dev/null | head -1)

if [ -z "$MODEL_PATH" ]; then
    echo "⚠️  No trained model found!"
    echo "Train a model first:"
    echo "  cd rl_module"
    echo "  python3 train_dqn_model.py --timesteps 10000"
    echo ""
    MODEL_PATH="rl_module/trained_models/YOUR_MODEL_HERE/dqn_traffic_final.zip"
fi

echo "📍 Detected Model: $MODEL_PATH"
echo ""
echo "=========================================="
echo "COPY & PASTE COMMANDS:"
echo "=========================================="
echo ""

echo "1️⃣  BASIC TEST (Rule-based, GUI, 500 steps)"
echo "./run_integrated_sumo_ns3.sh --gui --steps 500"
echo ""

echo "2️⃣  PROXIMITY-BASED RL (Recommended, GUI, 1000 steps)"
echo "./run_integrated_sumo_ns3.sh --proximity 250 --model $MODEL_PATH --gui --steps 1000"
echo ""

echo "3️⃣  COMPLETE SYSTEM (RL + Edge + Security + GUI)"
echo "./run_integrated_sumo_ns3.sh --proximity 250 --model $MODEL_PATH --gui --edge --security --steps 1000"
echo ""

echo "4️⃣  FAST DEMO (RL + Edge + GUI, No Security)"
echo "./run_integrated_sumo_ns3.sh --proximity 250 --model $MODEL_PATH --gui --edge --steps 1000"
echo ""

echo "5️⃣  TIGHTER PROXIMITY (150m threshold)"
echo "./run_integrated_sumo_ns3.sh --proximity 150 --model $MODEL_PATH --gui --steps 1000"
echo ""

echo "6️⃣  HYBRID MODE (Global switching)"
echo "./run_integrated_sumo_ns3.sh --hybrid --gui --edge --steps 1000"
echo ""

echo "=========================================="
echo "WHAT EACH FLAG DOES:"
echo "=========================================="
echo "--gui          Shows SUMO visualization (use Space to play/pause)"
echo "--proximity N  Activates RL only within N meters of emergencies"
echo "--model PATH   Uses trained DQN model for RL control"
echo "--edge         Enables smart RSU edge computing"
echo "--security     Enables RSA encryption (adds 30-60s startup)"
echo "--steps N      Runs N simulation steps (1 step ≈ 1 second)"
echo ""

echo "=========================================="
echo "RECOMMENDED COMMAND (Best Performance):"
echo "=========================================="
echo ""
echo "cd /home/shreyasdk/capstone/vanet_final_v3"
echo "./run_integrated_sumo_ns3.sh --proximity 250 --model $MODEL_PATH --gui --edge --steps 1000"
echo ""
echo "This command:"
echo "  ✅ Shows GUI visualization"
echo "  ✅ Uses proximity-based RL (efficient)"
echo "  ✅ Enables edge computing"
echo "  ✅ Runs 1000 steps (~16 minutes real-time)"
echo "  ✅ No security (faster startup)"
echo ""

echo "=========================================="
echo "VIEW RESULTS:"
echo "=========================================="
echo "cat sumo_simulation/output/integrated_simulation_results.json | python3 -m json.tool"
echo "cat sumo_simulation/output/v2i_metrics.csv"
echo ""
