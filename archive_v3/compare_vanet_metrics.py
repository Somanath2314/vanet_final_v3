#!/usr/bin/env python3
"""
Compare Rule-Based vs RL Traffic Control Simulations (Tripinfo & Summary Only)

Usage:
    python compare_vanet_metrics_simple.py --rule_dir ./output_rule --rl_dir ./output_rl --show

Generates plots:
 - Travel time, Waiting time, Time loss
 - Vehicle counts over time (summary.xml)
"""

import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import xml.etree.ElementTree as ET

# ---------- Utility Functions ----------
def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

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
    return pd.DataFrame(rows) if rows else None

def parse_summary(outdir):
    f = os.path.join(outdir, "summary.xml")
    if not os.path.isfile(f):
        return None
    root = ET.parse(f).getroot()
    rows = []
    for step in root.iter("step"):
        rows.append({k: float(step.get(k)) for k in step.keys()})
    return pd.DataFrame(rows) if rows else None

def plot_side_by_side(rule_df, rl_df, column, ylabel, title, outpath):
    """Compare histogram distributions side by side"""
    plt.figure(figsize=(10,5))
    plt.hist(rule_df[column].dropna(), bins=30, alpha=0.5, label="Rule-Based")
    plt.hist(rl_df[column].dropna(), bins=30, alpha=0.5, label="RL-Based")
    plt.title(title)
    plt.xlabel(ylabel)
    plt.ylabel("Count")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outpath)
    print(f"Saved {outpath}")
    plt.close()

def plot_timeseries_comparison(rule_df, rl_df, column, ylabel, title, outpath):
    """Compare time series from summary.xml"""
    plt.figure(figsize=(10,5))
    if "time" in rule_df.columns:
        plt.plot(rule_df["time"], rule_df[column], label="Rule-Based")
    if "time" in rl_df.columns:
        plt.plot(rl_df["time"], rl_df[column], label="RL-Based")
    plt.title(title)
    plt.xlabel("Time (s)")
    plt.ylabel(ylabel)
    plt.legend()
    plt.tight_layout()
    plt.savefig(outpath)
    print(f"Saved {outpath}")
    plt.close()

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rule_dir", required=True, help="Path to Rule-Based simulation outputs")
    ap.add_argument("--rl_dir", required=True, help="Path to RL simulation outputs")
    ap.add_argument("--show", action="store_true", help="Show plots interactively")
    args = ap.parse_args()

    output_dir = "plots_comparison_simple"
    ensure_dir(output_dir)

    trip_rule = parse_tripinfo(args.rule_dir)
    trip_rl = parse_tripinfo(args.rl_dir)
    summary_rule = parse_summary(args.rule_dir)
    summary_rl = parse_summary(args.rl_dir)

    # ----------------- Tripinfo Plots -----------------
    if trip_rule is not None and trip_rl is not None:
        plot_side_by_side(trip_rule, trip_rl, "duration", "Duration (s)", "Travel Time Distribution",
                          os.path.join(output_dir, "travel_time_comparison.png"))
        plot_side_by_side(trip_rule, trip_rl, "waitingTime", "Waiting Time (s)", "Vehicle Waiting Time Distribution",
                          os.path.join(output_dir, "waiting_time_comparison.png"))
        plot_side_by_side(trip_rule, trip_rl, "timeLoss", "Time Loss (s)", "Time Loss Distribution",
                          os.path.join(output_dir, "time_loss_comparison.png"))

    # ----------------- Summary Plots -----------------
    if summary_rule is not None and summary_rl is not None:
        # Make sure time column exists
        if "time" not in summary_rule.columns:
            summary_rule["time"] = summary_rule.index
        if "time" not in summary_rl.columns:
            summary_rl["time"] = summary_rl.index

        for col in ["running", "departed", "arrived", "waiting"]:
            if col in summary_rule.columns and col in summary_rl.columns:
                plot_timeseries_comparison(summary_rule, summary_rl, col, "Vehicles", f"{col.capitalize()} Vehicles Over Time",
                                           os.path.join(output_dir, f"{col}_timeseries_comparison.png"))

    # Show interactively if requested
    if args.show:
        import matplotlib.pyplot as plt
        plt.show()

if __name__ == "__main__":
    main()
