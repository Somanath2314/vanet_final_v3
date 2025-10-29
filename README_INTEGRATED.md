# 🚗 Integrated SUMO + NS3 VANET System

**Complete vehicular ad-hoc network simulation combining real traffic with network communications**

## Quick Start

```bash
./run_integrated_sumo_ns3.sh --gui
```

## What This Does

- **SUMO**: Simulates real traffic with vehicles, intersections, and emergency vehicles
- **Network Simulation**: WiFi (802.11p) for V2V, WiMAX for emergency V2I
- **Real-Time Integration**: Network uses actual vehicle positions from SUMO
- **Automatic Detection**: Emergency vehicles automatically use WiMAX

## Features

✅ Real SUMO traffic (not dummy data)  
✅ WiFi 802.11p for vehicle-to-vehicle  
✅ WiMAX for emergency vehicle-to-infrastructure  
✅ Automatic emergency vehicle detection  
✅ Comprehensive metrics (PDR, delay, throughput)  
✅ One-command execution  

## Results

After running, check `sumo_simulation/output/integrated_simulation_results.json` for:
- V2V communication metrics
- V2I communication metrics  
- Emergency vehicle statistics
- Network performance data

## Documentation

- **`FINAL_SYSTEM_SUMMARY.md`** - Complete overview
- **`INTEGRATED_SUMO_NS3_GUIDE.md`** - Detailed guide
- **`QUICK_REFERENCE.md`** - Command reference

## System Ready ✅

Your integrated VANET system is fully operational!
