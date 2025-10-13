"""
RL-Enhanced Traffic Controller
Integrates RL agent with existing VANET traffic controller
"""

import sys
import os
import numpy as np
import traci
from collections import OrderedDict

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from .vanet_env import VANETTrafficEnv


class RLTrafficController:
    """
    Traffic controller that uses RL agent for traffic light optimization.
    Can work in training or inference mode.
    """
    
    def __init__(self, mode='inference', model_path=None, config=None):
        """
        Initialize RL Traffic Controller.
        
        Parameters
        ----------
        mode : str
            'training' or 'inference'
        model_path : str
            Path to saved model (for inference mode)
        config : dict
            Configuration for RL environment
        """
        self.mode = mode
        self.model_path = model_path
        self.config = config or {}
        
        # Initialize environment
        self.env = None
        self.agent = None
        self.current_state = None
        
        # Metrics tracking
        self.episode_rewards = []
        self.episode_lengths = []
        self.current_episode_reward = 0
        self.current_episode_length = 0
        
    def initialize(self, sumo_connected=True):
        """Initialize the RL controller after SUMO is connected."""
        if not sumo_connected:
            print("Warning: SUMO not connected. RL controller initialization skipped.")
            return False
        
        try:
            # Auto-detect traffic lights from SUMO
            tl_ids = traci.trafficlight.getIDList()
            
            if not tl_ids:
                print("No traffic lights found in SUMO simulation")
                return False
            
            # Build action spec from detected traffic lights
            action_spec = OrderedDict()
            for tl_id in tl_ids:
                try:
                    # Get current state to determine format
                    current_state = traci.trafficlight.getRedYellowGreenState(tl_id)
                    
                    # Create simple two-phase system (all green vs all red alternating)
                    # This can be customized based on intersection geometry
                    green_state = current_state
                    red_state = 'r' * len(current_state)
                    
                    action_spec[tl_id] = [green_state, red_state]
                except Exception as e:
                    print(f"Error processing traffic light {tl_id}: {e}")
            
            # Update config with detected action spec
            self.config['action_spec'] = action_spec
            
            # Set default values if not provided
            if 'beta' not in self.config:
                self.config['beta'] = 20  # Observe up to 20 vehicles
            if 'algorithm' not in self.config:
                self.config['algorithm'] = 'DQN'
            
            # Create environment
            self.env = VANETTrafficEnv(config=self.config)
            
            print(f"RL Controller initialized with {len(action_spec)} traffic lights")
            print(f"Action space: {self.env.action_space}")
            print(f"Observation space: {self.env.observation_space}")
            
            return True
            
        except Exception as e:
            print(f"Error initializing RL controller: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def load_model(self, model_path=None):
        """Load a trained RL model."""
        path = model_path or self.model_path
        
        if not path:
            print("No model path provided")
            return False
        
        try:
            # TODO: Implement model loading based on algorithm
            # This will depend on whether using Ray RLlib, stable-baselines3, etc.
            print(f"Loading model from {path}")
            # self.agent = load_trained_agent(path)
            return True
        except Exception as e:
            print(f"Error loading model: {e}")
            return False
    
    def get_action(self, state=None):
        """
        Get action from RL agent or random policy.
        
        Parameters
        ----------
        state : np.array
            Current state observation
            
        Returns
        -------
        action : int or np.array
            Action to take
        """
        if state is None:
            state = self.current_state
        
        if state is None:
            # Return random action
            return self.env.action_space.sample()
        
        if self.agent is not None:
            # Use trained agent
            action = self.agent.compute_action(state)
        else:
            # Random policy (for testing or initial training)
            action = self.env.action_space.sample()
        
        return action
    
    def step(self):
        """
        Execute one step of RL control.
        
        Returns
        -------
        metrics : dict
            Step metrics including reward, state info, etc.
        """
        if self.env is None:
            return {'error': 'Environment not initialized'}
        
        try:
            # Get current state
            if self.current_state is None:
                self.current_state = self.env.reset()
            
            # Get action
            action = self.get_action(self.current_state)
            
            # Execute action
            next_state, reward, done, info = self.env.step(action)
            
            # Update tracking
            self.current_episode_reward += reward
            self.current_episode_length += 1
            
            # Update state
            self.current_state = next_state
            
            # Handle episode end
            if done:
                self.episode_rewards.append(self.current_episode_reward)
                self.episode_lengths.append(self.current_episode_length)
                
                # Reset for next episode
                self.current_state = self.env.reset()
                self.current_episode_reward = 0
                self.current_episode_length = 0
            
            # Return metrics
            metrics = {
                'reward': float(reward),
                'episode_reward': float(self.current_episode_reward),
                'done': done,
                'mean_speed': info.get('mean_speed', 0),
                'mean_emission': info.get('mean_emission', 0),
                'action': int(action) if isinstance(action, (int, np.integer)) else action.tolist(),
            }
            
            return metrics
            
        except Exception as e:
            print(f"Error in RL step: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e)}
    
    def get_metrics(self):
        """Get current RL metrics."""
        return {
            'mode': self.mode,
            'current_episode_reward': float(self.current_episode_reward),
            'current_episode_length': int(self.current_episode_length),
            'total_episodes': len(self.episode_rewards),
            'avg_episode_reward': float(np.mean(self.episode_rewards)) if self.episode_rewards else 0,
            'avg_episode_length': float(np.mean(self.episode_lengths)) if self.episode_lengths else 0,
        }
    
    def reset(self):
        """Reset the RL controller."""
        if self.env:
            self.current_state = self.env.reset()
            self.current_episode_reward = 0
            self.current_episode_length = 0
    
    def close(self):
        """Close the RL controller."""
        if self.env:
            self.env.close()
