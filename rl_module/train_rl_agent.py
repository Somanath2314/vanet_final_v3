#!/usr/bin/env python3
"""
Training script for RL traffic optimization agent.
Uses Ray RLlib for training DQN or PPO agents.
"""

import os
import sys
import argparse
import json
from datetime import datetime

import ray
from ray import tune
from ray.rllib.algorithms.dqn import DQNConfig
from ray.rllib.algorithms.ppo import PPOConfig
from ray.tune.registry import register_env

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from rl_module.vanet_env import VANETTrafficEnv


def create_env(config):
    """Environment creator function for Ray."""
    return VANETTrafficEnv(config=config)


def get_trainer_config(algorithm, env_config):
    """
    Get trainer configuration for specified algorithm.
    
    Parameters
    ----------
    algorithm : str
        'DQN' or 'PPO'
    env_config : dict
        Environment configuration
        
    Returns
    -------
    config : RLlib Config object
        Trainer configuration
    """
    if algorithm == "DQN":
        config = (
            DQNConfig()
            .environment(env="vanet_traffic_env", env_config=env_config)
            .framework("torch")
            .rollouts(num_rollout_workers=2)
            .training(
                hiddens=[256, 256],
                dueling=True,
                double_q=True,
                lr=5e-4,
                train_batch_size=32,
                target_network_update_freq=500,
            )
            .exploration(
                exploration_config={
                    "type": "EpsilonGreedy",
                    "initial_epsilon": 1.0,
                    "final_epsilon": 0.02,
                    "epsilon_timesteps": 10000,
                }
            )
        )
    elif algorithm == "PPO":
        config = (
            PPOConfig()
            .environment(env="vanet_traffic_env", env_config=env_config)
            .framework("torch")
            .rollouts(num_rollout_workers=2)
            .training(
                model={"fcnet_hiddens": [256, 256]},
                lr=5e-5,
                train_batch_size=4000,
                sgd_minibatch_size=128,
                num_sgd_iter=10,
                gamma=0.99,
                lambda_=0.95,
                clip_param=0.2,
            )
        )
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")
    
    return config


def train(args):
    """
    Train RL agent.
    
    Parameters
    ----------
    args : argparse.Namespace
        Training arguments
    """
    # Initialize Ray
    ray.init(ignore_reinit_error=True)
    
    # Register environment
    register_env("vanet_traffic_env", create_env)
    
    # Environment configuration
    env_config = {
        'beta': args.beta,
        'action_spec': {},  # Will be populated from SUMO
        'tl_constraint_min': args.tl_min,
        'tl_constraint_max': args.tl_max,
        'sim_step': args.sim_step,
        'algorithm': args.algorithm,
        'horizon': args.horizon,
    }
    
    # Get trainer configuration
    config = get_trainer_config(args.algorithm, env_config)
    
    # Create output directory
    output_dir = os.path.join(
        args.output_dir,
        f"{args.algorithm}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    os.makedirs(output_dir, exist_ok=True)
    
    # Save configuration
    config_path = os.path.join(output_dir, "config.json")
    with open(config_path, 'w') as f:
        json.dump({
            'algorithm': args.algorithm,
            'env_config': env_config,
        }, f, indent=2)
    
    print(f"Training {args.algorithm} agent...")
    print(f"Output directory: {output_dir}")
    print(f"Configuration saved to: {config_path}")
    
    # Training loop - build the algorithm
    trainer = config.build()
    
    best_reward = -float('inf')
    
    for iteration in range(args.iterations):
        result = trainer.train()
        
        episode_reward_mean = result.get('episode_reward_mean', 0)
        
        print(f"\nIteration {iteration + 1}/{args.iterations}")
        print(f"  Episode reward mean: {episode_reward_mean:.2f}")
        print(f"  Episodes this iter: {result.get('episodes_this_iter', 0)}")
        print(f"  Timesteps total: {result.get('timesteps_total', 0)}")
        
        # Save checkpoint
        if (iteration + 1) % args.checkpoint_freq == 0:
            checkpoint_path = trainer.save(output_dir)
            print(f"  Checkpoint saved: {checkpoint_path}")
        
        # Save best model
        if episode_reward_mean > best_reward:
            best_reward = episode_reward_mean
            best_path = trainer.save(os.path.join(output_dir, "best"))
            print(f"  New best model saved: {best_path}")
    
    # Save final model
    final_path = trainer.save(os.path.join(output_dir, "final"))
    print(f"\nTraining complete!")
    print(f"Final model saved: {final_path}")
    
    # Cleanup
    trainer.stop()
    ray.shutdown()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Train RL agent for VANET traffic optimization"
    )
    
    # Algorithm settings
    parser.add_argument(
        '--algorithm',
        type=str,
        default='DQN',
        choices=['DQN', 'PPO'],
        help='RL algorithm to use'
    )
    
    # Training settings
    parser.add_argument(
        '--iterations',
        type=int,
        default=100,
        help='Number of training iterations'
    )
    parser.add_argument(
        '--checkpoint-freq',
        type=int,
        default=10,
        help='Checkpoint frequency (iterations)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='./rl_models',
        help='Output directory for models'
    )
    
    # Environment settings
    parser.add_argument(
        '--beta',
        type=int,
        default=20,
        help='Number of observable vehicles'
    )
    parser.add_argument(
        '--horizon',
        type=int,
        default=1000,
        help='Episode horizon (steps)'
    )
    parser.add_argument(
        '--tl-min',
        type=int,
        default=5,
        help='Minimum time before traffic light change (seconds)'
    )
    parser.add_argument(
        '--tl-max',
        type=int,
        default=60,
        help='Maximum time before forced traffic light change (seconds)'
    )
    parser.add_argument(
        '--sim-step',
        type=float,
        default=1.0,
        help='Simulation step size (seconds)'
    )
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Train
    train(args)


if __name__ == '__main__':
    main()
