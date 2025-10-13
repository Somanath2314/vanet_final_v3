#!/bin/bash

echo "🚀 VANET System - New Developer Quick Start"
echo "=========================================="
echo ""

# Check prerequisites
echo "📋 Checking Prerequisites..."
python3 --version >/dev/null 2>&1 || { echo "❌ Python3 not found. Please install Python 3.8+"; exit 1; }
sumo --version >/dev/null 2>&1 || { echo "❌ SUMO not found. Please install SUMO traffic simulator"; exit 1; }
echo "✅ Prerequisites: OK"
echo ""

# Install dependencies
echo "📦 Installing Dependencies..."
cd backend
pip3 install -r requirements.txt >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Dependencies: Installed"
else
    echo "⚠️ Dependencies: Some packages may have failed"
fi
cd ..
echo ""

# Test components
echo "🧪 Testing Components..."

echo "Testing Sensor Network..."
cd sumo_simulation/sensors
python3 sensor_network.py >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Sensor Network: Working"
else
    echo "❌ Sensor Network: Error"
fi
cd ../..

echo "Testing SUMO Simulation..."
cd sumo_simulation
sumo -c test_simple.sumocfg >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ SUMO Simulation: Working"
else
    echo "❌ SUMO Simulation: Error"
fi
cd ..

echo "Testing Network Metrics..."
cd backend/utils
python3 -c "from network_metrics import NetworkMetricsCollector; c = NetworkMetricsCollector(); print('OK')" >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Network Metrics: Working"
else
    echo "❌ Network Metrics: Error"
fi
cd ../..

echo ""
echo "🎯 Phase 1 System Test Complete!"
echo ""
echo "🚀 TO START THE SYSTEM:"
echo "1. Terminal 1: cd backend && python3 app.py"
echo "2. Terminal 2: cd sumo_simulation && sumo-gui -c test_simple.sumocfg"  
echo "3. Terminal 3: curl http://localhost:5000/api/status"
echo ""
echo "📖 See QUICK_START.md for detailed instructions"
echo "🎯 Ready for Phase 2 Development!"