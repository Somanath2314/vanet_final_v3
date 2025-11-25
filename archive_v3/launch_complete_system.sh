#!/bin/bash

# VANET Complete System Launcher
# Runs backend server + SUMO RL simulation with security logging

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "🚀 VANET Complete System Launcher"
echo "=========================================="
echo ""
echo "🎯 Features:"
echo "   ✅ Backend API Server (Flask)"
echo "   ✅ SUMO-GUI RL Simulation"
echo "   ✅ V2V Security Logging"
echo "   ✅ Real-time Metrics"
echo "   ✅ Emergency Detection"
echo ""

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

echo -e "${BLUE}📋 System Status Check${NC}"
echo "----------------------------------------"

# Check if SUMO is available
if ! command -v sumo-gui &> /dev/null; then
    echo -e "${RED}❌ SUMO-GUI not found${NC}"
    echo "   Install with: sudo apt-get install sumo sumo-tools sumo-doc"
    exit 1
else
    echo -e "${GREEN}✅ SUMO-GUI available${NC}"
fi

# Check if config file exists
if [ ! -f "sumo_simulation/simulation.sumocfg" ]; then
    echo -e "${RED}❌ SUMO config file not found${NC}"
    exit 1
else
    echo -e "${GREEN}✅ SUMO config file found${NC}"
fi

# Check backend requirements
if [ -f "backend/requirements.txt" ]; then
    echo -e "${GREEN}✅ Backend requirements found${NC}"
else
    echo -e "${RED}❌ Backend requirements not found${NC}"
fi

echo ""
echo -e "${YELLOW}🚀 Starting VANET System${NC}"
echo "----------------------------------------"

# Function to start backend server
start_backend() {
    echo -e "${BLUE}🌐 Starting Backend API Server...${NC}"
    echo "   Server will run on: http://localhost:5000"
    echo "   API Documentation: http://localhost:5000"
    echo ""

    # Start backend server in background
    cd backend
    python3 app.py &
    BACKEND_PID=$!
    cd ..

    echo -e "${GREEN}✅ Backend server started (PID: $BACKEND_PID)${NC}"
    echo ""
    echo -e "${YELLOW}📡 Available API Endpoints:${NC}"
    echo "   GET  /                    - API information"
    echo "   GET  /api/status          - System status"
    echo "   GET  /api/traffic/current - Current traffic data"
    echo "   GET  /api/v2v/status      - V2V communication status"
    echo "   GET  /api/v2v/security    - V2V security metrics"
    echo "   POST /api/v2v/register    - Register V2V vehicle"
    echo "   POST /api/v2v/send        - Send V2V message"
    echo ""

    echo -e "${YELLOW}🔒 Security Monitoring:${NC}"
    echo "   Monitor V2V security at: http://localhost:5000/api/v2v/security"
    echo "   Monitor traffic data at: http://localhost:5000/api/traffic/current"
    echo ""

    return $BACKEND_PID
}

# Function to start SUMO RL simulation
start_sumo_rl() {
    echo -e "${BLUE}🚗 Starting SUMO RL Simulation...${NC}"
    echo "   SUMO-GUI will open with RL control"
    echo "   Emergency detection and V2V communication active"
    echo ""

    echo -e "${YELLOW}🎮 Controls:${NC}"
    echo "   Space    - Play/Pause"
    echo "   +/-      - Speed up/slow down"
    echo "   Ctrl+C   - Stop simulation"
    echo ""

    echo -e "${YELLOW}🔍 Security Logs:${NC}"
    echo "   V2V security logs will appear in terminal"
    echo "   Emergency vehicle detection logs shown"
    echo "   Central pole visualization updates"
    echo ""

    # Wait a moment for backend to start
    sleep 3

    # Start SUMO RL simulation
    ./run_sumo_rl.sh
}

# Function to monitor logs
monitor_logs() {
    echo -e "${BLUE}📊 Real-time Monitoring${NC}"
    echo "----------------------------------------"
    echo "Backend API: http://localhost:5000"
    echo "Security Metrics: http://localhost:5000/api/v2v/security"
    echo "Traffic Data: http://localhost:5000/api/traffic/current"
    echo ""
    echo -e "${YELLOW}💡 Tips:${NC}"
    echo "   • Open browser to http://localhost:5000 for API docs"
    echo "   • Watch terminal for V2V security logs"
    echo "   • Monitor emergency vehicle detection"
    echo "   • Check central pole color changes"
    echo ""
}

# Main execution
main() {
    echo -e "${GREEN}🎯 Launching Complete VANET System${NC}"
    echo ""

    # Start backend server in background
    start_backend
    BACKEND_PID=$!

    # Start SUMO RL simulation
    start_sumo_rl

    # Show monitoring info
    monitor_logs

    # Wait for backend to finish
    wait $BACKEND_PID
    echo -e "${GREEN}✅ VANET system shutdown complete${NC}"
}

# Trap to handle Ctrl+C
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Shutting down VANET system...${NC}"

    # Kill backend server
    if [ ! -z "$BACKEND_PID" ] && kill -0 $BACKEND_PID 2>/dev/null; then
        echo "Stopping backend server..."
        kill $BACKEND_PID 2>/dev/null || true
    fi

    # Kill any remaining SUMO processes
    echo "Stopping SUMO processes..."
    killall sumo-gui 2>/dev/null || true
    killall sumo 2>/dev/null || true

    echo -e "${GREEN}✅ Cleanup complete${NC}"
    exit 0
}

# Set trap for cleanup
trap cleanup SIGINT SIGTERM

# Run main function
main
