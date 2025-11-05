# Edge Computing Infrastructure Documentation

**Version**: 1.0  
**Date**: November 5, 2025  
**Status**: ✅ Operational

---

## Overview

The edge computing layer provides distributed processing capabilities through a network of 13 Smart Road-Side Units (RSUs) with three-tier architecture. RSUs perform local computation for collision avoidance, traffic optimization, emergency coordination, and data aggregation, reducing latency and network load.

---

## 🏗️ Architecture

### Three-Tier RSU Deployment

```
┌─────────────────────────────────────────────────────────────┐
│                    Edge Computing Network                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Tier 1: High-Performance Intersections (2 RSUs)           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Location: Major intersections (J0, J1)              │  │
│  │  Resources: 8 cores, 16GB RAM, 100GB storage        │  │
│  │  Coverage: 300m radius                               │  │
│  │  Priority: Highest - Traffic signal coordination     │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  Tier 2: Standard Road Segments (8 RSUs)                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Location: Every 400m along main roads (E1-E8)      │  │
│  │  Resources: 4 cores, 8GB RAM, 50GB storage          │  │
│  │  Coverage: 300m radius                               │  │
│  │  Priority: Medium - Vehicle monitoring               │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  Tier 3: Coverage Extension (3 RSUs)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Location: Network gaps (GAP0, GAP1, GAP2)          │  │
│  │  Resources: 2 cores, 4GB RAM, 20GB storage          │  │
│  │  Coverage: 300m radius                               │  │
│  │  Priority: Low - Coverage filling                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### RSU Placement Strategy

1. **Tier 1 (Intersections)**: Positioned at traffic light junctions for real-time signal optimization
2. **Tier 2 (Road Segments)**: Regular intervals (400m) along main roads for continuous vehicle tracking
3. **Tier 3 (Coverage Gaps)**: Strategic placement to eliminate coverage holes in the network

---

## 🔧 Services & Capabilities

### 1. Collision Avoidance Service

**Purpose**: Detect potential collisions and issue warnings to vehicles

**Features**:
- Real-time trajectory prediction (5-second horizon)
- Conflict detection between vehicle pairs
- Warning severity levels: Critical (<20m), Warning (<50m)
- Rate limiting (2-second cooldown per vehicle pair)
- Unique collision pair tracking

**Metrics**:
- Warnings issued (unique collision pairs)
- Collisions prevented
- False positive rate

**Algorithm**:
```python
1. Track all vehicles in RSU coverage
2. Predict future positions using velocity vectors
3. Calculate minimum distance between trajectories
4. If distance < threshold:
   - Issue warning (if not rate-limited)
   - Track collision pair
   - Recommend evasive action
```

### 2. Traffic Flow Service

**Purpose**: Analyze traffic patterns and optimize routes

**Features**:
- Real-time density monitoring
- Congestion detection and prediction
- Route optimization based on current conditions
- Traffic anomaly detection
- Speed averaging and trend analysis

**Metrics**:
- Vehicles analyzed
- Routes computed
- Congestion events detected
- Average speed

**Congestion Detection**:
- Density > 0.5 vehicles/meter
- Average speed < 5 m/s
- Queue length > 10 vehicles

### 3. Emergency Support Service

**Purpose**: Coordinate emergency vehicle priority and corridor management

**Features**:
- Emergency vehicle registration and tracking
- Priority corridor creation
- Yield warning generation for nearby vehicles
- Traffic light preemption requests (Tier 1 only)
- Inter-RSU coordination

**Metrics**:
- Emergencies handled (unique emergency vehicles)
- Vehicles notified to yield
- Traffic lights preempted
- Active emergency corridors

**Emergency Protocol**:
```python
1. Detect emergency vehicle in coverage
2. Register and create priority corridor
3. Identify vehicles in path (500m priority radius)
4. Issue yield warnings to affected vehicles
5. Coordinate with nearby RSUs
6. Request traffic light preemption if applicable
```

### 4. Data Aggregation Service

**Purpose**: Collect, process, and prepare data for cloud upload

**Features**:
- Local vehicle data collection
- Data compression and aggregation
- Upload scheduling based on urgency
- Bandwidth optimization
- Privacy-preserving aggregation

**Metrics**:
- Data collected (bytes)
- Compression ratio
- Upload frequency
- Bandwidth saved

**Upload Triggers**:
- Buffer size > 1MB
- Time since last upload > 60 seconds
- High-priority event detected

### 5. Cache Manager

**Purpose**: Store frequently accessed data locally to reduce latency

**Features**:
- LRU (Least Recently Used) eviction
- TTL (Time To Live) management
- Request pattern analysis
- Automatic cache warming

**Metrics**:
- Cache hits
- Cache misses
- Cache hit rate
- Storage utilization

**Cache Strategy**:
- Store: Map data, traffic updates, route information
- TTL: 300 seconds (5 minutes)
- Size: 1GB (Tier 1), 512MB (Tier 2), 256MB (Tier 3)

---

## 📊 Metrics & Monitoring

### Per-RSU Metrics (edge_metrics.csv)

| Column | Description | Expected Range |
|--------|-------------|----------------|
| **RSU_ID** | RSU identifier | RSU_[LOCATION]_TIER[1-3] |
| **Tier** | RSU tier level | 1, 2, or 3 |
| **Vehicles_Served** | Unique vehicles tracked | 0-30 per RSU |
| **Computations** | Processing operations | Equal to Vehicles_Served |
| **Cache_Hit_Rate** | Cache efficiency | 0-100% |
| **Avg_Latency_MS** | Processing latency | 0-10ms typical |
| **Warnings_Issued** | Collision warnings | 0-50 per RSU |
| **Routes_Computed** | Route optimizations | 0-10 per RSU |
| **Emergencies_Handled** | Emergency vehicles | 0-2 per RSU |

### System-Wide Metrics (edge_summary.json)

```json
{
  "summary_statistics": {
    "total_rsus": 13,
    "total_vehicles_served": 191,
    "total_computations": 191,
    "cache_hit_rate": 0.0,
    "avg_latency_ms": 0.0,
    "uptime_seconds": 12.5,
    "computations_per_second": 15.23
  },
  "service_metrics": {
    "traffic_flow": {
      "requests": 0,
      "avg_response_time": 0
    },
    "collision_avoidance": {
      "warnings": 49,
      "prevented": 0
    },
    "emergency_support": {
      "events": 16,
      "response_time": 0
    }
  }
}
```

---

## 🚀 Usage

### Enable Edge Computing

```bash
# Basic edge computing
./run_integrated_sumo_ns3.sh --edge --steps 100

# With GUI for visualization
./run_integrated_sumo_ns3.sh --edge --gui --steps 100

# Full system (edge + security)
./run_integrated_sumo_ns3.sh --edge --security --steps 100
```

### View Edge Metrics

```bash
# Per-RSU performance
cat sumo_simulation/output_rule_edge/edge_metrics.csv

# System summary
cat sumo_simulation/output_rule_edge/edge_summary.json | python3 -m json.tool
```

### Example Output

```csv
RSU_ID,Tier,Vehicles_Served,Computations,Cache_Hit_Rate,Avg_Latency_MS,Warnings_Issued,Routes_Computed,Emergencies_Handled
RSU_J0_TIER1,1,25,25,0.00%,0.00,41,0,2
RSU_E1_0_TIER2,2,21,21,0.00%,0.00,31,0,2
RSU_GAP0_TIER3,3,28,28,0.00%,0.00,42,0,2
```

---

## 🔍 Performance Analysis

### Expected Behavior

**For 100-step simulation (36 vehicles):**
- Total vehicles served across all RSUs: **150-200** (vehicles visit multiple RSUs)
- Vehicles per RSU: **0-30** (varies by location and traffic)
- Collision warnings: **20-50** per busy RSU (depends on traffic density)
- Emergency vehicles: **0-2** per RSU (if emergencies present)

### Interpreting Results

1. **High Vehicle Count at Intersection RSU**: Normal - intersections see converging traffic
2. **Zero Metrics at Some RSUs**: Normal - coverage/gap RSUs may be idle in short simulations
3. **Warnings > Vehicle Count**: Normal - many vehicle pairs can have conflicts
4. **Total > Actual Vehicles**: Normal - vehicles move through multiple RSU zones

---

## 🛠️ Implementation Details

### Core Classes

**EdgeRSU** (`edge_computing/edge_rsu.py`):
- Main RSU controller
- Service orchestration
- Vehicle tracking
- Request processing

**Services** (`edge_computing/services/`):
- `collision_avoidance.py` - Trajectory prediction & conflict detection
- `traffic_flow.py` - Traffic analysis & route optimization
- `emergency_support.py` - Emergency coordination
- `data_aggregation.py` - Data collection & upload
- `cache_manager.py` - Local caching

**Metrics** (`edge_computing/metrics/edge_metrics.py`):
- Metric collection
- Statistics aggregation
- CSV/JSON export

**Placement** (`edge_computing/placement/rsu_placement.py`):
- RSU positioning algorithm
- Coverage optimization
- Tier assignment

### Integration Points

**Traffic Controller** (`sumo_simulation/traffic_controller.py`):
```python
# Initialize edge infrastructure
self._initialize_edge_rsus()

# Update RSUs every simulation step
self._update_edge_rsus()

# Save metrics at end
self._save_edge_metrics()
```

---

## 📚 Technical Specifications

### Computing Resources

| Tier | CPU Cores | RAM | Storage | Coverage | Quantity |
|------|-----------|-----|---------|----------|----------|
| 1 | 8 cores | 16 GB | 100 GB | 300m | 2 |
| 2 | 4 cores | 8 GB | 50 GB | 300m | 8 |
| 3 | 2 cores | 4 GB | 20 GB | 300m | 3 |

### Network Parameters

- **Coverage Radius**: 300 meters per RSU
- **Update Frequency**: Every simulation step (1 second)
- **Processing Latency**: < 10ms typical
- **Data Offload**: Automatic when buffer > 1MB

### Algorithms

**Trajectory Prediction**:
- Linear extrapolation with velocity vectors
- 5-second prediction horizon
- 0.5-second time steps

**Collision Detection**:
- Pairwise vehicle comparison
- Minimum distance calculation
- Safety margin: (vehicle1_length + vehicle2_length)/2 + 2m

**Cache Eviction**:
- LRU (Least Recently Used)
- TTL enforcement
- Size-based limits

---

## 🐛 Troubleshooting

### Issue: No Edge Metrics Generated

**Solution**: Ensure `--edge` flag is used:
```bash
./run_integrated_sumo_ns3.sh --edge --steps 100
```

### Issue: All RSU Metrics Show Zero

**Solution**: Simulation too short or no vehicles:
- Increase steps: `--steps 200`
- Check SUMO network has vehicles

### Issue: Unrealistically High Counts

**Solution**: Verify you're using the fixed version:
- Check `docs/edge_metrics_fix.md`
- Ensure EdgeRSU tracks unique vehicles
- Verify collision service tracks unique pairs

---

## 📖 References

- **Main Documentation**: `README.md`
- **Metrics Fix**: `docs/edge_metrics_fix.md`
- **Source Code**: `edge_computing/` directory
- **Integration**: `sumo_simulation/traffic_controller.py`

---

**Last Updated**: November 5, 2025  
**Version**: 1.0  
**Status**: Production Ready
