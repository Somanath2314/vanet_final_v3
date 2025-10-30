"""
Train Ambulance-Aware RL Agent
Trains a PyTorch DQN agent that learns to optimize traffic lights for ambulance priority.
"""

import sys
import os
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import random
from collections import deque
import traci
import time
import json

# Add paths
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'sumo_simulation'))

from vanet_env_ambulance import AmbulanceAwareVANETEnv


class DQNNetwork(nn.Module):
    """Deep Q-Network for ambulance-aware traffic control."""
    
    def __init__(self, state_dim, action_dim, hidden_dim=256):
        super(DQNNetwork, self).__init__()
        
        self.network = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, action_dim)
        )
    
    def forward(self, x):
        return self.network(x)


class ReplayBuffer:
    """Experience replay buffer for DQN."""
    
    def __init__(self, capacity=50000):
        self.buffer = deque(maxlen=capacity)
    
    def push(self, state, action, reward, next_state, done):
        self.buffer.append((state, action, reward, next_state, done))
    
    def sample(self, batch_size):
        batch = random.sample(self.buffer, batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)
        return (
            np.array(states),
            np.array(actions),
            np.array(rewards),
            np.array(next_states),
            np.array(dones)
        )
    
    def __len__(self):
        return len(self.buffer)


class AmbulanceDQNAgent:
    """DQN Agent for ambulance-aware traffic optimization."""
    
    def __init__(self, state_dim, action_dim, config=None):
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # Default config
        default_config = {
            'learning_rate': 0.0001,
            'gamma': 0.99,
            'epsilon_start': 1.0,
            'epsilon_end': 0.05,
            'epsilon_decay': 0.995,
            'batch_size': 64,
            'target_update_freq': 10,
            'hidden_dim': 256,
        }
        self.config = {**default_config, **(config or {})}
        
        # Networks
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.policy_net = DQNNetwork(state_dim, action_dim, self.config['hidden_dim']).to(self.device)
        self.target_net = DQNNetwork(state_dim, action_dim, self.config['hidden_dim']).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()
        
        # Optimizer
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=self.config['learning_rate'])
        
        # Replay buffer
        self.replay_buffer = ReplayBuffer(capacity=50000)
        
        # Training state
        self.epsilon = self.config['epsilon_start']
        self.steps_done = 0
    
    def select_action(self, state, training=True):
        """Select action using epsilon-greedy policy."""
        if training and random.random() < self.epsilon:
            # Random exploration
            return random.randrange(self.action_dim)
        else:
            # Greedy exploitation
            with torch.no_grad():
                state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
                q_values = self.policy_net(state_tensor)
                return q_values.argmax(1).item()
    
    def update(self):
        """Perform one step of DQN training."""
        if len(self.replay_buffer) < self.config['batch_size']:
            return 0.0
        
        # Sample batch
        states, actions, rewards, next_states, dones = self.replay_buffer.sample(self.config['batch_size'])
        
        # Convert to tensors
        states = torch.FloatTensor(states).to(self.device)
        actions = torch.LongTensor(actions).to(self.device)
        rewards = torch.FloatTensor(rewards).to(self.device)
        next_states = torch.FloatTensor(next_states).to(self.device)
        dones = torch.FloatTensor(dones).to(self.device)
        
        # Compute current Q values
        current_q_values = self.policy_net(states).gather(1, actions.unsqueeze(1))
        
        # Compute target Q values
        with torch.no_grad():
            next_q_values = self.target_net(next_states).max(1)[0]
            target_q_values = rewards + (1 - dones) * self.config['gamma'] * next_q_values
        
        # Compute loss
        loss = nn.MSELoss()(current_q_values.squeeze(), target_q_values)
        
        # Optimize
        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), 10.0)
        self.optimizer.step()
        
        return loss.item()
    
    def decay_epsilon(self):
        """Decay exploration rate."""
        self.epsilon = max(self.config['epsilon_end'], self.epsilon * self.config['epsilon_decay'])
    
    def update_target_network(self):
        """Update target network with policy network weights."""
        self.target_net.load_state_dict(self.policy_net.state_dict())
    
    def save(self, path):
        """Save agent."""
        torch.save({
            'policy_net': self.policy_net.state_dict(),
            'target_net': self.target_net.state_dict(),
            'optimizer': self.optimizer.state_dict(),
            'epsilon': self.epsilon,
            'steps_done': self.steps_done,
        }, path)
        print(f"Agent saved to {path}")
    
    def load(self, path):
        """Load agent."""
        checkpoint = torch.load(path, map_location=self.device)
        self.policy_net.load_state_dict(checkpoint['policy_net'])
        self.target_net.load_state_dict(checkpoint['target_net'])
        self.optimizer.load_state_dict(checkpoint['optimizer'])
        self.epsilon = checkpoint.get('epsilon', self.config['epsilon_end'])
        self.steps_done = checkpoint.get('steps_done', 0)
        print(f"Agent loaded from {path}")


def connect_to_sumo(config_path=None, use_gui=False):
    """Connect to SUMO."""
    try:
        traci.close()
    except:
        pass
    
    # Auto-detect config path if not provided
    if config_path is None:
        # Try to find config relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths = [
            os.path.join(script_dir, '..', 'sumo_simulation', 'simulation.sumocfg'),
            os.path.join(script_dir, '..', 'sumo_simulation', 'working_simulation.sumocfg'),
            'sumo_simulation/simulation.sumocfg',
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                config_path = path
                break
        
        if config_path is None:
            raise FileNotFoundError("Could not find SUMO config file. Please specify --config-path")
    
    sumo_binary = "sumo-gui" if use_gui else "sumo"
    
    # Start SUMO with proper flags
    traci.start([
        sumo_binary, 
        "-c", config_path, 
        "--start",
        "--quit-on-end",
        "--no-warnings",
        "--time-to-teleport", "300"
    ])
    return True


def train_ambulance_agent(
    num_episodes=500,
    max_steps_per_episode=1000,
    save_freq=50,
    model_dir='rl_module/models',
    use_gui=False
):
    """Train ambulance-aware RL agent."""
    
    print("="*80)
    print("AMBULANCE-AWARE RL TRAINING")
    print("="*80)
    
    # Create model directory
    os.makedirs(model_dir, exist_ok=True)
    
    # Environment config
    env_config = {
        'beta': 10,
        'action_spec': {
            'J2': ['rrrGGG', 'rrryyy', 'GGGrrr', 'yyyrrr'],
            'J3': ['rrrGGG', 'rrryyy', 'GGGrrr', 'yyyrrr'],
        },
        'tl_constraint_min': 5,
        'tl_constraint_max': 60,
        'sim_step': 1.0,
        'algorithm': 'DQN',
        'horizon': max_steps_per_episode,
        'ambulance_spawn_prob': 0.15,  # 15% of episodes have ambulances (start conservative)
    }
    
    # Initialize environment
    env = AmbulanceAwareVANETEnv(config=env_config)
    
    state_dim = env.observation_space.shape[0]
    action_dim = env.action_space.n
    
    print(f"\nEnvironment Setup:")
    print(f"  State dimension: {state_dim}")
    print(f"  Action dimension: {action_dim}")
    print(f"  Ambulance spawn probability: {env_config['ambulance_spawn_prob']}")
    
    # Initialize agent
    agent = AmbulanceDQNAgent(state_dim, action_dim)
    
    print(f"\nAgent Setup:")
    print(f"  Device: {agent.device}")
    print(f"  Learning rate: {agent.config['learning_rate']}")
    print(f"  Epsilon: {agent.epsilon:.3f}")
    
    # Training metrics
    episode_rewards = []
    episode_losses = []
    ambulance_episodes = []
    ambulance_clearance_times = []
    
    # Training loop
    print(f"\nStarting training for {num_episodes} episodes...")
    print("="*80)
    
    for episode in range(num_episodes):
        # Connect to SUMO for this episode
        try:
            show_gui = use_gui and (episode % 20 == 0)
            if not connect_to_sumo(use_gui=show_gui):
                print(f"Failed to connect to SUMO for episode {episode}")
                continue
        except Exception as e:
            print(f"SUMO connection error in episode {episode}: {e}")
            continue
        
        # Reset environment
        state, _ = env.reset()
        episode_reward = 0
        episode_loss = []
        
        for step in range(max_steps_per_episode):
            # Select action
            action = agent.select_action(state, training=True)
            
            # Step environment
            next_state, reward, done, truncated, info = env.step(action)
            
            # Store transition
            agent.replay_buffer.push(state, action, reward, next_state, done or truncated)
            
            # Update agent
            loss = agent.update()
            if loss > 0:
                episode_loss.append(loss)
            
            # Update state
            state = next_state
            episode_reward += reward
            agent.steps_done += 1
            
            if done or truncated:
                break
        
        # Close SUMO
        try:
            traci.close()
        except:
            pass
        
        # Decay epsilon
        agent.decay_epsilon()
        
        # Update target network
        if episode % agent.config['target_update_freq'] == 0:
            agent.update_target_network()
        
        # Record metrics
        episode_rewards.append(episode_reward)
        avg_loss = np.mean(episode_loss) if episode_loss else 0.0
        episode_losses.append(avg_loss)
        
        # Track ambulance episodes
        if info.get('ambulance_active'):
            ambulance_episodes.append(episode)
            if info.get('ambulance_cleared'):
                clearance_time = step  # Simplified
                ambulance_clearance_times.append(clearance_time)
        
        # Print progress
        if (episode + 1) % 10 == 0:
            avg_reward_10 = np.mean(episode_rewards[-10:])
            avg_loss_10 = np.mean(episode_losses[-10:])
            print(f"Episode {episode + 1}/{num_episodes} | "
                  f"Avg Reward: {avg_reward_10:.2f} | "
                  f"Avg Loss: {avg_loss_10:.4f} | "
                  f"Epsilon: {agent.epsilon:.3f} | "
                  f"Ambulances: {len(ambulance_episodes)}")
        
        # Save checkpoint
        if (episode + 1) % save_freq == 0:
            checkpoint_path = os.path.join(model_dir, f'ambulance_dqn_ep{episode+1}.pth')
            agent.save(checkpoint_path)
    
    # Save final model
    final_path = os.path.join(model_dir, 'ambulance_dqn_final.pth')
    agent.save(final_path)
    
    # Save training metrics
    metrics = {
        'episode_rewards': episode_rewards,
        'episode_losses': episode_losses,
        'ambulance_episodes': ambulance_episodes,
        'ambulance_clearance_times': ambulance_clearance_times,
        'config': env_config,
        'final_epsilon': agent.epsilon,
    }
    
    metrics_path = os.path.join(model_dir, 'ambulance_training_metrics.json')
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    
    print("\n" + "="*80)
    print("TRAINING COMPLETE")
    print("="*80)
    print(f"Final model saved to: {final_path}")
    print(f"Metrics saved to: {metrics_path}")
    print(f"Total episodes: {num_episodes}")
    print(f"Ambulance episodes: {len(ambulance_episodes)} ({len(ambulance_episodes)/num_episodes*100:.1f}%)")
    if ambulance_clearance_times:
        print(f"Avg ambulance clearance time: {np.mean(ambulance_clearance_times):.1f} steps")
    print(f"Final epsilon: {agent.epsilon:.3f}")
    print(f"Avg reward (last 100): {np.mean(episode_rewards[-100:]):.2f}")
    
    return agent, metrics


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Train ambulance-aware RL agent')
    parser.add_argument('--episodes', type=int, default=500, help='Number of training episodes')
    parser.add_argument('--steps', type=int, default=1000, help='Max steps per episode')
    parser.add_argument('--save-freq', type=int, default=50, help='Save checkpoint every N episodes')
    parser.add_argument('--gui', action='store_true', help='Show SUMO GUI periodically')
    parser.add_argument('--model-dir', type=str, default='rl_module/models', help='Model save directory')
    parser.add_argument('--test', action='store_true', help='Run quick test (5 episodes)')
    
    args = parser.parse_args()
    
    # Quick test mode
    if args.test:
        print("\n" + "="*80)
        print("RUNNING QUICK TEST (5 episodes)")
        print("="*80)
        args.episodes = 5
        args.steps = 200
        args.save_freq = 2
        args.gui = True
    
    # Check SUMO availability
    print("\nChecking SUMO installation...")
    try:
        import subprocess
        result = subprocess.run(['sumo', '--version'], capture_output=True, text=True)
        print(f"✓ SUMO found: {result.stdout.strip()}")
    except FileNotFoundError:
        print("✗ SUMO not found in PATH!")
        print("  Please install SUMO and add it to your PATH")
        print("  Visit: https://sumo.dlr.de/docs/Installing/index.html")
        sys.exit(1)
    
    # Train agent
    try:
        agent, metrics = train_ambulance_agent(
            num_episodes=args.episodes,
            max_steps_per_episode=args.steps,
            save_freq=args.save_freq,
            model_dir=args.model_dir,
            use_gui=args.gui
        )
        
        print("\nTraining script finished successfully!")
        print(f"\n✓ Model saved to: {args.model_dir}/ambulance_dqn_final.pth")
        print(f"✓ Ready for fog integration!")
        
    except KeyboardInterrupt:
        print("\n\nTraining interrupted by user")
        print("Partial models may be saved in checkpoints")
    except Exception as e:
        print(f"\n\nTraining failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
