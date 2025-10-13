"""
Flask Backend API for VANET Traffic Management System
Provides REST endpoints for traffic data, control, and monitoring
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import time
import sys
import os
from datetime import datetime
import json

# Add paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'sumo_simulation'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'sumo_simulation', 'sensors'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

# Global variables
traffic_controller = None
rl_controller = None
simulation_thread = None
simulation_running = False
rl_mode_enabled = False

# In-memory storage for metrics (later replace with MongoDB)
metrics_history = []
current_metrics = {}
rl_metrics_history = []

@app.route('/')
def home():
    """Home endpoint"""
    return jsonify({
        "message": "VANET Traffic Management System API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": [
            "/api/status",
            "/api/traffic/current",
            "/api/traffic/metrics",
            "/api/sensors/data",
            "/api/control/start",
            "/api/control/stop",
            "/api/intersections",
            "/api/emergency",
            "/api/rl/status",
            "/api/rl/enable",
            "/api/rl/disable",
            "/api/rl/metrics"
        ]
    })

@app.route('/api/status')
def get_status():
    """Get system status"""
    global simulation_running, traffic_controller, rl_mode_enabled, rl_controller
    
    status = {
        "simulation_running": simulation_running,
        "timestamp": datetime.now().isoformat(),
        "sumo_connected": traffic_controller is not None and hasattr(traffic_controller, 'running'),
        "intersections_count": len(traffic_controller.intersections) if traffic_controller else 0,
        "simulation_step": traffic_controller.simulation_step if traffic_controller else 0,
        "rl_mode_enabled": rl_mode_enabled,
        "rl_initialized": rl_controller is not None
    }
    
    return jsonify(status)

@app.route('/api/traffic/current')
def get_current_traffic():
    """Get current traffic data"""
    global traffic_controller
    
    if not traffic_controller:
        return jsonify({"error": "Traffic controller not initialized"}), 400
    
    try:
        metrics = traffic_controller.get_metrics()
        return jsonify(metrics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/traffic/metrics')
def get_traffic_metrics():
    """Get traffic performance metrics"""
    global metrics_history
    
    # Calculate aggregate metrics
    if not metrics_history:
        return jsonify({
            "total_records": 0,
            "avg_vehicles": 0,
            "emergency_events": 0,
            "history": []
        })
    
    total_vehicles = sum(m.get('total_vehicles', 0) for m in metrics_history)
    emergency_events = sum(m.get('emergency_vehicles', 0) for m in metrics_history)
    avg_vehicles = total_vehicles / len(metrics_history) if metrics_history else 0
    
    return jsonify({
        "total_records": len(metrics_history),
        "avg_vehicles": round(avg_vehicles, 2),
        "emergency_events": emergency_events,
        "latest_metrics": metrics_history[-10:] if metrics_history else [],
        "summary": {
            "simulation_time": metrics_history[-1].get('simulation_step', 0) if metrics_history else 0,
            "total_vehicles_processed": total_vehicles,
            "emergency_responses": emergency_events
        }
    })

@app.route('/api/sensors/data')
def get_sensor_data():
    """Get sensor network data"""
    global traffic_controller
    
    if not traffic_controller:
        return jsonify({"error": "Traffic controller not initialized"}), 400
    
    try:
        sensor_summary = traffic_controller.sensor_network.get_sensor_data_summary()
        
        # Add detailed sensor readings
        detailed_sensors = {}
        for sensor_id, reading in traffic_controller.sensor_network.sensors.items():
            detailed_sensors[sensor_id] = {
                "sensor_type": reading.sensor_type.value,
                "position": reading.position,
                "occupancy": reading.occupancy,
                "vehicle_count": reading.vehicle_count,
                "average_speed": reading.average_speed,
                "distance_from_intersection": reading.distance_from_intersection,
                "lane_id": reading.lane_id,
                "timestamp": reading.timestamp
            }
        
        return jsonify({
            "summary": sensor_summary,
            "detailed_sensors": detailed_sensors,
            "sensor_count": len(detailed_sensors)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/intersections')
def get_intersections():
    """Get intersection status"""
    global traffic_controller
    
    if not traffic_controller:
        return jsonify({"error": "Traffic controller not initialized"}), 400
    
    try:
        intersections_data = {}
        for intersection_id, intersection in traffic_controller.intersections.items():
            phases = traffic_controller.default_phases.get(intersection_id, [])
            current_phase_info = phases[intersection.current_phase] if phases else None
            
            intersections_data[intersection_id] = {
                "current_phase": intersection.current_phase,
                "phase_duration": intersection.phase_duration,
                "time_in_phase": intersection.time_in_phase,
                "phase_description": current_phase_info.description if current_phase_info else "Unknown",
                "phase_state": current_phase_info.state if current_phase_info else "Unknown",
                "emergency_detected": intersection.emergency_detected,
                "queue_lengths": intersection.queue_lengths,
                "traffic_densities": intersection.traffic_densities
            }
        
        return jsonify(intersections_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/emergency')
def get_emergency_vehicles():
    """Get emergency vehicle data"""
    global traffic_controller
    
    if not traffic_controller:
        return jsonify({"error": "Traffic controller not initialized"}), 400
    
    try:
        emergency_vehicles = traffic_controller.sensor_network.detect_emergency_vehicles()
        
        emergency_data = []
        for vehicle in emergency_vehicles:
            emergency_data.append({
                "vehicle_id": vehicle.vehicle_id,
                "speed": vehicle.speed,
                "distance_from_intersection": vehicle.distance_from_intersection,
                "lane_id": vehicle.lane_id,
                "timestamp": vehicle.timestamp
            })
        
        return jsonify({
            "emergency_count": len(emergency_data),
            "vehicles": emergency_data,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/control/start', methods=['POST'])
def start_simulation():
    """Start the traffic simulation"""
    global traffic_controller, simulation_thread, simulation_running
    
    if simulation_running:
        return jsonify({"message": "Simulation already running"}), 200
    
    try:
        # Import here to avoid circular imports
        from traffic_controller import AdaptiveTrafficController
        
        traffic_controller = AdaptiveTrafficController()
        
        # Get config path from request or use default
        data = request.get_json() or {}
        config_path = data.get('config_path', 'simulation.sumocfg')
        
        # Connect to SUMO
        if traffic_controller.connect_to_sumo(config_path):
            simulation_running = True
            
            # Start simulation in separate thread
            def run_simulation():
                global simulation_running, metrics_history, rl_controller, rl_mode_enabled, rl_metrics_history
                try:
                    steps = data.get('steps', 3600)
                    for step in range(steps):
                        if not simulation_running:
                            break
                        
                        # Use RL controller if enabled, otherwise use default controller
                        if rl_mode_enabled and rl_controller:
                            # RL step
                            rl_metrics = rl_controller.step()
                            rl_metrics_history.append({
                                **rl_metrics,
                                'timestamp': datetime.now().isoformat()
                            })
                            
                            # Keep only last 1000 records
                            if len(rl_metrics_history) > 1000:
                                rl_metrics_history = rl_metrics_history[-1000:]
                        else:
                            # Default traffic controller step
                            success = traffic_controller.run_simulation_step()
                            if not success:
                                break
                        
                        # Store metrics every 30 steps
                        if step % 30 == 0:
                            metrics = traffic_controller.get_metrics()
                            metrics_history.append(metrics)
                            
                            # Keep only last 1000 records
                            if len(metrics_history) > 1000:
                                metrics_history = metrics_history[-1000:]
                        
                        time.sleep(0.1)
                        
                except Exception as e:
                    print(f"Simulation error: {e}")
                    import traceback
                    traceback.print_exc()
                finally:
                    simulation_running = False
            
            simulation_thread = threading.Thread(target=run_simulation)
            simulation_thread.start()
            
            return jsonify({
                "message": "Simulation started successfully",
                "config_path": config_path,
                "steps": data.get('steps', 3600)
            })
        else:
            return jsonify({"error": "Failed to connect to SUMO"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/control/stop', methods=['POST'])
def stop_simulation():
    """Stop the traffic simulation"""
    global traffic_controller, simulation_running
    
    if not simulation_running:
        return jsonify({"message": "Simulation not running"}), 200
    
    try:
        simulation_running = False
        if traffic_controller:
            traffic_controller.stop_simulation()
        
        return jsonify({"message": "Simulation stopped successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/control/override', methods=['POST'])
def manual_override():
    """Manual override for traffic signals"""
    global traffic_controller
    
    if not traffic_controller:
        return jsonify({"error": "Traffic controller not initialized"}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    intersection_id = data.get('intersection_id')
    phase = data.get('phase')
    duration = data.get('duration', 30)
    
    if not intersection_id or phase is None:
        return jsonify({"error": "intersection_id and phase required"}), 400
    
    try:
        # Manual override logic (implement based on requirements)
        # This is a placeholder for manual signal control
        return jsonify({
            "message": f"Override applied to {intersection_id}",
            "intersection_id": intersection_id,
            "new_phase": phase,
            "duration": duration
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/network/metrics')
def get_network_metrics():
    """Get network performance metrics for research paper"""
    global metrics_history
    
    if not metrics_history:
        return jsonify({"error": "No metrics data available"}), 404
    
    # Calculate network performance metrics
    recent_metrics = metrics_history[-100:] if len(metrics_history) >= 100 else metrics_history
    
    # Placeholder for network metrics (to be implemented in Phase 3)
    network_metrics = {
        "packet_delivery_ratio": 0.98,  # Placeholder
        "end_to_end_latency": 50.5,     # Placeholder in ms
        "packet_loss_rate": 0.02,       # Placeholder
        "throughput": 1.5,              # Placeholder in Mbps
        "jitter": 2.3,                  # Placeholder in ms
        "channel_utilization": 0.75,    # Placeholder
        "handoff_success_rate": 0.95,   # Placeholder
        "authentication_delay": 15.2,   # Placeholder in ms
        "samples": len(recent_metrics),
        "timestamp": datetime.now().isoformat()
    }
    
    return jsonify(network_metrics)

# RL-specific endpoints
@app.route('/api/rl/status')
def get_rl_status():
    """Get RL controller status"""
    global rl_controller, rl_mode_enabled
    
    if not rl_controller:
        return jsonify({
            "enabled": False,
            "initialized": False,
            "message": "RL controller not initialized"
        })
    
    try:
        metrics = rl_controller.get_metrics()
        return jsonify({
            "enabled": rl_mode_enabled,
            "initialized": True,
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/rl/enable', methods=['POST'])
def enable_rl_mode():
    """Enable RL-based traffic control"""
    global rl_controller, rl_mode_enabled, traffic_controller
    
    if not traffic_controller or not simulation_running:
        return jsonify({"error": "Simulation must be running first"}), 400
    
    try:
        # Import RL controller
        from rl_module.rl_traffic_controller import RLTrafficController
        
        # Get configuration from request
        data = request.get_json() or {}
        
        # Create RL controller
        rl_controller = RLTrafficController(
            mode=data.get('mode', 'inference'),
            model_path=data.get('model_path'),
            config=data.get('config', {})
        )
        
        # Initialize with SUMO connection
        if rl_controller.initialize(sumo_connected=True):
            rl_mode_enabled = True
            return jsonify({
                "message": "RL mode enabled successfully",
                "mode": rl_controller.mode,
                "config": rl_controller.config
            })
        else:
            return jsonify({"error": "Failed to initialize RL controller"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/rl/disable', methods=['POST'])
def disable_rl_mode():
    """Disable RL-based traffic control"""
    global rl_controller, rl_mode_enabled
    
    try:
        rl_mode_enabled = False
        if rl_controller:
            rl_controller.close()
            rl_controller = None
        
        return jsonify({"message": "RL mode disabled successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/rl/metrics')
def get_rl_metrics():
    """Get RL training/inference metrics"""
    global rl_controller, rl_metrics_history
    
    if not rl_controller:
        return jsonify({"error": "RL controller not initialized"}), 400
    
    try:
        current_metrics = rl_controller.get_metrics()
        
        return jsonify({
            "current": current_metrics,
            "history": rl_metrics_history[-100:] if rl_metrics_history else [],
            "total_records": len(rl_metrics_history)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/rl/step', methods=['POST'])
def rl_step():
    """Execute one RL control step"""
    global rl_controller, rl_metrics_history
    
    if not rl_controller or not rl_mode_enabled:
        return jsonify({"error": "RL mode not enabled"}), 400
    
    try:
        metrics = rl_controller.step()
        rl_metrics_history.append({
            **metrics,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep only last 1000 records
        if len(rl_metrics_history) > 1000:
            rl_metrics_history = rl_metrics_history[-1000:]
        
        return jsonify(metrics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    print("Starting VANET Traffic Management API Server...")
    print("Available endpoints:")
    print("  GET  /                    - API information")
    print("  GET  /api/status          - System status")
    print("  GET  /api/traffic/current - Current traffic data")
    print("  GET  /api/traffic/metrics - Traffic performance metrics")
    print("  GET  /api/sensors/data    - Sensor network data")
    print("  GET  /api/intersections   - Intersection status")
    print("  GET  /api/emergency       - Emergency vehicle data")
    print("  POST /api/control/start   - Start simulation")
    print("  POST /api/control/stop    - Stop simulation")
    print("  POST /api/control/override- Manual signal override")
    print("  GET  /api/network/metrics - Network performance metrics")
    
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)