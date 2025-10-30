#!/usr/bin/env python3
"""
Quick setup verification and test for ambulance RL training.
Run this before starting full training to catch issues early.
"""

import sys
import os

print("="*80)
print("AMBULANCE RL TRAINING - SETUP VERIFICATION")
print("="*80)

# Check 1: Python version
print("\n1. Checking Python version...")
if sys.version_info < (3, 8):
    print(f"  ✗ Python {sys.version_info.major}.{sys.version_info.minor} is too old")
    print(f"    Requires Python 3.8 or newer")
    sys.exit(1)
else:
    print(f"  ✓ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

# Check 2: Required packages
print("\n2. Checking required packages...")
required_packages = [
    ('torch', 'PyTorch'),
    ('numpy', 'NumPy'),
    ('gymnasium', 'Gymnasium'),
    ('traci', 'TraCI (SUMO)'),
]

missing_packages = []
for package, name in required_packages:
    try:
        __import__(package)
        print(f"  ✓ {name}")
    except ImportError:
        print(f"  ✗ {name} not found")
        missing_packages.append(package)

if missing_packages:
    print(f"\n  Missing packages: {', '.join(missing_packages)}")
    print(f"  Install with: pip install {' '.join(missing_packages)}")
    sys.exit(1)

# Check 3: SUMO installation
print("\n3. Checking SUMO installation...")
try:
    import subprocess
    result = subprocess.run(['sumo', '--version'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        version = result.stdout.strip().split('\n')[0]
        print(f"  ✓ SUMO found: {version}")
    else:
        print(f"  ✗ SUMO command failed")
        sys.exit(1)
except FileNotFoundError:
    print(f"  ✗ SUMO not found in PATH")
    print(f"    Install from: https://sumo.dlr.de/docs/Installing/index.html")
    sys.exit(1)
except subprocess.TimeoutExpired:
    print(f"  ✗ SUMO command timed out")
    sys.exit(1)

# Check 4: SUMO config files
print("\n4. Checking SUMO configuration...")
config_dir = os.path.join(os.path.dirname(__file__), '..', 'sumo_simulation')
config_file = os.path.join(config_dir, 'simulation.sumocfg')

if os.path.exists(config_file):
    print(f"  ✓ Config found: {config_file}")
else:
    print(f"  ✗ Config not found: {config_file}")
    sys.exit(1)

# Check network file
net_file = os.path.join(config_dir, 'maps', 'simple_network.net.xml')
if os.path.exists(net_file):
    print(f"  ✓ Network found: {net_file}")
else:
    print(f"  ⚠ Network not found: {net_file}")
    print(f"    Training may fail if SUMO can't load network")

# Check 5: Model output directory
print("\n5. Checking model output directory...")
model_dir = os.path.join(os.path.dirname(__file__), 'models')
os.makedirs(model_dir, exist_ok=True)
if os.path.exists(model_dir) and os.access(model_dir, os.W_OK):
    print(f"  ✓ Model directory: {model_dir}")
else:
    print(f"  ✗ Cannot write to: {model_dir}")
    sys.exit(1)

# Check 6: Try to import training modules
print("\n6. Checking training modules...")
sys.path.insert(0, os.path.dirname(__file__))

try:
    from vanet_env_ambulance import AmbulanceAwareVANETEnv
    print(f"  ✓ AmbulanceAwareVANETEnv")
except ImportError as e:
    print(f"  ✗ Cannot import AmbulanceAwareVANETEnv: {e}")
    sys.exit(1)

try:
    from train_ambulance_agent import AmbulanceDQNAgent
    print(f"  ✓ AmbulanceDQNAgent")
except ImportError as e:
    print(f"  ✗ Cannot import AmbulanceDQNAgent: {e}")
    sys.exit(1)

# Check 7: GPU availability (optional)
print("\n7. Checking GPU availability...")
try:
    import torch
    if torch.cuda.is_available():
        print(f"  ✓ CUDA available: {torch.cuda.get_device_name(0)}")
    else:
        print(f"  ⚠ No GPU found (will use CPU - slower but works)")
except:
    print(f"  ⚠ Cannot check GPU availability")

# All checks passed!
print("\n" + "="*80)
print("✓ ALL CHECKS PASSED!")
print("="*80)
print("\nYou're ready to train! Run one of these commands:\n")
print("  # Quick test (5 episodes, ~2 minutes):")
print("  python rl_module/train_ambulance_agent.py --test\n")
print("  # Prototype training (500 episodes, ~2-3 hours):")
print("  python rl_module/train_ambulance_agent.py --episodes 500\n")
print("  # Production training (2000 episodes, ~8-10 hours):")
print("  python rl_module/train_ambulance_agent.py --episodes 2000 --steps 1500\n")
print("="*80)
