#!/usr/bin/env python3
"""
Check RL training progress
Shows metrics and model checkpoints
"""

import os
import json
import glob

def check_training_progress():
    """Check current training progress."""
    print("="*80)
    print("RL TRAINING PROGRESS CHECK")
    print("="*80)
    
    model_dir = 'rl_module/models'
    
    # Check if model directory exists
    if not os.path.exists(model_dir):
        print(f"\n❌ Model directory not found: {model_dir}")
        print("   Training has not started yet.")
        return
    
    # List model checkpoints
    checkpoints = glob.glob(os.path.join(model_dir, '*.pth'))
    if checkpoints:
        print(f"\n✓ Found {len(checkpoints)} model checkpoint(s):")
        for cp in sorted(checkpoints):
            size_mb = os.path.getsize(cp) / (1024 * 1024)
            print(f"  - {os.path.basename(cp)} ({size_mb:.2f} MB)")
    else:
        print(f"\n⚠️  No model checkpoints found in {model_dir}")
        print("   Training may be in progress...")
    
    # Check training metrics
    metrics_path = os.path.join(model_dir, 'ambulance_training_metrics.json')
    if os.path.exists(metrics_path):
        print(f"\n✓ Training metrics found")
        try:
            with open(metrics_path, 'r') as f:
                metrics = json.load(f)
            
            print(f"\n  Training Statistics:")
            print(f"  - Total episodes: {len(metrics.get('episode_rewards', []))}")
            print(f"  - Ambulance episodes: {len(metrics.get('ambulance_episodes', []))}")
            
            rewards = metrics.get('episode_rewards', [])
            if rewards:
                print(f"  - Avg reward (last 100): {sum(rewards[-100:]) / len(rewards[-100:]):.2f}")
                print(f"  - Best reward: {max(rewards):.2f}")
            
            clearance = metrics.get('ambulance_clearance_times', [])
            if clearance:
                print(f"  - Avg ambulance clearance: {sum(clearance) / len(clearance):.1f} steps")
            
            print(f"  - Final epsilon: {metrics.get('final_epsilon', 'N/A')}")
            
        except Exception as e:
            print(f"  Error reading metrics: {e}")
    else:
        print(f"\n⚠️  No metrics file found")
        print("   Training is likely still in progress")
    
    # Check for final model
    final_model = os.path.join(model_dir, 'ambulance_dqn_final.pth')
    if os.path.exists(final_model):
        print(f"\n✅ TRAINING COMPLETE!")
        print(f"   Final model: {final_model}")
        size_mb = os.path.getsize(final_model) / (1024 * 1024)
        print(f"   Size: {size_mb:.2f} MB")
    else:
        print(f"\n⏳ Training in progress...")
        print(f"   Final model will be saved to: {final_model}")
    
    print("\n" + "="*80)

if __name__ == '__main__':
    check_training_progress()
