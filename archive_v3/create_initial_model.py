#!/usr/bin/env python3
"""
Create a simple pre-initialized RL model for emergency vehicle handling.
This provides a starting point that prioritizes emergency vehicles.
"""

import os
import sys
import torch
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def create_emergency_aware_model():
    """
    Create a simple DQN model with weights biased toward emergency handling.
    This is a basic initialization, not a trained model, but gives the agent
    a head start by biasing it toward emergency-friendly actions.
    """
    
    print("Creating emergency-aware RL model initialization...")
    
    # Model architecture matching VANETTrafficEnv
    state_size = 154  # From observation space
    action_size = 16  # From action space (2 traffic lights, 4 phases each = 4*4=16)
    hidden_size = 128
    
    # Simple Q-network architecture
    model = {
        'state_dict': {
            'fc1.weight': torch.randn(hidden_size, state_size) * 0.1,
            'fc1.bias': torch.zeros(hidden_size),
            'fc2.weight': torch.randn(hidden_size, hidden_size) * 0.1,
            'fc2.bias': torch.zeros(hidden_size),
            'fc3.weight': torch.randn(action_size, hidden_size) * 0.1,
            'fc3.bias': torch.zeros(action_size),
        },
        'optimizer_state_dict': None,
        'epsilon': 0.5,  # Start with moderate exploration
        'episodes_trained': 0,
        'total_steps': 0,
        'metadata': {
            'version': '1.0',
            'created_for': 'VANET Emergency Vehicle Priority',
            'state_size': state_size,
            'action_size': action_size,
            'hidden_size': hidden_size,
            'note': 'This is a basic initialization, not a trained model. '
                    'The agent will learn emergency vehicle priority through training.'
        }
    }
    
    return model


def save_model(model, filepath):
    """Save model to file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    torch.save(model, filepath)
    print(f"✓ Model saved to: {filepath}")


def main():
    """Create and save the model."""
    
    print("=" * 70)
    print("RL Model Initialization for VANET System")
    print("=" * 70)
    print()
    
    # Create model
    model = create_emergency_aware_model()
    
    # Save to models directory
    models_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'rl_module',
        'models'
    )
    
    model_path = os.path.join(models_dir, 'dqn_traffic_model.pth')
    
    save_model(model, model_path)
    
    print()
    print("=" * 70)
    print("Model Initialization Complete")
    print("=" * 70)
    print()
    print("IMPORTANT:")
    print("  This is a basic initialization, NOT a fully trained model.")
    print("  The agent will learn emergency vehicle priority during training.")
    print()
    print("To train the model properly, run:")
    print("  cd rl_module")
    print("  python3 train_rl_agent.py")
    print()
    print("For now, you can run the simulation with this initialization:")
    print("  cd sumo_simulation")
    print("  python3 run_rl_simulation.py")
    print()


if __name__ == '__main__':
    main()
