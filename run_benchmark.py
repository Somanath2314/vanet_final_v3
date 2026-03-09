#!/usr/bin/env python3
"""
VANET Benchmark Runner
Runs all control modes (fixed, density, proximity) across multiple seeds,
with and without security, and produces comparison tables.

Usage:
    python run_benchmark.py --seeds 30 --steps 1000
    python run_benchmark.py --seeds 5 --steps 500 --quick   # Quick test
"""

import os
import sys
import json
import subprocess
import argparse
import time
from collections import defaultdict

import numpy as np
import pandas as pd


def run_single_simulation(mode, seed, steps, security=False, model_path=None, proximity=250):
    """Run a single simulation and return the benchmark metrics JSON."""
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(project_root, "sumo_simulation", "run_complete_integrated.py")
    
    # Unique output dir per run to avoid conflicts
    sec_tag = "sec" if security else "nosec"
    run_name = f"{mode}_{sec_tag}_seed{seed}"
    output_dir = os.path.join(project_root, "sumo_simulation", "benchmark_output", run_name)
    
    # Check if already completed (cached metrics exist)
    cached_dir = os.path.join(project_root, "benchmark_results", "raw_metrics")
    cached_file = os.path.join(cached_dir, f"{run_name}.json")
    if os.path.exists(cached_file):
        with open(cached_file, 'r') as f:
            return json.load(f)
    
    os.makedirs(output_dir, exist_ok=True)
    
    cmd = [
        sys.executable, script,
        "--mode", mode,
        "--steps", str(steps),
        "--seed", str(seed),
        "--output", output_dir,
        "--edge",
    ]
    
    if security:
        cmd.append("--security")
    
    if mode == "proximity" and model_path:
        cmd.extend(["--model", model_path, "--proximity", str(proximity)])
    
    # Run headless (no GUI)
    env = os.environ.copy()
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=600,  # 10 min max per run
            env=env,
            cwd=project_root
        )
        
        if result.returncode != 0:
            print(f"    WARN: Non-zero exit ({result.returncode})")
            # Still try to read metrics
        
        # Read benchmark_metrics.json from output dir
        metrics_file = os.path.join(output_dir, "benchmark_metrics.json")
        if os.path.exists(metrics_file):
            with open(metrics_file, 'r') as f:
                metrics = json.load(f)
            
            # Cache the small metrics JSON and delete the large output dir
            os.makedirs(cached_dir, exist_ok=True)
            with open(cached_file, 'w') as f:
                json.dump(metrics, f, indent=2)
            
            # Cleanup large files to save disk space
            import shutil
            shutil.rmtree(output_dir, ignore_errors=True)
            
            return metrics
        else:
            print(f"    ERROR: No metrics file at {metrics_file}")
            if result.stderr:
                # Print last few lines of stderr for diagnosis
                err_lines = result.stderr.strip().split('\n')
                for line in err_lines[-5:]:
                    print(f"      {line}")
            # Cleanup failed run too
            import shutil
            shutil.rmtree(output_dir, ignore_errors=True)
            return None
            
    except subprocess.TimeoutExpired:
        print(f"    ERROR: Timeout (>600s)")
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)
        return None
    except Exception as e:
        print(f"    ERROR: {e}")
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)
        return None


def aggregate_metrics(all_results):
    """Compute mean ± std for each metric across seeds."""
    if not all_results:
        return {}
    
    # Metrics we want to aggregate
    metric_keys = [
        'avg_wait_time', 'avg_trip_speed', 'avg_queue_length',
        'total_completed_vehicles', 'throughput_veh_per_min',
        'emergency_avg_wait', 'emergency_avg_speed', 'emergency_completed',
        'normal_avg_wait', 'normal_avg_speed', 'normal_completed',
        'wifi_pdr', 'wimax_pdr',
        'wifi_packets_sent', 'wifi_packets_received',
        'wimax_packets_sent', 'wimax_packets_received',
        'elapsed_time_s',
    ]
    
    agg = {}
    for key in metric_keys:
        values = [r[key] for r in all_results if key in r and r[key] is not None]
        if values:
            agg[key] = {
                'mean': np.mean(values),
                'std': np.std(values),
                'min': np.min(values),
                'max': np.max(values),
                'n': len(values),
            }
    
    return agg


def format_table(results_by_mode, security_label):
    """Build a comparison DataFrame from aggregated results."""
    
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
    
    rows = []
    for metric_key, metric_label in display_metrics:
        row = {'Metric': metric_label}
        for mode in ['fixed', 'density', 'proximity']:
            agg = results_by_mode.get(mode, {})
            if metric_key in agg:
                m = agg[metric_key]
                row[mode.capitalize()] = f"{m['mean']:.2f} ± {m['std']:.2f}"
            else:
                row[mode.capitalize()] = "N/A"
        rows.append(row)
    
    df = pd.DataFrame(rows)
    df = df.set_index('Metric')
    return df


def main():
    parser = argparse.ArgumentParser(description='VANET Benchmark Runner')
    parser.add_argument('--seeds', type=int, default=30,
                       help='Number of seed runs (default: 30)')
    parser.add_argument('--seed-start', type=int, default=42,
                       help='Starting seed value (default: 42)')
    parser.add_argument('--steps', type=int, default=1000,
                       help='Simulation steps per run (default: 1000)')
    parser.add_argument('--model', type=str, 
                       default='rl_module/trained_models/dqn_traffic_20260304_222100/dqn_traffic_final.zip',
                       help='Path to trained DQN model for proximity mode')
    parser.add_argument('--quick', action='store_true',
                       help='Quick test with fewer seeds and steps')
    parser.add_argument('--modes', type=str, default='fixed,density,proximity',
                       help='Comma-separated list of modes to benchmark')
    parser.add_argument('--skip-nosec', action='store_true',
                       help='Skip the without-security runs')
    parser.add_argument('--skip-sec', action='store_true',
                       help='Skip the with-security runs')
    
    args = parser.parse_args()
    
    if args.quick:
        args.seeds = 3
        args.steps = 300
    
    modes = [m.strip() for m in args.modes.split(',')]
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    output_base = os.path.join(project_root, "benchmark_results")
    os.makedirs(output_base, exist_ok=True)
    
    print("=" * 70)
    print("VANET BENCHMARK RUNNER")
    print("=" * 70)
    print(f"  Modes: {modes}")
    print(f"  Seeds: {seeds[0]}–{seeds[-1]} ({len(seeds)} runs per mode)")
    print(f"  Steps: {args.steps}")
    print(f"  Model: {args.model}")
    print(f"  Security runs: {'No-Security' if not args.skip_nosec else 'SKIPPED'}"
          f" + {'Security' if not args.skip_sec else 'SKIPPED'}")
    total_runs = len(modes) * len(seeds) * (
        (1 if not args.skip_nosec else 0) + (1 if not args.skip_sec else 0))
    print(f"  Total runs: {total_runs}")
    print("=" * 70)
    print()
    
    # Collect all raw results
    all_raw = []
    
    for security_enabled in [False, True]:
        if security_enabled and args.skip_sec:
            continue
        if not security_enabled and args.skip_nosec:
            continue
        
        sec_label = "WITH SECURITY" if security_enabled else "WITHOUT SECURITY"
        print(f"\n{'='*70}")
        print(f"  PHASE: {sec_label}")
        print(f"{'='*70}")
        
        results_by_mode = {}
        
        for mode in modes:
            print(f"\n  Mode: {mode.upper()}")
            print(f"  {'─'*50}")
            
            mode_results = []
            
            for i, seed in enumerate(seeds):
                print(f"    [{i+1}/{len(seeds)}] seed={seed} ... ", end="", flush=True)
                t0 = time.time()
                
                metrics = run_single_simulation(
                    mode=mode,
                    seed=seed,
                    steps=args.steps,
                    security=security_enabled,
                    model_path=args.model,
                )
                
                dt = time.time() - t0
                
                if metrics:
                    mode_results.append(metrics)
                    all_raw.append(metrics)
                    print(f"OK ({dt:.1f}s) wait={metrics['avg_wait_time']:.1f}s "
                          f"speed={metrics['avg_trip_speed']:.1f}m/s "
                          f"completed={metrics['total_completed_vehicles']}")
                else:
                    print(f"FAILED ({dt:.1f}s)")
            
            # Aggregate
            agg = aggregate_metrics(mode_results)
            results_by_mode[mode] = agg
            
            n = len(mode_results)
            print(f"\n  {mode.upper()} summary ({n}/{len(seeds)} successful):")
            if 'avg_wait_time' in agg:
                print(f"    Avg Wait: {agg['avg_wait_time']['mean']:.2f} ± {agg['avg_wait_time']['std']:.2f}s")
            if 'avg_trip_speed' in agg:
                print(f"    Avg Speed: {agg['avg_trip_speed']['mean']:.2f} ± {agg['avg_trip_speed']['std']:.2f} m/s")
            if 'total_completed_vehicles' in agg:
                print(f"    Completed: {agg['total_completed_vehicles']['mean']:.0f} ± {agg['total_completed_vehicles']['std']:.0f}")
        
        # Build and print comparison table
        sec_tag = "security" if security_enabled else "no_security"
        table = format_table(results_by_mode, sec_label)
        
        print(f"\n\n{'='*70}")
        print(f"  COMPARISON TABLE — {sec_label}")
        print(f"{'='*70}")
        print(table.to_string())
        print()
        
        # Save to CSV
        csv_path = os.path.join(output_base, f"comparison_{sec_tag}.csv")
        table.to_csv(csv_path)
        print(f"  Saved: {csv_path}")
        
        # Save raw aggregated results as JSON
        json_agg_path = os.path.join(output_base, f"aggregated_{sec_tag}.json")
        # Convert numpy types for JSON serialization
        serializable = {}
        for mode, agg in results_by_mode.items():
            serializable[mode] = {}
            for k, v in agg.items():
                serializable[mode][k] = {kk: float(vv) for kk, vv in v.items()}
        with open(json_agg_path, 'w') as f:
            json.dump(serializable, f, indent=2)
        print(f"  Saved: {json_agg_path}")
    
    # Save all raw results
    raw_path = os.path.join(output_base, "all_raw_results.json")
    with open(raw_path, 'w') as f:
        json.dump(all_raw, f, indent=2)
    print(f"\n  All raw results: {raw_path}")
    
    print(f"\n{'='*70}")
    print("  BENCHMARK COMPLETE")
    print(f"{'='*70}")
    print(f"  Results directory: {output_base}")


if __name__ == "__main__":
    main()
