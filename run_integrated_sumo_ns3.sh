#!/bin/bash

# Integrated SUMO + NS3 VANET Simulation Runner
# Combines SUMO traffic simulation with NS3-based network simulation

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "🚗 Integrated SUMO + NS3 + RL VANET System"
echo "=========================================="
echo ""
echo "🎯 Features:"
echo "   ✅ SUMO Traffic Simulation with GUI"
echo "   ✅ NS3 Network Simulation (WiFi 802.11p + WiMAX)"
echo "   ✅ V2V Communication (802.11p)"
echo "   ✅ V2I Communication (WiMAX for emergency)"
echo "   ✅ RL Traffic Control (DQN with proximity-based switching)"
echo "   ✅ Edge Computing RSUs (Smart processing)"
echo "   ✅ Security (RSA encryption + CA authentication)"
echo "   ✅ Real-time visualization and metrics"
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
EDGE_FLAG=""
MODEL=""
PROXIMITY="250"

while [[ $# -gt 0 ]]; do
    case $1 in
        --rl)
            MODE="rl"
            shift
            ;;
        --hybrid)
            MODE="hybrid"
            shift
            ;;
        --proximity)
            MODE="proximity"
            PROXIMITY="$2"
            shift 2
            ;;
        --model)
            MODEL="$2"
            shift 2
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
        --edge)
            EDGE_FLAG="--edge"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Control Modes:"
            echo "  --rl                Use pure RL-based traffic control"
            echo "  --hybrid            Use hybrid global switching (RL during emergencies)"
            echo "  --proximity DIST    Use proximity-based RL (default: 250m)"
            echo "                      Only activates RL for junctions near emergencies"
            echo ""
            echo "Model Options:"
            echo "  --model PATH        Path to trained DQN model (.zip file)"
            echo "                      Required for --rl and --proximity modes"
            echo ""
            echo "Simulation Options:"
            echo "  --gui               Use SUMO-GUI for visualization"
            echo "  --steps N           Number of simulation steps (default: 1000)"
            echo "  --security          Enable RSA encryption (adds 30-60s startup)"
            echo "  --edge              Enable edge computing RSUs (smart processing)"
            echo ""
            echo "Examples:"
            echo "  # Rule-based with GUI"
            echo "  $0 --gui --steps 1000"
            echo ""
            echo "  # Proximity-based RL with all features"
            echo "  $0 --proximity 250 --model rl_module/trained_models/.../dqn_traffic_final.zip --gui --security --edge --steps 1000"
            echo ""
            echo "  # Hybrid mode with GUI"
            echo "  $0 --hybrid --gui --edge --steps 1000"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}📋 Configuration${NC}"
echo "  Mode: $MODE"
if [ "$MODE" = "proximity" ]; then
    echo "  Proximity Threshold: ${PROXIMITY}m"
fi
if [ -n "$MODEL" ]; then
    echo "  Model: $MODEL"
fi
echo "  Steps: $STEPS"
echo "  GUI: $([ -n "$GUI_FLAG" ] && echo 'Yes' || echo 'No')"
echo "  Security: $([ -n "$SECURITY_FLAG" ] && echo 'Enabled (RSA)' || echo 'Disabled')"
echo "  Edge Computing: $([ -n "$EDGE_FLAG" ] && echo 'Enabled' || echo 'Disabled')"
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
echo -e "${GREEN}🚀 Starting complete integrated SUMO + NS3 + RL simulation...${NC}"
echo ""

# Build command with all options
CMD="python3 run_complete_integrated.py --mode $MODE --steps $STEPS $GUI_FLAG $SECURITY_FLAG $EDGE_FLAG --output ./output"

# Add model if specified (adjust path to be relative from sumo_simulation dir)
if [ -n "$MODEL" ]; then
    # If model path doesn't start with ../, add it
    if [[ "$MODEL" != ../* ]]; then
        CMD="$CMD --model ../$MODEL"
    else
        CMD="$CMD --model $MODEL"
    fi
fi

# Add proximity if in proximity mode
if [ "$MODE" = "proximity" ]; then
    CMD="$CMD --proximity $PROXIMITY"
fi

echo "Running: $CMD"
echo ""

$CMD

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
