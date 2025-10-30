## Phase 2 - Backend API Quick Reference

### 🚀 Backend Status
✅ Running on **port 8000** (http://localhost:8000)
✅ Two new APIs implemented for fog-controller communication

---

### 📡 API Endpoints

#### 1. GET /api/wimax/getSignalData
**Purpose**: Fog nodes query nearby junction states for RL inference

**Query Parameters**:
- `x` (float): Query position X coordinate
- `y` (float): Query position Y coordinate  
- `radius` (float): Search radius in meters

**Response Example**:
```json
{
  "junctions": [
    {
      "poleId": "J2",
      "coords": {"x": 500.0, "y": 500.0},
      "distance_from_query": 150.5,
      "densities": {
        "north": 0.25,
        "south": 0.40,
        "east": 0.15,
        "west": 0.30
      },
      "phase_info": {
        "current_phase": 0,
        "phase_state": "GGrrrrGGrrrr",
        "time_since_last_switch": 12.5,
        "next_switch": 17.5
      },
      "lane_map": {
        "north": ["J2_N_0", "J2_N_1"],
        "south": ["J2_S_0", "J2_S_1"],
        "east": ["J2_E_0"],
        "west": ["J2_W_0"]
      }
    }
  ],
  "ambulance": {
    "detected": true,
    "vehicle_id": "emergency_1",
    "position": {"x": 350.0, "y": 420.0},
    "target": {"x": 800.0, "y": 500.0},
    "speed": 15.5,
    "direction": "east",
    "heading": 90.0,
    "lane_id": "E1_0"
  }
}
```

**Use Case**: 
Fog node at position (350, 420) with 1000m range queries:
```bash
curl "http://localhost:8000/api/wimax/getSignalData?x=350&y=420&radius=1000"
```

---

#### 2. POST /api/control/override
**Purpose**: Fog nodes send RL-based override commands to controller

**Request Body**:
```json
{
  "poleId": "J2",           // Junction ID
  "action": 2,              // Phase index to apply
  "duration_s": 25,         // Duration in seconds
  "vehicle_id": "emergency_1", // Optional: emergency vehicle ID
  "priority": 1             // Optional: 1=emergency, 2=high, 3=normal
}
```

**Response Example**:
```json
{
  "status": "success",
  "junction": "J2",
  "previous_phase": 0,
  "new_phase": 2,
  "duration_s": 25,
  "vehicle_id": "emergency_1",
  "override_type": "emergency",
  "timestamp": "2025-10-30T12:03:54.123"
}
```

**Use Case**:
Fog detects ambulance heading east, RL predicts action=2 (green for east), send override:
```bash
curl -X POST http://localhost:8000/api/control/override \
  -H "Content-Type: application/json" \
  -d '{
    "poleId": "J2",
    "action": 2,
    "duration_s": 25,
    "vehicle_id": "emergency_1",
    "priority": 1
  }'
```

---

### 🧪 Testing

**Automated Test Script**:
```bash
python test_backend_apis.py
```

Tests:
- ✅ Query signal data at various locations
- ✅ Ambulance detection
- ✅ Override command application
- ✅ Error handling

**Manual Testing**:

1. **Start Backend** (already running):
   ```bash
   python backend/app.py
   # Running on http://localhost:8000
   ```

2. **Query junction data**:
   ```bash
   curl "http://localhost:8000/api/wimax/getSignalData?x=500&y=500&radius=1000"
   ```

3. **Apply override**:
   ```bash
   curl -X POST http://localhost:8000/api/control/override \
     -H "Content-Type: application/json" \
     -d '{"poleId":"J2","action":0,"duration_s":20}'
   ```

---

### 🔄 Real-World Flow

```
1. Ambulance spawns in SUMO
   ↓
2. Fog node detects via V2V beacon
   ↓
3. Fog queries backend: GET /api/wimax/getSignalData
   └─ Gets: junction positions, densities, current phases, ambulance data
   ↓
4. Fog runs RL inference locally (rl_traffic_controller)
   └─ Input: 103-dim observation (densities + ambulance features)
   └─ Output: Action (which phase to apply)
   ↓
5. Fog sends command: POST /api/control/override
   └─ Includes: poleId, action, duration, vehicle_id
   ↓
6. Backend applies via TraCI
   └─ traci.trafficlight.setPhase(poleId, action)
   └─ traci.trafficlight.setPhaseDuration(poleId, duration)
   ↓
7. Traffic light changes → Ambulance clears faster
```

---

### 📋 Next Steps

**Phase 3**: Integrate sensor network with RL
- File: `sumo_simulation/sensors/sensor_network.py`
- Tasks:
  1. Load RL model on initialization
  2. Detect ambulances via existing V2V
  3. Call GET /api/wimax/getSignalData when detected
  4. Run RL inference
  5. Call POST /api/control/override with result

**Phase 4**: End-to-end testing
- Run: `./run_integrated_sumo_ns3.sh --rl`
- Verify complete ambulance preemption flow
- Check metrics: clearance time, waiting time reduction

---

### 🐛 Troubleshooting

**Backend not accessible?**
- Check it's running: `curl http://localhost:8000/`
- Check port: Should be 8000 (not 5000 - conflicts with AirPlay)

**MongoDB warning?**
- Safe to ignore - backend works without database for testing

**TraCI errors?**
- Ensure SUMO simulation is running before calling APIs
- Controller must be initialized with traffic lights

**No ambulance detected?**
- Check ambulance spawn probability (15% by default)
- Verify vehicle ID contains "emergency" or "ambulance"
