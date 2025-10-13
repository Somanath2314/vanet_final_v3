#!/usr/bin/env python3
"""
RL API Usage Example
Demonstrates how to control RL traffic optimization via REST API
"""

import requests
import time
import json


BASE_URL = "http://localhost:5000"


def check_server():
    """Check if server is running"""
    try:
        response = requests.get(f"{BASE_URL}/")
        return response.status_code == 200
    except:
        return False


def start_simulation():
    """Start the traffic simulation"""
    print("Starting simulation...")
    
    data = {
        "config_path": "../sumo_simulation/simulation.sumocfg",
        "steps": 3600
    }
    
    response = requests.post(f"{BASE_URL}/api/control/start", json=data)
    
    if response.status_code == 200:
        print("✓ Simulation started")
        return True
    else:
        print(f"✗ Failed to start simulation: {response.json()}")
        return False


def enable_rl_mode():
    """Enable RL-based traffic control"""
    print("\nEnabling RL mode...")
    
    data = {
        "mode": "inference",
        "config": {
            "beta": 20,
            "algorithm": "DQN",
            "tl_constraint_min": 5,
            "tl_constraint_max": 60,
            "horizon": 1000
        }
    }
    
    response = requests.post(f"{BASE_URL}/api/rl/enable", json=data)
    
    if response.status_code == 200:
        result = response.json()
        print("✓ RL mode enabled")
        print(f"  Algorithm: {result.get('mode')}")
        print(f"  Traffic lights: {len(result.get('config', {}).get('action_spec', {}))}")
        return True
    else:
        print(f"✗ Failed to enable RL mode: {response.json()}")
        return False


def get_rl_status():
    """Get RL controller status"""
    response = requests.get(f"{BASE_URL}/api/rl/status")
    
    if response.status_code == 200:
        return response.json()
    else:
        return None


def get_rl_metrics():
    """Get RL metrics"""
    response = requests.get(f"{BASE_URL}/api/rl/metrics")
    
    if response.status_code == 200:
        return response.json()
    else:
        return None


def monitor_rl_performance(duration=60):
    """Monitor RL performance for specified duration"""
    print(f"\nMonitoring RL performance for {duration} seconds...")
    print("=" * 70)
    
    start_time = time.time()
    
    while time.time() - start_time < duration:
        # Get current status
        status = get_rl_status()
        
        if status and status.get('enabled'):
            metrics = status.get('metrics', {})
            
            print(f"\rEpisode Reward: {metrics.get('current_episode_reward', 0):8.2f} | "
                  f"Episode Length: {metrics.get('current_episode_length', 0):4d} | "
                  f"Total Episodes: {metrics.get('total_episodes', 0):3d}", 
                  end='', flush=True)
        
        time.sleep(2)
    
    print("\n" + "=" * 70)


def get_final_metrics():
    """Get and display final metrics"""
    print("\nFinal Metrics:")
    print("=" * 70)
    
    # RL metrics
    rl_metrics = get_rl_metrics()
    if rl_metrics:
        current = rl_metrics.get('current', {})
        print("\nRL Performance:")
        print(f"  Total episodes: {current.get('total_episodes', 0)}")
        print(f"  Average episode reward: {current.get('avg_episode_reward', 0):.2f}")
        print(f"  Average episode length: {current.get('avg_episode_length', 0):.0f}")
    
    # Traffic metrics
    response = requests.get(f"{BASE_URL}/api/traffic/metrics")
    if response.status_code == 200:
        traffic_metrics = response.json()
        print("\nTraffic Performance:")
        print(f"  Total records: {traffic_metrics.get('total_records', 0)}")
        print(f"  Average vehicles: {traffic_metrics.get('avg_vehicles', 0):.2f}")
        print(f"  Emergency events: {traffic_metrics.get('emergency_events', 0)}")


def disable_rl_mode():
    """Disable RL mode"""
    print("\nDisabling RL mode...")
    
    response = requests.post(f"{BASE_URL}/api/rl/disable")
    
    if response.status_code == 200:
        print("✓ RL mode disabled")
        return True
    else:
        print(f"✗ Failed to disable RL mode: {response.json()}")
        return False


def stop_simulation():
    """Stop the simulation"""
    print("\nStopping simulation...")
    
    response = requests.post(f"{BASE_URL}/api/control/stop")
    
    if response.status_code == 200:
        print("✓ Simulation stopped")
        return True
    else:
        print(f"✗ Failed to stop simulation: {response.json()}")
        return False


def main():
    """Main function"""
    print("=" * 70)
    print("RL Traffic Optimization API Example")
    print("=" * 70)
    
    # Check if server is running
    if not check_server():
        print("\n✗ Server is not running!")
        print("Please start the server with: cd backend && python app.py")
        return
    
    print("✓ Server is running\n")
    
    try:
        # Start simulation
        if not start_simulation():
            return
        
        # Wait for simulation to initialize
        print("Waiting for simulation to initialize...")
        time.sleep(3)
        
        # Enable RL mode
        if not enable_rl_mode():
            stop_simulation()
            return
        
        # Wait for RL to initialize
        time.sleep(2)
        
        # Monitor performance
        monitor_rl_performance(duration=30)
        
        # Get final metrics
        get_final_metrics()
        
        # Cleanup
        disable_rl_mode()
        stop_simulation()
        
        print("\n✓ Example completed successfully")
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        disable_rl_mode()
        stop_simulation()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
