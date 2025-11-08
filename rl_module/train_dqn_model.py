#!/usr/bin/env python3
"""
Train DQN Model for Hybrid Traffic Control
Uses stable-baselines3 DQN algorithm with custom VANET environment
"""

import os
import sys
import argparse
from datetime import datetime

# Add paths
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)
sys.path.insert(0, os.path.join(parent_dir, 'rl_module'))

import traci
import numpy as np
from stable_baselines3 import DQN
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from rl_module.vanet_env import VANETTrafficEnv


def make_env(config_path, rank=0):
    """
    Create a VANET environment for training.
    
    Parameters
    ----------
    config_path : str
        Path to SUMO configuration file
    rank : int
        Environment rank (for multiple parallel environments)
    """
    def _init():
        # Start SUMO for this environment
        sumo_binary = "sumo"  # Use headless SUMO
        port = 8813 + rank  # Different port for each environment
        sumo_cmd = [
            sumo_binary,
            "-c", config_path,
            "--start",
            "--step-length", "1",
            "--no-warnings"
        ]
        
        # Note: port is passed to traci.start(), not in sumo_cmd
        traci.start(sumo_cmd, label=f"sim_{rank}", port=port)
        traci.switch(f"sim_{rank}")
        
        # Get traffic lights
        tl_ids = traci.trafficlight.getIDList()
        
        # Build action spec
        action_spec = {}
        for tl_id in tl_ids:
            try:
                logic = traci.trafficlight.getAllProgramLogics(tl_id)[0]
                phases = [phase.state for phase in logic.phases]
                action_spec[tl_id] = phases
            except Exception as e:
                print(f"Warning: Error getting phases for {tl_id}: {e}")
        
        # Create environment
        env_config = {
            'beta': 20,
            'action_spec': action_spec,
            'tl_constraint_min': 5,
            'tl_constraint_max': 60,
            'sim_step': 1.0,
            'algorithm': 'DQN',
            'horizon': 1000,
        }
        
        env = VANETTrafficEnv(config=env_config)
        env = Monitor(env)  # Wrap with Monitor for logging
        
        return env
    
    return _init


def train_dqn(
    config_path,
    output_dir="./trained_models",
    total_timesteps=100000,
    learning_rate=0.0001,
    buffer_size=50000,
    learning_starts=1000,
    batch_size=32,
    gamma=0.99,
    exploration_fraction=0.3,
    exploration_final_eps=0.05,
    target_update_interval=1000,
    save_freq=10000,
    log_interval=100,
):
    """
    Train DQN model for traffic control.
    
    Parameters
    ----------
    config_path : str
        Path to SUMO configuration file
    output_dir : str
        Directory to save trained models
    total_timesteps : int
        Total training timesteps
    learning_rate : float
        Learning rate for optimizer
    buffer_size : int
        Size of replay buffer
    learning_starts : int
        Steps before training starts
    batch_size : int
        Batch size for training
    gamma : float
        Discount factor
    exploration_fraction : float
        Fraction of training for exploration
    exploration_final_eps : float
        Final exploration rate
    target_update_interval : int
        Steps between target network updates
    save_freq : int
        Save checkpoint every N steps
    log_interval : int
        Log every N steps
    """
    
    print("=" * 80)
    print("TRAINING DQN MODEL FOR HYBRID TRAFFIC CONTROL")
    print("=" * 80)
    print()
    
    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_dir = os.path.join(output_dir, f"dqn_traffic_{timestamp}")
    os.makedirs(model_dir, exist_ok=True)
    
    print(f"✓ Output directory: {model_dir}")
    print(f"✓ SUMO config: {config_path}")
    print()
    
    # Create environment
    print("Creating training environment...")
    env = DummyVecEnv([make_env(config_path, rank=0)])
    
    print("✓ Environment created")
    print(f"  Observation space: {env.observation_space}")
    print(f"  Action space: {env.action_space}")
    print()
    
    # Create DQN model
    print("Creating DQN model...")
    print(f"  Learning rate: {learning_rate}")
    print(f"  Buffer size: {buffer_size}")
    print(f"  Batch size: {batch_size}")
    print(f"  Gamma: {gamma}")
    print(f"  Exploration: {exploration_fraction} → {exploration_final_eps}")
    print()
    
    model = DQN(
        "MlpPolicy",  # Multi-layer perceptron policy
        env,
        learning_rate=learning_rate,
        buffer_size=buffer_size,
        learning_starts=learning_starts,
        batch_size=batch_size,
        gamma=gamma,
        exploration_fraction=exploration_fraction,
        exploration_final_eps=exploration_final_eps,
        target_update_interval=target_update_interval,
        verbose=1,
        tensorboard_log=os.path.join(model_dir, "tensorboard"),
    )
    
    print("✓ DQN model created")
    print()
    
    # Setup callbacks
    checkpoint_callback = CheckpointCallback(
        save_freq=save_freq,
        save_path=os.path.join(model_dir, "checkpoints"),
        name_prefix="dqn_traffic"
    )
    
    print("=" * 80)
    print("STARTING TRAINING")
    print("=" * 80)
    print(f"Total timesteps: {total_timesteps}")
    print(f"Save frequency: {save_freq}")
    print(f"Log interval: {log_interval}")
    print()
    
    try:
        # Train the model
        model.learn(
            total_timesteps=total_timesteps,
            callback=checkpoint_callback,
            log_interval=log_interval,
            progress_bar=True
        )
        
        print()
        print("=" * 80)
        print("TRAINING COMPLETED!")
        print("=" * 80)
        print()
        
        # Save final model
        final_model_path = os.path.join(model_dir, "dqn_traffic_final")
        model.save(final_model_path)
        print(f"✓ Final model saved: {final_model_path}.zip")
        
        # Save config
        config_path_save = os.path.join(model_dir, "config.txt")
        with open(config_path_save, 'w') as f:
            f.write(f"SUMO Config: {config_path}\n")
            f.write(f"Total Timesteps: {total_timesteps}\n")
            f.write(f"Learning Rate: {learning_rate}\n")
            f.write(f"Buffer Size: {buffer_size}\n")
            f.write(f"Batch Size: {batch_size}\n")
            f.write(f"Gamma: {gamma}\n")
            f.write(f"Exploration: {exploration_fraction} → {exploration_final_eps}\n")
        print(f"✓ Config saved: {config_path_save}")
        
        print()
        print("Model can be loaded with:")
        print(f"  model = DQN.load('{final_model_path}')")
        print()
        
        return final_model_path
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Training interrupted by user (Ctrl+C)")
        print("Saving current model...")
        
        interrupted_path = os.path.join(model_dir, "dqn_traffic_interrupted")
        model.save(interrupted_path)
        print(f"✓ Model saved: {interrupted_path}.zip")
        
        return interrupted_path
        
    except Exception as e:
        print(f"\n\n❌ Training failed: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        env.close()
        try:
            traci.close()
        except:
            pass


def main():
    parser = argparse.ArgumentParser(description="Train DQN model for traffic control")
    
    parser.add_argument(
        '--config',
        type=str,
        default='../sumo_simulation/simulation.sumocfg',
        help='Path to SUMO configuration file'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='./trained_models',
        help='Output directory for trained models'
    )
    parser.add_argument(
        '--timesteps',
        type=int,
        default=100000,
        help='Total training timesteps'
    )
    parser.add_argument(
        '--lr',
        type=float,
        default=0.0001,
        help='Learning rate'
    )
    parser.add_argument(
        '--buffer-size',
        type=int,
        default=50000,
        help='Replay buffer size'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=32,
        help='Batch size'
    )
    parser.add_argument(
        '--gamma',
        type=float,
        default=0.99,
        help='Discount factor'
    )
    parser.add_argument(
        '--exploration',
        type=float,
        default=0.3,
        help='Exploration fraction'
    )
    parser.add_argument(
        '--save-freq',
        type=int,
        default=10000,
        help='Save checkpoint frequency'
    )
    
    args = parser.parse_args()
    
    # Check if config exists
    if not os.path.exists(args.config):
        print(f"❌ ERROR: Config file not found: {args.config}")
        sys.exit(1)
    
    # Train model
    model_path = train_dqn(
        config_path=args.config,
        output_dir=args.output,
        total_timesteps=args.timesteps,
        learning_rate=args.lr,
        buffer_size=args.buffer_size,
        batch_size=args.batch_size,
        gamma=args.gamma,
        exploration_fraction=args.exploration,
        save_freq=args.save_freq
    )
    
    if model_path:
        print("=" * 80)
        print("✅ SUCCESS!")
        print("=" * 80)
        sys.exit(0)
    else:
        print("=" * 80)
        print("❌ TRAINING FAILED")
        print("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()
