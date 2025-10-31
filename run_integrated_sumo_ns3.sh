#!/bin/bash

# Integrated SUMO + NS3 VANET Simulation Runner
# Combines SUMO traffic simulation with NS3-based network simulation

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "🚗 Integrated SUMO + NS3 VANET System"
echo "=========================================="
echo ""
echo "🎯 Features:"
echo "   ✅ SUMO Traffic Simulation"
echo "   ✅ NS3 Network Simulation (WiFi + WiMAX)"
echo "   ✅ V2V Communication (802.11p)"
echo "   ✅ V2I Communication (WiMAX for emergency)"
echo "   ✅ Real vehicle positions from SUMO"
echo "   ✅ Emergency vehicle priority"
echo ""

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Kill any existing SUMO processes
echo -e "${YELLOW}Cleaning up existing SUMO processes...${NC}"
killall sumo-gui 2>/dev/null || true
killall sumo 2>/dev/null || true
sleep 1

# Check SUMO installation
if ! command -v sumo-gui &> /dev/null; then
    echo -e "${RED}❌ SUMO not found${NC}"
    echo "Please install SUMO:"
    echo "  sudo apt-get install sumo sumo-tools sumo-doc"
    exit 1
fi

echo -e "${GREEN}✅ SUMO found: $(sumo --version 2>&1 | head -1)${NC}"
echo ""

# Parse arguments
MODE="rule"
STEPS=1000
GUI_FLAG=""
SECURITY_FLAG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --rl)
            MODE="rl"
            shift
            ;;
        --gui)
            GUI_FLAG="--gui"
            shift
            ;;
        --steps)
            STEPS="$2"
            shift 2
            ;;
        --security)
            SECURITY_FLAG="--security"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--rl] [--gui] [--steps N] [--security]"
            echo ""
            echo "Options:"
            echo "  --rl         Use RL-based traffic control (default: rule-based)"
            echo "  --gui        Use SUMO-GUI for visualization"
            echo "  --steps N    Number of simulation steps (default: 1000)"
            echo "  --security   Enable RSA encryption (adds 30-60s startup time)"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}📋 Configuration${NC}"
echo "  Mode: $MODE"
echo "  Steps: $STEPS"
echo "  GUI: $([ -n "$GUI_FLAG" ] && echo 'Yes' || echo 'No')"
echo "  Security: $([ -n "$SECURITY_FLAG" ] && echo 'Enabled (RSA)' || echo 'Disabled')"
echo ""

# Navigate to sumo_simulation directory
cd sumo_simulation

# Create output directory
mkdir -p output

# Check for config file
if [ ! -f "simulation.sumocfg" ]; then
    echo -e "${RED}❌ Error: simulation.sumocfg not found${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Configuration file found${NC}"
echo ""

# Run integrated simulation
echo -e "${GREEN}🚀 Starting integrated SUMO + NS3 simulation...${NC}"
echo ""

python3 run_integrated_simulation.py --mode $MODE --steps $STEPS $GUI_FLAG $SECURITY_FLAG --output ./output

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}=========================================="
    echo "✅ Simulation Completed Successfully"
    echo "==========================================${NC}"
    echo ""
    echo "📊 Results saved in: sumo_simulation/output/"
    echo ""
    echo "Output files:"
    echo "  - integrated_simulation_results.json (Network metrics)"
    echo "  - tripinfo.xml (SUMO trip information)"
    echo "  - summary.xml (SUMO summary)"
    echo "  - v2i_packets.csv (V2I communication packets)"
    echo "  - v2i_metrics.csv (V2I metrics)"
    echo ""
    echo "View results:"
    echo "  cat sumo_simulation/output/integrated_simulation_results.json | python3 -m json.tool"
else
    echo ""
    echo -e "${RED}=========================================="
    echo "❌ Simulation Failed"
    echo "==========================================${NC}"
    exit $EXIT_CODE
fi
