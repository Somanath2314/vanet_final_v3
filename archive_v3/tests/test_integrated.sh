#!/bin/bash
# Quick test of integrated simulation (10 steps only)

echo "Testing integrated SUMO + NS3 simulation..."
echo ""

cd /home/shreyasdk/capstone/vanet_final_v3

# Activate venv
source venv/bin/activate

# Run for just 10 steps to test
cd sumo_simulation
python3 run_integrated_simulation.py --mode rule --steps 10 --output ./output

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ Test passed! System is working."
    echo ""
    echo "Now run the full simulation with:"
    echo "  cd /home/shreyasdk/capstone/vanet_final_v3"
    echo "  ./run_integrated_sumo_ns3.sh --gui"
else
    echo ""
    echo "❌ Test failed with exit code $EXIT_CODE"
fi

exit $EXIT_CODE
