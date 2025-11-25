#!/bin/bash
# Quick test script for hybrid RL DQN system

echo "=========================================="
echo "Testing Hybrid RL DQN System"
echo "=========================================="
echo ""

cd /home/shreyasdk/capstone/vanet_final_v3

echo "Running hybrid control test..."
echo ""

python3 test_rl_hybrid.py

exitcode=$?

echo ""
if [ $exitcode -eq 0 ]; then
    echo "=========================================="
    echo "✅ All RL DQN tests PASSED!"
    echo "=========================================="
    echo ""
    echo "System Status:"
    echo "  ✓ Density-based control: Working"
    echo "  ✓ RL emergency mode: Working"
    echo "  ✓ Mode switching: Working"
    echo "  ✓ Emergency detection: Working"
    echo "  ✓ Greenwave creation: Working"
    echo ""
else
    echo "=========================================="
    echo "❌ Tests FAILED (exit code: $exitcode)"
    echo "=========================================="
    echo ""
    echo "Check the output above for errors"
fi

exit $exitcode
