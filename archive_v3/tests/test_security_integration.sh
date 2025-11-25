#!/bin/bash
# Quick test of secure VANET integration
# Tests the security features without running full simulation

cd /home/shreyasdk/capstone/vanet_final_v3

echo "=========================================="
echo "🔐 Testing Secure VANET Integration"
echo "=========================================="
echo ""

# Test 1: Check imports
echo "Test 1: Checking Python imports..."
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/shreyasdk/capstone/vanet_final_v3')

try:
    from v2v_communication.security import SecureMessageHandler
    from v2v_communication.key_management import initialize_vanet_security
    from sumo_simulation.wimax.secure_wimax import SecureWiMAXBaseStation
    print("  ✅ All security modules imported successfully")
except Exception as e:
    print(f"  ❌ Import error: {e}")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "❌ Import test failed"
    exit 1
fi

echo ""

# Test 2: Initialize security infrastructure
echo "Test 2: Initializing security infrastructure..."
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/shreyasdk/capstone/vanet_final_v3')

try:
    from v2v_communication.key_management import initialize_vanet_security
    
    # Initialize with small numbers for test
    ca, rsu_mgrs, vehicle_mgrs = initialize_vanet_security(
        rsu_ids=["RSU_J2", "RSU_J3"],
        num_vehicles=5
    )
    
    print(f"  ✅ CA initialized: {ca.ca_id}")
    print(f"  ✅ RSUs: {list(rsu_mgrs.keys())}")
    print(f"  ✅ Vehicles: {len(vehicle_mgrs)}")
    
except Exception as e:
    print(f"  ❌ Initialization error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "❌ Security initialization test failed"
    exit 1
fi

echo ""

# Test 3: Test traffic controller with security
echo "Test 3: Testing traffic controller with security..."
python3 << 'EOF'
import sys
import os
sys.path.insert(0, '/home/shreyasdk/capstone/vanet_final_v3')
os.chdir('/home/shreyasdk/capstone/vanet_final_v3/sumo_simulation')

try:
    from v2v_communication.key_management import initialize_vanet_security
    from sumo_simulation.traffic_controller import AdaptiveTrafficController
    
    # Initialize security
    ca, rsu_mgrs, vehicle_mgrs = initialize_vanet_security(
        rsu_ids=["RSU_J2", "RSU_J3"],
        num_vehicles=5
    )
    
    # Create traffic controller with security
    controller = AdaptiveTrafficController(
        security_managers=(ca, rsu_mgrs, vehicle_mgrs)
    )
    
    print(f"  ✅ Traffic controller created")
    print(f"  ✅ Security enabled: {controller.security_enabled}")
    print(f"  ✅ RSU managers: {len(controller.rsu_managers)}")
    print(f"  ✅ Vehicle managers: {len(controller.vehicle_managers)}")
    
except Exception as e:
    print(f"  ❌ Traffic controller test error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "❌ Traffic controller test failed"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ All integration tests passed!"
echo "=========================================="
echo ""
echo "Ready to run: ./run_integrated_sumo_ns3.sh --gui --steps 100"
echo ""
