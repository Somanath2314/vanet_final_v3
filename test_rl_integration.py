#!/usr/bin/env python3
"""
Test script for RL integration
Tests the RL module without requiring SUMO connection
"""

import sys
import os
import numpy as np

# Add paths
sys.path.append(os.path.dirname(__file__))

def test_imports():
    """Test that all RL modules can be imported"""
    print("Testing imports...")
    try:
        from rl_module.rewards import Rewards
        from rl_module.states import States
        from rl_module.helpers import flatten, pad_list, invert_tl_state
        from rl_module.vanet_env import VANETTrafficEnv
        from rl_module.rl_traffic_controller import RLTrafficController
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_helpers():
    """Test helper functions"""
    print("\nTesting helper functions...")
    try:
        from rl_module.helpers import flatten, pad_list, invert_tl_state
        
        # Test flatten
        nested = [[1, 2], [3, 4], [5]]
        flat = flatten(nested)
        assert flat == [1, 2, 3, 4, 5], "Flatten failed"
        
        # Test pad_list
        lst = [1, 2, 3]
        padded = pad_list(lst, 5, 0)
        assert padded == [1, 2, 3, 0, 0], "Pad list failed"
        
        # Test invert_tl_state
        state = "GGGGrrrr"
        inverted = invert_tl_state(state)
        assert inverted == "rrrrGGGG", "Invert TL state failed"
        
        print("✓ Helper functions working correctly")
        return True
    except Exception as e:
        print(f"✗ Helper test failed: {e}")
        return False

def test_rewards():
    """Test reward class"""
    print("\nTesting Rewards class...")
    try:
        from rl_module.rewards import Rewards
        
        action_spec = {
            'tl_1': ['GGGGrrrr', 'rrrrGGGG'],
            'tl_2': ['GGrr', 'rrGG']
        }
        
        rewards = Rewards(action_spec)
        
        # Test methods exist
        assert hasattr(rewards, 'penalize_min_speed')
        assert hasattr(rewards, 'penalize_max_wait')
        assert hasattr(rewards, 'penalize_max_acc')
        
        print("✓ Rewards class initialized correctly")
        return True
    except Exception as e:
        print(f"✗ Rewards test failed: {e}")
        return False

def test_states():
    """Test states class"""
    print("\nTesting States class...")
    try:
        from rl_module.states import States
        
        beta = 10
        states = States(beta)
        
        # Test attributes
        assert hasattr(states, 'tl')
        assert hasattr(states, 'veh')
        assert states.veh.beta == beta
        
        print("✓ States class initialized correctly")
        return True
    except Exception as e:
        print(f"✗ States test failed: {e}")
        return False

def test_environment():
    """Test RL environment"""
    print("\nTesting VANETTrafficEnv...")
    try:
        from rl_module.vanet_env import VANETTrafficEnv
        import gymnasium as gym
        
        config = {
            'beta': 10,
            'action_spec': {
                'tl_1': ['GGGGrrrr', 'rrrrGGGG'],
                'tl_2': ['GGrr', 'rrGG']
            },
            'algorithm': 'DQN',
            'horizon': 100
        }
        
        env = VANETTrafficEnv(config=config)
        
        # Test spaces
        assert env.action_space is not None
        assert env.observation_space is not None
        
        # Test reset (without SUMO connection, should return zero state)
        state = env.reset()
        assert isinstance(state, np.ndarray)
        assert state.shape == env.observation_space.shape
        
        print(f"  Action space: {env.action_space}")
        print(f"  Observation space: {env.observation_space.shape}")
        print("✓ Environment initialized correctly")
        return True
    except Exception as e:
        print(f"✗ Environment test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_rl_controller():
    """Test RL controller"""
    print("\nTesting RLTrafficController...")
    try:
        from rl_module.rl_traffic_controller import RLTrafficController
        
        config = {
            'beta': 10,
            'algorithm': 'DQN',
        }
        
        controller = RLTrafficController(mode='inference', config=config)
        
        # Test attributes
        assert controller.mode == 'inference'
        assert controller.config is not None
        
        # Test methods exist
        assert hasattr(controller, 'initialize')
        assert hasattr(controller, 'step')
        assert hasattr(controller, 'get_metrics')
        
        print("✓ RL controller initialized correctly")
        return True
    except Exception as e:
        print(f"✗ RL controller test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_dependencies():
    """Test that all required dependencies are installed"""
    print("\nTesting dependencies...")
    dependencies = {
        'gymnasium': 'Gymnasium',
        'numpy': 'NumPy',
        'torch': 'PyTorch',
        'ray': 'Ray RLlib',
        'flask': 'Flask',
        'traci': 'TraCI'
    }
    
    all_ok = True
    for module, name in dependencies.items():
        try:
            __import__(module)
            print(f"✓ {name} installed")
        except ImportError:
            print(f"✗ {name} NOT installed")
            all_ok = False
    
    return all_ok

def main():
    """Run all tests"""
    print("=" * 50)
    print("RL Integration Test Suite")
    print("=" * 50)
    
    tests = [
        ("Dependencies", test_dependencies),
        ("Imports", test_imports),
        ("Helpers", test_helpers),
        ("Rewards", test_rewards),
        ("States", test_states),
        ("Environment", test_environment),
        ("RL Controller", test_rl_controller),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! RL integration is ready.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed. Please check the errors above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
