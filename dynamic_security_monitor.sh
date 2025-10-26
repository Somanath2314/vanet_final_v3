#!/bin/bash

# VANET Dynamic Security Monitor
# Shows real-time V2V security metrics and emergency vehicle communication

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
API_BASE="http://localhost:5000"
UPDATE_INTERVAL=3

echo "=========================================="
echo "🔒 VANET Dynamic Security Monitor"
echo "=========================================="
echo ""
echo -e "${BLUE}📡 Real-time V2V Security Monitoring${NC}"
echo ""
echo -e "${YELLOW}🎯 Monitoring:${NC}"
echo "   🔐 RSA Encryption/Decryption Metrics"
echo "   🚨 Emergency Vehicle V2V Communication"
echo "   📊 Real-time Performance Data"
echo "   🚗 Vehicle Authentication Status"
echo ""

# Function to check if backend is running
check_backend() {
    if curl -s --head "$API_BASE" | grep "200 OK" > /dev/null; then
        return 0
    else
        echo -e "${RED}❌ Backend server not running${NC}"
        echo "   Start with: cd backend && python3 app.py"
        return 1
    fi
}

# Function to show V2V security metrics
show_v2v_security_metrics() {
    echo -e "${CYAN}🔐 V2V Security Metrics (Real-time)${NC}"
    echo "----------------------------------------"

    if ! curl -s "$API_BASE/api/v2v/security" > /dev/null 2>&1; then
        echo -e "${YELLOW}⏳ Waiting for V2V system to initialize...${NC}"
        return
    fi

    # Get security metrics
    response=$(curl -s "$API_BASE/api/v2v/security")

    if echo "$response" | grep -q "error"; then
        echo -e "${YELLOW}⏳ V2V system initializing...${NC}"
        return
    fi

    # Extract and display key metrics
    encryption_overhead=$(echo "$response" | grep -o '"encryption_overhead":[0-9.]*' | grep -o '[0-9.]*')
    decryption_overhead=$(echo "$response" | grep -o '"decryption_overhead":[0-9.]*' | grep -o '[0-9.]*')
    auth_success=$(echo "$response" | grep -o '"successful_authentications":[0-9]*' | grep -o '[0-9]*')
    auth_failed=$(echo "$response" | grep -o '"failed_authentications":[0-9]*' | grep -o '[0-9]*')
    total_messages=$(echo "$response" | grep -o '"total_messages_processed":[0-9]*' | grep -o '[0-9]*')

    echo -e "${GREEN}✅ RSA Encryption Metrics:${NC}"
    echo "   Encryption overhead: ${encryption_overhead:-0}ms"
    echo "   Decryption overhead: ${decryption_overhead:-0}ms"
    echo ""
    echo -e "${GREEN}🔑 Authentication Status:${NC}"
    echo "   Successful authentications: ${auth_success:-0}"
    echo "   Failed authentications: ${auth_failed:-0}"
    echo "   Total messages processed: ${total_messages:-0}"
    echo ""
}

# Function to show emergency vehicle communication
show_emergency_communication() {
    echo -e "${CYAN}🚨 Emergency Vehicle V2V Communication${NC}"
    echo "----------------------------------------"

    # Check for emergency vehicles
    emergency_response=$(curl -s "$API_BASE/api/emergency" 2>/dev/null)

    if echo "$emergency_response" | grep -q "error"; then
        echo -e "${YELLOW}⏳ Scanning for emergency vehicles...${NC}"
        return
    fi

    emergency_count=$(echo "$emergency_response" | grep -o '"emergency_count":[0-9]*' | grep -o '[0-9]*')

    if [ "${emergency_count:-0}" -gt 0 ]; then
        echo -e "${RED}🚨 EMERGENCY VEHICLES DETECTED: $emergency_count${NC}"

        # Show emergency vehicle details
        echo "$emergency_response" | grep -A 10 '"vehicles"' | head -20

        echo ""
        echo -e "${YELLOW}📡 Triggering V2V Emergency Broadcast...${NC}"

        # Simulate emergency V2V message
        emergency_broadcast=$(curl -s -X POST "$API_BASE/api/v2v/send" \
            -H "Content-Type: application/json" \
            -d '{
                "sender_id": "emergency_vehicle_001",
                "receiver_id": "BROADCAST",
                "message_type": "safety",
                "payload": {
                    "location": {"x": 500, "y": 500},
                    "speed": 80,
                    "emergency": true
                }
            }' 2>/dev/null)

        if echo "$emergency_broadcast" | grep -q "message_id"; then
            message_id=$(echo "$emergency_broadcast" | grep -o '"message_id":"[^"]*"' | grep -o '"[^"]*"$')
            echo -e "${GREEN}✅ Emergency broadcast sent: ${message_id}${NC}"
        fi
    else
        echo -e "${GREEN}✅ No emergency vehicles detected${NC}"
    fi
    echo ""
}

# Function to show real-time traffic data
show_traffic_data() {
    echo -e "${CYAN}🚗 Real-time Traffic Data${NC}"
    echo "----------------------------------------"

    traffic_response=$(curl -s "$API_BASE/api/traffic/current" 2>/dev/null)

    if echo "$traffic_response" | grep -q "error"; then
        echo -e "${YELLOW}⏳ Waiting for traffic simulation...${NC}"
        return
    fi

    total_vehicles=$(echo "$traffic_response" | grep -o '"total_vehicles":[0-9]*' | grep -o '[0-9]*')
    emergency_vehicles=$(echo "$traffic_response" | grep -o '"emergency_vehicles":[0-9]*' | grep -o '[0-9]*')
    simulation_step=$(echo "$traffic_response" | grep -o '"simulation_step":[0-9]*' | grep -o '[0-9]*')

    echo -e "${GREEN}📊 Traffic Status:${NC}"
    echo "   Total vehicles: ${total_vehicles:-0}"
    echo "   Emergency vehicles: ${emergency_vehicles:-0}"
    echo "   Simulation step: ${simulation_step:-0}"
    echo ""
}

# Function to demonstrate V2V emergency communication
demo_emergency_v2v() {
    echo -e "${CYAN}🚨 Emergency V2V Communication Demo${NC}"
    echo "----------------------------------------"

    # Register emergency vehicle
    echo -e "${YELLOW}📡 Registering emergency vehicle...${NC}"
    register_response=$(curl -s -X POST "$API_BASE/api/v2v/register" \
        -H "Content-Type: application/json" \
        -d '{"vehicle_id": "emergency_vehicle_001"}')

    if echo "$register_response" | grep -q "registered successfully"; then
        echo -e "${GREEN}✅ Emergency vehicle registered${NC}"
    fi

    # Register nearby vehicle
    register_nearby=$(curl -s -X POST "$API_BASE/api/v2v/register" \
        -H "Content-Type: application/json" \
        -d '{"vehicle_id": "nearby_vehicle_001"}')

    echo ""

    # Simulate emergency scenario
    echo -e "${YELLOW}🚨 Simulating Emergency Scenario...${NC}"

    # Send emergency broadcast
    emergency_msg=$(curl -s -X POST "$API_BASE/api/v2v/send" \
        -H "Content-Type: application/json" \
        -d '{
            "sender_id": "emergency_vehicle_001",
            "receiver_id": "BROADCAST",
            "message_type": "safety",
            "payload": {
                "location": {"x": 500, "y": 500},
                "speed": 80,
                "emergency": true
            }
        }')

    if echo "$emergency_msg" | grep -q "message_id"; then
        echo -e "${GREEN}✅ Emergency message broadcast sent${NC}"
        message_id=$(echo "$emergency_msg" | grep -o '"message_id":"[^"]*"' | cut -d'"' -f4)
        echo "   Message ID: $message_id"
    fi

    # Update emergency vehicle position
    update_position=$(curl -s -X POST "$API_BASE/api/v2v/update" \
        -H "Content-Type: application/json" \
        -d '{
            "vehicle_id": "emergency_vehicle_001",
            "x": 550,
            "y": 500,
            "speed": 75,
            "lane": "E1_0"
        }')

    if echo "$update_position" | grep -q "position updated"; then
        echo -e "${GREEN}✅ Emergency vehicle position updated${NC}"
    fi

    echo ""
}

# Function to show system status
show_system_status() {
    echo -e "${CYAN}🖥️  System Status${NC}"
    echo "----------------------------------------"

    status_response=$(curl -s "$API_BASE/api/status" 2>/dev/null)

    if echo "$status_response" | grep -q "simulation_running"; then
        simulation_running=$(echo "$status_response" | grep -o '"simulation_running":[a-z]*' | grep -o '[a-z]*')
        sumo_connected=$(echo "$status_response" | grep -o '"sumo_connected":[a-z]*' | grep -o '[a-z]*')

        echo -e "${GREEN}✅ Simulation Status:${NC}"
        echo "   Simulation running: $simulation_running"
        echo "   SUMO connected: $sumo_connected"
    else
        echo -e "${YELLOW}⏳ System initializing...${NC}"
    fi

    echo ""
}

# Main monitoring loop
main() {
    clear
    echo "=========================================="
    echo "🔒 VANET Dynamic Security Monitor"
    echo "=========================================="
    echo ""
    echo -e "${YELLOW}Press Ctrl+C to stop monitoring${NC}"
    echo ""

    # Check if backend is running
    if ! check_backend; then
        echo ""
        echo -e "${YELLOW}💡 To start the complete system:${NC}"
        echo "   1. Terminal 1: cd backend && python3 app.py"
        echo "   2. Terminal 2: ./run_sumo_rl.sh"
        echo "   3. Terminal 3: ./monitor_security_logs.sh"
        echo ""
        exit 1
    fi

    # Demo emergency V2V communication first
    echo -e "${BLUE}🚨 Initializing Emergency V2V Demo...${NC}"
    demo_emergency_v2v
    echo ""

    # Main monitoring loop
    while true; do
        echo "=========================================="
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Real-time Update"
        echo "=========================================="

        show_system_status
        show_v2v_security_metrics
        show_emergency_communication
        show_traffic_data

        echo "=========================================="
        echo -e "${YELLOW}⏳ Next update in $UPDATE_INTERVAL seconds...${NC}"
        echo ""

        sleep $UPDATE_INTERVAL
        clear
    done
}

# Trap to handle Ctrl+C
trap 'echo -e "\n${YELLOW}🛑 Monitoring stopped${NC}"; exit 0' SIGINT SIGTERM

# Run main function
main
