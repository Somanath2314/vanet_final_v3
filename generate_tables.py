#!/usr/bin/env python3
"""Validate all 180 benchmark result files and generate final comparison tables."""

import json
import os
import numpy as np
import pandas as pd

project_root = os.path.dirname(os.path.abspath(__file__))
raw_dir = os.path.join(project_root, 'benchmark_results', 'raw_metrics')
out_dir = os.path.join(project_root, 'benchmark_results')

# ---- Validate all 180 files ----
print("=" * 70)
print("VALIDATING ALL BENCHMARK DATA")
print("=" * 70)

issues = []
all_data = {}

for sec in ['nosec', 'sec']:
    for mode in ['fixed', 'density', 'proximity']:
        key = (mode, sec)
        all_data[key] = []
        for seed in range(42, 72):
            fname = '{}_{}_seed{}.json'.format(mode, sec, seed)
            fp = os.path.join(raw_dir, fname)
            if not os.path.exists(fp):
                issues.append('MISSING: {}'.format(fname))
                continue
            with open(fp, 'r') as f:
                data = json.load(f)
            
            if data.get('mode') != mode:
                issues.append('WRONG MODE: {} has mode={}'.format(fname, data.get('mode')))
            
            completed = data.get('total_completed_vehicles', 0)
            if completed < 200:
                issues.append('LOW COMPLETED: {} completed={}'.format(fname, completed))
            
            wait = data.get('avg_wait_time', 0)
            if wait < 0.1 or wait > 100:
                issues.append('BAD WAIT: {} wait={}'.format(fname, wait))
            
            all_data[key].append(data)

if issues:
    print("ISSUES FOUND ({}):".format(len(issues)))
    for i in issues:
        print("  " + i)
    print()
else:
    print("All 180 files OK - correct modes, valid metrics\n")

# ---- Summary statistics ----
print("Quick summary:")
for sec in ['nosec', 'sec']:
    sec_label = "No Security" if sec == 'nosec' else "With Security"
    print("  {}:".format(sec_label))
    for mode in ['fixed', 'density', 'proximity']:
        results = all_data[(mode, sec)]
        if results:
            waits = [r['avg_wait_time'] for r in results]
            arr = np.array(waits)
            print("    {}: n={} wait={:.2f} +/- {:.2f}s".format(
                mode, len(results), arr.mean(), arr.std()))
    print()

# ---- Generate comparison tables ----
display_metrics = [
    ('avg_wait_time', 'Avg Wait Time (s)'),
    ('avg_trip_speed', 'Avg Trip Speed (m/s)'),
    ('avg_queue_length', 'Avg Queue Length'),
    ('total_completed_vehicles', 'Total Completed Vehicles'),
    ('throughput_veh_per_min', 'Throughput (veh/min)'),
    ('emergency_avg_wait', 'Emergency Avg Wait (s)'),
    ('emergency_avg_speed', 'Emergency Avg Speed (m/s)'),
    ('emergency_completed', 'Emergency Vehicles Completed'),
    ('normal_avg_wait', 'Normal Avg Wait (s)'),
    ('normal_avg_speed', 'Normal Avg Speed (m/s)'),
    ('normal_completed', 'Normal Vehicles Completed'),
    ('wifi_pdr', 'WiFi PDR (%)'),
    ('wimax_pdr', 'WiMAX PDR (%)'),
    ('elapsed_time_s', 'Simulation Time (s)'),
]

for sec in ['nosec', 'sec']:
    sec_label = "WITHOUT SECURITY" if sec == 'nosec' else "WITH SECURITY"
    sec_tag = "no_security" if sec == 'nosec' else "security"
    
    rows = []
    for metric_key, metric_label in display_metrics:
        row = {'Metric': metric_label}
        for mode in ['fixed', 'density', 'proximity']:
            results = all_data[(mode, sec)]
            values = [r[metric_key] for r in results if metric_key in r and r[metric_key] is not None]
            if values:
                m = np.mean(values)
                s = np.std(values)
                row[mode.capitalize()] = "{:.2f} +/- {:.2f}".format(m, s)
            else:
                row[mode.capitalize()] = "N/A"
        rows.append(row)
    
    df = pd.DataFrame(rows).set_index('Metric')
    
    print("=" * 70)
    print("  COMPARISON TABLE -- {}".format(sec_label))
    print("  (30 seeds x 1000 steps each)")
    print("=" * 70)
    print(df.to_string())
    print()
    
    csv_path = os.path.join(out_dir, 'comparison_{}.csv'.format(sec_tag))
    df.to_csv(csv_path)
    print("  Saved: {}".format(csv_path))
    print()

print("DONE")
