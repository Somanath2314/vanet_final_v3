#!/bin/bash
# Quick script to run SUMO simulation with adaptive traffic control

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "VANET SUMO Simulation Launcher"
echo "=========================================="
echo ""

# Check if venv is activated
# if [[ "$VIRTUAL_ENV" == "" ]]; then
#     echo -e "${YELLOW}Activating virtual environment...${NC}"
#     source venv/bin/activate
# fi

# Kill any existing SUMO processes
echo -e "${YELLOW}Cleaning up existing SUMO processes...${NC}"
killall sumo-gui 2>/dev/null || true
killall sumo 2>/dev/null || true
sleep 1

# Check SUMO installation
if ! command -v sumo-gui &> /dev/null; then
    echo -e "${RED}Error: SUMO not found${NC}"
    echo "Please install SUMO:"
    echo "  sudo apt-get install sumo sumo-tools sumo-doc"
    exit 1
fi

echo -e "${GREEN}✓ SUMO found: $(sumo --version 2>&1 | head -1)${NC}"
echo ""

# Navigate to sumo_simulation directory
cd sumo_simulation

# Create output directory if it doesn't exist
mkdir -p output

# Check for config file
if [ ! -f "simulation.sumocfg" ]; then
    echo -e "${RED}Error: simulation.sumocfg not found${NC}"
    echo "Available config files:"
    ls -1 *.sumocfg 2>/dev/null || echo "  None found"
    exit 1
fi

echo -e "${GREEN}✓ Configuration file found${NC}"
echo ""

# Run simulation
echo -e "${GREEN}Starting simulation...${NC}"
echo "SUMO-GUI will open in a moment..."
echo ""
echo "Controls:"
echo "  Space    - Play/Pause"
echo "  +/-      - Speed up/slow down"
echo "  Ctrl+C   - Stop simulation"
echo ""
echo "=========================================="
echo ""

python3 run_simulation.py

echo ""
echo -e "${GREEN}Simulation completed${NC}"
