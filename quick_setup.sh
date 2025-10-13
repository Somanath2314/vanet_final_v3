#!/bin/bash

echo "🚀 FAST SETUP - New Developer (30 seconds)"
echo "========================================="

# Quick checks only
echo "✅ Python3: $(python3 --version 2>/dev/null || echo 'Not found')"
echo "✅ SUMO: $(sumo --version 2>/dev/null | head -1 || echo 'Not found')"

echo ""
echo "🎯 3 COMMANDS TO START EVERYTHING:"
echo ""
echo "Terminal 1 - Backend API:"
echo "cd backend && python3 app.py"
echo ""
echo "Terminal 2 - SUMO Simulation:" 
echo "cd sumo_simulation && sumo-gui -c test_simple.sumocfg"
echo ""
echo "Terminal 3 - Test API:"
echo "curl http://localhost:5000/api/status"
echo ""
echo "🚀 That's it! Phase 1 is ready."
echo "📖 See QUICK_START.md for details."