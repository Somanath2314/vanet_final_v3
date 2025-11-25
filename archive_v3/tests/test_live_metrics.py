#!/usr/bin/env python3
"""
Test script to simulate live metrics updates
Run this to test the live dashboard without running full SUMO simulation
"""

import time
import random
from live_metrics_bridge import get_bridge

def simulate_live_metrics(duration_seconds=30):
    """Simulate live metrics for testing dashboard"""
    bridge = get_bridge()
    
    print("🚀 Starting live metrics simulation...")
    print(f"📊 Will update metrics every second for {duration_seconds} seconds")
    print("🌐 Open http://localhost:5173/live in your browser")
    print("✨ Status should show 'Live 🔴'\n")
    
    try:
        for i in range(duration_seconds):
            # Simulate varying metrics
            vehicles = random.randint(15, 45)
            wait = random.uniform(1.5, 8.0)
            pdr = random.uniform(88, 99)
            queue = random.randint(0, 6)
            throughput = random.uniform(250, 550)
            emergency = random.randint(0, 4)
            
            metrics = {
                'activeVehicles': vehicles,
                'avgWait': wait,
                'pdr': pdr,
                'queueLength': queue,
                'throughput': throughput,
                'emergencyCount': emergency,
            }
            
            bridge.write_metrics(metrics)
            
            # Print update every 5 seconds
            if i % 5 == 0:
                print(f"[{i:3d}s] Vehicles: {vehicles:2d} | Wait: {wait:4.1f}s | "
                      f"PDR: {pdr:5.1f}% | Queue: {queue} | Emergency: {emergency}")
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n⚠️  Stopped by user")
    finally:
        bridge.cleanup()
        print("\n✅ Cleaned up metrics file")
        print("💡 Dashboard should now show 'Demo' status")

if __name__ == '__main__':
    print("="*70)
    print("Live Metrics Test - Simulating VANET Metrics")
    print("="*70)
    print()
    simulate_live_metrics(30)
