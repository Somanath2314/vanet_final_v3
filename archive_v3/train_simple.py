"""
Simple RL Training Script (without Ray)
Trains DQN agent for traffic control
"""

import sys
import os
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from collections import deque
import random

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from rl_module.vanet_env import VANETTrafficEnv


class DQNNetwork(nn.Module):
    """Simple DQN network"""
    
    def __init__(self, state_dim, action_dim, hidden_dim=128):
        super(DQNNetwork, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, action_dim)
        )
    
    def forward(self, x):
        return self.network(x)


class SimpleDQNAgent:
    """Simple DQN agent for training"""
    
    def __init__(self, state_dim, action_dim, learning_rate=0.001):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Networks
        self.policy_net = DQNNetwork(state_dim, action_dim).to(self.device)
        self.target_net = DQNNetwork(state_dim, action_dim).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        
        # Optimizer
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=learning_rate)
        
        # Replay buffer
        self.memory = deque(maxlen=10000)
        self.batch_size = 64
        
        # Hyperparameters
        self.gamma = 0.99
        self.epsilon = 1.0
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995
        
    def select_action(self, state, training=True):
        """Select action using epsilon-greedy policy"""
        if training and random.random() < self.epsilon:
            return random.randrange(self.action_dim)
        
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_values = self.policy_net(state_tensor)
            return q_values.argmax().item()
    
    def store_transition(self, state, action, reward, next_state, done):
        """Store transition in replay buffer"""
        self.memory.append((state, action, reward, next_state, done))
    
    def train_step(self):
        """Perform one training step"""
        if len(self.memory) < self.batch_size:
            return 0.0
        
        # Sample batch
        batch = random.sample(self.memory, self.batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)
        
        # Convert to tensors
        states = torch.FloatTensor(states).to(self.device)
        actions = torch.LongTensor(actions).to(self.device)
        rewards = torch.FloatTensor(rewards).to(self.device)
        next_states = torch.FloatTensor(next_states).to(self.device)
        dones = torch.FloatTensor(dones).to(self.device)
        
        # Compute Q values
        current_q = self.policy_net(states).gather(1, actions.unsqueeze(1))
        
        # Compute target Q values
        with torch.no_grad():
            next_q = self.target_net(next_states).max(1)[0]
            target_q = rewards + (1 - dones) * self.gamma * next_q
        
        # Compute loss
        loss = nn.MSELoss()(current_q.squeeze(), target_q)
        
        # Optimize
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        return loss.item()
    
    def update_target_network(self):
        """Update target network"""
        self.target_net.load_state_dict(self.policy_net.state_dict())
    
    def decay_epsilon(self):
        """Decay exploration rate"""
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
    
    def save(self, path):
        """Save model"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save({
            'policy_net': self.policy_net.state_dict(),
            'target_net': self.target_net.state_dict(),
            'optimizer': self.optimizer.state_dict(),
            'epsilon': self.epsilon
        }, path)
        print(f"Model saved to {path}")
    
    def load(self, path):
        """Load model"""
        checkpoint = torch.load(path, map_location=self.device)
        self.policy_net.load_state_dict(checkpoint['policy_net'])
        self.target_net.load_state_dict(checkpoint['target_net'])
        self.optimizer.load_state_dict(checkpoint['optimizer'])
        self.epsilon = checkpoint['epsilon']
        print(f"Model loaded from {path}")


def train_dqn(episodes=100, max_steps=1000):
    """Train DQN agent"""
    
    print("=" * 60)
    print("Simple DQN Training for Traffic Control")
    print("=" * 60)
    print()
    
    # Configuration
    config_path = os.path.join(os.path.dirname(__file__), '..', 'sumo_simulation', 'simulation.sumocfg')
    
    # Start SUMO
    import traci
    import sumolib
    
    print("Starting SUMO...")
    sumo_binary = sumolib.checkBinary('sumo')  # Use sumo (no GUI) for training
    sumo_cmd = [sumo_binary, "-c", config_path, "--start", "--quit-on-end"]
    
    traci.start(sumo_cmd)
    
    # Get traffic light IDs
    tl_ids = traci.trafficlight.getIDList()
    print(f"Found traffic lights: {tl_ids}")
    
    # Create action spec
    action_spec = {}
    for tl_id in tl_ids:
        logic = traci.trafficlight.getAllProgramLogics(tl_id)[0]
        phases = [phase.state for phase in logic.phases]
        action_spec[tl_id] = phases
    
    print(f"Action spec: {len(action_spec)} intersections")
    
    # Create environment config
    env_config = {
        'beta': 10,
        'action_spec': action_spec,
        'tl_constraint_min': 5,
        'tl_constraint_max': 60,
        'sim_step': 1.0,
        'algorithm': 'DQN',
        'horizon': max_steps,
    }
    
    # Create environment
    print("Creating environment...")
    env = VANETTrafficEnv(config=env_config)
    
    # Get dimensions
    state_dim = env.observation_space.shape[0]
    action_dim = env.action_space.n
    
    print(f"State dimension: {state_dim}")
    print(f"Action dimension: {action_dim}")
    print()
    
    # Create agent
    agent = SimpleDQNAgent(state_dim, action_dim)
    
    # Training loop
    best_reward = -float('inf')
    episode_rewards = []
    
    for episode in range(episodes):
        # Restart SUMO for each episode
        traci.close()
        traci.start(sumo_cmd)
        
        reset_result = env.reset()
        if len(reset_result) == 2:
            # Gymnasium API
            state, _ = reset_result
        else:
            # Old gym API or single return
            state = reset_result
        episode_reward = 0
        losses = []
        
        for step in range(max_steps):
            # Select action
            action = agent.select_action(state, training=True)
            
            # Take step
            step_result = env.step(action)
            if len(step_result) == 5:
                # Gymnasium API
                next_state, reward, terminated, truncated, info = step_result
                done = terminated or truncated
            else:
                # Old gym API
                next_state, reward, done, info = step_result
            
            # Store transition
            agent.store_transition(state, action, reward, next_state, done)
            
            # Train
            loss = agent.train_step()
            if loss > 0:
                losses.append(loss)
            
            episode_reward += reward
            state = next_state
            
            if done:
                break
        
        # Update target network every 10 episodes
        if episode % 10 == 0:
            agent.update_target_network()
        
        # Decay epsilon
        agent.decay_epsilon()
        
        # Track rewards
        episode_rewards.append(episode_reward)
        avg_loss = np.mean(losses) if losses else 0
        
        # Print progress
        if episode % 5 == 0:
            avg_reward = np.mean(episode_rewards[-10:])
            print(f"Episode {episode}/{episodes}")
            print(f"  Reward: {episode_reward:.2f} | Avg(10): {avg_reward:.2f}")
            print(f"  Loss: {avg_loss:.4f} | Epsilon: {agent.epsilon:.3f}")
            print()
        
        # Save best model
        if episode_reward > best_reward:
            best_reward = episode_reward
            agent.save('models/dqn_traffic_model.pth')
    
    # Save final model
    agent.save('models/dqn_traffic_final.pth')
    
    print("=" * 60)
    print("Training completed!")
    print(f"Best reward: {best_reward:.2f}")
    print(f"Final epsilon: {agent.epsilon:.3f}")
    print("=" * 60)
    
    # Close SUMO
    traci.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Train DQN agent for traffic control')
    parser.add_argument('--episodes', type=int, default=100, help='Number of episodes')
    parser.add_argument('--steps', type=int, default=1000, help='Max steps per episode')
    
    args = parser.parse_args()
    
    train_dqn(episodes=args.episodes, max_steps=args.steps)
