#!/bin/bash
# Setup script for RL Traffic Optimization Integration

set -e

echo "=========================================="
echo "RL Traffic Optimization Setup"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip

# Install requirements
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r backend/requirements.txt

# Verify critical installations
echo ""
echo -e "${YELLOW}Verifying installations...${NC}"

# Check gymnasium
if python -c "import gymnasium" 2>/dev/null; then
    echo -e "${GREEN}✓ Gymnasium installed${NC}"
else
    echo -e "${RED}✗ Gymnasium installation failed${NC}"
    exit 1
fi

# Check ray
if python -c "import ray" 2>/dev/null; then
    echo -e "${GREEN}✓ Ray RLlib installed${NC}"
else
    echo -e "${RED}✗ Ray RLlib installation failed${NC}"
    exit 1
fi

# Check torch
if python -c "import torch" 2>/dev/null; then
    echo -e "${GREEN}✓ PyTorch installed${NC}"
else
    echo -e "${RED}✗ PyTorch installation failed${NC}"
    exit 1
fi

# Check numpy
if python -c "import numpy" 2>/dev/null; then
    echo -e "${GREEN}✓ NumPy installed${NC}"
else
    echo -e "${RED}✗ NumPy installation failed${NC}"
    exit 1
fi

# Check traci
if python -c "import traci" 2>/dev/null; then
    echo -e "${GREEN}✓ TraCI installed${NC}"
else
    echo -e "${RED}✗ TraCI installation failed${NC}"
    exit 1
fi

# Check SUMO installation
echo ""
echo -e "${YELLOW}Checking SUMO installation...${NC}"
if command -v sumo &> /dev/null; then
    SUMO_VERSION=$(sumo --version 2>&1 | head -n 1)
    echo -e "${GREEN}✓ SUMO installed: $SUMO_VERSION${NC}"
else
    echo -e "${RED}✗ SUMO not found in PATH${NC}"
    echo -e "${YELLOW}Please install SUMO: https://sumo.dlr.de/docs/Installing/index.html${NC}"
fi

# Create necessary directories
echo ""
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p rl_models
mkdir -p logs
echo -e "${GREEN}✓ Directories created${NC}"

# Test RL module imports
echo ""
echo -e "${YELLOW}Testing RL module imports...${NC}"
if python -c "from rl_module.vanet_env import VANETTrafficEnv; from rl_module.rewards import Rewards; from rl_module.states import States" 2>/dev/null; then
    echo -e "${GREEN}✓ RL module imports successful${NC}"
else
    echo -e "${RED}✗ RL module import failed${NC}"
    exit 1
fi

# Summary
echo ""
echo "=========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Start the backend server:"
echo "   cd backend && python app.py"
echo ""
echo "2. Start a simulation and enable RL mode via API"
echo ""
echo "3. Or train a new RL agent:"
echo "   cd rl_module"
echo "   python train_rl_agent.py --algorithm DQN --iterations 100"
echo ""
echo "See RL_INTEGRATION_README.md for detailed documentation"
echo ""
