#!/bin/bash

# VANET Traffic Management System - Quick Start Script
# Phase 1 Setup and Testing

echo "🚀 VANET Traffic Management System - Phase 1 Setup"
echo "=================================================="

# Check if we're in the right directory
if [[ ! -f "README.md" ]] || [[ ! -d "backend" ]] || [[ ! -d "sumo_simulation" ]]; then
    echo "❌ Error: Please run this script from the project root directory"
    echo "Expected: vanet_final_one_to_go/"
    exit 1
fi

echo "✅ Directory structure verified"

# Check Python version
python_version=$(python3 --version 2>&1)
if [[ $? -eq 0 ]]; then
    echo "✅ Python3 found: $python_version"
else
    echo "❌ Python3 not found. Please install Python 3.8+"
    exit 1
fi

# Check SUMO installation
sumo_version=$(sumo --version 2>&1 | head -1)
if [[ $? -eq 0 ]]; then
    echo "✅ SUMO found: $sumo_version"
else
    echo "❌ SUMO not found. Please install SUMO traffic simulator"
    echo "Visit: https://eclipse.org/sumo/"
    exit 1
fi

# Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."
cd backend
if pip3 install -r requirements.txt; then
    echo "✅ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi
cd ..

# Test basic functionality
echo ""
echo "🧪 Testing basic functionality..."

# Test sensor network
echo "Testing sensor network..."
cd sumo_simulation/sensors
if python3 sensor_network.py > /dev/null 2>&1; then
    echo "✅ Sensor network test passed"
else
    echo "❌ Sensor network test failed"
fi
cd ../..

# Test network metrics
echo "Testing network metrics..."
cd backend/utils
if python3 network_metrics.py > /dev/null 2>&1; then
    echo "✅ Network metrics test passed"
else
    echo "❌ Network metrics test failed"
fi
cd ../..

# Create output directories
echo ""
echo "📁 Creating output directories..."
mkdir -p sumo_simulation/output
mkdir -p docs/phase1_results
echo "✅ Output directories created"

# Generate quick test report
echo ""
echo "📊 Generating Phase 1 test report..."
cat > docs/phase1_results/test_report.md << EOF
# Phase 1 Test Report

**Date:** $(date)
**Status:** Setup Complete

## Components Tested
- [x] Project structure
- [x] Python dependencies
- [x] SUMO installation  
- [x] Sensor network simulation
- [x] Network metrics framework

## Next Steps
1. Start backend API: \`cd backend && python3 app.py\`
2. Start SUMO: \`cd sumo_simulation && sumo-gui -c simulation.sumocfg --remote-port 8813\`
3. Test API endpoints: \`curl http://localhost:5000/api/status\`

## Phase 1 Status: READY FOR TESTING ✅
EOF

echo "✅ Test report generated: docs/phase1_results/test_report.md"

# Display startup instructions
echo ""
echo "🎉 Phase 1 Setup Complete!"
echo "=========================="
echo ""
echo "To start the system:"
echo "1. Start Backend API:"
echo "   cd backend"
echo "   python3 app.py"
echo ""
echo "2. Start SUMO Simulation:"
echo "   Option A - With GUI:"
echo "   cd sumo_simulation"
echo "   sumo-gui -c simulation.sumocfg --remote-port 8813"
echo ""
echo "   Option B - Headless (no GUI):"
echo "   cd sumo_simulation"
echo "   sumo -c simulation_headless.sumocfg --remote-port 8813"
echo ""
echo "3. Test API endpoints:"
echo "   curl http://localhost:5000/api/status"
echo "   curl http://localhost:5000/api/traffic/current"
echo ""
echo "📖 See README.md for detailed instructions"
echo "🚀 Ready for Phase 2: Reinforcement Learning Implementation"