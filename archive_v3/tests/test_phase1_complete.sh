#!/bin/bash

echo "🚀 VANET Phase 1 - Complete System Test"
echo "======================================"

# Test 1: Component Tests
echo ""
echo "📋 TEST 1: Testing Individual Components"
echo "----------------------------------------"

echo "Testing Sensor Network..."
cd /Users/apple/Desktop/vanet_final_one_to_go/sumo_simulation/sensors
python3 sensor_network.py > /tmp/sensor_test.log 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Sensor Network: PASS"
else
    echo "❌ Sensor Network: FAIL"
fi

echo "Testing Network Metrics..."
cd /Users/apple/Desktop/vanet_final_one_to_go/backend/utils
python3 network_metrics.py > /tmp/metrics_test.log 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Network Metrics: PASS"
else
    echo "❌ Network Metrics: FAIL"
fi

# Test 2: Manual Instructions
echo ""
echo "📋 TEST 2: Manual Testing Required"
echo "---------------------------------"
echo "Now run these commands in separate terminals:"
echo ""
echo "Terminal 1 - SUMO Simulation:"
echo "cd /Users/apple/Desktop/vanet_final_one_to_go/sumo_simulation"
echo "sumo-gui -c working_simulation.sumocfg --remote-port 8813"
echo "Expected: See road network + moving vehicles"
echo ""
echo "Terminal 2 - Backend API:"
echo "cd /Users/apple/Desktop/vanet_final_one_to_go/backend"
echo "python3 app.py"
echo "Expected: Server starts on port 5000"
echo ""
echo "Terminal 3 - API Tests:"
echo "curl http://localhost:5000/api/status"
echo "curl http://localhost:5000/api/network/metrics"
echo "Expected: JSON responses"
echo ""
echo "🎯 Phase 1 Success = All components working without errors!"