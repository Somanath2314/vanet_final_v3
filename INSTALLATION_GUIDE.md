# Installation Guide - RL Traffic Optimization

## Quick Installation

### Step 1: Activate Virtual Environment
```bash
cd /home/mahesh/Desktop/capstone/vanet_final_v3
source venv/bin/activate
```

### Step 2: Install Core Dependencies
```bash
pip install flask==2.3.3 flask-cors==4.0.0 traci==1.18.0 numpy==1.24.3 requests==2.31.0 python-dotenv==1.0.0
```

### Step 3: Install RL Dependencies (This may take 5-10 minutes)
```bash
pip install gymnasium==0.28.1
pip install "ray[rllib]==2.9.0"
pip install pandas matplotlib scipy
```

**Note**: PyTorch is optional. Ray RLlib will work without it, but for better performance:
```bash
# CPU-only version (faster install)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# OR CUDA version (if you have NVIDIA GPU)
pip install torch==2.0.1
```

### Step 4: Verify Installation
```bash
python test_rl_integration.py
```

## Alternative: Install All at Once
```bash
pip install -r backend/requirements.txt
```
**Warning**: This may take 10-15 minutes due to Ray RLlib dependencies.

## Troubleshooting

### Issue: Ray installation takes too long
**Solution**: Install Ray without RLlib first, then add RLlib:
```bash
pip install ray==2.9.0
pip install "ray[rllib]==2.9.0"
```

### Issue: Gymnasium version conflict
**Solution**: Ray 2.9.0 requires gymnasium 0.28.1 specifically:
```bash
pip install gymnasium==0.28.1
```

### Issue: PyTorch CUDA errors
**Solution**: Use CPU-only version:
```bash
pip uninstall torch
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### Issue: Import errors after installation
**Solution**: Restart Python and verify:
```bash
python -c "import gymnasium; import ray; print('Success!')"
```

## Minimal Installation (Testing Only)

If you just want to test the code structure without RL functionality:
```bash
pip install flask flask-cors traci numpy requests python-dotenv gymnasium
```

This allows you to:
- Run the backend API
- Test imports
- View code structure

But you won't be able to:
- Train RL agents
- Run RL inference
- Use Ray RLlib features

## Full Installation Verification

After installation, run:
```bash
python test_rl_integration.py
```

Expected output:
```
==================================================
RL Integration Test Suite
==================================================

Testing dependencies...
✓ Gymnasium installed
✓ NumPy installed
✓ PyTorch installed
✓ Ray RLlib installed
✓ Flask installed
✓ TraCI installed

Testing imports...
✓ All imports successful

... (more tests)

Total: 7/7 tests passed
✓ All tests passed! RL integration is ready.
```

## Installation Time Estimates

- **Core dependencies**: 1-2 minutes
- **Gymnasium**: 30 seconds
- **Ray RLlib**: 5-10 minutes
- **PyTorch (CPU)**: 2-3 minutes
- **PyTorch (CUDA)**: 5-7 minutes
- **Total**: 10-20 minutes

## System Requirements

- **Python**: 3.8-3.10 (3.11+ not fully supported by Ray 2.9.0)
- **RAM**: 4GB minimum, 8GB recommended
- **Disk Space**: 2-3GB for all dependencies
- **OS**: Linux (tested), macOS, Windows (with WSL recommended)

## Next Steps

After successful installation:
1. Read `RL_INTEGRATION_README.md` for usage guide
2. Try examples in `examples/` directory
3. Start backend: `cd backend && python app.py`
4. Test RL mode via API or standalone scripts
