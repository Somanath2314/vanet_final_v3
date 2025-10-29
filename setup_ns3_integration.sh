#!/bin/bash

# Setup script for NS3 VANET integration
set -e

# Directory paths
PROJECT_ROOT="/home/shreyasdk/capstone/vanet_final_v3"
NS3_PATH="/home/shreyasdk/capstone/ns-allinone-3.39/ns-3.39"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Setting up NS3 VANET integration...${NC}"

# Check if NS3 is installed
if [ ! -d "$NS3_PATH" ]; then
    echo -e "${RED}Error: NS3 not found at $NS3_PATH${NC}"
    exit 1
fi

# Build NS3
echo "Building NS3..."
cd "$NS3_PATH"
./ns3 configure --enable-examples --enable-tests
./ns3 build

# Verify NS3 build
if [ $? -eq 0 ]; then
    echo -e "${GREEN}NS3 build completed successfully${NC}"
else
    echo -e "${RED}NS3 build failed${NC}"
    exit 1
fi

# Create symbolic link to NS3 scripts
echo "Creating symbolic links..."
ln -sf "$NS3_PATH/scratch/vanet-protocol.cc" "$PROJECT_ROOT/ns3_protocols/vanet-protocol.cc"

# Set up Python environment for NS3 integration
echo "Setting up Python environment..."
cd "$PROJECT_ROOT"

# Install required Python packages
python3 -m pip install --upgrade pip
python3 -m pip install numpy scipy matplotlib networkx

echo -e "${GREEN}NS3 VANET integration setup completed successfully${NC}"