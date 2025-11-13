"""
Live Metrics Bridge - Connects SUMO simulation to Flask API
Uses shared file for inter-process communication between simulation and web server
"""
import json
import os
import time
from threading import Lock

class LiveMetricsBridge:
    """Manages live metrics from running SUMO simulation"""
    
    def __init__(self, metrics_file='live_metrics.json'):
        self.metrics_file = metrics_file
        self.lock = Lock()
        
    def write_metrics(self, metrics):
        """Write metrics from simulation (called by SUMO process)"""
        with self.lock:
            try:
                with open(self.metrics_file, 'w') as f:
                    json.dump({
                        'timestamp': time.time(),
                        'metrics': metrics
                    }, f)
            except Exception as e:
                print(f"Warning: Failed to write live metrics: {e}")
    
    def read_metrics(self):
        """Read metrics for API (called by Flask server)"""
        with self.lock:
            try:
                if not os.path.exists(self.metrics_file):
                    return None
                
                # Check if file is recent (updated within last 5 seconds)
                file_age = time.time() - os.path.getmtime(self.metrics_file)
                if file_age > 5:
                    return None  # Simulation not actively running
                
                with open(self.metrics_file, 'r') as f:
                    data = json.load(f)
                    return data.get('metrics')
            except Exception as e:
                return None
    
    def is_simulation_running(self):
        """Check if simulation is actively running"""
        if not os.path.exists(self.metrics_file):
            return False
        file_age = time.time() - os.path.getmtime(self.metrics_file)
        return file_age < 5  # Updated within last 5 seconds
    
    def cleanup(self):
        """Remove metrics file (called when simulation ends)"""
        try:
            if os.path.exists(self.metrics_file):
                os.remove(self.metrics_file)
        except:
            pass


# Global singleton instance
_bridge = LiveMetricsBridge()

def get_bridge():
    """Get global metrics bridge instance"""
    return _bridge
