from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import threading
import os

app = Flask(__name__)
CORS(app)

selected_method = None  # store which method user selected


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

    # Path to Git Bash
    git_bash = r"C:\Program Files\Git\bin\bash.exe"

    # Path to your .sh script
    script_path = os.path.abspath('./run_integrated_sumo_ns3.sh')
    print("📁 Script Path:", script_path)

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

    def run_script():
        try:
            cmd = [git_bash, script_path] + args
            print("🚀 Running command:", " ".join(cmd))
            subprocess.run(cmd, check=True)
            print("✅ Simulation finished successfully.")
        except subprocess.CalledProcessError as e:
            print("❌ Error running simulation:", e)

    threading.Thread(target=run_script).start()
    return jsonify({"message": f"Simulation started in background using {selected_method} method"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
