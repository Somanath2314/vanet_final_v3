#!/usr/bin/env python3
"""
network_metrics_sim.py

SUMO + TraCI script to simulate V2I (WiMAX-like) communication using only SUMO + Python.
Place this file in your sumo_simulation/ folder and run it pointing to simulation.sumocfg.

Outputs (in sumo_simulation/output/):
 - v2i_packets.csv  : per-packet event log
 - v2i_metrics.csv  : summary metrics
"""

import argparse
import math
import os
import random
import time
import csv
from collections import deque, defaultdict
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# SUMO imports (these require SUMO's python tools on PYTHONPATH / SUMO_HOME)
try:
    import traci
    import sumolib
except Exception as e:
    raise SystemExit("traci/sumolib not found. Ensure SUMO is installed and SUMO_HOME is set.") from e

# ---- dataclasses ----
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

# ---- utility functions ----
def dist(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

def path_error_prob(distance_m, max_range):
    """Simple distance-based packet error probability [0..1]."""
    base = 0.01
    scale = 0.6
    rel = min(distance_m / max_range, 1.0)
    return min(1.0, base + (rel ** 2) * scale)

def parse_sumocfg_for_net(sumocfg_path):
    """Parse .sumocfg to find net-file path (relative paths supported)."""
    import xml.etree.ElementTree as ET
    tree = ET.parse(sumocfg_path)
    root = tree.getroot()
    for inp in root.findall('input'):
        for child in inp:
            if child.tag == 'net-file':
                netfile = child.attrib.get('value')
                # normalize path relative to sumocfg dir
                if not os.path.isabs(netfile):
                    return os.path.join(os.path.dirname(sumocfg_path), netfile)
                return netfile
    raise RuntimeError("net-file not found in sumocfg.")

# ---- main simulator class ----
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
        self.pkt_log = []  # list of Packet
        self.veh_last_pkt_time = {}  # vid -> last gen time
        self.veh_connected = {}  # vid -> rsu_id
        self.next_pkt_id = 1
        self.sim_time = 0.0

        # ensure output folder
        self.outdir = os.path.join(os.path.dirname(self.sumocfg), "output")
        os.makedirs(self.outdir, exist_ok=True)

    def spawn_rsus_from_net(self):
        netfile = parse_sumocfg_for_net(self.sumocfg)
        net = sumolib.net.readNet(netfile)
        idx = 0
        # place RSUs on edges that are "non-internal" (function==0 are internal; skip them)
        for edge in net.getEdges():
            if edge.getFunction() != 0:
                elen = edge.getLength()
                if elen < 1.0:
                    continue
                n = max(1, math.floor(elen / self.rsu_interval) + 1)
                # sample positions along edge shape
                shape = edge.getShape()
                for i in range(n):
                    fpos = min(i * self.rsu_interval, elen)
                    # get coordinate by interpolation along shape segments
                    # sumolib doesn't provide direct interpolation; we'll approximate by sampling points of shape
                    # choose first or last shape point as simple heuristic for placement
                    # better: use edge.getCoord but it's not always available, so use shape centroid around fpos
                    # For simplicity: use linear interpolation between first and last point
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

    def vehicle_rsus_in_range(self, x, y):
        hits = []
        for rsu in self.rsus.values():
            d = dist((x,y),(rsu.x, rsu.y))
            if d <= rsu.range_m:
                hits.append((rsu, d))
        return sorted(hits, key=lambda t: t[1])

    def run(self):
        sumo_bin = os.environ.get("SUMO_BINARY", "sumo")
        if not self.headless:
            # if GUI requested, try sumo-gui
            sumo_bin = os.environ.get("SUMO_BINARY", "sumo-gui")
        # start SUMO
        traci.start([sumo_bin, "-c", self.sumocfg, "--step-length", "0.1"])
        if self.verbose:
            print("[run] SUMO started.")
        self.spawn_rsus_from_net()

        # simulation loop
        while True:
            traci.simulationStep()
            self.sim_time = traci.simulation.getTime()
            # break condition
            if self.sim_time >= self.duration:
                break

            # register vehicles
            vehs = traci.vehicle.getIDList()
            for vid in vehs:
                if vid not in self.veh_last_pkt_time:
                    self.veh_last_pkt_time[vid] = -999.0
                    self.veh_connected[vid] = None

            # generate packets per vehicle periodically
            for vid in vehs:
                last = self.veh_last_pkt_time.get(vid, -999.0)
                if (self.sim_time - last) >= self.pkt_period:
                    # generate packet
                    pkt = Packet(id=f"pkt_{self.next_pkt_id}", src=vid, gen_time=self.sim_time,
                                 size_bits=self.packet_size_bits)
                    self.next_pkt_id += 1
                    self.veh_last_pkt_time[vid] = self.sim_time
                    # find RSU in range
                    try:
                        x,y = traci.vehicle.getPosition(vid)
                    except Exception:
                        # vehicle may have left
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
                            print(f"[{self.sim_time:.2f}] {pkt.id} by {vid} -> no coverage")
                    else:
                        chosen, d = inrange[0]
                        pkt.rsu = chosen.id
                        pkt.enq_time = self.sim_time
                        # enqueue
                        if len(chosen.queue) >= chosen.buffer_max:
                            pkt.success = False
                            pkt.reason = "queue_drop"
                            self.pkt_log.append(pkt)
                        else:
                            chosen.queue.append(pkt)
                            if self.verbose:
                                print(f"[{self.sim_time:.2f}] {pkt.id} enqueued at {chosen.id} dist={d:.1f}m")

                        # update connected RSU for handoff logic
                        prev = self.veh_connected.get(vid)
                        if prev != chosen.id:
                            # handoff attempt
                            self.veh_connected[vid] = chosen.id
                            # can log handoff event if desired

            # RSUs process queues (simple FIFO, one packet at a time)
            for rsu in list(self.rsus.values()):
                if rsu.queue and self.sim_time >= rsu.busy_until:
                    pkt = rsu.queue.popleft()
                    pkt.start_tx = self.sim_time
                    tx_duration = pkt.size_bits / rsu.data_rate_bps
                    # compute propagation delay based on vehicle position at tx start
                    try:
                        vx, vy = traci.vehicle.getPosition(pkt.src)
                        d = dist((vx,vy),(rsu.x, rsu.y))
                    except Exception:
                        d = rsu.range_m * 0.5
                    prop_delay = d / 3e8
                    # error prob
                    p_err = path_error_prob(d, rsu.range_m)
                    success = (random.random() > p_err)
                    # Handoff modeling simplified:
                    # if vehicle connected RSU at this time is different -> possible handoff failure
                    vconn = self.veh_connected.get(pkt.src)
                    if vconn and vconn != rsu.id:
                        # handoff attempt with small chance of fail
                        if random.random() < 0.05:
                            success = False
                            pkt.reason = "handoff_fail"
                        else:
                            pkt.reason = "handoff_ok"
                            # small extra delay
                            tx_duration += 0.05
                    # finalize
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

        # simulation done
        traci.close()
        if self.verbose:
            print("[run] SUMO closed.")
        self.compute_and_save()

    def compute_and_save(self):
        # DataFrame from packet log
        rows = []
        for p in self.pkt_log:
            rows.append({
                "pkt_id": p.id,
                "src": p.src,
                "rsu": p.rsu,
                "gen_time": p.gen_time,
                "enq_time": p.enq_time,
                "start_tx": p.start_tx,
                "end_tx": p.end_tx,
                "rx_time": p.rx_time,
                "success": p.success,
                "reason": p.reason,
                "size_bits": p.size_bits
            })
        df = pd.DataFrame(rows)
        pfile = os.path.join(self.outdir, "v2i_packets.csv")
        df.to_csv(pfile, index=False)

    # metrics
        total = len(df)
        succ = int(df['success'].sum()) if total>0 else 0
        pdr = succ / total if total>0 else float('nan')
        loss_rate = 1 - pdr if total>0 else float('nan')
        # latencies for successful packets
        lat = df[df.success].apply(lambda r: r.rx_time - r.gen_time, axis=1).dropna()
        mean_latency = float(lat.mean()) if not lat.empty else float('nan')
        jitter = float(lat.diff().abs().mean()) if len(lat) >= 2 else float('nan')
        total_bits_received = int(df[df.success]['size_bits'].sum())
        throughput_bps = total_bits_received / (self.duration if self.duration>0 else 1.0)

        # loss reasons
        loss_reasons = df[~df.success]['reason'].value_counts().to_dict()
        # per-rsu util
        rsu_stats = {}
        for rid, rsu in self.rsus.items():
            util = rsu.tx_time_busy / self.duration if self.duration>0 else 0.0
            rsu_stats[rid] = {"utilization": util, "tx_bytes": rsu.tx_bytes_total}

        # handoff metrics: simple counts
        hs = df[df.reason == 'handoff_ok'].shape[0]
        hf = df[df.reason == 'handoff_fail'].shape[0]
        attempts = hs + hf
        handoff_success_rate = hs / attempts if attempts>0 else float('nan')

        metrics = {
            "total_packets": total,
            "successful_packets": succ,
            "PDR": pdr,
            "mean_latency_s": mean_latency,
            "jitter_s": jitter,
            "packet_loss_rate": loss_rate,
            "throughput_bps": throughput_bps,
            "loss_reasons": loss_reasons,
            "handoff_success_rate": handoff_success_rate,
            "rsu_stats_sample": dict(list(rsu_stats.items())[:10])
        }

        mfile = os.path.join(self.outdir, "v2i_metrics.csv")
        # save metrics as simple two-column CSV
        with open(mfile, "w", newline='') as f:
            writer = csv.writer(f)
            for k,v in metrics.items():
                writer.writerow([k, v])

        # print summary
        print("=== V2I Metrics Summary ===")
        print(f"Duration: {self.duration}s")
        print(f"Total packets: {total}  Successful: {succ}  PDR: {pdr:.4f}")
        print(f"Mean latency (s): {mean_latency}  Jitter (s): {jitter}")
        print(f"Throughput (bps): {throughput_bps:.2f}")
        print(f"Handoff success rate: {handoff_success_rate}")
        print(f"Loss reasons: {loss_reasons}")
        print(f"Saved logs -> {pfile}")
        print(f"Saved metrics -> {mfile}")

        # ---- Try to log to MongoDB if configured ----
        try:
            # local import so pymongo is optional for users who don't want DB logging
            from mongo_logger import MongoMetricsLogger
            mongo = MongoMetricsLogger.from_env()
            if mongo is not None:
                try:
                    # insert packet DataFrame and metrics dict
                    mongo.insert_packets(df)
                    mongo.insert_metrics(metrics)
                    # optional: insert RSU stats and per-step summary if desired
                except Exception:
                    print("[network_metrics_sim] Error writing to MongoDB")
        except Exception:
            # Import error or mongo client not available - skip silently but inform
            pass

# ---- CLI ----
def cli():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sumocfg", required=True, help="path to sumo .sumocfg (relative or absolute)")
    ap.add_argument("--duration", type=float, default=300.0, help="simulation time in seconds")
    ap.add_argument("--rsu-interval", type=float, default=200.0, help="meters between RSUs")
    ap.add_argument("--rsu-range", type=float, default=300.0, help="RSU coverage radius (m)")
    ap.add_argument("--pkt-period", type=float, default=1.0, help="seconds between vehicle packets")
    ap.add_argument("--packet-size-bytes", type=int, default=1024, help="packet payload in bytes")
    ap.add_argument("--data-rate-mbps", type=float, default=20.0, help="RSU data rate (Mbps)")
    ap.add_argument("--headless", action="store_true", help="use headless SUMO (sumo) instead of sumo-gui")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    sim = NetworkMetricsSimulator(sumocfg=args.sumocfg, duration=args.duration,
                                  rsu_interval=args.rsu_interval, rsu_range=args.rsu_range,
                                  pkt_period=args.pkt_period, packet_size_bytes=args.packet_size_bytes,
                                  data_rate_mbps=args.data_rate_mbps, headless=args.headless,
                                  verbose=args.verbose)
    sim.run()

if __name__ == "__main__":
    cli()
