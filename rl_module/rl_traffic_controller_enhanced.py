#!/usr/bin/env python3
"""
Enhanced RL Traffic Controller with Edge Computing & Security Integration
Implements DQN with experience replay for adaptive traffic light control
"""

import os
import sys
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from collections import deque
import random
from typing import List, Tuple, Dict, Any

# Add paths
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


class DQN(nn.Module):
    """Deep Q-Network for traffic control"""
    
    def __init__(self, state_dim: int, action_dim: int, hidden_layers=[256, 256, 128], dropout=0.2):
        super(DQN, self).__init__()
        
        layers = []
        prev_dim = state_dim
        
        for hidden_dim in hidden_layers:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout))
            prev_dim = hidden_dim
        
        layers.append(nn.Linear(prev_dim, action_dim))
        
        self.network = nn.Sequential(*layers)
    
    def forward(self, x):
        return self.network(x)


class ReplayBuffer:
    """Experience replay buffer for DQN"""
    
    def __init__(self, capacity=100000):
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


class RLTrafficController:
    """
    Enhanced Deep Q-Network Traffic Controller
    with Edge Computing and Security Integration
    """
    
    def __init__(self, tl_ids: List[str], edge_enabled=True, security_enabled=True,
                 state_dim=None, action_dim=None, config=None):
        """
        Initialize RL Traffic Controller
        
        Args:
            tl_ids: List of traffic light IDs
            edge_enabled: Enable edge computing features
            security_enabled: Enable security features
            state_dim: State space dimension (auto-calculated if None)
            action_dim: Action space dimension (auto-calculated if None)
            config: Training configuration dictionary
        """
        self.tl_ids = tl_ids
        self.edge_enabled = edge_enabled
        self.security_enabled = security_enabled
        self.config = config or {}
        
        # Calculate dimensions if not provided
        if state_dim is None:
            state_dim = self._calculate_state_dim()
        if action_dim is None:
            action_dim = self._calculate_action_dim()
        
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # Device
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Networks
        network_config = self.config.get('network', {})
        hidden_layers = network_config.get('hidden_layers', [256, 256, 128])
        dropout = network_config.get('dropout', 0.2)
        
        self.policy_net = DQN(state_dim, action_dim, hidden_layers, dropout).to(self.device)
        self.target_net = DQN(state_dim, action_dim, hidden_layers, dropout).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()
        
        # Optimizer
        learning_rate = self.config.get('training', {}).get('learning_rate', 0.0001)
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=learning_rate)
        
        # Replay buffer
        self.memory = ReplayBuffer(capacity=100000)
        
        # Training parameters
        self.gamma = self.config.get('training', {}).get('gamma', 0.99)
        self.epsilon = self.config.get('training', {}).get('epsilon_start', 1.0)
        self.epsilon_min = self.config.get('training', {}).get('epsilon_end', 0.01)
        self.epsilon_decay = self.config.get('training', {}).get('epsilon_decay', 0.995)
        
        # Metrics
        self.train_step_count = 0
        self.episode_count = 0
        
        print(f"✅ RL Controller Initialized:")
        print(f"   - Traffic Lights: {tl_ids}")
        print(f"   - State Dim: {state_dim}")
        print(f"   - Action Dim: {action_dim}")
        print(f"   - Edge Computing: {edge_enabled}")
        print(f"   - Security: {security_enabled}")
        print(f"   - Device: {self.device}")
    
    def _calculate_state_dim(self) -> int:
        """Calculate state dimension based on features"""
        # Base features per TL: queue(4) + wait(4) + phase(4) + time(1) = 13
        base_per_tl = 13
        
        if self.edge_enabled:
            base_per_tl += 4  # warnings, emergencies, load, vehicles
        
        if self.security_enabled:
            base_per_tl += 2  # encrypted ratio, auth failures
        
        return base_per_tl * len(self.tl_ids)
    
    def _calculate_action_dim(self) -> int:
        """Calculate action dimension"""
        # 4 phases per TL, combined actions for all TLs
        return 4 * len(self.tl_ids)
    
    def select_action(self, state: np.ndarray, training=True) -> int:
        """
        Select action using epsilon-greedy policy
        
        Args:
            state: Current state observation
            training: Whether in training mode (uses epsilon-greedy)
            
        Returns:
            action: Selected action
        """
        if training and random.random() < self.epsilon:
            # Explore: random action
            return random.randrange(self.action_dim)
        else:
            # Exploit: best action from Q-network
            with torch.no_grad():
                state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
                q_values = self.policy_net(state_tensor)
                return q_values.argmax().item()
    
    def remember(self, state, action, reward, next_state, done):
        """Store transition in replay buffer"""
        self.memory.push(state, action, reward, next_state, done)
    
    def train_step(self, batch_size=64) -> float:
        """
        Perform one training step
        
        Args:
            batch_size: Batch size for training
            
        Returns:
            loss: Training loss
        """
        if len(self.memory) < batch_size:
            return 0.0
        
        # Sample batch
        states, actions, rewards, next_states, dones = self.memory.sample(batch_size)
        
        # Convert to tensors
        states = torch.FloatTensor(states).to(self.device)
        actions = torch.LongTensor(actions).to(self.device)
        rewards = torch.FloatTensor(rewards).to(self.device)
        next_states = torch.FloatTensor(next_states).to(self.device)
        dones = torch.FloatTensor(dones).to(self.device)
        
        # Current Q values
        current_q = self.policy_net(states).gather(1, actions.unsqueeze(1)).squeeze(1)
        
        # Next Q values (Double DQN)
        with torch.no_grad():
            next_actions = self.policy_net(next_states).argmax(1)
            next_q = self.target_net(next_states).gather(1, next_actions.unsqueeze(1)).squeeze(1)
            target_q = rewards + (1 - dones) * self.gamma * next_q
        
        # Compute loss
        loss = F.smooth_l1_loss(current_q, target_q)
        
        # Optimize
        self.optimizer.zero_grad()
        loss.backward()
        # Clip gradients
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), 1.0)
        self.optimizer.step()
        
        self.train_step_count += 1
        
        return loss.item()
    
    def update_target_network(self):
        """Update target network with policy network weights"""
        self.target_net.load_state_dict(self.policy_net.state_dict())
        print(f"  🔄 Target network updated (step {self.train_step_count})")
    
    def save_model(self, path: str):
        """
        Save model checkpoint
        
        Args:
            path: Path to save model
        """
        checkpoint = {
            'policy_net_state_dict': self.policy_net.state_dict(),
            'target_net_state_dict': self.target_net.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'epsilon': self.epsilon,
            'train_step_count': self.train_step_count,
            'episode_count': self.episode_count,
            'state_dim': self.state_dim,
            'action_dim': self.action_dim,
            'config': self.config
        }
        
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save(checkpoint, path)
        print(f"  💾 Model saved to {path}")
    
    def load_model(self, path: str):
        """
        Load model checkpoint
        
        Args:
            path: Path to load model from
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model file not found: {path}")
        
        checkpoint = torch.load(path, map_location=self.device)
        
        self.policy_net.load_state_dict(checkpoint['policy_net_state_dict'])
        self.target_net.load_state_dict(checkpoint['target_net_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.epsilon = checkpoint.get('epsilon', self.epsilon_min)
        self.train_step_count = checkpoint.get('train_step_count', 0)
        self.episode_count = checkpoint.get('episode_count', 0)
        
        print(f"  ✅ Model loaded from {path}")
        print(f"     - Training steps: {self.train_step_count}")
        print(f"     - Episodes: {self.episode_count}")
        print(f"     - Epsilon: {self.epsilon:.4f}")
    
    def set_eval_mode(self):
        """Set controller to evaluation mode (no exploration)"""
        self.policy_net.eval()
        self.epsilon = 0.0
    
    def set_train_mode(self):
        """Set controller to training mode"""
        self.policy_net.train()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current training metrics"""
        return {
            'train_steps': self.train_step_count,
            'episodes': self.episode_count,
            'epsilon': self.epsilon,
            'memory_size': len(self.memory),
            'state_dim': self.state_dim,
            'action_dim': self.action_dim
        }
