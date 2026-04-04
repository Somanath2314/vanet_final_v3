#!/usr/bin/env python3
"""
Generate IEEE paper figures and tables from benchmark results.

Produces:
  - Table II:  Network communication metrics (PDR, latency, emergency comm)
  - Table III: Traffic performance comparison (wait, queue, speed)
  - Fig 2:    Average wait time by vehicle type (bar chart)
  - Fig 3:    Average queue length by vehicle type (bar chart)
  - Fig 4:    Average communication delay over time (line chart)
  - Fig 5:    Average wait time over time (line chart)
  - Fig 9:    DQN epsilon decay schedule (from trained model config)
  - Fig 10:   DQN training convergence (episode rewards from trained model)

Usage:
  python generate_paper_figures.py
  python generate_paper_figures.py --results-dir benchmark_results
  python generate_paper_figures.py --nosec-only
"""

import argparse
import json
import os
import glob
import numpy as np

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("WARNING: matplotlib not available. Tables will be generated but plots will be skipped.")


def load_raw_metrics(results_dir):
    """Load all per-run benchmark_metrics.json files from raw_metrics/."""
    raw_dir = os.path.join(results_dir, 'raw_metrics')
    files = sorted(glob.glob(os.path.join(raw_dir, '*.json')))
    
    data = []
    for f in files:
        with open(f) as fh:
            d = json.load(fh)
            data.append(d)
    
    return data


def group_by(data, keys):
    """Group data records by a tuple of key values."""
    groups = {}
    for d in data:
        key = tuple(d.get(k) for k in keys)
        groups.setdefault(key, []).append(d)
    return groups


def mean_std(values):
    """Return mean ± std string."""
    if not values:
        return "N/A", 0.0, 0.0
    m, s = np.mean(values), np.std(values)
    return f"{m:.2f} ± {s:.2f}", m, s


def extract_metric(records, key, default=0):
    """Extract a metric from a list of records."""
    return [r.get(key, default) for r in records if r.get(key) is not None]


# ──────────────────────────────────────────────────────────────────
#  TABLE II: Network Communication Metrics (proximity mode)
# ──────────────────────────────────────────────────────────────────

def generate_table_ii(data, output_dir):
    """Table II: Network metrics for proximity mode, nosec vs sec."""
    print("\n" + "="*70)
    print("  TABLE II: Network Communication Metrics")
    print("="*70)
    
    # Group by security
    groups = group_by([d for d in data if d.get('mode') == 'proximity'], ['security'])
    
    metrics_spec = [
        ('overall_pdr', 'Overall PDR (%)', '%'),
        ('v2v_pdr', 'V2V PDR (%)', '%'),
        ('v2i_pdr', 'V2I PDR (%)', '%'),
        ('avg_latency_ms', 'Avg Latency (ms)', 'ms'),
        ('emergency_comm_avg_delay_ms', 'Emergency Comm Delay (ms)', 'ms'),
        ('emergency_comm_success_rate', 'Emergency Comm Success Rate (%)', '%'),
    ]
    
    header = f"{'Metric':<35} {'No Security':>20} {'With Security':>20}"
    print(header)
    print("-" * 77)
    
    lines = [header, "-" * 77]
    
    for key, label, unit in metrics_spec:
        row = f"{label:<35}"
        for sec in [False, True]:
            recs = groups.get((sec,), [])
            vals = extract_metric(recs, key)
            s, _, _ = mean_std(vals)
            row += f" {s:>20}"
        print(row)
        lines.append(row)
    
    # Save
    path = os.path.join(output_dir, 'table_ii_network_metrics.txt')
    with open(path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f"\n  Saved: {path}")


# ──────────────────────────────────────────────────────────────────
#  TABLE III: Traffic Performance Comparison (density vs proximity)
# ──────────────────────────────────────────────────────────────────

def generate_table_iii(data, output_dir):
    """Table III: Traffic metrics comparing density (adaptive) vs proximity (RL)."""
    print("\n" + "="*70)
    print("  TABLE III: Traffic Performance Comparison")
    print("="*70)
    
    # Use no-security data for traffic comparison
    nosec = [d for d in data if not d.get('security', False)]
    groups = group_by(nosec, ['mode'])
    
    metrics_spec = [
        ('normal_avg_wait', 'Normal Avg Wait (s)'),
        ('emergency_avg_wait', 'Emergency Avg Wait (s)'),
        ('avg_queue_length', 'Avg Queue Length'),
        ('emergency_avg_queue_length', 'Emergency Avg Queue Length'),
        ('normal_avg_queue_length', 'Normal Avg Queue Length'),
        ('avg_trip_speed', 'Avg Trip Speed (m/s)'),
        ('total_completed_vehicles', 'Total Completed Vehicles'),
        ('throughput_veh_per_min', 'Throughput (veh/min)'),
    ]
    
    modes_display = [
        ('fixed', 'Fixed Time'),
        ('density', 'Density Based'),
        ('proximity', 'Proximity Based RL'),
    ]
    
    header = f"{'Metric':<30}"
    for _, label in modes_display:
        header += f" {label:>20}"
    print(header)
    print("-" * 95)
    
    lines = [header, "-" * 95]
    
    for key, label in metrics_spec:
        row = f"{label:<30}"
        for mode_key, _ in modes_display:
            recs = groups.get((mode_key,), [])
            vals = extract_metric(recs, key)
            s, _, _ = mean_std(vals)
            row += f" {s:>20}"
        print(row)
        lines.append(row)
    
    # Save
    path = os.path.join(output_dir, 'table_iii_traffic_comparison.txt')
    with open(path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f"\n  Saved: {path}")


# ──────────────────────────────────────────────────────────────────
#  FULL COMPARISON TABLE (all metrics, all modes, sec vs nosec)
# ──────────────────────────────────────────────────────────────────

def generate_full_table(data, output_dir):
    """Full comparison table with all metrics."""
    print("\n" + "="*70)
    print("  FULL COMPARISON TABLE")
    print("="*70)
    
    for sec_val, sec_label in [(False, 'No Security'), (True, 'With Security')]:
        subset = [d for d in data if d.get('security', False) == sec_val]
        if not subset:
            continue
        
        groups = group_by(subset, ['mode'])
        
        all_metrics = [
            ('avg_wait_time', 'Avg Wait Time (s)'),
            ('avg_trip_speed', 'Avg Trip Speed (m/s)'),
            ('avg_queue_length', 'Avg Queue Length'),
            ('emergency_avg_queue_length', 'Emergency Avg Queue Length'),
            ('normal_avg_queue_length', 'Normal Avg Queue Length'),
            ('total_completed_vehicles', 'Total Completed Vehicles'),
            ('throughput_veh_per_min', 'Throughput (veh/min)'),
            ('emergency_avg_wait', 'Emergency Avg Wait (s)'),
            ('emergency_avg_speed', 'Emergency Avg Speed (m/s)'),
            ('emergency_completed', 'Emergency Vehicles Completed'),
            ('normal_avg_wait', 'Normal Avg Wait (s)'),
            ('normal_avg_speed', 'Normal Avg Speed (m/s)'),
            ('normal_completed', 'Normal Vehicles Completed'),
            ('v2v_pdr', 'V2V PDR (%)'),
            ('v2i_pdr', 'V2I PDR (%)'),
            ('overall_pdr', 'Overall PDR (%)'),
            ('avg_latency_ms', 'Avg Comm Latency (ms)'),
            ('emergency_comm_success_rate', 'Emergency Comm Success (%)'),
            ('emergency_comm_avg_delay_ms', 'Emergency Comm Delay (ms)'),
            ('elapsed_time_s', 'Simulation Runtime (s)'),
        ]
        
        header = f"\n  --- {sec_label} ---\n"
        header += f"{'Metric':<35} {'Fixed':>18} {'Density':>18} {'Proximity':>18}"
        print(header)
        print("-" * 91)
        
        lines = [header, "-" * 91]
        
        for key, label in all_metrics:
            row = f"{label:<35}"
            for mode in ['fixed', 'density', 'proximity']:
                recs = groups.get((mode,), [])
                vals = extract_metric(recs, key)
                s, _, _ = mean_std(vals)
                row += f" {s:>18}"
            print(row)
            lines.append(row)
        
        path = os.path.join(output_dir, f'full_comparison_{sec_label.lower().replace(" ", "_")}.txt')
        with open(path, 'w') as f:
            f.write('\n'.join(lines) + '\n')
        print(f"\n  Saved: {path}")


# ──────────────────────────────────────────────────────────────────
#  FIG 2: Average Wait Time by Vehicle Type (Bar Chart)
# ──────────────────────────────────────────────────────────────────

def generate_fig2(data, output_dir):
    """Bar chart: avg wait time by vehicle type, grouped by vehicle type, bars per mode."""
    if not HAS_MPL:
        return
    
    nosec = [d for d in data if not d.get('security', False)]
    groups = group_by(nosec, ['mode'])
    
    modes = ['fixed', 'density', 'proximity']
    mode_labels = ['Fixed Time', 'Density Based', 'Proximity Based RL']
    mode_colors = ['#A5A5A5', '#ED7D31', '#548235']
    
    # Gather data: [normal, emergency] for each mode
    vtype_labels = ['Normal Vehicle\nAverage Waiting Time', 'Emergency Vehicle\nAverage Waiting Time']
    vtype_keys = ['normal_avg_wait', 'emergency_avg_wait']
    
    # means[mode_idx][vtype_idx]
    means = []
    stds = []
    for mode in modes:
        recs = groups.get((mode,), [])
        m_row, s_row = [], []
        for key in vtype_keys:
            vals = extract_metric(recs, key)
            m_row.append(np.mean(vals) if vals else 0)
            s_row.append(np.std(vals) if vals else 0)
        means.append(m_row)
        stds.append(s_row)
    
    n_groups = len(vtype_labels)
    n_bars = len(modes)
    width = 0.25
    x = np.arange(n_groups)
    
    fig, ax = plt.subplots(figsize=(9, 6))
    
    all_bars = []
    for i in range(n_bars):
        offset = (i - (n_bars - 1) / 2) * width
        bars = ax.bar(x + offset, [means[i][j] for j in range(n_groups)], width,
                      yerr=[stds[i][j] for j in range(n_groups)],
                      label=mode_labels[i], color=mode_colors[i], capsize=4,
                      edgecolor='white', linewidth=0.5)
        all_bars.append(bars)
    
    ax.set_ylabel('Waiting Time (seconds)', fontsize=13)
    ax.set_title('Average Waiting Time by Vehicle Type', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(vtype_labels, fontsize=11)
    ax.set_xlabel('Vehicle Type', fontsize=12)
    ax.legend(fontsize=10, loc='upper right')
    ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(bottom=0)
    
    for bars in all_bars:
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax.annotate(f'{h:.2f}', xy=(bar.get_x() + bar.get_width() / 2, h),
                           xytext=(0, 3), textcoords="offset points",
                           ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    fig.tight_layout()
    path = os.path.join(output_dir, 'fig2_wait_time_by_type.png')
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {path}")


# ──────────────────────────────────────────────────────────────────
#  FIG 3: Average Queue Length by Vehicle Type (Bar Chart)
# ──────────────────────────────────────────────────────────────────

def generate_fig3(data, output_dir):
    """Bar chart: avg queue length by vehicle type, grouped by vehicle type, bars per mode."""
    if not HAS_MPL:
        return
    
    nosec = [d for d in data if not d.get('security', False)]
    groups = group_by(nosec, ['mode'])
    
    modes = ['fixed', 'density', 'proximity']
    mode_labels = ['Fixed Time', 'Density Based', 'Proximity Based RL']
    mode_colors = ['#A5A5A5', '#ED7D31', '#548235']
    
    vtype_labels = ['Normal Vehicle\nAverage Queue Length', 'Emergency Vehicle\nAverage Queue Length']
    vtype_keys = ['normal_avg_queue_length', 'emergency_avg_queue_length']
    
    means = []
    stds = []
    for mode in modes:
        recs = groups.get((mode,), [])
        m_row, s_row = [], []
        for key in vtype_keys:
            vals = extract_metric(recs, key)
            m_row.append(np.mean(vals) if vals else 0)
            s_row.append(np.std(vals) if vals else 0)
        means.append(m_row)
        stds.append(s_row)
    
    n_groups = len(vtype_labels)
    n_bars = len(modes)
    width = 0.25
    x = np.arange(n_groups)
    
    fig, ax = plt.subplots(figsize=(9, 6))
    
    all_bars = []
    for i in range(n_bars):
        offset = (i - (n_bars - 1) / 2) * width
        bars = ax.bar(x + offset, [means[i][j] for j in range(n_groups)], width,
                      yerr=[stds[i][j] for j in range(n_groups)],
                      label=mode_labels[i], color=mode_colors[i], capsize=4,
                      edgecolor='white', linewidth=0.5)
        all_bars.append(bars)
    
    ax.set_ylabel('Queue Length (vehicles)', fontsize=13)
    ax.set_title('Average Queue Length by Vehicle Type', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(vtype_labels, fontsize=11)
    ax.set_xlabel('Vehicle Type', fontsize=12)
    ax.legend(fontsize=10, loc='upper right')
    ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(bottom=0)
    
    for bars in all_bars:
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax.annotate(f'{h:.2f}', xy=(bar.get_x() + bar.get_width() / 2, h),
                           xytext=(0, 3), textcoords="offset points",
                           ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    fig.tight_layout()
    path = os.path.join(output_dir, 'fig3_queue_length_by_type.png')
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {path}")


# ──────────────────────────────────────────────────────────────────
#  FIG 4: Communication Delay Over Time (Line Chart)
# ──────────────────────────────────────────────────────────────────

def average_time_series(records, key, max_steps=1000):
    """Average per-step time series across multiple runs, handling different lengths."""
    all_series = [r.get(key, []) for r in records if r.get(key)]
    if not all_series:
        return [], []
    
    max_len = min(max(len(s) for s in all_series), max_steps)
    
    means = []
    stds = []
    for i in range(max_len):
        vals = [s[i] for s in all_series if i < len(s)]
        if vals:
            means.append(np.mean(vals))
            stds.append(np.std(vals))
        else:
            means.append(0)
            stds.append(0)
    
    return means, stds


def generate_fig4(data, output_dir):
    """Line chart: average communication delay over simulation time."""
    if not HAS_MPL:
        return
    
    nosec = [d for d in data if not d.get('security', False)]
    groups = group_by(nosec, ['mode'])
    
    fig, ax = plt.subplots(figsize=(10, 5))
    
    mode_styles = [
        ('fixed', 'Fixed Time', '#A5A5A5', '--'),
        ('density', 'Density Based', '#4472C4', '-.'),
        ('proximity', 'Proximity Based RL', '#ED7D31', '-'),
    ]
    
    for mode, label, color, linestyle in mode_styles:
        recs = groups.get((mode,), [])
        means, stds = average_time_series(recs, 'per_step_delay_ms')
        if means:
            steps = np.arange(1, len(means) + 1)
            means_arr = np.array(means)
            stds_arr = np.array(stds)
            ax.plot(steps, means_arr, label=label, color=color, linestyle=linestyle, linewidth=1.5)
            ax.fill_between(steps, means_arr - stds_arr, means_arr + stds_arr,
                           alpha=0.15, color=color)
    
    ax.set_xlabel('timestamp(s)', fontsize=12)
    ax.set_ylabel('Avg Latency (ms)', fontsize=12)
    ax.set_title('Average Latency Over Time', fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(alpha=0.3)
    
    fig.tight_layout()
    path = os.path.join(output_dir, 'fig4_delay_over_time.png')
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {path}")


# ──────────────────────────────────────────────────────────────────
#  FIG 5: Average Wait Time Over Time (Line Chart)
# ──────────────────────────────────────────────────────────────────

def generate_fig5(data, output_dir):
    """Line chart: average wait time over simulation time."""
    if not HAS_MPL:
        return
    
    nosec = [d for d in data if not d.get('security', False)]
    groups = group_by(nosec, ['mode'])
    
    fig, ax = plt.subplots(figsize=(10, 5))
    
    mode_styles = [
        ('fixed', 'Fixed Time', '#A5A5A5', '--'),
        ('density', 'Density Based', '#4472C4', '-.'),
        ('proximity', 'Proximity Based RL', '#ED7D31', '-'),
    ]
    
    for mode, label, color, linestyle in mode_styles:
        recs = groups.get((mode,), [])
        means, stds = average_time_series(recs, 'per_step_wait_time')
        if means:
            steps = np.arange(1, len(means) + 1)
            means_arr = np.array(means)
            stds_arr = np.array(stds)
            ax.plot(steps, means_arr, label=label, color=color, linestyle=linestyle, linewidth=1.5)
            ax.fill_between(steps, means_arr - stds_arr, means_arr + stds_arr,
                           alpha=0.15, color=color)
    
    ax.set_xlabel('Simulation Step', fontsize=12)
    ax.set_ylabel('Avg Wait Time (s)', fontsize=12)
    ax.set_title('Average Wait Time Over Simulation Time', fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(alpha=0.3)
    
    fig.tight_layout()
    path = os.path.join(output_dir, 'fig5_wait_time_over_time.png')
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {path}")


# ──────────────────────────────────────────────────────────────────
#  FIG 6 (BONUS): Queue Length Over Time
# ──────────────────────────────────────────────────────────────────

def generate_fig6(data, output_dir):
    """Line chart: queue length over simulation time."""
    if not HAS_MPL:
        return
    
    nosec = [d for d in data if not d.get('security', False)]
    groups = group_by(nosec, ['mode'])
    
    fig, ax = plt.subplots(figsize=(10, 5))
    
    mode_styles = [
        ('fixed', 'Fixed Time', '#A5A5A5', '--'),
        ('density', 'Density Based', '#4472C4', '-.'),
        ('proximity', 'Proximity Based RL', '#ED7D31', '-'),
    ]
    
    for mode, label, color, linestyle in mode_styles:
        recs = groups.get((mode,), [])
        means, stds = average_time_series(recs, 'per_step_queue_length')
        if means:
            steps = np.arange(1, len(means) + 1)
            means_arr = np.array(means)
            stds_arr = np.array(stds)
            ax.plot(steps, means_arr, label=label, color=color, linestyle=linestyle, linewidth=1.5)
            ax.fill_between(steps, means_arr - stds_arr, means_arr + stds_arr,
                           alpha=0.15, color=color)
    
    ax.set_xlabel('Simulation Step', fontsize=12)
    ax.set_ylabel('Queue Length (vehicles)', fontsize=12)
    ax.set_title('Queue Length Over Simulation Time', fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(alpha=0.3)
    
    fig.tight_layout()
    path = os.path.join(output_dir, 'fig6_queue_over_time.png')
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {path}")


# ──────────────────────────────────────────────────────────────────
#  FIG 7 (BONUS): Emergency Wait Time Over Time
# ──────────────────────────────────────────────────────────────────

def generate_fig7(data, output_dir):
    """Line chart: emergency vehicle wait time over simulation time."""
    if not HAS_MPL:
        return
    
    nosec = [d for d in data if not d.get('security', False)]
    groups = group_by(nosec, ['mode'])
    
    fig, ax = plt.subplots(figsize=(10, 5))
    
    mode_styles = [
        ('fixed', 'Fixed Time', '#A5A5A5', '--'),
        ('density', 'Density Based', '#4472C4', '-.'),
        ('proximity', 'Proximity Based RL', '#ED7D31', '-'),
    ]
    
    for mode, label, color, linestyle in mode_styles:
        recs = groups.get((mode,), [])
        means, stds = average_time_series(recs, 'per_step_emergency_wait')
        if means:
            steps = np.arange(1, len(means) + 1)
            means_arr = np.array(means)
            stds_arr = np.array(stds)
            ax.plot(steps, means_arr, label=label, color=color, linestyle=linestyle, linewidth=1.5)
            ax.fill_between(steps, means_arr - stds_arr, means_arr + stds_arr,
                           alpha=0.15, color=color)
    
    ax.set_xlabel('Simulation Step', fontsize=12)
    ax.set_ylabel('Emergency Avg Wait Time (s)', fontsize=12)
    ax.set_title('Emergency Vehicle Wait Time Over Simulation Time', fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(alpha=0.3)
    
    fig.tight_layout()
    path = os.path.join(output_dir, 'fig7_emergency_wait_over_time.png')
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {path}")


# ──────────────────────────────────────────────────────────────────
#  FIG 8 (BONUS): Security Impact — PDR comparison bar chart
# ──────────────────────────────────────────────────────────────────

def generate_fig8(data, output_dir):
    """Bar chart: PDR with and without security for proximity mode."""
    if not HAS_MPL:
        return
    
    prox = [d for d in data if d.get('mode') == 'proximity']
    if not prox:
        return
    
    groups = group_by(prox, ['security'])
    
    metrics = [
        ('overall_pdr', 'Overall PDR'),
        ('v2v_pdr', 'V2V PDR'),
        ('v2i_pdr', 'V2I PDR'),
    ]
    
    nosec_means, nosec_stds = [], []
    sec_means, sec_stds = [], []
    xlabels = []
    
    for key, label in metrics:
        xlabels.append(label)
        nv = extract_metric(groups.get((False,), []), key)
        sv = extract_metric(groups.get((True,), []), key)
        nosec_means.append(np.mean(nv) if nv else 0)
        nosec_stds.append(np.std(nv) if nv else 0)
        sec_means.append(np.mean(sv) if sv else 0)
        sec_stds.append(np.std(sv) if sv else 0)
    
    x = np.arange(len(metrics))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x - width/2, nosec_means, width, yerr=nosec_stds,
           label='No Security', color='#4472C4', capsize=4)
    ax.bar(x + width/2, sec_means, width, yerr=sec_stds,
           label='With Security', color='#ED7D31', capsize=4)
    
    ax.set_ylabel('PDR (%)', fontsize=12)
    ax.set_title('Security Impact on Packet Delivery Ratio', fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels(xlabels, fontsize=11)
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(bottom=max(0, min(nosec_means + sec_means) - 10))
    
    fig.tight_layout()
    path = os.path.join(output_dir, 'fig8_security_impact_pdr.png')
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {path}")


# ──────────────────────────────────────────────────────────────────
#  FIG 9: DQN Epsilon Decay Schedule (from trained model)
# ──────────────────────────────────────────────────────────────────

def find_trained_model_dir():
    """Find the latest trained model directory with training_config.json."""
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rl_module', 'trained_models')
    if not os.path.isdir(base):
        return None
    dirs = sorted([d for d in os.listdir(base)
                   if os.path.isfile(os.path.join(base, d, 'training_config.json'))],
                  reverse=True)
    return os.path.join(base, dirs[0]) if dirs else None


def load_training_config():
    """Load training_config.json from the latest trained model."""
    model_dir = find_trained_model_dir()
    if not model_dir:
        return None, None
    config_path = os.path.join(model_dir, 'training_config.json')
    with open(config_path) as f:
        config = json.load(f)
    return config, model_dir


def generate_fig9(output_dir):
    """Plot the epsilon (exploration rate) decay schedule from the trained DQN model."""
    if not HAS_MPL:
        return

    config, model_dir = load_training_config()
    if config is None:
        print("  Skipping Fig 9: no trained model found")
        return

    eps_cfg = config.get('epsilon_schedule', {})
    total_timesteps = config.get('total_timesteps', 200000)
    eps_start = eps_cfg.get('epsilon_start', 1.0)
    eps_final = eps_cfg.get('epsilon_final', 0.05)
    exploration_fraction = eps_cfg.get('exploration_fraction', 0.3)
    exploration_steps = int(total_timesteps * exploration_fraction)

    # Build epsilon curve
    timesteps = np.arange(0, total_timesteps + 1, 100)
    epsilon = np.where(
        timesteps <= exploration_steps,
        eps_start + (eps_final - eps_start) * (timesteps / exploration_steps),
        eps_final
    )

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(timesteps, epsilon, color='#4472C4', linewidth=2)
    ax.axvline(x=exploration_steps, color='#ED7D31', linestyle='--', linewidth=1.2,
               label=f'Exploration ends ({exploration_steps:,} steps)')
    ax.axhline(y=eps_final, color='#A5A5A5', linestyle=':', linewidth=1, alpha=0.7,
               label=f'$\\epsilon_{{final}}$ = {eps_final}')

    ax.set_xlabel('Training Timestep', fontsize=12)
    ax.set_ylabel('Epsilon ($\\epsilon$)', fontsize=12)
    ax.set_title('DQN Epsilon Decay Schedule', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(alpha=0.3)
    ax.set_xlim(0, total_timesteps)
    ax.set_ylim(0, 1.05)
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{int(x/1000)}k'))

    # Annotate key points
    ax.annotate(f'$\\epsilon_{{start}}$ = {eps_start}',
                xy=(0, eps_start), xytext=(total_timesteps * 0.08, eps_start - 0.1),
                fontsize=10, arrowprops=dict(arrowstyle='->', color='gray'),
                bbox=dict(boxstyle='round,pad=0.3', facecolor='wheat', alpha=0.7))
    ax.annotate(f'$\\epsilon_{{final}}$ = {eps_final}',
                xy=(exploration_steps, eps_final),
                xytext=(exploration_steps + total_timesteps * 0.05, eps_final + 0.15),
                fontsize=10, arrowprops=dict(arrowstyle='->', color='gray'),
                bbox=dict(boxstyle='round,pad=0.3', facecolor='wheat', alpha=0.7))

    fig.tight_layout()
    path = os.path.join(output_dir, 'fig9_epsilon_decay_schedule.png')
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {path}")


# ──────────────────────────────────────────────────────────────────
#  FIG 10: DQN Training Convergence (from trained model)
# ──────────────────────────────────────────────────────────────────

def generate_fig10(output_dir):
    """Plot training convergence: episode rewards over episodes from the trained DQN model."""
    if not HAS_MPL:
        return

    config, model_dir = load_training_config()
    if config is None:
        print("  Skipping Fig 10: no trained model found")
        return

    results = config.get('training_results', {})
    rewards = results.get('episode_rewards', [])
    if not rewards:
        print("  Skipping Fig 10: no episode rewards in training config")
        return

    episodes = np.arange(1, len(rewards) + 1)
    rewards_arr = np.array(rewards)

    # Compute rolling average (window=10)
    window = 10
    rolling_avg = np.convolve(rewards_arr, np.ones(window) / window, mode='valid')
    rolling_episodes = episodes[window - 1:]

    fig, ax = plt.subplots(figsize=(10, 5))

    # Raw episode rewards
    ax.plot(episodes, rewards_arr / 1000, color='#A5A5A5', alpha=0.4, linewidth=0.8,
            label='Episode Reward')
    # Rolling average
    ax.plot(rolling_episodes, rolling_avg / 1000, color='#ED7D31', linewidth=2,
            label=f'Rolling Avg (window={window})')

    # Mark exploration / exploitation phases
    eps_cfg = config.get('epsilon_schedule', {})
    total_timesteps = config.get('total_timesteps', 200000)
    exploration_fraction = eps_cfg.get('exploration_fraction', 0.3)
    steps_per_episode = results.get('episode_rewards', [0])
    # Each episode is ~1000 steps according to the config
    env_cfg = config.get('environment', {})
    horizon = env_cfg.get('horizon', 1000)
    exploration_episodes = int(total_timesteps * exploration_fraction / horizon) if horizon else 60

    ax.axvline(x=exploration_episodes, color='#4472C4', linestyle='--', linewidth=1.2,
               label=f'Exploration → Exploitation (ep {exploration_episodes})')

    # Final average annotation
    final_avg = results.get('final_avg_reward_last10', np.mean(rewards_arr[-10:]))
    ax.axhline(y=final_avg / 1000, color='#548235', linestyle=':', linewidth=1,
               alpha=0.7, label=f'Final Avg (last 10): {final_avg/1000:.1f}k')

    ax.set_xlabel('Episode', fontsize=12)
    ax.set_ylabel('Episode Reward (×1000)', fontsize=12)
    ax.set_title('DQN Training Convergence', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10, loc='lower right')
    ax.grid(alpha=0.3)
    ax.set_xlim(1, len(rewards))

    fig.tight_layout()
    path = os.path.join(output_dir, 'fig10_training_convergence.png')
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {path}")


# ──────────────────────────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Generate IEEE paper figures and tables')
    parser.add_argument('--results-dir', type=str, default='benchmark_results',
                       help='Path to benchmark results directory')
    parser.add_argument('--nosec-only', action='store_true',
                       help='Only use no-security data')
    args = parser.parse_args()
    
    results_dir = os.path.abspath(args.results_dir)
    output_dir = os.path.join(results_dir, 'paper_figures')
    os.makedirs(output_dir, exist_ok=True)
    
    print("="*70)
    print("  GENERATING PAPER FIGURES AND TABLES")
    print("="*70)
    print(f"  Results dir: {results_dir}")
    print(f"  Output dir:  {output_dir}")
    
    # Load data
    data = load_raw_metrics(results_dir)
    print(f"  Loaded {len(data)} benchmark runs")
    
    if args.nosec_only:
        data = [d for d in data if not d.get('security', False)]
        print(f"  Filtered to {len(data)} no-security runs")
    
    if not data:
        print("\n  ERROR: No benchmark data found. Run benchmarks first.")
        return
    
    # Summary
    modes = set(d.get('mode') for d in data)
    secs = set(d.get('security') for d in data)
    print(f"  Modes: {sorted(modes)}")
    print(f"  Security configs: {sorted(secs)}")
    
    # Generate everything
    generate_table_ii(data, output_dir)
    generate_table_iii(data, output_dir)
    generate_full_table(data, output_dir)
    
    print("\n" + "="*70)
    print("  GENERATING FIGURES")
    print("="*70)
    
    generate_fig2(data, output_dir)
    generate_fig3(data, output_dir)
    generate_fig4(data, output_dir)
    generate_fig5(data, output_dir)
    generate_fig6(data, output_dir)
    generate_fig7(data, output_dir)
    generate_fig8(data, output_dir)
    generate_fig9(output_dir)
    generate_fig10(output_dir)
    
    print("\n" + "="*70)
    print("  ALL DONE")
    print("="*70)
    print(f"  Output directory: {output_dir}")


if __name__ == "__main__":
    main()
