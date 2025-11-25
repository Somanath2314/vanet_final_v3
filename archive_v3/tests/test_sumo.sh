#!/bin/bash

# Simple SUMO test script
echo "🚗 Testing SUMO simulation..."

cd /Users/apple/Desktop/vanet_final_one_to_go/sumo_simulation

echo "Step 1: Testing network file..."
if [ -f "maps/simple_network.net.xml" ]; then
    echo "✅ Network file exists"
else
    echo "❌ Network file missing"
    exit 1
fi

echo "Step 2: Testing routes file..."
if [ -f "maps/routes.rou.xml" ]; then
    echo "✅ Routes file exists"
else
    echo "❌ Routes file missing"
    exit 1
fi

echo "Step 3: Testing configuration..."
if [ -f "simulation.sumocfg" ]; then
    echo "✅ Configuration file exists"
else
    echo "❌ Configuration file missing"
    exit 1
fi

echo ""
echo "🎯 Manual SUMO GUI steps:"
echo "1. In the SUMO GUI window that's open:"
echo "2. Go to File → Open Simulation..."
echo "3. Select 'simulation.sumocfg'"
echo "4. Click the Play button ▶️"
echo "5. You should see vehicles moving!"
echo ""
echo "🔧 Alternative: Close SUMO and run:"
echo "sumo-gui -c simulation.sumocfg"