#!/usr/bin/env python3
"""
Train RL Models for VANET Hybrid Traffic Control.
Supports both stable-baselines3 DQN and PPO with VANETTrafficEnv.

Usage:
    python train.py                          # Default: 500k steps, headless PPO
    python train.py --timesteps 100000       # Shorter run
    python train.py --timesteps 20000 --lr 0.0003  # Quick test run
    python train.py --algo dqn --max-tl 8 --max-joint-actions 100000
    python train.py --algo ppo --max-tl 0 --timesteps 500000
"""

import os
import sys
import json
import argparse
import time
import random
import math
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

# ---------------------------------------------------------------------------
# Path setup – ensure project root and rl_module are importable
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
for p in (PROJECT_ROOT, SCRIPT_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np
import traci
from stable_baselines3 import DQN, PPO
from stable_baselines3.common.callbacks import (
    CheckpointCallback,
    BaseCallback,
)
from stable_baselines3.common.monitor import Monitor

from vanet_env import VANETTrafficEnv


# ---------------------------------------------------------------------------
# Custom callback – restarts SUMO when an episode ends (horizon reached)
# ---------------------------------------------------------------------------
class SUMOResetCallback(BaseCallback):
    """
    Restarts the SUMO simulation at the beginning of each new episode so the
    environment always has fresh traffic.  Also logs episode-level metrics.
    """

    def __init__(
        self,
        verbose: int = 0,
        heartbeat_steps: int = 100,
        total_timesteps: Optional[int] = None,
    ):
        super().__init__(verbose)
        self.episode_count = 0
        self.episode_rewards: list[float] = []
        self._current_ep_reward = 0.0
        self.heartbeat_steps = max(1, int(heartbeat_steps))
        self.total_timesteps = total_timesteps
        self._start_wall_time = 0.0
        self._last_heartbeat_step = 0

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if not math.isfinite(seconds):
            return "unknown"
        total_seconds = int(max(0, seconds))
        hours, rem = divmod(total_seconds, 3600)
        minutes, secs = divmod(rem, 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        if minutes > 0:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    def _on_training_start(self) -> None:
        self._start_wall_time = time.time()
        self._last_heartbeat_step = 0
        print(
            f"  Live progress heartbeat: every {self.heartbeat_steps} steps",
            flush=True,
        )

    def _on_step(self) -> bool:
        # Accumulate reward
        reward = self.locals.get("rewards", [0])[0]
        try:
            reward = float(reward)
        except (TypeError, ValueError):
            reward = 0.0
        self._current_ep_reward += reward

        # Print lightweight heartbeat so long episodes do not look frozen.
        if self.num_timesteps - self._last_heartbeat_step >= self.heartbeat_steps:
            elapsed = max(1e-9, time.time() - self._start_wall_time)
            steps_per_sec = self.num_timesteps / elapsed

            if self.total_timesteps and self.total_timesteps > 0:
                pct = 100.0 * (self.num_timesteps / self.total_timesteps)
                remaining_steps = max(self.total_timesteps - self.num_timesteps, 0)
                eta_seconds = remaining_steps / steps_per_sec if steps_per_sec > 0 else float("inf")
                eta_text = self._format_duration(eta_seconds)
                print(
                    f"  Progress: {self.num_timesteps:,}/{self.total_timesteps:,} "
                    f"({pct:5.1f}%) | {steps_per_sec:6.1f} steps/s | ETA {eta_text} | "
                    f"Ep {self.episode_count + 1} reward so far: {self._current_ep_reward:8.1f}",
                    flush=True,
                )
            else:
                print(
                    f"  Progress: {self.num_timesteps:,} steps | "
                    f"{steps_per_sec:6.1f} steps/s | "
                    f"Ep {self.episode_count + 1} reward so far: {self._current_ep_reward:8.1f}",
                    flush=True,
                )
            self._last_heartbeat_step = self.num_timesteps

        # Check if episode ended (terminated or truncated)
        dones = self.locals.get("dones", [False])
        if dones[0]:
            self.episode_count += 1
            self.episode_rewards.append(self._current_ep_reward)

            avg_last10 = np.mean(self.episode_rewards[-10:])
            print(
                f"  Episode {self.episode_count:4d} | "
                f"Reward: {self._current_ep_reward:8.1f} | "
                f"Avg(10): {avg_last10:8.1f} | "
                f"Steps so far: {self.num_timesteps}"
                ,
                flush=True,
            )
            self._current_ep_reward = 0.0

        return True  # Continue training


# ---------------------------------------------------------------------------
# Environment wrapper – handles SUMO lifecycle
# ---------------------------------------------------------------------------
class SUMOEnvWrapper(Monitor):
    """Thin wrapper that keeps a reference to the SUMO command so we can
    restart on reset()."""

    def __init__(self, env, sumo_cmd, label="train", filename=None, sumo_cmd_builder=None, scenario_history=None):
        super().__init__(env, filename=filename)
        self.sumo_cmd = sumo_cmd
        self.label = label
        self._sumo_running = False
        self.sumo_cmd_builder = sumo_cmd_builder
        self.scenario_history = scenario_history if scenario_history is not None else []
        self._episode_index = 0

    def _ensure_sumo(self):
        if not self._sumo_running:
            try:
                traci.start(self.sumo_cmd, label=self.label)
                traci.switch(self.label)
                self._sumo_running = True
            except traci.exceptions.TraCIException:
                # Already connected
                traci.switch(self.label)
                self._sumo_running = True

    def reset(self, **kwargs):
        # Restart SUMO for a clean episode
        try:
            traci.close()
        except Exception:
            pass
        self._sumo_running = False

        if self.sumo_cmd_builder is not None:
            self.sumo_cmd, scenario = self.sumo_cmd_builder(self._episode_index)
            self.scenario_history.append(scenario)
            msg = (
                f"  Scenario {self._episode_index + 1}: "
                f"scale={scenario['scale']:.2f}, seed={scenario['seed']}"
            )

            route_profile = scenario.get("route_profile")
            if route_profile and route_profile.get("randomized"):
                msg += (
                    f", route veh/h={route_profile['min_vehs_per_hour']}"
                    f"..{route_profile['max_vehs_per_hour']}"
                )

            print(msg)
            self._episode_index += 1

        self._ensure_sumo()
        return super().reset(**kwargs)

    def step(self, action):
        self._ensure_sumo()
        return super().step(action)

    def close(self):
        try:
            traci.close()
        except Exception:
            pass
        self._sumo_running = False
        super().close()


# ---------------------------------------------------------------------------
# Build SUMO command and the Gym environment
# ---------------------------------------------------------------------------
def estimate_joint_action_space(action_spec: dict) -> int:
    """Return cartesian-product action space size for all controlled TLs."""
    count = 1
    for phases in action_spec.values():
        count *= max(1, len(phases))
    return count


def select_spread_traffic_lights(tl_ids: list[str], max_tl: int) -> list[str]:
    """Select traffic lights spatially spread across the map (greedy max-min)."""
    ordered = sorted(tl_ids)
    if max_tl <= 0 or len(ordered) <= max_tl:
        return ordered

    positions = {}
    for tl_id in ordered:
        try:
            positions[tl_id] = traci.junction.getPosition(tl_id)
        except Exception:
            continue

    if len(positions) < max_tl:
        return ordered[:max_tl]

    xs = [p[0] for p in positions.values()]
    ys = [p[1] for p in positions.values()]
    center = (sum(xs) / len(xs), sum(ys) / len(ys))

    def dist2(a, b):
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

    # Start from the TL farthest from geometric center.
    first = max(positions.keys(), key=lambda tl: dist2(positions[tl], center))
    selected = [first]
    remaining = [tl for tl in ordered if tl != first]

    while len(selected) < max_tl and remaining:
        best_tl = max(
            remaining,
            key=lambda cand: min(dist2(positions[cand], positions[s]) for s in selected),
        )
        selected.append(best_tl)
        remaining.remove(best_tl)

    return sorted(selected)


def resolve_route_files_from_config(config_path: str) -> list[str]:
    """Resolve absolute route file paths from a SUMO config file."""
    try:
        tree = ET.parse(config_path)
        root = tree.getroot()
        route_node = root.find("./input/route-files")
        if route_node is None:
            return []

        route_value = (route_node.get("value") or "").strip()
        if not route_value:
            return []

        config_dir = os.path.dirname(os.path.abspath(config_path))
        route_files = []
        for token in route_value.split(","):
            rel_path = token.strip()
            if not rel_path:
                continue
            route_files.append(os.path.abspath(os.path.join(config_dir, rel_path)))
        return route_files
    except Exception:
        return []


def randomize_route_flow_file(
    base_route_file: str,
    output_route_file: str,
    rng: random.Random,
    min_multiplier: float,
    max_multiplier: float,
    preserve_total: bool = True,
) -> dict:
    """Create an episode-specific route file with randomized passenger flow rates."""
    try:
        tree = ET.parse(base_route_file)
        root = tree.getroot()
    except Exception as e:
        os.makedirs(os.path.dirname(output_route_file), exist_ok=True)
        shutil.copyfile(base_route_file, output_route_file)
        return {
            "randomized": False,
            "reason": f"parse failed: {e}",
            "route_file": output_route_file,
        }

    flow_nodes = [
        node for node in root.findall("flow")
        if node.get("type") == "passenger" and node.get("vehsPerHour") is not None
    ]

    valid_nodes = []
    base_rates = []
    for node in flow_nodes:
        try:
            base_rate = float(node.get("vehsPerHour", "0"))
        except ValueError:
            continue
        if base_rate <= 0:
            continue
        valid_nodes.append(node)
        base_rates.append(base_rate)

    if not valid_nodes:
        os.makedirs(os.path.dirname(output_route_file), exist_ok=True)
        tree.write(output_route_file, encoding="UTF-8", xml_declaration=True)
        return {
            "randomized": False,
            "reason": "no passenger flows found",
            "route_file": output_route_file,
        }

    multipliers = [rng.uniform(min_multiplier, max_multiplier) for _ in valid_nodes]
    if preserve_total:
        avg_multiplier = sum(multipliers) / len(multipliers)
        if avg_multiplier > 0:
            multipliers = [m / avg_multiplier for m in multipliers]

    new_rates = []
    for node, base_rate, mult in zip(valid_nodes, base_rates, multipliers):
        new_rate = max(1, int(round(base_rate * mult)))
        node.set("vehsPerHour", str(new_rate))
        new_rates.append(new_rate)

    os.makedirs(os.path.dirname(output_route_file), exist_ok=True)
    tree.write(output_route_file, encoding="UTF-8", xml_declaration=True)

    return {
        "randomized": True,
        "route_file": output_route_file,
        "num_passenger_flows": len(new_rates),
        "min_vehs_per_hour": int(min(new_rates)),
        "max_vehs_per_hour": int(max(new_rates)),
        "avg_vehs_per_hour": float(sum(new_rates) / len(new_rates)),
        "preserve_total": bool(preserve_total),
    }


def build_env(
    config_path: str,
    log_dir: Optional[str] = None,
    algorithm: str = "PPO",
    max_tl: int = 0,
    max_joint_actions: int = 100_000,
    scenario_randomization: bool = True,
    scenario_scales: Optional[list[float]] = None,
    scenario_seed: Optional[int] = None,
    route_randomization: bool = False,
    route_rate_min: float = 0.7,
    route_rate_max: float = 1.3,
    route_preserve_total: bool = True,
):
    """Create the SB3-compatible VANET environment around SUMO."""

    sumo_binary = "sumo"  # headless – no GUI during training
    base_sumo_cmd = [
        sumo_binary,
        "-c", config_path,
        "--start",
        "--step-length", "1",
        "--no-warnings",
        "--time-to-teleport", "300",
    ]

    label = "train"

    if scenario_scales is None:
        scenario_scales = [0.7, 0.9, 1.0, 1.2, 1.4]

    rng = random.Random(scenario_seed)

    resolved_route_files = resolve_route_files_from_config(config_path)
    base_route_file = resolved_route_files[0] if resolved_route_files else None
    static_route_files = resolved_route_files[1:] if len(resolved_route_files) > 1 else []

    route_randomization_active = (
        route_randomization
        and base_route_file is not None
        and os.path.exists(base_route_file)
    )

    route_episode_dir = None
    if route_randomization_active:
        route_episode_dir = os.path.join(log_dir or os.path.dirname(os.path.abspath(config_path)), "randomized_routes")
        os.makedirs(route_episode_dir, exist_ok=True)
        print(
            f"  Route randomization: on ({route_rate_min:.2f}x..{route_rate_max:.2f}x, "
            f"preserve total={'yes' if route_preserve_total else 'no'})"
        )
    else:
        if route_randomization:
            print("  ⚠️  Route randomization requested but route-files could not be resolved from SUMO config")
        print("  Route randomization: off")

    def build_sumo_cmd_for_episode(episode_index: int):
        if scenario_randomization:
            scale = float(rng.choice(scenario_scales))
            seed = int(rng.randint(1, 2_147_483_647))
        else:
            scale = 1.0
            seed = int(scenario_seed if scenario_seed is not None else 42)

        cmd = base_sumo_cmd + ["--seed", str(seed), "--scale", f"{scale:.3f}"]

        route_profile = None
        if route_randomization_active and route_episode_dir and base_route_file:
            episode_route_file = os.path.join(route_episode_dir, f"routes_ep_{episode_index + 1:05d}.rou.xml")
            route_profile = randomize_route_flow_file(
                base_route_file=base_route_file,
                output_route_file=episode_route_file,
                rng=rng,
                min_multiplier=route_rate_min,
                max_multiplier=route_rate_max,
                preserve_total=route_preserve_total,
            )

            episode_route_files = [episode_route_file] + static_route_files
            cmd += ["--route-files", ",".join(episode_route_files)]

        scenario = {
            "episode": episode_index + 1,
            "scale": scale,
            "seed": seed,
        }
        if route_profile is not None:
            scenario["route_profile"] = route_profile
        return cmd, scenario

    # Start SUMO once to inspect traffic lights
    initial_cmd, initial_scenario = build_sumo_cmd_for_episode(0)
    traci.start(initial_cmd, label=label)
    traci.switch(label)
    print(
        f"  Initial scenario: scale={initial_scenario['scale']:.2f}, "
        f"seed={initial_scenario['seed']}"
    )

    all_tl_ids = list(traci.trafficlight.getIDList())
    selected_tl_ids = select_spread_traffic_lights(all_tl_ids, max_tl)

    print(f"  Discovered traffic lights: {len(all_tl_ids)}")
    print(f"  RL-controlled lights (pre-cap): {len(selected_tl_ids)}")

    action_spec = {}
    for tl_id in selected_tl_ids:
        try:
            logic = traci.trafficlight.getAllProgramLogics(tl_id)[0]
            phases = [phase.state for phase in logic.phases]
            action_spec[tl_id] = phases
        except Exception as e:
            print(f"  ⚠️  Could not read phases for {tl_id}: {e}")

    if not action_spec:
        raise RuntimeError("No controllable traffic lights found for RL training")

    algorithm = (algorithm or "PPO").upper()
    joint_actions = estimate_joint_action_space(action_spec)
    if algorithm == "DQN":
        while joint_actions > max_joint_actions and len(action_spec) > 1:
            drop_tl = max(action_spec.keys(), key=lambda tl: (len(action_spec[tl]), tl))
            drop_n = len(action_spec[drop_tl])
            del action_spec[drop_tl]
            joint_actions = estimate_joint_action_space(action_spec)
            print(
                f"  ⚠️  Dropped {drop_tl} ({drop_n} phases) to keep "
                f"joint action space <= {max_joint_actions:,}"
            )

    print(f"  RL traffic lights: {list(action_spec.keys())}")
    print(f"  Action spec: { {k: len(v) for k, v in action_spec.items()} }")
    if algorithm == "DQN":
        print(f"  Joint action space: {joint_actions:,}")
    else:
        print(f"  PPO factorized dimensions: {len(action_spec)}")
        print(f"  Equivalent joint combinations: {joint_actions:,}")

    env_config = {
        "beta": 20,
        "action_spec": action_spec,
        "tl_constraint_min": 5,
        "tl_constraint_max": 60,
        "sim_step": 1.0,
        "algorithm": algorithm,
        "horizon": 1000,  # steps per episode
        "max_discrete_actions": max_joint_actions,
    }

    env = VANETTrafficEnv(config=env_config)

    scenario_history = []

    # Wrap with our SUMO-aware Monitor
    wrapped = SUMOEnvWrapper(
        env,
        sumo_cmd=initial_cmd,
        label=label,
        filename=os.path.join(log_dir, "monitor") if log_dir else None,
        sumo_cmd_builder=build_sumo_cmd_for_episode,
        scenario_history=scenario_history,
    )

    print(f"  Observation space: {env.observation_space}")
    print(f"  Action space:      {env.action_space}")

    return wrapped, action_spec, scenario_history


# ---------------------------------------------------------------------------
# Main training function
# ---------------------------------------------------------------------------
def train(
    config_path: str,
    output_dir: str,
    total_timesteps: int = 500_000,
    algorithm: str = "PPO",
    learning_rate: float = 1e-4,
    buffer_size: int = 50_000,
    learning_starts: int = 1_000,
    batch_size: int = 32,
    gamma: float = 0.99,
    exploration_fraction: float = 0.30,
    exploration_final_eps: float = 0.05,
    target_update_interval: int = 1_000,
    save_freq: int = 10_000,
    max_tl: int = 0,
    max_joint_actions: int = 100_000,
    ppo_n_steps: int = 1024,
    ppo_n_epochs: int = 10,
    ppo_clip_range: float = 0.2,
    scenario_randomization: bool = True,
    scenario_scales: Optional[list[float]] = None,
    scenario_seed: Optional[int] = None,
    route_randomization: bool = False,
    route_rate_min: float = 0.7,
    route_rate_max: float = 1.3,
    route_preserve_total: bool = True,
    progress_bar: bool = False,
    heartbeat_steps: int = 100,
):
    algorithm = (algorithm or "PPO").upper()
    if algorithm not in {"DQN", "PPO"}:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_prefix = "dqn" if algorithm == "DQN" else "ppo"
    model_dir = os.path.join(output_dir, f"{model_prefix}_traffic_{timestamp}")
    os.makedirs(model_dir, exist_ok=True)

    print("=" * 70)
    print(f"  {algorithm} TRAINING — VANET Hybrid Traffic Control")
    print("=" * 70)
    print(f"  SUMO config : {config_path}")
    print(f"  Output dir  : {model_dir}")
    print(f"  Timesteps   : {total_timesteps:,}")
    print(f"  LR          : {learning_rate}")
    print(f"  Buffer      : {buffer_size:,}")
    print(f"  Batch       : {batch_size}")
    print(f"  Gamma       : {gamma}")
    if algorithm == "DQN":
        print(f"  Explore     : {exploration_fraction} -> {exploration_final_eps}")
    else:
        print(f"  PPO n_steps : {ppo_n_steps}")
        print(f"  PPO epochs  : {ppo_n_epochs}")
        print(f"  PPO clip    : {ppo_clip_range}")
    print(f"  Max RL TLs  : {max_tl}")
    print(f"  Max actions : {max_joint_actions:,}")
    print(f"  Scenario rnd: {'on' if scenario_randomization else 'off'}")
    if scenario_scales:
        print(f"  Scenario scales: {scenario_scales}")
    print(f"  Route rnd   : {'on' if route_randomization else 'off'}")
    if route_randomization:
        print(
            f"  Route mult  : {route_rate_min:.2f}..{route_rate_max:.2f} "
            f"(preserve total={'yes' if route_preserve_total else 'no'})"
        )
    print(f"  Progress bar: {'on' if progress_bar else 'off'}")
    print(f"  Heartbeat   : {heartbeat_steps} steps")
    print("=" * 70)
    print()

    # ---- environment ----
    print("Setting up SUMO environment …")
    log_dir = os.path.join(model_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    env, action_spec, scenario_history = build_env(
        config_path,
        log_dir=log_dir,
        algorithm=algorithm,
        max_tl=max_tl,
        max_joint_actions=max_joint_actions,
        scenario_randomization=scenario_randomization,
        scenario_scales=scenario_scales,
        scenario_seed=scenario_seed,
        route_randomization=route_randomization,
        route_rate_min=route_rate_min,
        route_rate_max=route_rate_max,
        route_preserve_total=route_preserve_total,
    )

    # ---- model ----
    print(f"\nCreating {algorithm} model …")
    if algorithm == "DQN":
        model = DQN(
            "MlpPolicy",
            env,
            learning_rate=learning_rate,
            buffer_size=buffer_size,
            learning_starts=learning_starts,
            batch_size=batch_size,
            gamma=gamma,
            exploration_fraction=exploration_fraction,
            exploration_final_eps=exploration_final_eps,
            target_update_interval=target_update_interval,
            verbose=0,
            tensorboard_log=os.path.join(model_dir, "tensorboard"),
            device="auto",
        )
    else:
        model = PPO(
            "MlpPolicy",
            env,
            learning_rate=learning_rate,
            n_steps=ppo_n_steps,
            batch_size=batch_size,
            n_epochs=ppo_n_epochs,
            gamma=gamma,
            clip_range=ppo_clip_range,
            verbose=0,
            tensorboard_log=os.path.join(model_dir, "tensorboard"),
            device="auto",
        )
    print(f"  ✅ {algorithm} model created\n")

    # ---- callbacks ----
    ckpt_cb = CheckpointCallback(
        save_freq=save_freq,
        save_path=os.path.join(model_dir, "checkpoints"),
        name_prefix=f"{model_prefix}_traffic",
    )
    sumo_cb = SUMOResetCallback(
        verbose=0,
        heartbeat_steps=heartbeat_steps,
        total_timesteps=total_timesteps,
    )

    # ---- train ----
    print("Starting training …\n")
    t0 = time.time()

    try:
        model.learn(
            total_timesteps=total_timesteps,
            callback=[ckpt_cb, sumo_cb],
            log_interval=10,
            progress_bar=progress_bar,
        )
    except KeyboardInterrupt:
        print("\n⚠️  Training interrupted — saving current model …")
        interrupted_path = os.path.join(model_dir, f"{model_prefix}_traffic_interrupted")
        model.save(interrupted_path)
        print(f"  Saved: {interrupted_path}.zip")
    except Exception as e:
        print(f"\n❌ Training error: {e}")
        import traceback
        traceback.print_exc()
    else:
        elapsed = time.time() - t0
        print(f"\n✅ Training completed in {elapsed/60:.1f} minutes")

    # ---- save final model ----
    final_path = os.path.join(model_dir, f"{model_prefix}_traffic_final")
    model.save(final_path)
    print(f"  Final model : {final_path}.zip")

    # ---- save training config (plain text) ----
    cfg_path = os.path.join(model_dir, "config.txt")
    explore_steps = int(exploration_fraction * total_timesteps)
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write(f"Algorithm: {algorithm}\n")
        f.write(f"SUMO Config: {config_path}\n")
        f.write(f"Total Timesteps: {total_timesteps}\n")
        f.write(f"Learning Rate: {learning_rate}\n")
        f.write(f"Batch Size: {batch_size}\n")
        f.write(f"Gamma: {gamma}\n")
        if algorithm == "DQN":
            f.write(f"Buffer Size: {buffer_size}\n")
            f.write(f"Exploration: {exploration_fraction} -> {exploration_final_eps}\n")
            f.write(f"Epsilon Start: 1.0\n")
            f.write(f"Epsilon End: {exploration_final_eps}\n")
            f.write(
                f"Epsilon Decay: linear over first {explore_steps:,} steps "
                f"({exploration_fraction*100:.0f}% of training)\n"
            )
            f.write(f"Target Network Update Interval: {target_update_interval}\n")
            f.write(f"Learning Starts: {learning_starts}\n")
        else:
            f.write(f"PPO n_steps: {ppo_n_steps}\n")
            f.write(f"PPO epochs: {ppo_n_epochs}\n")
            f.write(f"PPO clip range: {ppo_clip_range}\n")
        f.write(f"Episodes completed: {sumo_cb.episode_count}\n")
        if sumo_cb.episode_rewards:
            f.write(f"Final avg reward (last 10): {np.mean(sumo_cb.episode_rewards[-10:]):.2f}\n")
            f.write(f"Best episode reward: {max(sumo_cb.episode_rewards):.2f}\n")
    print(f"  Config      : {cfg_path}")

    # ---- save detailed JSON config (for reproducibility / paper) ----
    json_cfg = {
        "sumo_config": config_path,
        "algorithm": algorithm,
        "framework": "stable-baselines3",
        "policy": "MlpPolicy",
        "total_timesteps": total_timesteps,
        "learning_rate": learning_rate,
        "batch_size": batch_size,
        "gamma": gamma,
        "reward_coefficients": {
            "alpha_1_speed": {"value": 0.01, "description": "c * penalize_min_speed(8 km/h): +0.01 per vehicle above threshold"},
            "alpha_2_waiting": {"value": -0.5, "description": "c * penalize_max_wait(60 steps, penalty=-50): -0.5 per idled vehicle"},
            "alpha_3_emergency": {
                "fast_bonus": 200, "moderate_bonus": 100, "slow_penalty": -150,
                "wait_penalty": -100, "greenwave_bonus": 50,
                "description": "Emergency vehicle speed/wait bonuses and penalties",
            },
            "alpha_4_queue": {
                "severe_penalty": -20, "moderate_penalty": -5,
                "description": "Queue congestion penalty per lane (avg speed < 2 m/s or < 5 m/s)",
            },
            "base_scaling_c": 0.01,
            "emergency_weight_reduction": {
                "base_factor": 0.3, "queue_factor": 0.5,
                "description": "When emergency vehicles present: R = 0.3*R_base + R_emerg + 0.5*R_queue",
            },
        },
        "environment": {
            "beta": 20,
            "horizon": 1000,
            "tl_constraint_min": 5,
            "tl_constraint_max": 60,
            "sim_step": 1.0,
            "num_controlled_traffic_lights": len(action_spec),
            "controlled_traffic_lights": list(action_spec.keys()),
            "joint_action_space": estimate_joint_action_space(action_spec),
            "max_joint_actions_limit": max_joint_actions,
            "scenario_randomization": scenario_randomization,
            "scenario_scales": scenario_scales,
            "scenario_seed": scenario_seed,
            "route_randomization": route_randomization,
            "route_rate_multiplier_min": route_rate_min,
            "route_rate_multiplier_max": route_rate_max,
            "route_preserve_total": route_preserve_total,
            "scenarios_observed": scenario_history,
        },
        "training_results": {
            "episodes_completed": sumo_cb.episode_count,
            "episode_rewards": sumo_cb.episode_rewards,
            "final_avg_reward_last10": float(np.mean(sumo_cb.episode_rewards[-10:])) if sumo_cb.episode_rewards else None,
            "best_episode_reward": float(max(sumo_cb.episode_rewards)) if sumo_cb.episode_rewards else None,
            "worst_episode_reward": float(min(sumo_cb.episode_rewards)) if sumo_cb.episode_rewards else None,
        },
        "seed": 42,
        "device": "auto",
    }

    if algorithm == "DQN":
        json_cfg["buffer_size"] = buffer_size
        json_cfg["learning_starts"] = learning_starts
        json_cfg["target_update_interval"] = target_update_interval
        json_cfg["epsilon_schedule"] = {
            "type": "linear",
            "epsilon_start": 1.0,
            "epsilon_final": exploration_final_eps,
            "exploration_fraction": exploration_fraction,
            "exploration_timesteps": explore_steps,
            "description": (
                f"Linear decay from 1.0 to {exploration_final_eps} over the "
                f"first {exploration_fraction*100:.0f}% of training "
                f"({explore_steps:,} steps), then held constant."
            ),
        }
    else:
        json_cfg["ppo_config"] = {
            "n_steps": ppo_n_steps,
            "n_epochs": ppo_n_epochs,
            "clip_range": ppo_clip_range,
        }
    json_path = os.path.join(model_dir, "training_config.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_cfg, f, indent=2)
    print(f"  JSON config : {json_path}")

    # ---- save convergence plot ----
    if sumo_cb.episode_rewards and len(sumo_cb.episode_rewards) >= 2:
        try:
            import matplotlib
            matplotlib.use("Agg")  # non-interactive backend
            import matplotlib.pyplot as plt

            rewards = sumo_cb.episode_rewards
            episodes = list(range(1, len(rewards) + 1))

            # Compute rolling averages
            window = min(10, len(rewards))
            rolling_avg = []
            for i in range(len(rewards)):
                start = max(0, i - window + 1)
                rolling_avg.append(np.mean(rewards[start:i + 1]))

            fig, ax = plt.subplots(figsize=(10, 6))
            ax.plot(episodes, rewards, alpha=0.3, color="steelblue", linewidth=0.8, label="Episode reward")
            ax.plot(episodes, rolling_avg, color="darkorange", linewidth=2.0,
                    label=f"Rolling mean ({window}-episode)")
            ax.set_xlabel("Episode", fontsize=12)
            ax.set_ylabel("Cumulative Reward", fontsize=12)
            ax.set_title(f"{algorithm} Training Convergence — VANET Traffic Control", fontsize=14)
            ax.legend(fontsize=11)
            ax.grid(True, alpha=0.3)

            # Add annotation for final performance
            final_avg = np.mean(rewards[-window:])
            ax.axhline(y=final_avg, color="green", linestyle="--", alpha=0.5, linewidth=1)
            ax.annotate(
                f"Final avg: {final_avg:.1f}",
                xy=(len(rewards), final_avg),
                xytext=(-120, 20),
                textcoords="offset points",
                fontsize=10,
                arrowprops=dict(arrowstyle="->", color="green"),
                color="green",
            )

            plot_path = os.path.join(model_dir, "convergence_plot.png")
            fig.savefig(plot_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            print(f"  Conv. plot  : {plot_path}")

            # Also save raw rewards CSV for external plotting
            csv_path = os.path.join(model_dir, "episode_rewards.csv")
            with open(csv_path, "w", encoding="utf-8") as f:
                f.write("episode,reward,rolling_avg\n")
                for ep, r, ra in zip(episodes, rewards, rolling_avg):
                    f.write(f"{ep},{r:.4f},{ra:.4f}\n")
            print(f"  Rewards CSV : {csv_path}")

        except ImportError:
            print("  ⚠️  matplotlib not installed — skipping convergence plot")
        except Exception as e:
            print(f"  ⚠️  Could not generate convergence plot: {e}")

    # ---- cleanup ----
    env.close()

    print()
    print("=" * 70)
    print("  DONE — Load the model with:")
    loader = "DQN" if algorithm == "DQN" else "PPO"
    print(f'    model = {loader}.load("{final_path}")')
    print()
    print("  Run simulation with:")
    print(f'    .\\run_vanet.ps1 -proximity 250 -model "{final_path}.zip" -gui -steps 1000')
    print("=" * 70)

    return f"{final_path}.zip"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Train DQN/PPO for VANET traffic control",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--config", default=os.path.join(PROJECT_ROOT, "sumo_simulation", "simulation.sumocfg"),
        help="SUMO .sumocfg file",
    )
    parser.add_argument(
        "--output", default=os.path.join(SCRIPT_DIR, "trained_models"),
        help="Directory to save models",
    )
    parser.add_argument("--algo", choices=["dqn", "ppo"], default="ppo", help="RL algorithm")
    parser.add_argument("--timesteps", type=int, default=500_000, help="Total training timesteps")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--buffer-size", type=int, default=50_000, help="Replay buffer size")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--gamma", type=float, default=0.99, help="Discount factor")
    parser.add_argument("--exploration", type=float, default=0.30, help="Exploration fraction")
    parser.add_argument("--save-freq", type=int, default=10_000, help="Checkpoint frequency (steps)")
    parser.add_argument("--max-tl", type=int, default=0, help="Maximum traffic lights under RL control (0 = all)")
    parser.add_argument("--max-joint-actions", type=int, default=100_000, help="Upper bound for cartesian joint action count")
    parser.add_argument("--ppo-n-steps", type=int, default=1024, help="PPO rollout horizon per update")
    parser.add_argument("--ppo-n-epochs", type=int, default=10, help="PPO epochs per update")
    parser.add_argument("--ppo-clip-range", type=float, default=0.2, help="PPO clipping range")
    parser.add_argument("--scenario-randomization", dest="scenario_randomization", action="store_true", help="Randomize SUMO traffic scenario per episode")
    parser.add_argument("--no-scenario-randomization", dest="scenario_randomization", action="store_false", help="Disable scenario randomization")
    parser.set_defaults(scenario_randomization=True)
    parser.add_argument("--scenario-scales", type=str, default="0.7,0.9,1.0,1.2,1.4", help="Comma-separated demand scales sampled per episode")
    parser.add_argument("--scenario-seed", type=int, default=None, help="Seed for scenario randomization")
    parser.add_argument("--route-randomization", action="store_true", help="Randomize passenger flow rates across routes per episode")
    parser.add_argument("--route-rate-min", type=float, default=0.7, help="Minimum multiplier for passenger flow rates when route randomization is enabled")
    parser.add_argument("--route-rate-max", type=float, default=1.3, help="Maximum multiplier for passenger flow rates when route randomization is enabled")
    parser.add_argument("--no-route-preserve-total", dest="route_preserve_total", action="store_false", help="Do not normalize randomized route multipliers; total demand can drift")
    parser.set_defaults(route_preserve_total=True)
    parser.add_argument("--progress-bar", action="store_true", help="Show SB3 progress bar (requires tqdm and rich)")
    parser.add_argument("--heartbeat-steps", type=int, default=100, help="Print live training heartbeat every N steps")

    args = parser.parse_args()

    if not os.path.exists(args.config):
        print(f"❌ SUMO config not found: {args.config}")
        sys.exit(1)

    try:
        scenario_scales = [float(x.strip()) for x in args.scenario_scales.split(",") if x.strip()]
    except ValueError:
        print(f"❌ Invalid --scenario-scales: {args.scenario_scales}")
        sys.exit(1)

    if not scenario_scales or any(v <= 0 for v in scenario_scales):
        print("❌ --scenario-scales must contain positive numbers")
        sys.exit(1)

    if args.route_rate_min <= 0 or args.route_rate_max <= 0:
        print("❌ --route-rate-min and --route-rate-max must be positive")
        sys.exit(1)
    if args.route_rate_min > args.route_rate_max:
        print("❌ --route-rate-min must be <= --route-rate-max")
        sys.exit(1)

    model_path = train(
        config_path=args.config,
        output_dir=args.output,
        total_timesteps=args.timesteps,
        algorithm=args.algo,
        learning_rate=args.lr,
        buffer_size=args.buffer_size,
        batch_size=args.batch_size,
        gamma=args.gamma,
        exploration_fraction=args.exploration,
        save_freq=args.save_freq,
        max_tl=args.max_tl,
        max_joint_actions=args.max_joint_actions,
        ppo_n_steps=args.ppo_n_steps,
        ppo_n_epochs=args.ppo_n_epochs,
        ppo_clip_range=args.ppo_clip_range,
        scenario_randomization=args.scenario_randomization,
        scenario_scales=scenario_scales,
        scenario_seed=args.scenario_seed,
        route_randomization=args.route_randomization,
        route_rate_min=args.route_rate_min,
        route_rate_max=args.route_rate_max,
        route_preserve_total=args.route_preserve_total,
        progress_bar=args.progress_bar,
        heartbeat_steps=args.heartbeat_steps,
    )

    if model_path:
        print(f"\n✅ Model ready at: {model_path}")
    else:
        print("\n❌ Training failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
