#!/bin/bash

# VANET SUMO Simulation with RL Control and GUI
# This version uses RL control with SUMO-GUI visualization

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "VANET SUMO RL Simulation with GUI"
echo "=========================================="
echo ""

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Kill any existing SUMO processes
echo "Cleaning up existing SUMO processes..."
killall sumo-gui 2>/dev/null || true
killall sumo 2>/dev/null || true
sleep 1

# Check SUMO installation
if ! command -v sumo-gui &> /dev/null; then
    echo -e "${RED}Error: SUMO-GUI not found${NC}"
    echo "Please install SUMO with GUI:"
    echo "  sudo apt-get install sumo sumo-tools sumo-doc"
    exit 1
fi

echo -e "${GREEN}✓ SUMO-GUI found: $(sumo-gui --version 2>&1 | head -1)${NC}"
echo ""

# Navigate to sumo_simulation directory
cd sumo_simulation

# Create output directory if it doesn't exist
mkdir -p output

# Check for config file
if [ ! -f "simulation.sumocfg" ]; then
    echo -e "${RED}Error: simulation.sumocfg not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Configuration file found${NC}"
echo ""
echo -e "${GREEN}Starting RL simulation with GUI...${NC}"
echo "SUMO-GUI will open in a moment..."
echo ""
echo "Controls:"
echo "  Space    - Play/Pause"
echo "  +/-      - Speed up/slow down"
echo "  Ctrl+C   - Stop simulation"
echo ""
echo "=========================================="
echo ""

# Run RL simulation with GUI
python3 run_rl_simulation.py

echo ""
echo -e "${GREEN}✓ RL Simulation completed${NC}"
