#!/bin/bash

# NS3 VANET System Runner
# Runs the complete VANET system with NS3 integration

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "🚀 NS3 VANET System Launcher"
echo "=========================================="
echo ""

# Configuration
NUM_VEHICLES=10
SIMULATION_TIME=60
WIFI_RANGE=300

echo -e "${BLUE}📋 Configuration${NC}"
echo "  Vehicles: $NUM_VEHICLES"
echo "  Simulation Time: ${SIMULATION_TIME}s"
echo "  WiFi Range: ${WIFI_RANGE}m"
echo ""

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

echo -e "${BLUE}🔧 Starting Backend API Server${NC}"
cd backend
python app.py &
BACKEND_PID=$!
cd ..

echo "Backend PID: $BACKEND_PID"
sleep 3

echo ""
echo -e "${BLUE}🚗 Running NS3 VANET Simulation${NC}"
python3 << EOF
from backend.ns3_integration import NS3VANETIntegration, NS3SimulationConfig

# Create configuration
config = NS3SimulationConfig(
    num_vehicles=$NUM_VEHICLES,
    simulation_time=$SIMULATION_TIME,
    wifi_range=$WIFI_RANGE,
    enable_pcap=False,
    enable_animation=False
)

# Run simulation
vanet = NS3VANETIntegration()
try:
    results = vanet.run_complete_vanet_simulation(config)
    print("\n" + "="*50)
    print("📊 SIMULATION RESULTS")
    print("="*50)
    print(f"WiFi Results: {results.get('wifi', 'N/A')}")
    print(f"WiMAX Results: {results.get('wimax', 'N/A')}")
    print(f"Combined Metrics: {results.get('combined', 'N/A')}")
except Exception as e:
    print(f"❌ Simulation failed: {e}")
EOF

echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the system${NC}"

# Cleanup function
cleanup() {
    echo ""
    echo -e "${RED}🛑 Shutting down...${NC}"
    kill $BACKEND_PID 2>/dev/null
    echo "✅ System stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Keep running
wait
