#!/bin/bash
# Verification script to check if everything is ready

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "VANET Setup Verification"
echo "=========================================="
echo ""

ERRORS=0

# Check 1: Virtual environment
echo -n "Checking virtual environment... "
if [ -d "venv" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ venv not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check 2: SUMO installation
echo -n "Checking SUMO installation... "
if command -v sumo &> /dev/null; then
    VERSION=$(sumo --version 2>&1 | head -1)
    echo -e "${GREEN}✓ $VERSION${NC}"
else
    echo -e "${RED}✗ SUMO not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check 3: Configuration file
echo -n "Checking SUMO configuration... "
if [ -f "sumo_simulation/simulation.sumocfg" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ simulation.sumocfg not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check 4: Network file
echo -n "Checking network file... "
if [ -f "sumo_simulation/maps/simple_network.net.xml" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Network file not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check 5: Output directory
echo -n "Checking output directory... "
if [ -d "sumo_simulation/output" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠ Creating output directory...${NC}"
    mkdir -p sumo_simulation/output
    echo -e "${GREEN}✓ Created${NC}"
fi

# Check 6: Python dependencies
echo -n "Checking Python dependencies... "
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    if python -c "import traci; import flask; import gymnasium" 2>/dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗ Dependencies missing${NC}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${RED}✗ Cannot activate venv${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check 7: Traffic controller
echo -n "Checking traffic controller... "
if [ -f "sumo_simulation/traffic_controller.py" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ traffic_controller.py not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check 8: Run script
echo -n "Checking run script... "
if [ -f "run_sumo.sh" ] && [ -x "run_sumo.sh" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠ Making run_sumo.sh executable...${NC}"
    chmod +x run_sumo.sh 2>/dev/null
    echo -e "${GREEN}✓${NC}"
fi

echo ""
echo "=========================================="

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "You're ready to run the simulation:"
    echo "  ./run_sumo.sh"
    echo ""
    exit 0
else
    echo -e "${RED}✗ $ERRORS error(s) found${NC}"
    echo ""
    echo "Please fix the errors above before running."
    echo ""
    exit 1
fi
