#!/usr/bin/env python3
"""
Train DQN Model for VANET Hybrid Traffic Control
Uses stable-baselines3 DQN with the VANETTrafficEnv gymnasium environment.

Usage:
    python train.py                          # Default: 200k steps, headless
    python train.py --timesteps 100000       # Shorter run
    python train.py --timesteps 20000 --lr 0.0003  # Quick test run
"""

import os
import sys
import json
import argparse
import time
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
from stable_baselines3 import DQN
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

    def __init__(self, sumo_cmd: list, label: str = "train", verbose: int = 0):
        super().__init__(verbose)
        self.sumo_cmd = sumo_cmd
        self.label = label
        self.episode_count = 0
        self.episode_rewards: list[float] = []
        self._current_ep_reward = 0.0

    def _on_step(self) -> bool:
        # Accumulate reward
        reward = self.locals.get("rewards", [0])[0]
        self._current_ep_reward += reward

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
            )
            self._current_ep_reward = 0.0

            # Restart SUMO for the next episode
            try:
                traci.close()
            except Exception:
                pass
            try:
                traci.start(self.sumo_cmd, label=self.label)
                traci.switch(self.label)
            except Exception as e:
                print(f"  ⚠️  SUMO restart error: {e}")

        return True  # Continue training


# ---------------------------------------------------------------------------
# Environment wrapper – handles SUMO lifecycle
# ---------------------------------------------------------------------------
class SUMOEnvWrapper(Monitor):
    """Thin wrapper that keeps a reference to the SUMO command so we can
    restart on reset()."""

    def __init__(self, env, sumo_cmd, label="train", filename=None):
        super().__init__(env, filename=filename)
        self.sumo_cmd = sumo_cmd
        self.label = label
        self._sumo_running = False

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
def build_env(config_path: str, log_dir: Optional[str] = None):
    """Create the SB3-compatible VANET environment around SUMO."""

    sumo_binary = "sumo"  # headless – no GUI during training
    sumo_cmd = [
        sumo_binary,
        "-c", config_path,
        "--start",
        "--step-length", "1",
        "--no-warnings",
        "--time-to-teleport", "300",
    ]

    label = "train"

    # Start SUMO once to inspect traffic lights
    traci.start(sumo_cmd, label=label)
    traci.switch(label)

    tl_ids = traci.trafficlight.getIDList()
    action_spec = {}
    for tl_id in tl_ids:
        try:
            logic = traci.trafficlight.getAllProgramLogics(tl_id)[0]
            phases = [phase.state for phase in logic.phases]
            action_spec[tl_id] = phases
        except Exception as e:
            print(f"  ⚠️  Could not read phases for {tl_id}: {e}")

    print(f"  Traffic lights: {list(tl_ids)}")
    print(f"  Action spec: { {k: len(v) for k, v in action_spec.items()} }")

    env_config = {
        "beta": 20,
        "action_spec": action_spec,
        "tl_constraint_min": 5,
        "tl_constraint_max": 60,
        "sim_step": 1.0,
        "algorithm": "DQN",
        "horizon": 1000,  # steps per episode
    }

    env = VANETTrafficEnv(config=env_config)

    # Wrap with our SUMO-aware Monitor
    wrapped = SUMOEnvWrapper(
        env,
        sumo_cmd=sumo_cmd,
        label=label,
        filename=os.path.join(log_dir, "monitor") if log_dir else None,
    )

    print(f"  Observation space: {env.observation_space}")
    print(f"  Action space:      {env.action_space}")

    return wrapped, sumo_cmd, label


# ---------------------------------------------------------------------------
# Main training function
# ---------------------------------------------------------------------------
def train(
    config_path: str,
    output_dir: str,
    total_timesteps: int = 200_000,
    learning_rate: float = 1e-4,
    buffer_size: int = 50_000,
    learning_starts: int = 1_000,
    batch_size: int = 32,
    gamma: float = 0.99,
    exploration_fraction: float = 0.30,
    exploration_final_eps: float = 0.05,
    target_update_interval: int = 1_000,
    save_freq: int = 10_000,
):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_dir = os.path.join(output_dir, f"dqn_traffic_{timestamp}")
    os.makedirs(model_dir, exist_ok=True)

    print("=" * 70)
    print("  DQN TRAINING — VANET Hybrid Traffic Control")
    print("=" * 70)
    print(f"  SUMO config : {config_path}")
    print(f"  Output dir  : {model_dir}")
    print(f"  Timesteps   : {total_timesteps:,}")
    print(f"  LR          : {learning_rate}")
    print(f"  Buffer      : {buffer_size:,}")
    print(f"  Batch       : {batch_size}")
    print(f"  Gamma       : {gamma}")
    print(f"  Explore     : {exploration_fraction} -> {exploration_final_eps}")
    print("=" * 70)
    print()

    # ---- environment ----
    print("Setting up SUMO environment …")
    log_dir = os.path.join(model_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    env, sumo_cmd, label = build_env(config_path, log_dir=log_dir)

    # ---- model ----
    print("\nCreating DQN model …")
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
    print("  ✅ DQN model created\n")

    # ---- callbacks ----
    ckpt_cb = CheckpointCallback(
        save_freq=save_freq,
        save_path=os.path.join(model_dir, "checkpoints"),
        name_prefix="dqn_traffic",
    )
    sumo_cb = SUMOResetCallback(sumo_cmd=sumo_cmd, label=label, verbose=0)

    # ---- train ----
    print("Starting training …\n")
    t0 = time.time()

    try:
        model.learn(
            total_timesteps=total_timesteps,
            callback=[ckpt_cb, sumo_cb],
            log_interval=10,
            progress_bar=True,
        )
    except KeyboardInterrupt:
        print("\n⚠️  Training interrupted — saving current model …")
        interrupted_path = os.path.join(model_dir, "dqn_traffic_interrupted")
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
    final_path = os.path.join(model_dir, "dqn_traffic_final")
    model.save(final_path)
    print(f"  Final model : {final_path}.zip")

    # ---- save training config (plain text) ----
    cfg_path = os.path.join(model_dir, "config.txt")
    explore_steps = int(exploration_fraction * total_timesteps)
    with open(cfg_path, "w") as f:
        f.write(f"SUMO Config: {config_path}\n")
        f.write(f"Total Timesteps: {total_timesteps}\n")
        f.write(f"Learning Rate: {learning_rate}\n")
        f.write(f"Buffer Size: {buffer_size}\n")
        f.write(f"Batch Size: {batch_size}\n")
        f.write(f"Gamma: {gamma}\n")
        f.write(f"Exploration: {exploration_fraction} \u2192 {exploration_final_eps}\n")
        f.write(f"Epsilon Start: 1.0\n")
        f.write(f"Epsilon End: {exploration_final_eps}\n")
        f.write(f"Epsilon Decay: linear over first {explore_steps:,} steps "
                f"({exploration_fraction*100:.0f}% of training)\n")
        f.write(f"Target Network Update Interval: {target_update_interval}\n")
        f.write(f"Learning Starts: {learning_starts}\n")
        f.write(f"Episodes completed: {sumo_cb.episode_count}\n")
        if sumo_cb.episode_rewards:
            f.write(f"Final avg reward (last 10): {np.mean(sumo_cb.episode_rewards[-10:]):.2f}\n")
            f.write(f"Best episode reward: {max(sumo_cb.episode_rewards):.2f}\n")
    print(f"  Config      : {cfg_path}")

    # ---- save detailed JSON config (for reproducibility / paper) ----
    json_cfg = {
        "sumo_config": config_path,
        "algorithm": "DQN",
        "framework": "stable-baselines3",
        "policy": "MlpPolicy",
        "total_timesteps": total_timesteps,
        "learning_rate": learning_rate,
        "buffer_size": buffer_size,
        "learning_starts": learning_starts,
        "batch_size": batch_size,
        "gamma": gamma,
        "target_update_interval": target_update_interval,
        "epsilon_schedule": {
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
        },
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
    json_path = os.path.join(model_dir, "training_config.json")
    with open(json_path, "w") as f:
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
            ax.set_title("DQN Training Convergence — VANET Traffic Control", fontsize=14)
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
            with open(csv_path, "w") as f:
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
    print(f'    model = DQN.load("{final_path}")')
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
        description="Train DQN for VANET traffic control",
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
    parser.add_argument("--timesteps", type=int, default=200_000, help="Total training timesteps")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--buffer-size", type=int, default=50_000, help="Replay buffer size")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--gamma", type=float, default=0.99, help="Discount factor")
    parser.add_argument("--exploration", type=float, default=0.30, help="Exploration fraction")
    parser.add_argument("--save-freq", type=int, default=10_000, help="Checkpoint frequency (steps)")

    args = parser.parse_args()

    if not os.path.exists(args.config):
        print(f"❌ SUMO config not found: {args.config}")
        sys.exit(1)

    model_path = train(
        config_path=args.config,
        output_dir=args.output,
        total_timesteps=args.timesteps,
        learning_rate=args.lr,
        buffer_size=args.buffer_size,
        batch_size=args.batch_size,
        gamma=args.gamma,
        exploration_fraction=args.exploration,
        save_freq=args.save_freq,
    )

    if model_path:
        print(f"\n✅ Model ready at: {model_path}")
    else:
        print("\n❌ Training failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
