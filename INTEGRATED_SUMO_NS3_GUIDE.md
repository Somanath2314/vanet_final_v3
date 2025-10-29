## Integrated SUMO + NS3 VANET System

### Overview

This system combines **SUMO traffic simulation** with **NS3-based network simulation** to create a realistic VANET environment where:

- **SUMO** provides realistic vehicle movements, traffic patterns, and emergency vehicle scenarios
- **NS3 Bridge** simulates network communications based on actual vehicle positions
- **WiFi (802.11p)** is used for V2V communication between vehicles
- **WiMAX** is used for V2I communication when emergency vehicles are detected
- **Real-time integration** - network simulation uses actual SUMO vehicle positions

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Integrated VANET System                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │     SUMO     │         │  NS3 Bridge  │                 │
│  │   Traffic    │◄───────►│   Network    │                 │
│  │  Simulation  │         │  Simulation  │                 │
│  └──────────────┘         └──────────────┘                 │
│         │                        │                          │
│         │                        │                          │
│    Vehicle Positions      Communication Events             │
│    Emergency Detection    WiFi (V2V) + WiMAX (V2I)         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Quick Start

#### Option 1: Simple Run (Recommended)

```bash
cd /home/shreyasdk/capstone/vanet_final_v3
./run_integrated_sumo_ns3.sh
```

#### Option 2: With GUI

```bash
./run_integrated_sumo_ns3.sh --gui
```

#### Option 3: With RL Control

```bash
./run_integrated_sumo_ns3.sh --rl --gui
```

#### Option 4: Custom Steps

```bash
./run_integrated_sumo_ns3.sh --gui --steps 2000
```

### How It Works

#### 1. Vehicle Movement (SUMO)
- SUMO simulates realistic traffic with cars, trucks, and emergency vehicles
- Vehicles follow traffic rules, signals, and road networks
- Emergency vehicles (ambulances) are detected automatically

#### 2. Network Communication (NS3 Bridge)

**V2V Communication (Vehicle-to-Vehicle)**
- Protocol: **WiFi 802.11p**
- Range: **300 meters**
- Use: Beacon messages, safety alerts between nearby vehicles
- All vehicles use WiFi for V2V

**V2I Communication (Vehicle-to-Infrastructure)**
- **Emergency Vehicles**: Use **WiMAX** (1000m range, better reliability)
- **Normal Vehicles**: Use **WiFi 802.11p** (300m range)
- RSUs placed at intersections

#### 3. Real-Time Integration
- Every simulation step:
  1. SUMO advances vehicle positions
  2. NS3 Bridge reads vehicle positions from SUMO
  3. Network simulation calculates which vehicles can communicate
  4. Packets are sent based on distance and protocol
  5. Metrics are collected (PDR, delay, throughput)

### Communication Protocols

#### WiFi 802.11p (V2V)
```
Range: 300m
Frequency: 5.9 GHz (DSRC)
Beacon Rate: 10 Hz
PDR: 92-98% (distance-dependent)
Delay: 20-50ms
Use Case: Vehicle-to-vehicle safety messages
```

#### WiMAX (Emergency V2I)
```
Range: 1000m
PDR: 95-99%
Delay: 15-30ms
Priority: High for emergency vehicles
Use Case: Emergency vehicle to infrastructure
```

### Output Files

After running the simulation, you'll find these files in `sumo_simulation/output/`:

1. **`integrated_simulation_results.json`** - Main results file
   - Network metrics (PDR, delay, throughput)
   - Emergency vehicle statistics
   - Communication events
   
2. **`tripinfo.xml`** - SUMO trip information
   - Vehicle routes and travel times
   
3. **`summary.xml`** - SUMO summary statistics
   - Overall traffic metrics
   
4. **`v2i_packets.csv`** - V2I communication packets
   
5. **`v2i_metrics.csv`** - V2I performance metrics

### Example Output

```
======================================================================
SUMO-NS3 INTEGRATED SIMULATION RESULTS
======================================================================

📊 Vehicle Statistics:
  Total Vehicles: 45
  Emergency Vehicles: 3
  Normal Vehicles: 42

🔷 V2V Communication (WiFi 802.11p):
  Packets Sent: 12450
  Packets Received: 11823
  Packet Delivery Ratio: 94.96%

🔶 V2I Communication (WiMAX for Emergency):
  Packets Sent: 3420
  Packets Received: 3351
  Packet Delivery Ratio: 97.98%

📈 Combined Performance:
  Overall PDR: 95.65%
  Average Delay: 28.34 ms
  Throughput: 18.45 Mbps

🚑 Emergency Vehicle Communication:
  Total Emergency Events: 1240
  Successful Events: 1215
  Success Rate: 97.98%
  Average Delay: 18.23 ms
  Protocol: WiMAX

🌐 Infrastructure:
  RSUs: 4
  WiFi Range: 300 m
  WiMAX Range: 1000 m
======================================================================
```

### View Results

```bash
# View main results
cat sumo_simulation/output/integrated_simulation_results.json | python3 -m json.tool

# Quick metrics
python3 << 'EOF'
import json
with open('sumo_simulation/output/integrated_simulation_results.json') as f:
    data = json.load(f)
    m = data['metrics']
    print(f"Overall PDR: {m['combined']['overall_pdr']*100:.2f}%")
    print(f"Average Delay: {m['combined']['average_delay_ms']:.2f} ms")
    print(f"Emergency Success: {m['emergency']['success_rate']*100:.2f}%")
EOF

# List all output files
ls -lh sumo_simulation/output/
```

### Key Features

#### ✅ Realistic Vehicle Movements
- Uses SUMO for accurate traffic simulation
- Real road networks and intersections
- Traffic signals and rules

#### ✅ Emergency Vehicle Detection
- Automatically detects emergency vehicles (ambulances)
- Switches to WiMAX for better reliability
- Priority communication handling

#### ✅ Distance-Based Communication
- Realistic range limits (300m WiFi, 1000m WiMAX)
- PDR decreases with distance
- Delay increases with distance

#### ✅ Comprehensive Metrics
- Packet Delivery Ratio (PDR)
- End-to-end delay
- Throughput
- Emergency vehicle success rates
- Per-protocol statistics

### Comparison with Previous System

| Feature | Previous (Standalone NS3) | New (Integrated) |
|---------|---------------------------|------------------|
| **Vehicle Movement** | Simulated/Static | Real SUMO traffic |
| **Traffic Patterns** | Predefined | Dynamic from SUMO |
| **Emergency Detection** | Manual | Automatic from SUMO |
| **Realism** | Medium | High |
| **Data Source** | Simulated | SUMO + Network sim |
| **Use Case** | Network research | Complete VANET research |

### Advanced Usage

#### Run with RL Traffic Control
```bash
./run_integrated_sumo_ns3.sh --rl --gui --steps 2000
```

#### Run Headless (No GUI, Faster)
```bash
./run_integrated_sumo_ns3.sh --steps 5000
```

#### Python API
```python
from sumo_simulation.sumo_ns3_bridge import SUMONS3Bridge
from sumo_simulation.traffic_controller import AdaptiveTrafficController

# Initialize
bridge = SUMONS3Bridge()
controller = AdaptiveTrafficController()

# Set RSU positions
bridge.initialize_rsus([(500, 500), (1500, 500)])

# Connect to SUMO
controller.connect_to_sumo('simulation.sumocfg')

# Run simulation
for step in range(1000):
    import traci
    traci.simulationStep()
    bridge.step(traci.simulation.getTime())

# Get metrics
metrics = bridge.get_metrics()
print(f"PDR: {metrics['combined']['overall_pdr']}")
```

### Troubleshooting

#### SUMO Not Found
```bash
sudo apt-get install sumo sumo-tools sumo-doc
```

#### Config File Missing
```bash
cd sumo_simulation
ls -la simulation.sumocfg
```

#### Virtual Environment
```bash
source venv/bin/activate
pip install -r backend/requirements.txt
```

#### No Emergency Vehicles
- Check SUMO route files for emergency vehicle types
- Emergency vehicles should have type containing "emergency" or "ambulance"

### For Research

#### Collect Data for Multiple Scenarios
```bash
#!/bin/bash
for steps in 500 1000 2000 5000; do
    echo "Running with $steps steps"
    ./run_integrated_sumo_ns3.sh --steps $steps
    mv sumo_simulation/output/integrated_simulation_results.json \
       results_${steps}_steps.json
done
```

#### Analyze Results
```python
import json
import glob
import pandas as pd

results = []
for f in glob.glob('results_*_steps.json'):
    with open(f) as fp:
        data = json.load(fp)
        results.append({
            'file': f,
            'pdr': data['metrics']['combined']['overall_pdr'],
            'delay': data['metrics']['combined']['average_delay_ms'],
            'emergency_success': data['metrics']['emergency']['success_rate']
        })

df = pd.DataFrame(results)
print(df)
df.to_csv('analysis.csv', index=False)
```

### Next Steps

1. **Modify RSU Positions**: Edit `run_integrated_simulation.py` line 48-53
2. **Adjust Communication Ranges**: Edit `sumo_ns3_bridge.py` lines 35-36
3. **Add More Emergency Vehicles**: Modify SUMO route files
4. **Extend Simulation Time**: Use `--steps` parameter
5. **Visualize Results**: Create plots from JSON output

### References

- **SUMO Documentation**: https://sumo.dlr.de/docs/
- **IEEE 802.11p**: WAVE/DSRC standard for V2V
- **IEEE 802.16e**: Mobile WiMAX for V2I
- **TraCI**: SUMO's Traffic Control Interface

---

**System Version**: v3.1 - Integrated SUMO + NS3  
**Last Updated**: 2025-10-29  
**Status**: ✅ Fully Operational with Real SUMO Data
