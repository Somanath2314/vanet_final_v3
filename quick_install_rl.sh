#!/bin/bash
# Quick RL Dependencies Installation Script

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "Quick RL Installation"
echo "=========================================="
echo ""

# Check if venv is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

echo -e "${GREEN}Step 1/5: Installing core dependencies...${NC}"
pip install -q flask==2.3.3 flask-cors==4.0.0 traci==1.18.0 numpy==1.24.3 requests==2.31.0 python-dotenv==1.0.0
echo -e "${GREEN}✓ Core dependencies installed${NC}"

echo ""
echo -e "${GREEN}Step 2/5: Installing Gymnasium...${NC}"
pip install -q gymnasium==0.28.1
echo -e "${GREEN}✓ Gymnasium installed${NC}"

echo ""
echo -e "${GREEN}Step 3/5: Installing Ray RLlib (this may take 5-10 minutes)...${NC}"
pip install -q "ray[rllib]==2.9.0"
echo -e "${GREEN}✓ Ray RLlib installed${NC}"

echo ""
echo -e "${GREEN}Step 4/5: Installing data science libraries...${NC}"
pip install -q pandas matplotlib scipy
echo -e "${GREEN}✓ Data science libraries installed${NC}"

echo ""
echo -e "${YELLOW}Step 5/5: PyTorch (optional, recommended)${NC}"
echo "Do you want to install PyTorch? (y/n)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "Choose PyTorch version:"
    echo "1) CPU-only (faster install, ~200MB)"
    echo "2) CUDA (GPU support, ~2GB)"
    read -r pytorch_choice
    
    if [[ "$pytorch_choice" == "1" ]]; then
        echo -e "${GREEN}Installing PyTorch CPU...${NC}"
        pip install -q torch --index-url https://download.pytorch.org/whl/cpu
        echo -e "${GREEN}✓ PyTorch CPU installed${NC}"
    elif [[ "$pytorch_choice" == "2" ]]; then
        echo -e "${GREEN}Installing PyTorch CUDA...${NC}"
        pip install -q torch==2.0.1
        echo -e "${GREEN}✓ PyTorch CUDA installed${NC}"
    else
        echo -e "${YELLOW}Skipping PyTorch installation${NC}"
    fi
else
    echo -e "${YELLOW}Skipping PyTorch installation${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}Installation Complete!${NC}"
echo "=========================================="
echo ""

# Verify installation
echo "Verifying installation..."
python3 << 'EOF'
import sys
try:
    import gymnasium
    print("✓ Gymnasium")
except:
    print("✗ Gymnasium")
    sys.exit(1)

try:
    import ray
    print("✓ Ray")
except:
    print("✗ Ray")
    sys.exit(1)

try:
    import numpy
    print("✓ NumPy")
except:
    print("✗ NumPy")
    sys.exit(1)

try:
    import flask
    print("✓ Flask")
except:
    print("✗ Flask")
    sys.exit(1)

try:
    import torch
    print("✓ PyTorch")
except:
    print("⚠ PyTorch (optional, not installed)")

print("\n✓ All required dependencies installed successfully!")
EOF

echo ""
echo "Next steps:"
echo "1. Test the integration:"
echo "   python test_rl_integration.py"
echo ""
echo "2. Start the backend:"
echo "   cd backend && python app.py"
echo ""
echo "3. See INSTALLATION_GUIDE.md for more details"
echo ""
