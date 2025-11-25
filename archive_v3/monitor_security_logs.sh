#!/bin/bash

# VANET Security Log Monitor
# Monitors V2V security logs and system status in real-time

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "🔒 VANET Security Log Monitor"
echo "=========================================="
echo ""
echo -e "${BLUE}📡 Monitoring V2V Security Logs${NC}"
echo ""
echo -e "${YELLOW}🎯 What to Monitor:${NC}"
echo "   🔐 V2V Security Events:"
echo "      • Vehicle registration/authentication"
echo "      • Message encryption/decryption"
echo "      • Digital signature verification"
echo "      • Emergency message handling"
echo ""
echo -e "${YELLOW}🚨 Emergency Detection:${NC}"
echo "   • Emergency vehicle detection"
echo "   • Central pole color changes"
echo "   • Priority routing activation"
echo ""
echo -e "${YELLOW}📊 Performance Metrics:${NC}"
echo "   • Encryption/decryption overhead"
echo "   • Authentication success/failure rates"
echo "   • Message throughput and latency"
echo ""

# Function to monitor API endpoints
monitor_api() {
    echo -e "${BLUE}🌐 API Endpoints for Monitoring:${NC}"
    echo "   http://localhost:5000/api/v2v/security    - Security metrics"
    echo "   http://localhost:5000/api/v2v/status      - V2V status"
    echo "   http://localhost:5000/api/traffic/current - Traffic data"
    echo "   http://localhost:5000/api/emergency       - Emergency vehicles"
    echo ""
}

# Function to show real-time log examples
show_log_examples() {
    echo -e "${BLUE}📋 Expected Security Log Examples:${NC}"
    echo ""
    echo -e "${GREEN}✅ Vehicle Registration:${NC}"
    echo "   Key generation for vehicle_001 took 45.23ms"
    echo "   ✅ Vehicle 1 registered: 5faa437ccb2b5f09..."
    echo ""
    echo -e "${GREEN}✅ Secure Message Transmission:${NC}"
    echo "   Sent secure traffic_info message from vehicle_001 to vehicle_002"
    echo "   (took 22.14ms total, 0.09ms encryption)"
    echo ""
    echo -e "${GREEN}✅ Emergency Detection:${NC}"
    echo "   🚨 EMERGENCY VEHICLE DETECTED at J2 - switching to red_lanes"
    echo "   Attempting to update central pole color..."
    echo "   Debug: state= red"
    echo ""
    echo -e "${GREEN}✅ Signature Verification:${NC}"
    echo "   Verified message msg_1760597688130_9810 in 0.18ms"
    echo ""
    echo -e "${YELLOW}⚠️  Authentication Failures:${NC}"
    echo "   Authentication failed for sender vehicle_unknown"
    echo "   Invalid signature for message msg_1760597688130_9810"
    echo ""
}

# Function to show monitoring commands
show_monitoring_commands() {
    echo -e "${BLUE}🔍 Monitoring Commands:${NC}"
    echo ""
    echo -e "${YELLOW}📊 Real-time API Monitoring:${NC}"
    echo "   # Monitor security metrics every 2 seconds"
    echo "   watch -n 2 'curl -s http://localhost:5000/api/v2v/security | jq .'"
    echo ""
    echo -e "${YELLOW}🚨 Emergency Detection:${NC}"
    echo "   # Monitor emergency vehicles"
    echo "   curl http://localhost:5000/api/emergency"
    echo ""
    echo -e "${YELLOW}📈 Traffic Metrics:${NC}"
    echo "   # Monitor current traffic data"
    echo "   curl http://localhost:5000/api/traffic/current"
    echo ""
}

# Function to show troubleshooting
show_troubleshooting() {
    echo -e "${BLUE}🔧 Troubleshooting:${NC}"
    echo ""
    echo -e "${YELLOW}❌ If Backend Not Running:${NC}"
    echo "   cd /home/mahesh/Desktop/capstone/vanet_final_v3"
    echo "   source venv/bin/activate"
    echo "   cd backend && python3 app.py"
    echo ""
    echo -e "${YELLOW}❌ If SUMO Issues:${NC}"
    echo "   # Kill existing SUMO processes"
    echo "   killall sumo-gui"
    echo "   killall sumo"
    echo ""
    echo -e "${YELLOW}❌ If V2V Not Working:${NC}"
    echo "   # Check if cryptography is installed"
    echo "   python3 -c 'import cryptography; print(\"✅ Cryptography available\")'"
    echo ""
    echo -e "${YELLOW}❌ If No Emergency Detection:${NC}"
    echo "   # Check sensor network"
    echo "   python3 -c 'from sumo_simulation.sensors.sensor_network import SensorNetwork; sn = SensorNetwork(); print(\"✅ Sensor network working\")'"
    echo ""
}

# Main function
main() {
    echo -e "${GREEN}🚀 VANET Security Monitoring Guide${NC}"
    echo ""

    monitor_api
    show_log_examples
    show_monitoring_commands
    show_troubleshooting

    echo -e "${GREEN}💡 Quick Start:${NC}"
    echo "   1. Run: ./launch_complete_system.sh"
    echo "   2. Open: http://localhost:5000"
    echo "   3. Monitor: Terminal logs for security events"
    echo "   4. Watch: SUMO-GUI for visual emergency detection"
    echo ""
}

# Run main function
main
