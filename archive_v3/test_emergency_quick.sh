#!/bin/bash
# Quick Test for Emergency Vehicle Greenwave System

echo "=================================================="
echo "Emergency Vehicle Greenwave System - Quick Test"
echo "=================================================="
echo ""

# Navigate to sumo_simulation directory
cd "$(dirname "$0")"

echo "Step 1: Testing emergency coordinator..."
python3 test_emergency_system.py

echo ""
echo "Step 2: You can now run the full RL simulation:"
echo "  python3 run_rl_simulation.py"
echo ""
echo "Monitor for these messages:"
echo "  🚨 Emergency vehicle detected"
echo "  🟢 Greenwave created"
echo "  🟢 Greenwave: J2 set to phase X"
echo ""
echo "Key improvements:"
echo "  ✓ RSU-based ambulance detection (300m range)"
echo "  ✓ Multi-junction greenwave coordination"
echo "  ✓ Handles short-distance vehicles"
echo "  ✓ Huge rewards for emergency vehicle passage"
echo "  ✓ No crashes when vehicles complete routes"
echo ""
