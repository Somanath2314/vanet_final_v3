#!/bin/bash
# Setup script for DQN training environment

echo "=========================================="
echo "Setting up DQN Training Environment"
echo "=========================================="
echo ""

cd /home/shreyasdk/capstone/vanet_final_v3

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please create it first with: python3 -m venv venv"
    exit 1
fi

# Activate venv
echo "Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo ""
echo "Installing DQN training requirements..."
echo ""
pip install -r rl_dqn_requirements.txt

# Check installation
echo ""
echo "=========================================="
echo "Verifying installation..."
echo "=========================================="
echo ""

python3 << 'EOF'
import sys

packages = {
    'stable_baselines3': 'Stable-Baselines3',
    'torch': 'PyTorch',
    'gymnasium': 'Gymnasium',
    'tensorboard': 'TensorBoard',
}

all_ok = True
for module, name in packages.items():
    try:
        __import__(module)
        version = getattr(__import__(module), '__version__', 'unknown')
        print(f"✓ {name:20s} version {version}")
    except ImportError:
        print(f"❌ {name:20s} NOT INSTALLED")
        all_ok = False

if all_ok:
    print("\n✅ All packages installed successfully!")
    sys.exit(0)
else:
    print("\n❌ Some packages failed to install")
    sys.exit(1)
EOF

exitcode=$?

echo ""
if [ $exitcode -eq 0 ]; then
    echo "=========================================="
    echo "✅ DQN Environment Setup Complete!"
    echo "=========================================="
    echo ""
    echo "You can now train the model with:"
    echo "  cd rl_module"
    echo "  python3 train_dqn_model.py --timesteps 100000"
    echo ""
else
    echo "=========================================="
    echo "❌ Setup failed"
    echo "=========================================="
    echo ""
    echo "Please check the error messages above"
    exit 1
fi
