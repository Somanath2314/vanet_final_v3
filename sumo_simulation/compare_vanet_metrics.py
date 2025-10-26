#!/usr/bin/env python3
"""
Compare Rule-Based vs RL Traffic Control Simulations

Usage:
    python compare_vanet_metrics.py --rule_dir ./output_rule --rl_dir ./output_rl --show

Generates plots:
 - PDR, Latency, Throughput
 - Travel time, Waiting time, Time loss
 - RSU utilization
 - Side-by-side comparison for Rule vs RL
"""

import os
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import xml.etree.ElementTree as ET

sns.set(style="whitegrid", context="talk")


# ---------- Utility Functions ----------
def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def read_packets(outdir):
    f = os.path.join(outdir, "v2i_packets.csv")
    if not os.path.isfile(f):
        return None
    df = pd.read_csv(f)
    for col in ["gen_time", "rx_time"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "success" in df.columns:
        df["success"] = df["success"].astype(bool)
    if "size_bits" not in df.columns:
        df["size_bits"] = 1024 * 8
    return df


def parse_tripinfo(outdir):
    f = os.path.join(outdir, "tripinfo.xml")
    if not os.path.isfile(f):
        return None
    root = ET.parse(f).getroot()
    rows = []
    for ti in root.iter("tripinfo"):
        rows.append({
            "id": ti.get("id"),
            "duration": float(ti.get("duration", 0)),
            "waitingTime": float(ti.get("waitingTime", 0)),
            "timeLoss": float(ti.get("timeLoss", 0)),
        })
    if not rows:
        return None
    return pd.DataFrame(rows)


def parse_summary(outdir):
    f = os.path.join(outdir, "summary.xml")
    if not os.path.isfile(f):
        return None
    root = ET.parse(f).getroot()
    rows = []
    for step in root.iter("step"):
        d = {k: float(step.get(k)) for k in step.keys()}
        rows.append(d)
    return pd.DataFrame(rows)


def plot_side_by_side(rule_df, rl_df, column, ylabel, title, outpath):
    """Compare histogram distributions side by side"""
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.kdeplot(rule_df[column].dropna(), label="Rule-Based", ax=ax, fill=True, alpha=0.4)
    sns.kdeplot(rl_df[column].dropna(), label="RL-Based", ax=ax, fill=True, alpha=0.4)
    ax.set_title(title)
    ax.set_xlabel(ylabel)
    ax.legend()
    fig.tight_layout()
    fig.savefig(outpath, dpi=150)
    print(f"Saved {outpath}")


def plot_timeseries_comparison(rule_df, rl_df, column, ylabel, title, outpath):
    """Compare time series over simulation time"""
    fig, ax = plt.subplots(figsize=(10, 5))
    if "time" in rule_df.columns:
        ax.plot(rule_df["time"], rule_df[column], label="Rule-Based")
    if "time" in rl_df.columns:
        ax.plot(rl_df["time"], rl_df[column], label="RL-Based")
    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(ylabel)
    ax.legend()
    fig.tight_layout()
    fig.savefig(outpath, dpi=150)
    print(f"Saved {outpath}")


def compute_pdr(packets):
    if packets is None or packets.empty:
        return None
    total = len(packets)
    success = packets["success"].sum()
    return success / total if total > 0 else 0.0


def compute_latency(packets):
    if packets is None or packets.empty or not {"rx_time", "gen_time"}.issubset(packets.columns):
        return None
    lat = (packets["rx_time"] - packets["gen_time"]).dropna()
    return lat.mean() if not lat.empty else None


# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rule_dir", required=True, help="Path to Rule-Based simulation outputs")
    ap.add_argument("--rl_dir", required=True, help="Path to RL simulation outputs")
    ap.add_argument("--show", action="store_true", help="Show plots interactively")
    args = ap.parse_args()

    output_dir = "plots_comparison"
    ensure_dir(output_dir)

    # ---------- Load Data ----------
    packets_rule = read_packets(args.rule_dir)
    packets_rl = read_packets(args.rl_dir)

    trip_rule = parse_tripinfo(args.rule_dir)
    trip_rl = parse_tripinfo(args.rl_dir)

    summary_rule = parse_summary(args.rule_dir)
    summary_rl = parse_summary(args.rl_dir)

    # ---------- VANET Metrics ----------
    # Packet Delivery Ratio
    pdr_rule = compute_pdr(packets_rule)
    pdr_rl = compute_pdr(packets_rl)
    print(f"PDR: Rule-Based={pdr_rule:.3f}, RL={pdr_rl:.3f}")

    # Latency
    latency_rule = compute_latency(packets_rule)
    latency_rl = compute_latency(packets_rl)
    print(f"Mean Latency (s): Rule-Based={latency_rule:.3f}, RL={latency_rl:.3f}")

    # Plot travel time comparison
    if trip_rule is not None and trip_rl is not None:
        plot_side_by_side(trip_rule, trip_rl, "duration", "Duration (s)", "Travel Time Distribution", 
                          os.path.join(output_dir, "travel_time_comparison.png"))
        plot_side_by_side(trip_rule, trip_rl, "waitingTime", "Waiting Time (s)", "Vehicle Waiting Time Distribution", 
                          os.path.join(output_dir, "waiting_time_comparison.png"))
        plot_side_by_side(trip_rule, trip_rl, "timeLoss", "Time Loss (s)", "Time Loss Distribution", 
                          os.path.join(output_dir, "time_loss_comparison.png"))

    # Plot summary metrics over time
    for col in ["running", "departed", "arrived", "waiting"]:
        if summary_rule is not None and summary_rl is not None and col in summary_rule.columns:
            plot_timeseries_comparison(summary_rule, summary_rl, col, "Count", f"{col.capitalize()} Vehicles Over Time",
                                       os.path.join(output_dir, f"{col}_timeseries_comparison.png"))

    # Throughput over time (approximate, using packet size / time bins)
    def compute_throughput(packets):
        if packets is None or packets.empty:
            return None
        df = packets.copy()
        tcol = "rx_time" if "rx_time" in df.columns else "gen_time"
        df = df.dropna(subset=[tcol])
        df["t_bin"] = df[tcol].round().astype(int)
        agg_bits = df.groupby("t_bin")["size_bits"].sum().reset_index()
        agg_bits["mbps"] = agg_bits["size_bits"] / 1_000_000
        return agg_bits

    tp_rule = compute_throughput(packets_rule)
    tp_rl = compute_throughput(packets_rl)

    if tp_rule is not None and tp_rl is not None:
        fig, ax = plt.subplots(figsize=(10,5))
        ax.plot(tp_rule["t_bin"], tp_rule["mbps"], label="Rule-Based")
        ax.plot(tp_rl["t_bin"], tp_rl["mbps"], label="RL-Based")
        ax.set_title("Throughput Over Time")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Mb/s")
        ax.legend()
        fig.tight_layout()
        fig.savefig(os.path.join(output_dir, "throughput_comparison.png"))
        print(f"Saved {os.path.join(output_dir, 'throughput_comparison.png')}")

    # Show plots if requested
    if args.show:
        plt.show()


if __name__ == "__main__":
    main()
