from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import threading
import os
import shutil
import platform
import shlex

app = Flask(__name__)
CORS(app)

selected_method = None  # store which method user selected


def get_script_path():
    """Return absolute path to run_integrated_sumo_ns3.sh resolved from this file's directory."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(base_dir, 'run_integrated_sumo_ns3.sh'))


def to_wsl_path(win_path: str) -> str:
    """Convert a Windows path like C:\\path\\to\\file to a WSL path /mnt/c/path/to/file.
    If path doesn't look like a Windows drive path, return a forward-slash-normalized path."""
    p = os.path.abspath(win_path)
    # Windows absolute path starts with DriveLetter ':' e.g. C:\\
    if len(p) >= 2 and p[1] == ':' and p[0].isalpha():
        drive = p[0].lower()
        rest = p[2:].replace('\\', '/')
        if rest.startswith('/'):
            rest = rest[1:]
        return f"/mnt/{drive}/{rest}"
    return p.replace('\\', '/')


def preflight_status():
    """Return a dict describing availability of script, bash, wsl and sumo."""
    script_path = get_script_path()
    bash_exists = bool(shutil.which('bash') or shutil.which('bash.exe') or (platform.system() != 'Windows' and os.path.exists('/bin/bash')))
    wsl_exists = bool(shutil.which('wsl'))
    sumo_exists = bool(shutil.which('sumo-gui') or shutil.which('sumo'))
    script_exists = os.path.isfile(script_path)
    # Require SUMO for GUI runs as well
    runnable = script_exists and (bash_exists or (platform.system() == 'Windows' and wsl_exists) or platform.system() != 'Windows') and sumo_exists
    missing = []
    if not script_exists:
        missing.append('script')
    if not bash_exists and not (platform.system() == 'Windows' and wsl_exists):
        missing.append('bash')
    if not sumo_exists:
        missing.append('sumo')

    message = 'OK' if runnable else f"Missing: {', '.join(missing)}"
    return {
        'script_path': script_path,
        'script_exists': script_exists,
        'bash_exists': bash_exists,
        'wsl_exists': wsl_exists,
        'sumo_exists': sumo_exists,
        'runnable': runnable,
        'message': message,
    }



@app.route('/api/preflight', methods=['GET'])
def preflight():
    status = preflight_status()
    return jsonify(status), (200 if status['runnable'] else 400)


@app.route('/api/live', methods=['GET'])
def live():
    """Return live metrics payload. Reads from running simulation if available,
    otherwise returns synthetic demo data.
    """
    import time, math, random
    from live_metrics_bridge import get_bridge
    
    bridge = get_bridge()
    t = time.time()
    mode = selected_method or 'unknown'
    
    # Try to get real metrics from running simulation
    real_metrics = bridge.read_metrics()
    # If no bridge file, try to query a running SUMO via TraCI as a fallback
    if not real_metrics:
        try:
            # Attempt to import traci and connect to common ports
            import traci
            traci_available = True
        except Exception:
            traci_available = False

        if traci_available:
            # Try some common TRACI ports (8813 is common default, 34363 seen in configs)
            for port in (8813, 34363, 8873, 13333):
                try:
                    # Try to connect briefly to the running SUMO instance
                    # use a small timeout via numRetries=1 to avoid long waits
                    conn = traci.connect(port=port)
                    try:
                        vehicles = traci.vehicle.getIDList()
                        active = len(vehicles)
                        emergency_count = sum(1 for v in vehicles if 'emerg' in v.lower() or 'emergency' in v.lower())

                        # queue length from lanes
                        queue_len = 0
                        try:
                            for lane in traci.lane.getIDList():
                                try:
                                    queue_len += traci.lane.getLastStepHaltingNumber(lane)
                                except Exception:
                                    pass
                        except Exception:
                            queue_len = 0

                        # Build minimal live metrics (pdr/throughput unknown here)
                        real_metrics = {
                            'activeVehicles': active,
                            'avgWait': 0.0,
                            'pdr': 0.0,
                            'queueLength': queue_len,
                            'throughput': 0.0,
                            'emergencyCount': emergency_count,
                        }
                        # Persist to bridge so frontend sees a file immediately
                        try:
                            bridge.write_metrics(real_metrics)
                        except Exception:
                            pass
                        # Close connection and break
                        traci.close()
                        break
                    finally:
                        # Ensure traci closed if still connected
                        try:
                            traci.close()
                        except Exception:
                            pass
                except Exception:
                    # try next port
                    continue
    
    if real_metrics:
        # Return REAL data from live simulation
        return jsonify({
            'timestamp': int(t),
            'activeVehicles': real_metrics.get('activeVehicles', 0),
            'avgWait': round(real_metrics.get('avgWait', 0.0), 2),
            'pdr': round(real_metrics.get('pdr', 0.0), 2),
            'queueLength': real_metrics.get('queueLength', 0),
            'throughput': round(real_metrics.get('throughput', 0.0), 2),
            'emergencyCount': real_metrics.get('emergencyCount', 0),
            'mode': mode,
            'isLive': True,  # Flag indicating real data
        }), 200
    else:
        # Fallback to synthetic data for demo (when simulation not running)
        active = int(30 + 10 * math.sin(t / 5) + random.uniform(-3, 3))
        avg_wait = max(0.5, 5 + 2 * math.sin(t / 7) + random.uniform(-0.5, 0.5))
        pdr = max(80, min(100, 95 + 2 * math.sin(t / 6) + random.uniform(-1.5, 1.5)))
        queue_len = max(0, int(2 + 2 * math.sin(t / 4) + random.uniform(-1, 1)))
        throughput = max(100, 400 + 60 * math.sin(t / 8) + random.uniform(-20, 20))
        emergency_count = max(0, int(3 + 2 * math.sin(t / 9) + random.uniform(-1, 1)))
        
        return jsonify({
            'timestamp': int(t),
            'activeVehicles': active,
            'avgWait': round(avg_wait, 2),
            'pdr': round(pdr, 2),
            'queueLength': queue_len,
            'throughput': round(throughput, 2),
            'emergencyCount': emergency_count,
            'mode': mode,
            'isLive': False,  # Flag indicating synthetic demo data
        }), 200


@app.route('/api/method', methods=['POST'])
def set_method():
    global selected_method
    data = request.get_json()
    method = data.get('method')
    selected_method = method
    print(f"✅ Selected method: {method}")
    return jsonify({"message": f"Method set to {method}"}), 200


@app.route('/api/run', methods=['POST'])
def run_simulation():
    global selected_method
    if not selected_method:
        return jsonify({"message": "No method selected"}), 400

    # Resolve script path relative to this file so repo can be run from any working directory
    script_path = get_script_path()
    print("📁 Script Path:", script_path)

    # Try to find a bash executable in PATH (works on Unix and Git Bash on Windows)
    bash_exe = shutil.which('bash') or shutil.which('bash.exe')
    # platform fallback: on POSIX try /bin/bash if which didn't find it
    if not bash_exe and platform.system() != 'Windows' and os.path.exists('/bin/bash'):
        bash_exe = '/bin/bash'
    # detect WSL if available (used as fallback on Windows)
    wsl_exe = shutil.which('wsl')

    # Choose args based on method
    if selected_method == 'rl':
        args = [
            '--proximity', '250',
            '--model', 'rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip',
            '--gui', '--edge', '--security', '--steps', '1000'
        ]
    elif selected_method == 'rule':
        args = ['--gui', '--security', '--steps', '1000']
    else:
        return jsonify({"message": "Invalid method"}), 400

    # Run a quick preflight check and return error to frontend if not runnable
    status = preflight_status()
    if not status.get('runnable'):
        print("❌ Preflight failed:", status.get('message'))
        return jsonify(status), 400

    def run_script():
        try:
            # Ensure script exists
            if not os.path.isfile(script_path):
                print(f"❌ Script not found: {script_path}")
                return

            if bash_exe:
                cmd = [bash_exe, script_path] + args
            else:
                # Try WSL on Windows as a fallback
                if platform.system() == 'Windows' and wsl_exe:
                    wsl_path = to_wsl_path(script_path)
                    quoted_args = ' '.join(shlex.quote(a) for a in args)
                    # Build a single command string for wsl to execute under bash
                    cmd = ['wsl', f"bash {shlex.quote(wsl_path)} {quoted_args}"]
                else:
                    # No bash available. On Windows without WSL we can't run .sh
                    if platform.system() == 'Windows':
                        print("❌ No bash found on PATH and WSL not available. Install Git for Windows or enable WSL.")
                        return
                    # On non-Windows fallback to executing the script directly (requires executable bit)
                    cmd = [script_path] + args

            # Use a string for display but pass list to subprocess to avoid shell=True
            print("🚀 Running command:", " ".join(cmd))
            subprocess.run(cmd, check=True)
            print("✅ Simulation finished successfully.")
        except FileNotFoundError as e:
            print("❌ Execution failed, file not found:", e)
        except subprocess.CalledProcessError as e:
            print("❌ Error running simulation:", e)
        except Exception as e:
            print("❌ Unexpected error while running simulation:", e)

    threading.Thread(target=run_script).start()
    return jsonify({"message": f"Simulation started in background using {selected_method} method"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
