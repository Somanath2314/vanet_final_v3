#!/usr/bin/env python3
"""
plot_vanet_metrics.py

Generate rich visualizations for VANET + SUMO outputs.

Inputs (default path: ./output/):
 - v2i_packets.csv   (from network_metrics_sim/analyze script)
 - v2i_metrics.csv   (summary with rsu utilization + aggregates)
 - tripinfo.xml      (SUMO tripinfo output)
 - summary.xml       (SUMO summary output)

Outputs:
 - ./output/plots/*.png  (many plots saved)
Optionally shows interactive windows with --show

Usage:
  python plot_vanet_metrics.py --out ./sumo_simulation/output --show

Requires: pandas, numpy, matplotlib, seaborn
"""

import os
import argparse
import math
import json
import ast
import xml.etree.ElementTree as ET
from typing import Dict, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

sns.set(style="whitegrid", context="talk")


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def read_packets(outdir: str) -> Optional[pd.DataFrame]:
    f = os.path.join(outdir, "v2i_packets.csv")
    if not os.path.isfile(f):
        print(f"WARN: Missing {f}")
        return None
    df = pd.read_csv(f)
    for col in ["gen_time", "enq_time", "start_tx", "end_tx", "rx_time"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "success" in df.columns:
        if df["success"].dtype == object:
            df["success"] = df["success"].astype(str).str.lower().isin(["true", "1", "yes"])
        else:
            df["success"] = df["success"].astype(bool)
    if "size_bits" not in df.columns:
        df["size_bits"] = 8 * 1024
    return df


def read_metrics(outdir: str) -> Optional[pd.DataFrame]:
    f = os.path.join(outdir, "v2i_metrics.csv")
    if not os.path.isfile(f):
        print(f"WARN: Missing {f}")
        return None
    try:
        df = pd.read_csv(f)
        return df
    except Exception:
        try:
            kv = pd.read_csv(f, header=None, names=["key", "value"])
            return kv
        except Exception as e:
            print(f"ERROR reading metrics csv: {e}")
            return None


def parse_tripinfo(outdir: str) -> Optional[pd.DataFrame]:
    f = os.path.join(outdir, "tripinfo.xml")
    if not os.path.isfile(f):
        print(f"WARN: Missing {f}")
        return None
    try:
        root = ET.parse(f).getroot()
    except Exception as e:
        print(f"WARN: Could not parse tripinfo.xml: {e}")
        return None
    rows = []
    for ti in root.iter("tripinfo"):
        rows.append({
            "id": ti.get("id"),
            "depart": float(ti.get("depart", 0)),
            "arrival": float(ti.get("arrival", 0)),
            "duration": float(ti.get("duration", 0)),
            "routeLength": float(ti.get("routeLength", 0)),
            "waitingTime": float(ti.get("waitingTime", 0)),
            "timeLoss": float(ti.get("timeLoss", 0)),
            "departDelay": float(ti.get("departDelay", 0)),
            "rerouteNo": float(ti.get("rerouteNo", 0)),
        })
    if not rows:
        return None
    return pd.DataFrame(rows)


def parse_summary(outdir: str) -> Optional[pd.DataFrame]:
    f = os.path.join(outdir, "summary.xml")
    if not os.path.isfile(f):
        print(f"WARN: Missing {f}")
        return None
    try:
        root = ET.parse(f).getroot()
    except Exception as e:
        print(f"WARN: Could not parse summary.xml: {e}")
        return None
    rows = []
    for step in root.iter("step"):
        d = {k: float(step.get(k)) if k != "time" else float(step.get(k)) for k in step.keys()}
        rows.append(d)
    if not rows:
        return None
    df = pd.DataFrame(rows)
    if "time" in df.columns:
        df.sort_values("time", inplace=True)
    return df


# ---------- Plot helpers ----------

def savefig(fig, outpath):
    fig.tight_layout()
    fig.savefig(outpath, dpi=150)
    print(f"Saved {outpath}")


def parse_dict_column(val) -> Dict:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return ast.literal_eval(val)
        except Exception:
            try:
                return json.loads(val)
            except Exception:
                return {}
    return {}


# ---------- Plot functions ----------

def plot_pdr_over_time(packets: pd.DataFrame, plots_dir: str, window_s: float = 10.0):
    if packets is None or packets.empty or "gen_time" not in packets.columns:
        return
    df = packets.copy()
    df["t"] = df["gen_time"].fillna(df.get("rx_time", 0)).fillna(0.0)
    df = df.dropna(subset=["t"])
    df["t_bin"] = df["t"].round().astype(int)
    agg = df.groupby("t_bin")["success"].agg(["sum", "count"]).reset_index()
    agg.rename(columns={"sum": "succ", "count": "total"}, inplace=True)
    agg["pdr"] = np.where(agg["total"] > 0, agg["succ"] / agg["total"], np.nan)
    agg.sort_values("t_bin", inplace=True)
    win = max(1, int(window_s))
    agg["pdr_smooth"] = agg["pdr"].rolling(win, min_periods=1).mean()
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(agg["t_bin"], agg["pdr"], alpha=0.3, label="PDR (per sec)")
    ax.plot(agg["t_bin"], agg["pdr_smooth"], linewidth=2, label=f"PDR (rolling {win}s)")
    ax.set_title("Packet Delivery Ratio over Time")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("PDR")
    ax.set_ylim(0, 1.05)
    ax.legend()
    savefig(fig, os.path.join(plots_dir, "pdr_over_time.png"))


def plot_latency_hist_cdf(packets: pd.DataFrame, plots_dir: str):
    if packets is None or packets.empty:
        return
    df = packets.copy()
    if {"rx_time", "gen_time"}.issubset(df.columns):
        lat = (df["rx_time"] - df["gen_time"]).dropna()
    elif "latency_ms" in df.columns:
        lat = (df["latency_ms"].dropna()) / 1000.0
    else:
        return
    lat = lat[(lat >= 0) & (lat < lat.quantile(0.99) if len(lat) > 10 else True)]
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.histplot(lat, bins=40, kde=True, ax=ax)
    ax.set_title("Latency Distribution (s)")
    ax.set_xlabel("Latency (s)")
    savefig(fig, os.path.join(plots_dir, "latency_hist.png"))
    fig, ax = plt.subplots(figsize=(10, 4))
    lat_sorted = np.sort(lat.values)
    y = np.arange(1, len(lat_sorted)+1) / len(lat_sorted)
    ax.plot(lat_sorted, y)
    ax.set_title("Latency CDF")
    ax.set_xlabel("Latency (s)")
    ax.set_ylabel("CDF")
    savefig(fig, os.path.join(plots_dir, "latency_cdf.png"))


def plot_latency_timeseries(packets: pd.DataFrame, plots_dir: str):
    if packets is None or packets.empty or not {"gen_time", "rx_time"}.issubset(packets.columns):
        return
    df = packets.copy()
    df = df[df["success"] == True]
    df = df.dropna(subset=["gen_time", "rx_time"])
    if df.empty:
        return
    df["t"] = df["rx_time"]
    df["latency"] = df["rx_time"] - df["gen_time"]
    df = df.dropna(subset=["latency"])
    df["t_bin"] = df["t"].round().astype(int)
    agg = df.groupby("t_bin")["latency"].mean().reset_index()
    if agg.empty:
        return
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(agg["t_bin"], agg["latency"], label="Mean Latency")
    ax.set_title("Latency Over Time")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Latency (s)")
    savefig(fig, os.path.join(plots_dir, "latency_over_time.png"))


def plot_throughput_timeseries(packets: pd.DataFrame, plots_dir: str):
    if packets is None or packets.empty:
        return
    df = packets.copy()
    df = df[df.get("success", True) == True]
    tcol = "rx_time" if "rx_time" in df.columns else ("end_tx" if "end_tx" in df.columns else None)
    if tcol is None:
        return
    df = df.dropna(subset=[tcol, "size_bits"])
    if df.empty:
        return
    df["t_bin"] = df[tcol].round().astype(int)
    agg_bits = df.groupby("t_bin")["size_bits"].sum().reset_index()
    agg_bits["mbps"] = agg_bits["size_bits"] / 1_000_000
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(agg_bits["t_bin"], agg_bits["mbps"], label="Throughput (Mb/s)")
    ax.set_title("Throughput Over Time")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Mb/s")
    savefig(fig, os.path.join(plots_dir, "throughput_over_time.png"))


def plot_loss_reasons(packets: pd.DataFrame, plots_dir: str):
    if packets is None or packets.empty or "reason" not in packets.columns:
        return
    df = packets.copy()
    reasons = df.loc[df["success"] == False, "reason"].fillna("unknown")
    counts = reasons.value_counts().reset_index()
    counts.columns = ["reason", "count"]
    if counts.empty:
        return
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.barplot(data=counts, x="reason", y="count", ax=ax)
    ax.set_title("Packet Loss Reasons")
    ax.set_xlabel("")
    ax.set_ylabel("Count")
    for tick in ax.get_xticklabels():
        tick.set_rotation(30)
        tick.set_ha("right")
    savefig(fig, os.path.join(plots_dir, "loss_reasons.png"))


def plot_per_rsu_success(packets: pd.DataFrame, plots_dir: str):
    if packets is None or packets.empty or "rsu" not in packets.columns:
        return
    df = packets.copy()
    grp = df.groupby("rsu")["success"].agg(["sum", "count"]).reset_index()
    grp["pdr"] = np.where(grp["count"] > 0, grp["sum"] / grp["count"], np.nan)
    grp = grp.dropna(subset=["pdr"])
    if grp.empty:
        return
    grp.sort_values("pdr", inplace=True)
    fig, ax = plt.subplots(figsize=(10, max(4, 0.3*len(grp))))
    sns.barplot(data=grp, y="rsu", x="pdr", ax=ax)
    ax.set_title("Per-RSU PDR")
    ax.set_xlabel("PDR")
    ax.set_ylabel("RSU")
    ax.set_xlim(0, 1.05)
    savefig(fig, os.path.join(plots_dir, "per_rsu_pdr.png"))


def plot_rsu_utilization(metrics_df: pd.DataFrame, plots_dir: str):
    if metrics_df is None or metrics_df.empty:
        return
    util_map = {}
    if set(["key", "value"]).issubset(metrics_df.columns):
        for _, row in metrics_df.iterrows():
            key = str(row["key"]).lower()
            if "rsu" in key and "util" in key:
                util_map = parse_dict_column(row["value"]) or {}
                break
    else:
        col = None
        for c in metrics_df.columns:
            if "rsu_util" in c:
                col = c
                break
            if "rsu_stats" in c:
                col = c
                break
        if col is not None:
            util_map = parse_dict_column(metrics_df.iloc[0][col]) or {}
            if util_map and isinstance(next(iter(util_map.values())), dict):
                util_map = {k: v.get("utilization", 0.0) for k, v in util_map.items()}
    if not util_map:
        return
    util_df = pd.DataFrame({"rsu": list(util_map.keys()), "util": list(util_map.values())})
    util_df = util_df.dropna(subset=["util"])
    if util_df.empty:
        return
    util_df.sort_values("util", inplace=True)
    fig, ax = plt.subplots(figsize=(10, max(4, 0.3*len(util_df))))
    sns.barplot(data=util_df, y="rsu", x="util", ax=ax)
    ax.set_title("Per-RSU Channel Utilization")
    ax.set_xlabel("Utilization (fraction of time busy)")
    ax.set_ylabel("RSU")
    ax.set_xlim(0, 1.0)
    savefig(fig, os.path.join(plots_dir, "per_rsu_utilization.png"))


def plot_handoff_over_time(packets: pd.DataFrame, plots_dir: str):
    if packets is None or packets.empty or "reason" not in packets.columns:
        return
    tcol = "rx_time" if "rx_time" in packets.columns else ("end_tx" if "end_tx" in packets.columns else None)
    if tcol is None:
        return
    df = packets.copy()
    df = df.dropna(subset=[tcol])
    if df.empty:
        return
    df["t_bin"] = df[tcol].round().astype(int)
    df["handoff_ok"] = (df["reason"] == "handoff_ok").astype(int)
    df["handoff_fail"] = (df["reason"] == "handoff_fail").astype(int)
    agg = df.groupby("t_bin")[["handoff_ok", "handoff_fail"]].sum().reset_index()
    if agg.empty:
        return
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(agg["t_bin"], agg["handoff_ok"], label="handoff_ok")
    ax.plot(agg["t_bin"], agg["handoff_fail"], label="handoff_fail")
    ax.set_title("Handoffs Over Time")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Count per sec")
    ax.legend()
    savefig(fig, os.path.join(plots_dir, "handoffs_over_time.png"))


def plot_tripinfo_distributions(ti: pd.DataFrame, plots_dir: str):
    if ti is None or ti.empty:
        return
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.histplot(ti["duration"], bins=40, kde=True, ax=ax)
    ax.set_title("Vehicle Travel Time Distribution")
    ax.set_xlabel("Duration (s)")
    savefig(fig, os.path.join(plots_dir, "travel_time_hist.png"))
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.histplot(ti["waitingTime"], bins=40, kde=True, ax=ax)
    ax.set_title("Vehicle Waiting Time Distribution")
    ax.set_xlabel("Waiting Time (s)")
    savefig(fig, os.path.join(plots_dir, "waiting_time_hist.png"))
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.histplot(ti["timeLoss"], bins=40, kde=True, ax=ax)
    ax.set_title("Time Loss Distribution")
    ax.set_xlabel("Time Loss (s)")
    savefig(fig, os.path.join(plots_dir, "time_loss_hist.png"))
    fig, ax = plt.subplots(figsize=(6, 6))
    sns.boxplot(y=ti["duration"], ax=ax)
    ax.set_title("Travel Time Boxplot")
    ax.set_ylabel("Duration (s)")
    savefig(fig, os.path.join(plots_dir, "travel_time_box.png"))


def plot_summary_timeseries(summary: pd.DataFrame, plots_dir: str):
    if summary is None or summary.empty or "time" not in summary.columns:
        return
    fig, ax = plt.subplots(figsize=(10, 4))
    for col in ["running", "departed", "arrived", "waiting"]:
        if col in summary.columns:
            ax.plot(summary["time"], summary[col], label=col)
    ax.set_title("Network State Over Time")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Count")
    ax.legend()
    savefig(fig, os.path.join(plots_dir, "summary_timeseries.png"))


# ---------- Main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "output"), help="Path to SUMO output directory")
    ap.add_argument("--show", action="store_true", help="Show figures interactively")
    args = ap.parse_args()

    outdir = os.path.abspath(args.out)
    plots_dir = os.path.join(outdir, "plots")
    ensure_dir(plots_dir)

    packets = read_packets(outdir)
    metrics = read_metrics(outdir)
    tripinfo = parse_tripinfo(outdir)
    summary = parse_summary(outdir)

    plot_pdr_over_time(packets, plots_dir)
    plot_latency_hist_cdf(packets, plots_dir)
    plot_latency_timeseries(packets, plots_dir)
    plot_throughput_timeseries(packets, plots_dir)
    plot_loss_reasons(packets, plots_dir)
    plot_per_rsu_success(packets, plots_dir)
    plot_rsu_utilization(metrics, plots_dir)
    plot_handoff_over_time(packets, plots_dir)
    plot_tripinfo_distributions(tripinfo, plots_dir)
    plot_summary_timeseries(summary, plots_dir)

    if args.show:
        plt.show()


if __name__ == "__main__":
    main()
