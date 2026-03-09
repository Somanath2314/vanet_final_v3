#!/usr/bin/env python3
"""Re-run only the missing nosec benchmark runs."""

import json
import os
import subprocess
import sys
import time
import shutil

project_root = os.path.dirname(os.path.abspath(__file__))
cached_dir = os.path.join(project_root, 'benchmark_results', 'raw_metrics')
model_path = 'rl_module/trained_models/dqn_traffic_20260304_222100/dqn_traffic_final.zip'

# Find missing nosec runs
missing = []
for mode in ['density', 'proximity']:
    for seed in range(42, 72):
        f = os.path.join(cached_dir, '{}_nosec_seed{}.json'.format(mode, seed))
        if not os.path.exists(f):
            missing.append((mode, seed))

print('Missing runs: {}'.format(len(missing)))
for mode, seed in missing:
    print('  {} nosec seed={}'.format(mode, seed))

# Run each missing one
for mode, seed in missing:
    print('\nRunning {} nosec seed={}...'.format(mode, seed), flush=True)
    t0 = time.time()
    
    run_name = '{}_nosec_seed{}'.format(mode, seed)
    output_dir = os.path.join(project_root, 'sumo_simulation', 'benchmark_output', run_name)
    os.makedirs(output_dir, exist_ok=True)
    
    cmd = [
        sys.executable, 
        os.path.join(project_root, 'sumo_simulation', 'run_complete_integrated.py'),
        '--mode', mode,
        '--steps', '1000',
        '--seed', str(seed),
        '--output', output_dir,
        '--edge',
    ]
    
    if mode == 'proximity':
        cmd.extend(['--model', model_path, '--proximity', '250'])
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=project_root)
    
    # Read metrics
    metrics_file = os.path.join(output_dir, 'benchmark_metrics.json')
    if os.path.exists(metrics_file):
        with open(metrics_file, 'r') as f:
            data = json.load(f)
        cached_file = os.path.join(cached_dir, '{}.json'.format(run_name))
        with open(cached_file, 'w') as f:
            json.dump(data, f, indent=2)
        shutil.rmtree(output_dir, ignore_errors=True)
        dt = time.time() - t0
        print('  OK ({:.1f}s) wait={:.1f}s completed={}'.format(
            dt, data['avg_wait_time'], data['total_completed_vehicles']))
    else:
        dt = time.time() - t0
        print('  FAILED ({:.1f}s)'.format(dt))
        if result.stderr:
            for line in result.stderr.strip().split('\n')[-3:]:
                print('    {}'.format(line))
        shutil.rmtree(output_dir, ignore_errors=True)

print('\nDone. Checking completeness...')
still_missing = 0
for mode in ['fixed', 'density', 'proximity']:
    for seed in range(42, 72):
        f = os.path.join(cached_dir, '{}_nosec_seed{}.json'.format(mode, seed))
        if not os.path.exists(f):
            print('  STILL MISSING: {} nosec seed={}'.format(mode, seed))
            still_missing += 1

if still_missing == 0:
    print('All nosec runs complete!')
else:
    print('{} runs still missing'.format(still_missing))
