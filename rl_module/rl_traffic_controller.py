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

import torch
import torch.nn as nn

from vanet_env import VANETTrafficEnv


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
                    # Get the actual program logic to get all phases
                    logic = traci.trafficlight.getAllProgramLogics(tl_id)[0]
                    phases = [phase.state for phase in logic.phases]

                    print(f"Traffic light {tl_id}: {len(phases)} phases")
                    for i, phase in enumerate(phases):
                        print(f"  Phase {i}: {phase}")

                    action_spec[tl_id] = phases
                except Exception as e:
                    print(f"Error processing traffic light {tl_id}: {e}")
                    # Fallback to simple two-phase system
                    current_state = traci.trafficlight.getRedYellowGreenState(tl_id)
                    green_state = current_state
                    red_state = 'r' * len(current_state)
                    action_spec[tl_id] = [green_state, red_state]
            
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
            # Prefer absolute path
            path = os.path.abspath(path)

            print(f"Loading model from {path}")

            if not os.path.exists(path):
                print(f"Model file not found: {path}")
                return False

            # Ensure environment is initialized so we can infer shapes
            if self.env is None:
                print("Environment not initialized; cannot infer model shapes")
                return False

            # Determine observation and action dimensions
            try:
                obs_shape = self.env.observation_space.shape
                state_dim = int(obs_shape[0])
            except Exception:
                # Fallback: try flattened observation
                state_dim = int(self.env.observation_space.shape[0])

            # Support only discrete action space for now
            if hasattr(self.env.action_space, 'n'):
                action_dim = int(self.env.action_space.n)
            else:
                print("Unsupported action space for loader (only Discrete supported)")
                return False

            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            # Define a compatible network architecture (matches train_simple/train_working)
            class DQNNetwork(nn.Module):
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

            # Wrapper that provides compute_action(state) used by controller
            class LoadedAgent:
                def __init__(self, policy_net, device):
                    self.policy_net = policy_net.to(device)
                    self.device = device
                    self.policy_net.eval()

                def compute_action(self, state):
                    with torch.no_grad():
                        s = torch.FloatTensor(state).unsqueeze(0).to(self.device)
                        q = self.policy_net(s)
                        return int(q.argmax(dim=1).item())

            # Instantiate network and load checkpoint
            net = DQNNetwork(state_dim, action_dim).to(device)

            checkpoint = torch.load(path, map_location=device)

            # Check for common checkpoint structures
            if isinstance(checkpoint, dict) and 'policy_net' in checkpoint:
                net.load_state_dict(checkpoint['policy_net'])
            else:
                # Try loading assuming the file is a state_dict
                try:
                    net.load_state_dict(checkpoint)
                except Exception as e:
                    print(f"Failed to load checkpoint into network: {e}")
                    return False

            # Create loaded agent wrapper and attach
            self.agent = LoadedAgent(net, device)
            print(f"Model loaded and agent created (state_dim={state_dim}, action_dim={action_dim})")
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
                reset_result = self.env.reset()
                if len(reset_result) == 2:
                    # Gymnasium API
                    self.current_state, _ = reset_result
                else:
                    # Gym API or single return
                    self.current_state = reset_result

            # Get action from RL agent
            action = self.get_action(self.current_state)

            # Execute action in environment
            step_result = self.env.step(action)
            if len(step_result) == 5:
                # Gymnasium API
                next_state, reward, terminated, truncated, info = step_result
                done = terminated or truncated
            else:
                # Gym API
                next_state, reward, done, info = step_result

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
                reset_result = self.env.reset()
                if len(reset_result) == 2:
                    # Gymnasium API
                    self.current_state, _ = reset_result
                else:
                    # Gym API or single return
                    self.current_state = reset_result
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
            if len(reset_result) == 2:
                # Gymnasium API
                self.current_state, _ = reset_result
            else:
                # Gym API or single return
                self.current_state = reset_result
            self.current_episode_reward = 0
            self.current_episode_length = 0
    
    def get_state(self):
        """
        Get the current state of the environment.
        
        Returns
        -------
        np.array
            Current state observation
        """
        if self.env is None:
            raise RuntimeError("Environment not initialized")
            
        # Get the current state from the environment
        if hasattr(self.env, 'get_state'):
            return self.env.get_state()
        elif hasattr(self.env, 'state'):
            return self.env.state
        else:
            # Fallback: return a zero state
            return np.zeros(self.env.observation_space.shape)
    
    def apply_action(self, action):
        """
        Apply an action to the traffic lights.
        
        Parameters
        ----------
        action : int or np.array
            Action to apply
        """
        if self.env is None:
            raise RuntimeError("Environment not initialized")
            
        # Convert action to the appropriate format if needed
        if isinstance(action, np.ndarray) and action.size == 1:
            action = action.item()
            
        # Apply the action to the environment
        if hasattr(self.env, 'apply_action'):
            return self.env.apply_action(action)
        else:
            # Fallback: use the step method
            self.env.step(action)
            return True
    
    def run_simulation(self, config_path=None, max_steps=3600):
        """
        Run RL-based simulation.

        Parameters
        ----------
        config_path : str
            Path to SUMO configuration file
        max_steps : int
            Maximum simulation steps
        """
        print("Starting RL-based traffic control simulation...")

        # Import required modules
        import traci
        import sumolib

        # Start SUMO
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), '..', 'sumo_simulation', 'simulation.sumocfg')

        sumo_binary = sumolib.checkBinary('sumo')
        sumo_cmd = [sumo_binary, "-c", config_path, "--start"]

        try:
            traci.start(sumo_cmd)
            print("✓ Connected to SUMO simulation")
        except Exception as e:
            print(f"✗ Error connecting to SUMO: {e}")
            return

        # Initialize RL controller
        if not self.initialize(sumo_connected=True):
            print("✗ Failed to initialize RL controller")
            traci.close()
            return

        # Load model if available
        model_path = os.path.join(os.path.dirname(__file__), 'models', 'dqn_traffic_model.pth')
        if os.path.exists(model_path):
            self.load_model(model_path)
            print(f"✓ Loaded trained model from {model_path}")
        else:
            print("⚠ No trained model found, using random policy")

        # Run simulation loop
        step = 0
        try:
            while step < max_steps and traci.simulation.getMinExpectedNumber() > 0:
                # Execute RL step
                metrics = self.step()

                if 'error' in metrics:
                    print(f"✗ Error in step {step}: {metrics['error']}")
                    break

                # Print progress
                if step % 100 == 0:
                    print(f"Step {step}: Reward={metrics.get('reward', 0):.2f}, "
                          f"Episode Reward={metrics.get('episode_reward', 0):.2f}")

                step += 1

        except KeyboardInterrupt:
            print("\\nSimulation interrupted by user")
        except Exception as e:
            print(f"\\nSimulation error: {e}")
        finally:
            print(f"Simulation completed after {step} steps")
            traci.close()
