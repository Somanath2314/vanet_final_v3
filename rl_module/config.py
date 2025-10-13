"""
Configuration file for RL Traffic Optimization
"""

# Default RL Environment Configuration
DEFAULT_RL_CONFIG = {
    # Environment parameters
    'beta': 20,                      # Number of observable vehicles
    'tl_constraint_min': 5,          # Minimum time before traffic light can change (seconds)
    'tl_constraint_max': 60,         # Maximum time before traffic light must change (seconds)
    'sim_step': 1.0,                 # Simulation step size (seconds)
    'horizon': 1000,                 # Episode length (steps)
    'algorithm': 'DQN',              # RL algorithm: 'DQN' or 'PPO'
    
    # Action space (auto-detected from SUMO if empty)
    'action_spec': {},
}

# DQN Training Configuration
DQN_TRAINING_CONFIG = {
    'num_workers': 2,
    'framework': 'torch',
    'hiddens': [256, 256],
    'dueling': True,
    'double_q': True,
    'exploration_config': {
        'type': 'EpsilonGreedy',
        'initial_epsilon': 1.0,
        'final_epsilon': 0.02,
        'epsilon_timesteps': 10000,
    },
    'lr': 5e-4,
    'train_batch_size': 32,
    'target_network_update_freq': 500,
    'gamma': 0.99,
}

# PPO Training Configuration
PPO_TRAINING_CONFIG = {
    'num_workers': 2,
    'framework': 'torch',
    'model': {
        'fcnet_hiddens': [256, 256],
    },
    'lr': 5e-5,
    'train_batch_size': 4000,
    'sgd_minibatch_size': 128,
    'num_sgd_iter': 10,
    'gamma': 0.99,
    'lambda': 0.95,
    'clip_param': 0.2,
}

# Reward Function Parameters
REWARD_CONFIG = {
    'min_speed': 10,              # Minimum desired speed (km/h)
    'idled_max_steps': 80,        # Maximum idle time before penalty (steps)
    'max_abs_acc': 0.15,          # Maximum acceleration threshold (m/s^2)
    'reward_scale': 0.001,        # Scaling factor for rewards
    
    # Reward weights
    'speed_weight': 1.0,
    'wait_weight': -10.0,
    'acceleration_weight': 1.0,
    'emission_weight': 0.0,       # Set to non-zero to penalize emissions
}

# Training Parameters
TRAINING_CONFIG = {
    'iterations': 100,
    'checkpoint_freq': 10,
    'output_dir': './rl_models',
    'log_level': 'INFO',
}

# Inference Parameters
INFERENCE_CONFIG = {
    'model_path': None,            # Path to trained model
    'deterministic': True,         # Use deterministic actions
}
