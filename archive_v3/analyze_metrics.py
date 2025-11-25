#!/usr/bin/env python3
"""
network_metrics_sim.py

Phase 3 VANET V2I Simulation using SUMO + Python (no OMNeT++ required).

Outputs (inside sumo_simulation/output/):
 - v2i_packets.csv  : per-packet log
 - v2i_metrics.csv  : summary metrics
"""

import argparse
import math
import os
import random
import csv
from collections import deque
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# SUMO imports
try:
    import traci
    import sumolib
except Exception as e:
    raise SystemExit("traci/sumolib not found. Make sure SUMO is installed and SUMO_HOME is set.") from e

# ---------------- dataclasses ----------------
@dataclass
class RSU:
    id: str
    x: float
    y: float
    range_m: float
    data_rate_bps: float
    queue: deque = field(default_factory=deque)
    buffer_max: int = 200
    busy_until: float = 0.0
    tx_time_busy: float = 0.0
    tx_bytes_total: int = 0

@dataclass
class Packet:
    id: str
    src: str
    rsu: str = None
    gen_time: float = None
    enq_time: float = None
    start_tx: float = None
    end_tx: float = None
    rx_time: float = None
    size_bits: int = 8 * 1024  # default 1 KB
    success: bool = False
    reason: str = ""

# ---------------- utility functions ----------------
def dist(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

def path_error_prob(distance_m, max_range):
    """Distance-based packet error probability."""
    base = 0.01
    scale = 0.6
    rel = min(distance_m / max_range, 1.0)
    return min(1.0, base + (rel ** 2) * scale)

def parse_sumocfg_for_net(sumocfg_path):
    import xml.etree.ElementTree as ET
    tree = ET.parse(sumocfg_path)
    root = tree.getroot()
    for inp in root.findall('input'):
        for child in inp:
            if child.tag == 'net-file':
                netfile = child.attrib.get('value')
                if not os.path.isabs(netfile):
                    return os.path.join(os.path.dirname(sumocfg_path), netfile)
                return netfile
    raise RuntimeError("net-file not found in sumocfg.")

# ---------------- main simulator ----------------
class NetworkMetricsSimulator:
    def __init__(self, sumocfg, duration=300, rsu_interval=200, rsu_range=300,
                 pkt_period=1.0, packet_size_bytes=1024, data_rate_mbps=20.0,
                 headless=False, verbose=False):
        self.sumocfg = sumocfg
        self.duration = duration
        self.rsu_interval = rsu_interval
        self.rsu_range = rsu_range
        self.pkt_period = pkt_period
        self.packet_size_bits = packet_size_bytes * 8
        self.data_rate_bps = data_rate_mbps * 1e6
        self.headless = headless
        self.verbose = verbose

        self.rsus = {}  # id -> RSU
        self.pkt_log = []
        self.veh_last_pkt_time = {}  # vid -> last gen time
        self.veh_connected = {}  # vid -> rsu_id
        self.next_pkt_id = 1
        self.sim_time = 0.0

        # ensure output folder
        self.outdir = os.path.join(os.path.dirname(self.sumocfg), "output")
        os.makedirs(self.outdir, exist_ok=True)

    # ---------------- RSU placement ----------------
    def spawn_rsus_from_net(self):
        netfile = parse_sumocfg_for_net(self.sumocfg)
        net = sumolib.net.readNet(netfile)
        idx = 0
        for edge in net.getEdges():
            if edge.getFunction() != 0:
                elen = edge.getLength()
                if elen < 1.0:
                    continue
                n = max(1, math.floor(elen / self.rsu_interval) + 1)
                shape = edge.getShape()
                for i in range(n):
                    fpos = min(i * self.rsu_interval, elen)
                    x0, y0 = shape[0]
                    x1, y1 = shape[-1]
                    t = (fpos / elen) if elen > 0 else 0
                    x = x0 + (x1 - x0) * t
                    y = y0 + (y1 - y0) * t
                    rid = f"rsu_{idx}"
                    self.rsus[rid] = RSU(id=rid, x=x, y=y, range_m=self.rsu_range,
                                         data_rate_bps=self.data_rate_bps)
                    idx += 1
        if self.verbose:
            print(f"[init] Spawned {len(self.rsus)} RSUs.")

    # ---------------- check RSU coverage ----------------
    def vehicle_rsus_in_range(self, x, y):
        hits = []
        for rsu in self.rsus.values():
            d = dist((x,y),(rsu.x, rsu.y))
            if d <= rsu.range_m:
                hits.append((rsu, d))
        return sorted(hits, key=lambda t: t[1])

    # ---------------- main simulation ----------------
    def run(self):
        sumo_bin = os.environ.get("SUMO_BINARY", "sumo")
        if not self.headless:
            sumo_bin = os.environ.get("SUMO_BINARY", "sumo-gui")
        traci.start([sumo_bin, "-c", self.sumocfg, "--step-length", "0.1"])
        if self.verbose:
            print("[run] SUMO started.")
        self.spawn_rsus_from_net()

        while True:
            traci.simulationStep()
            self.sim_time = traci.simulation.getTime()
            if self.sim_time >= self.duration:
                break

            vehs = traci.vehicle.getIDList()
            for vid in vehs:
                if vid not in self.veh_last_pkt_time:
                    self.veh_last_pkt_time[vid] = -999.0
                    self.veh_connected[vid] = None

            # generate packets
            for vid in vehs:
                last = self.veh_last_pkt_time.get(vid, -999.0)
                if (self.sim_time - last) >= self.pkt_period:
                    pkt = Packet(id=f"pkt_{self.next_pkt_id}", src=vid, gen_time=self.sim_time,
                                 size_bits=self.packet_size_bits)
                    self.next_pkt_id += 1
                    self.veh_last_pkt_time[vid] = self.sim_time

                    try:
                        x,y = traci.vehicle.getPosition(vid)
                    except Exception:
                        pkt.reason = "no_position"
                        pkt.success = False
                        self.pkt_log.append(pkt)
                        continue

                    inrange = self.vehicle_rsus_in_range(x,y)
                    if not inrange:
                        pkt.reason = "no_coverage"
                        pkt.success = False
                        self.pkt_log.append(pkt)
                        if self.verbose:
                            print(f"[{self.sim_time:.2f}] {pkt.id} -> no coverage")
                    else:
                        chosen, d = inrange[0]
                        pkt.rsu = chosen.id
                        pkt.enq_time = self.sim_time
                        if len(chosen.queue) >= chosen.buffer_max:
                            pkt.success = False
                            pkt.reason = "queue_drop"
                            self.pkt_log.append(pkt)
                        else:
                            chosen.queue.append(pkt)
                            if self.verbose:
                                print(f"[{self.sim_time:.2f}] {pkt.id} enqueued at {chosen.id} dist={d:.1f}m")
                        prev = self.veh_connected.get(vid)
                        if prev != chosen.id:
                            self.veh_connected[vid] = chosen.id

            # RSU transmission
            for rsu in list(self.rsus.values()):
                if rsu.queue and self.sim_time >= rsu.busy_until:
                    pkt = rsu.queue.popleft()
                    pkt.start_tx = self.sim_time
                    tx_duration = pkt.size_bits / rsu.data_rate_bps
                    try:
                        vx, vy = traci.vehicle.getPosition(pkt.src)
                        d = dist((vx,vy),(rsu.x, rsu.y))
                    except Exception:
                        d = rsu.range_m * 0.5
                    prop_delay = d / 3e8
                    p_err = path_error_prob(d, rsu.range_m)
                    success = (random.random() > p_err)
                    vconn = self.veh_connected.get(pkt.src)
                    if vconn and vconn != rsu.id:
                        if random.random() < 0.05:
                            success = False
                            pkt.reason = "handoff_fail"
                        else:
                            pkt.reason = "handoff_ok"
                            tx_duration += 0.05
                    end_t = self.sim_time + tx_duration + prop_delay
                    pkt.end_tx = end_t
                    if success:
                        pkt.rx_time = end_t
                        pkt.success = True
                        pkt.reason = pkt.reason or "ok"
                        rsu.tx_bytes_total += (pkt.size_bits // 8)
                    else:
                        pkt.success = False
                        pkt.reason = pkt.reason or "rx_error"
                    rsu.busy_until = end_t
                    rsu.tx_time_busy += tx_duration
                    self.pkt_log.append(pkt)
                    if self.verbose:
                        print(f"[{self.sim_time:.2f}] RSU {rsu.id} tx {pkt.id} success={pkt.success} reason={pkt.reason}")

        traci.close()
        if self.verbose:
            print("[run] SUMO closed.")
        self.compute_and_save()

    # ---------------- metrics computation ----------------
    def compute_and_save(self):
        df = pd.DataFrame([p.__dict__ for p in self.pkt_log])
        csv_path = os.path.join(self.outdir, "v2i_packets.csv")
        df.to_csv(csv_path, index=False)

        total_packets = len(df)
        successful_packets = df['success'].sum()
        pdr = successful_packets / total_packets if total_packets>0 else 0
        latency = df.loc[df['success'], 'rx_time'] - df.loc[df['success'], 'gen_time']
        mean_latency = latency.mean() if not latency.empty else 0
        jitter = latency.std() if not latency.empty else 0
        throughput = df.loc[df['success'], 'size_bits'].sum() / self.duration
        handoff_total = len(df[df['reason'].isin(['handoff_ok','handoff_fail'])])
        handoff_success = len(df[df['reason']=='handoff_ok'])
        handoff_rate = handoff_success / handoff_total if handoff_total>0 else 1.0
        loss_reasons = df.loc[~df['success'],'reason'].value_counts().to_dict()

        # per-RSU utilization
        rsu_util = {r.id: r.tx_time_busy / self.duration for r in self.rsus.values()}

        metrics = {
            "duration_s": self.duration,
            "total_packets": total_packets,
            "successful_packets": int(successful_packets),
            "pdr": pdr,
            "mean_latency_s": mean_latency,
            "jitter_s": jitter,
            "throughput_bps": throughput,
            "handoff_success_rate": handoff_rate,
            "loss_reasons": loss_reasons,
            "rsu_utilization": rsu_util
        }

        metrics_csv = os.path.join(self.outdir, "v2i_metrics.csv")
        pd.DataFrame([metrics]).to_csv(metrics_csv, index=False)

        print("\n=== V2I Metrics Summary ===")
        print(f"Duration: {self.duration}s")
        print(f"Total packets: {total_packets}")
        print(f"Successful packets: {int(successful_packets)}")
        print(f"PDR: {pdr:.4f}")
        print(f"Mean latency (s): {mean_latency:.2f}")
        print(f"Jitter (s): {jitter:.2f}")
        print(f"Throughput (bps): {throughput:.2f}")
        print(f"Handoff success rate: {handoff_rate:.2f}")
        print(f"Loss reasons: {loss_reasons}")
        print(f"Saved logs -> {csv_path}")
        print(f"Saved metrics -> {metrics_csv}")

# ---------------- argument parser ----------------
def parse_args():
    parser = argparse.ArgumentParser(description="V2I Network Metrics Simulation (SUMO + Python)")
    parser.add_argument("--sumocfg", type=str, required=True, help="Path to SUMO .sumocfg file")
    parser.add_argument("--duration", type=float, default=300.0, help="Simulation duration (s)")
    parser.add_argument("--rsu-interval", type=float, default=200.0, help="RSU placement interval (m)")
    parser.add_argument("--rsu-range", type=float, default=300.0, help="RSU coverage radius (m)")
    parser.add_argument("--pkt-period", type=float, default=1.0, help="Packet generation interval (s)")
    parser.add_argument("--data-rate-mbps", type=float, default=20.0, help="RSU data rate (Mbps)")
    parser.add_argument("--headless", action="store_true", help="Run SUMO in headless mode")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    return parser.parse_args()

# ---------------- main ----------------
if __name__ == "__main__":
    args = parse_args()
    sim = NetworkMetricsSimulator(
        sumocfg=args.sumocfg,
        duration=args.duration,
        rsu_interval=args.rsu_interval,
        rsu_range=args.rsu_range,
        pkt_period=args.pkt_period,
        data_rate_mbps=args.data_rate_mbps,
        headless=args.headless,
        verbose=args.verbose
    )
    sim.run()
