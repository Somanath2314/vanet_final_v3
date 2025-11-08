#!/usr/bin/env python3
"""
Deep RL Training for Adaptive Traffic Control with Edge Computing & Security
Trains DQN agent integrated with edge RSUs and secure communication
"""

import os
import sys
import argparse
import yaml
import time
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from collections import deque
import matplotlib.pyplot as plt
from datetime import datetime
import json

# Add paths
sys.path.append(os.path.join(os.path.dirname(__file__), 'sumo_simulation'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'rl_module'))

import traci
from rl_module.rl_traffic_controller_enhanced import RLTrafficController
from rl_module.rl_environment import TrafficEnvironment


class DQNTrainer:
    """
    Deep Q-Network Trainer with Edge Computing and Security Integration
    """
    
    def __init__(self, config_path='rl_module/config.yaml'):
        """Initialize trainer with configuration"""
        self.config = self._load_config(config_path)
        
        # Setup directories
        self.model_dir = self.config['paths']['model_dir']
        self.log_dir = self.config['paths']['log_dir']
        os.makedirs(self.model_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Training parameters
        self.num_episodes = self.config['training']['num_episodes']
        self.max_steps = self.config['training']['max_steps_per_episode']
        self.batch_size = self.config['training']['batch_size']
        self.gamma = self.config['training']['gamma']
        self.learning_rate = self.config['training']['learning_rate']
        self.epsilon_start = self.config['training']['epsilon_start']
        self.epsilon_end = self.config['training']['epsilon_end']
        self.epsilon_decay = self.config['training']['epsilon_decay']
        self.target_update = self.config['training']['target_update_freq']
        
        # Edge computing and security
        self.edge_enabled = self.config['environment']['edge_computing']
        self.security_enabled = self.config['environment']['security']
        
        # Metrics
        self.episode_rewards = []
        self.episode_lengths = []
        self.avg_waiting_times = []
        self.collision_warnings = []  # Edge metric
        self.emergency_response_times = []  # Edge + Security metric
        
        # Best model tracking
        self.best_reward = -float('inf')
        
        print("\n" + "="*70)
        print("🚀 DEEP RL TRAINING FOR ADAPTIVE TRAFFIC CONTROL")
        print("="*70)
        print(f"Episodes: {self.num_episodes}")
        print(f"Steps per episode: {self.max_steps}")
        print(f"Edge Computing: {'✅ Enabled' if self.edge_enabled else '❌ Disabled'}")
        print(f"Security: {'✅ Enabled' if self.security_enabled else '❌ Disabled'}")
        print(f"Model Directory: {self.model_dir}")
        print("="*70 + "\n")
    
    def _load_config(self, config_path):
        """Load training configuration"""
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        else:
            # Default configuration
            return {
                'training': {
                    'num_episodes': 5000,
                    'max_steps_per_episode': 1800,  # 30 minutes
                    'batch_size': 64,
                    'gamma': 0.99,
                    'learning_rate': 0.0001,
                    'epsilon_start': 1.0,
                    'epsilon_end': 0.01,
                    'epsilon_decay': 0.995,
                    'target_update_freq': 10,
                    'save_freq': 100,
                    'eval_freq': 50
                },
                'environment': {
                    'sumo_config': 'sumo_simulation/simulation.sumocfg',
                    'edge_computing': True,
                    'security': True,
                    'gui': False
                },
                'network': {
                    'hidden_layers': [256, 256, 128],
                    'dropout': 0.2
                },
                'paths': {
                    'model_dir': 'rl_module/models',
                    'log_dir': 'rl_module/logs'
                },
                'reward': {
                    'waiting_time_weight': -1.0,
                    'throughput_weight': 0.5,
                    'phase_change_penalty': -0.1,
                    'emergency_priority_bonus': 5.0,
                    'collision_warning_penalty': -2.0,
                    'edge_efficiency_bonus': 0.2
                }
            }
    
    def train(self):
        """Main training loop"""
        # Initialize environment
        env = TrafficEnvironment(
            sumo_config=self.config['environment']['sumo_config'],
            edge_enabled=self.edge_enabled,
            security_enabled=self.security_enabled,
            use_gui=False
        )
        
        # Reset environment to initialize SUMO and get traffic lights
        initial_state = env.reset()
        
        # Get traffic light IDs (now available after reset)
        tl_ids = env.get_traffic_light_ids()
        
        # Initialize RL controller
        agent = RLTrafficController(
            tl_ids=tl_ids,
            edge_enabled=self.edge_enabled,
            security_enabled=self.security_enabled,
            state_dim=env.state_dim,
            action_dim=env.action_dim,
            config=self.config
        )
        
        print(f"📊 State Dimension: {env.state_dim}")
        print(f"🎯 Action Dimension: {env.action_dim}")
        print(f"🚦 Traffic Lights: {tl_ids}")
        print(f"\n{'='*70}")
        print("TRAINING STARTING...")
        print(f"{'='*70}\n")
        
        start_time = time.time()
        
        for episode in range(1, self.num_episodes + 1):
            episode_start = time.time()
            
            # Reset environment
            state = env.reset()
            episode_reward = 0
            episode_steps = 0
            
            # Episode metrics
            waiting_times = []
            edge_warnings = 0
            emergency_handled = 0
            
            # Epsilon decay
            agent.epsilon = max(
                self.epsilon_end,
                self.epsilon_start * (self.epsilon_decay ** episode)
            )
            
            # Run episode
            for step in range(self.max_steps):
                # Select and perform action
                action = agent.select_action(state, training=True)
                next_state, reward, done, info = env.step(action)
                
                # Store transition
                agent.remember(state, action, reward, next_state, done)
                
                # Train agent
                if len(agent.memory) > self.batch_size:
                    loss = agent.train_step(self.batch_size)
                
                # Collect metrics
                episode_reward += reward
                episode_steps += 1
                waiting_times.append(info.get('avg_waiting_time', 0))
                edge_warnings += info.get('collision_warnings', 0)
                emergency_handled += info.get('emergencies_handled', 0)
                
                state = next_state
                
                if done:
                    break
            
            # Episode finished
            episode_time = time.time() - episode_start
            avg_waiting_time = np.mean(waiting_times) if waiting_times else 0
            
            # Store metrics
            self.episode_rewards.append(episode_reward)
            self.episode_lengths.append(episode_steps)
            self.avg_waiting_times.append(avg_waiting_time)
            self.collision_warnings.append(edge_warnings)
            self.emergency_response_times.append(info.get('avg_emergency_response', 0))
            
            # Update target network
            if episode % self.target_update == 0:
                agent.update_target_network()
            
            # Print progress
            if episode % 10 == 0:
                avg_reward = np.mean(self.episode_rewards[-10:])
                avg_wait = np.mean(self.avg_waiting_times[-10:])
                
                print(f"Episode {episode}/{self.num_episodes} | "
                      f"Reward: {episode_reward:.2f} | "
                      f"Avg Reward (10): {avg_reward:.2f} | "
                      f"Avg Wait: {avg_wait:.2f}s | "
                      f"Epsilon: {agent.epsilon:.4f} | "
                      f"Steps: {episode_steps} | "
                      f"Time: {episode_time:.1f}s")
                
                if self.edge_enabled:
                    print(f"  └─ Edge Warnings: {edge_warnings} | "
                          f"Emergencies: {emergency_handled}")
            
            # Save best model
            if episode_reward > self.best_reward:
                self.best_reward = episode_reward
                agent.save_model(os.path.join(self.model_dir, 'dqn_best.pth'))
                print(f"  🌟 New best model saved! Reward: {episode_reward:.2f}")
            
            # Periodic saving
            if episode % self.config['training']['save_freq'] == 0:
                agent.save_model(os.path.join(self.model_dir, f'dqn_episode_{episode}.pth'))
                self._save_training_curves(episode)
                print(f"  💾 Checkpoint saved at episode {episode}")
            
            # Evaluation
            if episode % self.config['training']['eval_freq'] == 0:
                eval_reward = self._evaluate(env, agent)
                print(f"  📈 Evaluation Reward: {eval_reward:.2f}")
        
        # Training finished
        total_time = time.time() - start_time
        print(f"\n{'='*70}")
        print("✅ TRAINING COMPLETED!")
        print(f"{'='*70}")
        print(f"Total Time: {total_time/3600:.2f} hours")
        print(f"Best Reward: {self.best_reward:.2f}")
        print(f"Final Model: {self.model_dir}/dqn_best.pth")
        print(f"{'='*70}\n")
        
        # Save final model and metrics
        agent.save_model(os.path.join(self.model_dir, 'dqn_final.pth'))
        self._save_training_curves(self.num_episodes)
        self._save_training_summary(total_time)
        
        # Cleanup
        env.close()
    
    def _evaluate(self, env, agent, num_episodes=5):
        """Evaluate agent performance"""
        agent.epsilon = 0.0  # No exploration
        total_reward = 0
        
        for _ in range(num_episodes):
            state = env.reset()
            episode_reward = 0
            
            for _ in range(self.max_steps):
                action = agent.select_action(state, training=False)
                next_state, reward, done, _ = env.step(action)
                episode_reward += reward
                state = next_state
                
                if done:
                    break
            
            total_reward += episode_reward
        
        return total_reward / num_episodes
    
    def _save_training_curves(self, episode):
        """Save training progress plots"""
        fig, axes = plt.subplots(2, 3, figsize=(18, 10))
        
        # Episode rewards
        axes[0, 0].plot(self.episode_rewards, alpha=0.6, label='Raw')
        if len(self.episode_rewards) >= 100:
            smoothed = np.convolve(self.episode_rewards, np.ones(100)/100, mode='valid')
            axes[0, 0].plot(smoothed, linewidth=2, label='Smoothed (100)')
        axes[0, 0].set_title('Episode Rewards')
        axes[0, 0].set_xlabel('Episode')
        axes[0, 0].set_ylabel('Total Reward')
        axes[0, 0].legend()
        axes[0, 0].grid(True)
        
        # Average waiting time
        axes[0, 1].plot(self.avg_waiting_times, alpha=0.6, label='Raw')
        if len(self.avg_waiting_times) >= 100:
            smoothed = np.convolve(self.avg_waiting_times, np.ones(100)/100, mode='valid')
            axes[0, 1].plot(smoothed, linewidth=2, label='Smoothed (100)')
        axes[0, 1].set_title('Average Waiting Time')
        axes[0, 1].set_xlabel('Episode')
        axes[0, 1].set_ylabel('Waiting Time (s)')
        axes[0, 1].legend()
        axes[0, 1].grid(True)
        
        # Episode lengths
        axes[0, 2].plot(self.episode_lengths)
        axes[0, 2].set_title('Episode Lengths')
        axes[0, 2].set_xlabel('Episode')
        axes[0, 2].set_ylabel('Steps')
        axes[0, 2].grid(True)
        
        # Collision warnings (Edge)
        if self.edge_enabled:
            axes[1, 0].plot(self.collision_warnings, alpha=0.6)
            axes[1, 0].set_title('Collision Warnings (Edge)')
            axes[1, 0].set_xlabel('Episode')
            axes[1, 0].set_ylabel('Count')
            axes[1, 0].grid(True)
        
        # Emergency response (Edge + Security)
        if self.edge_enabled or self.security_enabled:
            axes[1, 1].plot(self.emergency_response_times, alpha=0.6)
            axes[1, 1].set_title('Emergency Response Time')
            axes[1, 1].set_xlabel('Episode')
            axes[1, 1].set_ylabel('Time (s)')
            axes[1, 1].grid(True)
        
        # Learning progress
        if len(self.episode_rewards) >= 100:
            window = 100
            rolling_avg = [np.mean(self.episode_rewards[max(0, i-window):i+1]) 
                          for i in range(len(self.episode_rewards))]
            axes[1, 2].plot(rolling_avg, linewidth=2)
            axes[1, 2].set_title('Learning Progress (100-ep avg)')
            axes[1, 2].set_xlabel('Episode')
            axes[1, 2].set_ylabel('Average Reward')
            axes[1, 2].grid(True)
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.log_dir, f'training_curves_ep{episode}.png'), dpi=150)
        plt.close()
    
    def _save_training_summary(self, total_time):
        """Save training summary to JSON"""
        summary = {
            'training_info': {
                'total_episodes': self.num_episodes,
                'total_time_hours': total_time / 3600,
                'best_reward': float(self.best_reward),
                'final_reward': float(np.mean(self.episode_rewards[-100:])),
                'edge_computing': self.edge_enabled,
                'security': self.security_enabled
            },
            'final_metrics': {
                'avg_reward': float(np.mean(self.episode_rewards[-100:])),
                'avg_waiting_time': float(np.mean(self.avg_waiting_times[-100:])),
                'avg_episode_length': float(np.mean(self.episode_lengths[-100:])),
                'total_collision_warnings': int(np.sum(self.collision_warnings)),
                'avg_emergency_response': float(np.mean(self.emergency_response_times[-100:]))
            },
            'configuration': self.config,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(os.path.join(self.log_dir, 'training_summary.json'), 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"📄 Training summary saved to {self.log_dir}/training_summary.json")


def main():
    parser = argparse.ArgumentParser(description='Train RL agent for traffic control')
    parser.add_argument('--config', type=str, default='rl_module/config.yaml',
                       help='Path to configuration file')
    parser.add_argument('--episodes', type=int, default=None,
                       help='Number of training episodes (overrides config)')
    parser.add_argument('--no-edge', action='store_true',
                       help='Disable edge computing')
    parser.add_argument('--no-security', action='store_true',
                       help='Disable security features')
    
    args = parser.parse_args()
    
    # Initialize trainer
    trainer = DQNTrainer(config_path=args.config)
    
    # Override config if specified
    if args.episodes:
        trainer.num_episodes = args.episodes
    if args.no_edge:
        trainer.edge_enabled = False
    if args.no_security:
        trainer.security_enabled = False
    
    # Start training
    try:
        trainer.train()
    except KeyboardInterrupt:
        print("\n⚠️  Training interrupted by user")
    except Exception as e:
        print(f"\n❌ Training failed with error: {e}")
        raise


if __name__ == '__main__':
    main()
