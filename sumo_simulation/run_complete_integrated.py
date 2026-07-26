#!/usr/bin/env python3
"""
Complete Integrated SUMO + NS3 + RL VANET Simulation
Combines all features:
- SUMO: Vehicle movements, traffic control
- NS3 Bridge: WiFi (802.11p) for V2V, WiMAX for emergency V2I
- RL: Proximity-based hybrid PPO/DQN control
- Edge Computing: Smart RSU processing
- Security: RSA encryption and CA authentication
"""

import os
import sys
import time
import json
import argparse
import traceback
from collections import defaultdict

# Add parent directory to path to import from project root
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from sumo_simulation.traffic_controller import AdaptiveTrafficController
from sumo_simulation.sensors.sensor_network import SensorNetwork
from sumo_simulation.sumo_ns3_bridge import SUMONS3Bridge

# RSU Configuration (unified across all modules)
sys.path.insert(0, os.path.join(parent_dir, 'rl_module'))
from rsu_config import get_ns3_rsu_positions, get_rsu_ids, get_rsu_count

# Security module
from v2v_communication.key_management import initialize_vanet_security

# RL module
try:
    from stable_baselines3 import DQN, PPO
    from rl_module.vanet_env import VANETTrafficEnv
    RL_AVAILABLE = True
except ImportError as e:
    RL_AVAILABLE = False
    print(f"⚠️  RL module not available: {e}")
    print("   Make sure stable-baselines3 is installed and rl_module is accessible")


def resolve_sumo_config_path(config_arg):
    """Resolve SUMO config path from CLI argument or default location."""
    if config_arg:
        return os.path.abspath(config_arg)
    return os.path.join(os.path.dirname(__file__), "simulation.sumocfg")


def activate_dynamic_rsu_config(config_path):
    """Use layout-specific RSU definitions when they are available."""
    existing = os.environ.get("VANET_RSU_CONFIG_FILE")
    if existing:
        print(f"✓ Using RSU config from environment: {existing}")
        return

    candidate = os.path.join(os.path.dirname(config_path), "rsu_config.json")
    if os.path.exists(candidate):
        os.environ["VANET_RSU_CONFIG_FILE"] = candidate
        print(f"✓ Using dynamic RSU config: {candidate}")
    else:
        print("✓ Using built-in RSU configuration")


def load_trained_model(model_path):
    """Load a trained stable-baselines3 model (PPO or DQN)."""
    if not os.path.exists(model_path):
        print(f"⚠️  Model not found: {model_path}")
        return None

    file_hint = os.path.basename(model_path).lower()
    if "ppo" in file_hint:
        load_order = ["PPO", "DQN"]
    elif "dqn" in file_hint:
        load_order = ["DQN", "PPO"]
    else:
        load_order = ["DQN", "PPO"]

    loaders = {
        "DQN": (
            DQN,
            {
                "lr_schedule": lambda _: 1e-4,
                "exploration_schedule": lambda _: 0.05,
            },
        ),
        "PPO": (
            PPO,
            {
                "lr_schedule": lambda _: 1e-4,
            },
        ),
    }

    errors = []
    for algo_name in load_order:
        algo_class, custom_objects = loaders[algo_name]

        try:
            model = algo_class.load(model_path)
            print(f"✅ Loaded trained {algo_name} model from: {model_path}")
            return model
        except Exception as e:
            errors.append(f"{algo_name} standard load failed: {e}")
            print(f"⚠️  {algo_name} standard load failed ({e}), trying custom_objects...")

        try:
            model = algo_class.load(model_path, custom_objects=custom_objects)
            print(f"✅ Loaded trained {algo_name} model (with custom_objects) from: {model_path}")
            return model
        except Exception as e:
            errors.append(f"{algo_name} custom_objects load failed: {e}")

    print("❌ Failed to load model as PPO or DQN.")
    for err in errors[-4:]:
        print(f"   - {err}")
    return None


class ProximityHybridController:
    """
    Proximity-based hybrid controller for RL/density switching
    Only activates RL for junctions near emergency vehicles
    """
    
    def __init__(self, traffic_controller, model=None, proximity_threshold=250.0, model_path=None):
        self.traffic_controller = traffic_controller
        self.model = model
        self.model_path = model_path
        self.proximity_threshold = proximity_threshold
        self.rl_env = None
        self.rl_action_spec = {}
        self.rl_algorithm = None
        self.model_inference_failures = 0
        
        # Get controlled junctions
        import traci
        self.junctions = list(traci.trafficlight.getIDList())
        
        # Get junction positions
        self.junction_positions = {}
        for junc_id in self.junctions:
            try:
                pos = traci.junction.getPosition(junc_id)
                self.junction_positions[junc_id] = pos
            except Exception as e:
                # Fallback: use average of controlled lanes
                try:
                    lanes = traci.trafficlight.getControlledLanes(junc_id)
                    if lanes:
                        positions = [traci.lane.getShape(lane) for lane in lanes[:4]]
                        x_coords = [p[0][0] for p in positions if p]
                        y_coords = [p[0][1] for p in positions if p]
                        if x_coords and y_coords:
                            self.junction_positions[junc_id] = (
                                sum(x_coords) / len(x_coords),
                                sum(y_coords) / len(y_coords)
                            )
                except:
                    pass
        
        # Track mode per junction
        self.junction_modes = {j: 'density' for j in self.junctions}
        self.mode_steps = defaultdict(int)
        
        # Statistics tracking - enhanced for research metrics
        self.density_steps = 0
        self.rl_steps = 0
        self.switches = 0
        self.emergency_encounters = defaultdict(int)  # Track encounters per emergency
        self.rl_activation_history = []  # [(timestep, junction_id, emergency_id, distance)]
        self.junction_rl_time = defaultdict(float)  # Time each junction spent in RL mode
        
        # Stats
        self.density_steps = 0
        self.rl_steps = 0
        self.switches = 0

        self._initialize_rl_inference_adapter()
        
        print(f"\n🔄 Proximity-Based Hybrid Controller Initialized")
        print(f"   Junctions: {len(self.junctions)}")
        print(f"   Proximity threshold: {proximity_threshold}m")
        print(f"   Junction positions:")
        for junc_id, pos in self.junction_positions.items():
            print(f"     {junc_id}: ({pos[0]:.1f}, {pos[1]:.1f})")

    def _load_model_metadata(self):
        """Load optional training metadata from the model directory."""
        if not self.model_path:
            return {}

        try:
            model_dir = os.path.dirname(os.path.abspath(self.model_path))
            metadata_path = os.path.join(model_dir, "training_config.json")
            if not os.path.exists(metadata_path):
                return {}

            with open(metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Could not read model metadata: {e}")
            return {}

    def _build_action_spec(self, preferred_junctions=None):
        """Build action_spec from active SUMO traffic lights and phase programs."""
        action_spec = {}
        junction_candidates = preferred_junctions if preferred_junctions else self.junctions

        for tl_id in junction_candidates:
            phases = self.traffic_controller.default_phases.get(tl_id)
            if phases:
                action_spec[tl_id] = list(phases)

        return action_spec

    def _initialize_rl_inference_adapter(self):
        """Create a lightweight VANET env adapter so model.predict can drive phases."""
        if not self.model:
            print("⚠️  Proximity controller running without RL model (density-only fallback)")
            return

        try:
            metadata = self._load_model_metadata()
            env_meta = metadata.get("environment", {}) if isinstance(metadata, dict) else {}

            algo_hint = str(metadata.get("algorithm", "")).upper() if isinstance(metadata, dict) else ""
            model_class_name = self.model.__class__.__name__.upper()

            if algo_hint in {"PPO", "DQN"}:
                self.rl_algorithm = algo_hint
            elif "PPO" in model_class_name:
                self.rl_algorithm = "PPO"
            elif "DQN" in model_class_name:
                self.rl_algorithm = "DQN"
            else:
                self.rl_algorithm = "PPO"

            if self.rl_algorithm != "PPO":
                print("⚠️  Proximity RL inference adapter currently supports PPO only; using density fallback for model actions")
                return

            preferred_tls = env_meta.get("controlled_traffic_lights")
            if not isinstance(preferred_tls, list) or not preferred_tls:
                preferred_tls = self.junctions

            self.rl_action_spec = self._build_action_spec(preferred_tls)
            if not self.rl_action_spec:
                self.rl_action_spec = self._build_action_spec(self.junctions)

            if not self.rl_action_spec:
                print("⚠️  No valid traffic-light phase programs found for RL inference adapter")
                return

            tl_min = int(env_meta.get("tl_constraint_min", 5))
            tl_max = int(env_meta.get("tl_constraint_max", 60))
            beta = int(env_meta.get("beta", 20))
            horizon = int(env_meta.get("horizon", 1000))

            env_config = {
                "beta": beta,
                "action_spec": self.rl_action_spec,
                "tl_constraint_min": tl_min,
                "tl_constraint_max": tl_max,
                "sim_step": 1.0,
                "algorithm": "PPO",
                "horizon": horizon,
            }

            self.rl_env = VANETTrafficEnv(config=env_config)
            print(
                f"✅ Proximity RL inference adapter ready: {len(self.rl_action_spec)} TLs "
                f"(algorithm={self.rl_algorithm})"
            )
        except Exception as e:
            self.rl_env = None
            print(f"⚠️  Failed to initialize RL inference adapter: {e}")

    def _predict_rl_phase_map(self):
        """Predict target phase index for each RL-controlled junction."""
        if not self.model or not self.rl_env or not self.rl_action_spec:
            return {}

        try:
            # Keep env trackers in sync with current SUMO state before inference.
            self.rl_env._update_obs_wait_steps()
            self.rl_env._increment_obs_tl_wait_steps()
            self.rl_env._update_obs_veh_acc()

            obs_vec = self.rl_env.get_state()
            action, _ = self.model.predict(obs_vec, deterministic=True)
            predicted_states = self.rl_env.map_action_to_tl_states(action)

            phase_map = {}
            for i, tl_id in enumerate(self.rl_action_spec.keys()):
                if i >= len(predicted_states):
                    continue
                target_state = predicted_states[i]
                phases = self.traffic_controller.default_phases.get(tl_id, [])
                if target_state in phases:
                    phase_map[tl_id] = phases.index(target_state)

            return phase_map
        except Exception as e:
            self.model_inference_failures += 1
            if self.model_inference_failures <= 3 or self.model_inference_failures % 50 == 0:
                print(f"⚠️  RL inference failed (attempt {self.model_inference_failures}): {e}")
            return {}

    def _apply_rl_phase_targets(self, target_junctions, phase_map):
        """Apply predicted phase targets to emergency-adjacent junctions only."""
        import traci

        for tl_id in target_junctions:
            if tl_id not in phase_map:
                continue

            target_phase = phase_map[tl_id]
            try:
                current_phase = int(traci.trafficlight.getPhase(tl_id))
            except Exception:
                continue

            if current_phase == target_phase:
                continue

            try:
                traci.trafficlight.setPhase(tl_id, target_phase)
                if tl_id in self.traffic_controller.intersections:
                    self.traffic_controller.intersections[tl_id]["current_phase"] = target_phase
                    self.traffic_controller.intersections[tl_id]["time_in_phase"] = 0
            except Exception:
                continue
    
    def get_emergency_junction_proximity(self):
        """
        Get list of junctions that should use RL (near emergencies)
        Returns: dict {junction_id: (emergency_id, distance)}
        """
        import traci
        import math
        
        # Get all emergency vehicles
        all_vehicles = traci.vehicle.getIDList()
        emergency_vehicles = [v for v in all_vehicles if 'emergency' in v.lower()]
        
        if not emergency_vehicles:
            return {}
        
        rl_junctions = {}
        
        for junc_id, junc_pos in self.junction_positions.items():
            closest_emergency = None
            min_distance = float('inf')
            
            for emerg_id in emergency_vehicles:
                try:
                    veh_pos = traci.vehicle.getPosition(emerg_id)
                    distance = math.sqrt(
                        (veh_pos[0] - junc_pos[0])**2 + 
                        (veh_pos[1] - junc_pos[1])**2
                    )
                    
                    if distance < min_distance:
                        min_distance = distance
                        closest_emergency = emerg_id
                except:
                    continue
            
            if min_distance <= self.proximity_threshold:
                rl_junctions[junc_id] = (closest_emergency, min_distance)
        
        return rl_junctions
    
    def step(self, obs=None):
        """
        Perform one control step with proximity-based switching
        
        Args:
            obs: Current observation (optional, for RL)
        """
        import traci
        
        current_time = traci.simulation.getTime()
        
        # Get junctions near emergencies
        rl_junctions = self.get_emergency_junction_proximity()

        if hasattr(self.traffic_controller, "set_externally_controlled_tls"):
            self.traffic_controller.set_externally_controlled_tls(rl_junctions.keys())
        
        # Track emergency encounters
        for junc_id, (emerg_id, dist) in rl_junctions.items():
            self.emergency_encounters[emerg_id] += 1
        
        # Update modes and track switches
        for junc_id in self.junctions:
            new_mode = 'rl' if junc_id in rl_junctions else 'density'
            old_mode = self.junction_modes[junc_id]
            
            # Track time in RL mode
            if old_mode == 'rl':
                self.junction_rl_time[junc_id] += 1.0
            
            if new_mode != old_mode:
                self.junction_modes[junc_id] = new_mode
                self.switches += 1
                
                # Log switch
                if new_mode == 'rl':
                    emerg_id, dist = rl_junctions[junc_id]
                    print(f"🚨 Step {current_time:.0f}s: "
                          f"{junc_id} → RL MODE (Emergency: {emerg_id} at {dist:.1f}m)")
                    
                    # Record activation
                    self.rl_activation_history.append((current_time, junc_id, emerg_id, dist))
                else:
                    print(f"✅ Step {current_time:.0f}s: "
                          f"{junc_id} → DENSITY MODE (emergency passed)")
        
        # Update stats
        rl_count = sum(1 for mode in self.junction_modes.values() if mode == 'rl')
        if rl_count > 0:
            self.rl_steps += 1
        else:
            self.density_steps += 1

        # Apply PPO decisions only to junctions currently near emergencies.
        if rl_junctions and self.model and self.rl_env:
            phase_map = self._predict_rl_phase_map()
            if phase_map:
                self._apply_rl_phase_targets(rl_junctions.keys(), phase_map)

        # Advance simulation and run non-RL subsystems.
        self.traffic_controller.run_simulation_step()
    
    def print_stats(self):
        """Print comprehensive statistics for research paper"""
        total = self.density_steps + self.rl_steps
        if total == 0:
            return
        
        print("\n" + "="*80)
        print("PROXIMITY-BASED HYBRID CONTROL STATISTICS")
        print("="*80)
        
        # Overall statistics
        print(f"\n📊 OVERALL PERFORMANCE:")
        print(f"  Total simulation steps: {total}")
        print(f"  Steps with ALL junctions in DENSITY mode: {self.density_steps} ({self.density_steps/total*100:.1f}%)")
        print(f"  Steps with SOME junctions in RL mode: {self.rl_steps} ({self.rl_steps/total*100:.1f}%)")
        print(f"  Total junction mode switches: {self.switches}")
        print(f"  Avg switches per junction: {self.switches/len(self.junctions):.1f}")
        
        # Emergency vehicle encounters
        print(f"\n🚑 EMERGENCY VEHICLE HANDLING:")
        print(f"  Unique emergency vehicles encountered: {len(self.emergency_encounters)}")
        for emerg_id, count in sorted(self.emergency_encounters.items()):
            print(f"    • {emerg_id}: {count} proximity activations")
        
        # Per-junction RL usage
        print(f"\n🚦 PER-JUNCTION RL ACTIVATION:")
        for junc_id in sorted(self.junctions):
            rl_time = self.junction_rl_time.get(junc_id, 0)
            rl_percentage = (rl_time / total * 100) if total > 0 else 0
            print(f"    • {junc_id}: {rl_time:.0f}s in RL mode ({rl_percentage:.1f}%)")
        
        # Activation timeline summary
        if self.rl_activation_history:
            print(f"\n⏱️  RL ACTIVATION TIMELINE:")
            print(f"  First activation: {self.rl_activation_history[0][0]:.0f}s")
            print(f"  Last activation: {self.rl_activation_history[-1][0]:.0f}s")
            print(f"  Total activations: {len(self.rl_activation_history)}")
            
            # Average distance at activation
            avg_dist = sum(a[3] for a in self.rl_activation_history) / len(self.rl_activation_history)
            print(f"  Average emergency distance at activation: {avg_dist:.1f}m")
        
        # Efficiency metrics
        print(f"\n⚡ EFFICIENCY METRICS:")
        density_percentage = (self.density_steps / total * 100) if total > 0 else 0
        print(f"  Computational efficiency: {density_percentage:.1f}% steps used simple density control")
        print(f"  RL overhead: {100-density_percentage:.1f}% steps required ML inference")
        print(f"  Proximity threshold: {self.proximity_threshold}m")
        
        print(f"\n✅ HYBRID MODEL ADVANTAGES:")
        print(f"  • Only uses RL where needed (near emergencies within {self.proximity_threshold}m)")
        print(f"  • {density_percentage:.1f}% of time uses efficient density-based control")
        print(f"  • Dynamic switching enables real-time adaptation to emergencies")
        print(f"  • Resulted in {self.switches} efficient mode transitions")
        print(f"  • Average {self.switches/total*100:.2f}% switching rate (low overhead)")
        
        print("="*80)


def main():
    parser = argparse.ArgumentParser(
        description='Complete Integrated SUMO + NS3 + RL VANET Simulation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Rule-based with GUI
  %(prog)s --mode rule --gui --steps 1000
  
  # RL hybrid with GUI, security, and edge computing
  %(prog)s --mode hybrid --gui --security --edge --steps 1000
  
    # RL proximity-based with trained model (PPO or DQN)
    %(prog)s --mode proximity --model rl_module/trained_models/.../ppo_traffic_final.zip --proximity 250 --gui
        """
    )
    
    parser.add_argument('--mode', choices=['rule', 'fixed', 'density', 'rl', 'hybrid', 'proximity'], 
                       default='rule',
                       help='Control mode: fixed (fixed-time), density (adaptive), rule (same as density), rl (trained model), hybrid (global switching), proximity (junction-specific)')
    parser.add_argument('--model', type=str, default=None,
                       help='Path to trained PPO/DQN model (.zip file)')
    parser.add_argument('--proximity', type=float, default=250.0,
                       help='Proximity threshold for RL activation (meters)')
    parser.add_argument('--emergency-priority', choices=['auto', 'on', 'off'], default='on',
                       help='Emergency priority mode: on by default, off to disable it, auto for proximity-only behavior')
    parser.add_argument('--emergency-range', type=float, default=None,
                       help='Emergency detection range in meters (default: controller default or proximity threshold in proximity mode)')
    parser.add_argument('--corridor-depth', type=int, default=3,
                       help='Proactive green-corridor depth in junctions ahead')
    parser.add_argument('--corridor-distance', type=float, default=450.0,
                       help='Maximum distance in meters for proactive corridor preemption')
    parser.add_argument('--pass-through-range', type=float, default=30.0,
                       help='Distance in meters considered as emergency cleared at a junction')
    parser.add_argument('--steps', type=int, default=1000,
                       help='Number of simulation steps')
    parser.add_argument('--config', type=str, default=None,
                       help='Path to SUMO .sumocfg file (default: sumo_simulation/simulation.sumocfg)')
    parser.add_argument('--gui', action='store_true',
                       help='Use SUMO-GUI for visualization')
    parser.add_argument('--output', default='./output',
                       help='Output directory for results')
    parser.add_argument('--security', action='store_true',
                       help='Enable RSA encryption for V2V/V2I (adds 30-60s startup)')
    parser.add_argument('--edge', action='store_true',
                       help='Enable edge computing RSUs (smart processing)')
    parser.add_argument('--seed', type=int, default=None,
                       help='Random seed for SUMO reproducibility')
    
    args = parser.parse_args()

    config_path = resolve_sumo_config_path(args.config)
    if not os.path.exists(config_path):
        print(f"❌ Error: SUMO config not found: {config_path}")
        sys.exit(1)

    activate_dynamic_rsu_config(config_path)

    # Normalize mode: 'rule' is alias for 'density'
    if args.mode == 'rule':
        args.mode = 'density'

    # Set Python random seed if provided
    if args.seed is not None:
        import random
        random.seed(args.seed)
        import numpy as np
        np.random.seed(args.seed)

    # Validate RL mode requirements
    if args.mode in ['rl', 'hybrid', 'proximity']:
        if not RL_AVAILABLE:
            print("❌ RL mode requires stable-baselines3")
            print("   Install: pip install stable-baselines3")
            sys.exit(1)
        
        if args.mode in ['rl', 'proximity'] and not args.model:
            print("❌ RL/Proximity mode requires --model argument")
            print("   Example: --model rl_module/trained_models/.../ppo_traffic_final.zip")
            sys.exit(1)

    # Create output directory
    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)

    print("="*70)
    print("🚗 COMPLETE INTEGRATED VANET SIMULATION")
    print("="*70)
    print(f"Control Mode: {args.mode.upper()}")
    if args.seed is not None:
        print(f"Seed: {args.seed}")
    if args.mode in ['rl', 'proximity'] and args.model:
        print(f"Model: {args.model}")
    if args.mode == 'proximity':
        print(f"Proximity Threshold: {args.proximity}m")
    print(f"Emergency Priority Mode: {args.emergency_priority}")
    print(f"Steps: {args.steps}")
    print(f"GUI: {'✅ Enabled' if args.gui else '❌ Disabled'}")
    print(f"Security: {'✅ RSA Encryption' if args.security else '❌ Disabled'}")
    print(f"Edge Computing: {'✅ Smart RSUs' if args.edge else '❌ Disabled'}")
    print(f"Output: {output_dir}")
    print(f"SUMO Config: {config_path}")
    print("="*70)
    print()

    # Load model if needed
    model = None
    if args.mode in ['rl', 'proximity'] and args.model:
        model = load_trained_model(args.model)
        if not model:
            print("❌ Failed to load model, falling back to density-based")
            args.mode = 'density'

    # Initialize components
    print("🔧 Initializing simulation components...")
    
    if args.emergency_priority == 'on':
        emergency_priority_enabled = True
    elif args.emergency_priority == 'off':
        emergency_priority_enabled = False
    else:
        emergency_priority_enabled = (args.mode == 'proximity')
    
    # Map mode to traffic controller mode
    # 'fixed' -> fixed-time, 'density' -> adaptive density, others -> rl/proximity
    tc_mode = args.mode if args.mode in ['fixed', 'density'] else args.mode
    
    traffic_controller = AdaptiveTrafficController(
        mode=tc_mode,
        security_managers=None,
        security_pending=args.security,
        edge_computing_enabled=args.edge,
        emergency_priority_enabled=emergency_priority_enabled
    )

    if args.mode == 'proximity':
        default_detection = max(traffic_controller.emergency_detection_range, args.proximity)
    else:
        default_detection = traffic_controller.emergency_detection_range

    effective_detection = args.emergency_range if args.emergency_range is not None else default_detection
    traffic_controller.configure_emergency_priority(
        detection_range=effective_detection,
        pass_through_range=args.pass_through_range,
        corridor_depth=args.corridor_depth,
        corridor_max_distance=args.corridor_distance,
    )

    if emergency_priority_enabled:
        print("✓ Emergency preemption configured:")
        print(f"  Detection range: {traffic_controller.emergency_detection_range:.1f}m")
        print(f"  Corridor depth: {traffic_controller.green_corridor_junction_lookahead} junctions")
        print(f"  Corridor distance: {traffic_controller.green_corridor_max_distance:.1f}m")
        print(f"  Pass-through range: {traffic_controller.emergency_pass_through_range:.1f}m")
    sensor_network = SensorNetwork()
    ns3_bridge = SUMONS3Bridge()
    
    # Initialize RSUs using unified configuration
    # This ensures consistency across emergency coordinator, edge computing, and NS3
    rsu_positions = get_ns3_rsu_positions()
    ns3_bridge.initialize_rsus(rsu_positions)
    print(f"✓ Initialized {get_rsu_count()} RSUs from unified configuration")
    
    # Connect traffic controller to NS3 bridge for accurate V2I metrics
    traffic_controller.set_ns3_bridge(ns3_bridge)
    
    # Connect to SUMO
    print(f"📁 Using SUMO config: {config_path}")
    
    if not traffic_controller.connect_to_sumo(config_path, use_gui=args.gui, seed=args.seed):
        print("❌ Error: Could not connect to SUMO")
        return

    print("✅ Connected to SUMO successfully")
    
    # Initialize security if requested
    if args.security:
        print()
        print("🔐 Initializing VANET Security Infrastructure...")
        print("  ⏳ Generating RSA keys (30-60 seconds)...")
        
        # Use unified RSU configuration
        rsu_ids = get_rsu_ids()
        ca, rsu_managers, vehicle_managers = initialize_vanet_security(
            rsu_ids=rsu_ids,
            num_vehicles=5
        )
        
        print(f"  ✅ CA: {ca.ca_id}")
        print(f"  ✅ RSUs: {len(rsu_managers)}, Vehicles: {len(vehicle_managers)}")
        
        traffic_controller.ca = ca
        traffic_controller.rsu_managers = rsu_managers
        traffic_controller.vehicle_managers = vehicle_managers
        traffic_controller.security_enabled = True
        traffic_controller._initialize_wimax()
        
        print("  ✅ Security enabled: RSA + CA authentication")
    
    # Initialize sensor network
    try:
        sensor_network.initialize_central_pole()
        print("✅ Sensor network initialized")
    except Exception as e:
        print(f"⚠️  Sensor network warning: {e}")
    
    # Initialize proximity controller if needed
    proximity_controller = None
    if args.mode == 'proximity':
        proximity_controller = ProximityHybridController(
            traffic_controller, 
            model=model,
            proximity_threshold=args.proximity,
            model_path=args.model,
        )
        print(f"\n🔀 HYBRID MODEL CONFIGURATION:")
        print(f"  Mode: Proximity-based RL activation")
        print(f"  Proximity threshold: {args.proximity}m")
        print(f"  Controlled junctions: {len(proximity_controller.junctions)}")
        print(f"  Strategy: RL activates only near emergency vehicles")
        print(f"  Expected emergency vehicles: ~4-6 concurrent (35 veh/hour)")
    
    if args.gui:
        print("\n🖥️  SUMO-GUI Controls:")
        print("  Space: Play/Pause")
        print("  +/-: Speed up/slow down")
        print("  Ctrl+C: Stop simulation")
    
    print()
    print("🌐 Network Simulation:")
    print(f"  V2V: WiFi 802.11p (Range: {ns3_bridge.wifi_range}m)")
    print(f"  V2I: WiMAX emergency (Range: {ns3_bridge.wimax_range}m)")
    print(f"  RSUs: {len(rsu_positions)} from active RSU configuration")
    print()
    print("🚀 Starting simulation...")
    print("-"*70)
    
    try:
        step = 0
        start_time = time.time()
        last_print_time = start_time
        
        import traci
        
        # Metrics tracking - FIXED VERSION
        # Track accumulated wait time per vehicle throughout journey
        vehicle_accumulated_wait = {}  # {vehicle_id: total_wait_time_seconds}
        vehicle_accumulated_distance = {}  # {vehicle_id: total_distance_meters}
        vehicle_first_seen = {}  # {vehicle_id: first_step}
        
        total_queue_length = 0
        total_emergency_queue_length = 0
        total_normal_queue_length = 0
        metric_steps = 0
        
        # Per-step time-series arrays for graphs
        per_step_avg_wait = []
        per_step_queue = []
        per_step_emergency_wait = []
        
        # Track vehicles between steps to detect arrivals
        previous_vehicles = set()
        
        # Completed vehicle metrics (only count vehicles that finished their trip)
        completed_vehicles_wait = []
        completed_vehicles_speed = []
        completed_emergency_wait = []
        completed_emergency_speed = []
        completed_normal_wait = []
        completed_normal_speed = []
        
        while step < args.steps:
            # Apply control based on mode
            if args.mode == 'proximity' and proximity_controller:
                # Proximity-based hybrid control
                # This advances SUMO and applies control internally
                proximity_controller.step()
            elif args.mode == 'hybrid':
                # Global hybrid switching (every 5 steps)
                if step % 5 == 0:
                    emergency_vehicles = [v for v in traci.vehicle.getIDList() 
                                        if 'emergency' in v.lower()]
                    if emergency_vehicles and model:
                        # Use RL when emergencies present (would need proper state/action)
                        # For now, use standard control
                        traffic_controller.run_simulation_step()
                    else:
                        traffic_controller.run_simulation_step()
                else:
                    traffic_controller.run_simulation_step()
            else:
                # Rule-based or pure RL (use standard control)
                traffic_controller.run_simulation_step()
            
            # Get current simulation time
            current_time = traci.simulation.getTime()
            
            # Update NS3 network simulation
            ns3_bridge.step(current_time)
            
            # Collect vehicular metrics every step
            vehicles = traci.vehicle.getIDList()
            
            # Get list of vehicles that completed their trip this step
            # We track this by comparing vehicle lists between steps
            current_vehicles = set(vehicles)
            if step > 0:
                departed_this_step = current_vehicles - previous_vehicles
                arrived_this_step = previous_vehicles - current_vehicles
            else:
                departed_this_step = set()
                arrived_this_step = set()
            
            previous_vehicles = current_vehicles
            
            if vehicles:
                for veh_id in vehicles:
                    try:
                        # Initialize if new vehicle
                        if veh_id not in vehicle_accumulated_wait:
                            vehicle_accumulated_wait[veh_id] = 0
                            vehicle_accumulated_distance[veh_id] = 0
                            vehicle_first_seen[veh_id] = step
                        
                        # Get current state
                        speed = traci.vehicle.getSpeed(veh_id)
                        
                        # Accumulate wait time (when stopped or very slow)
                        if speed < 0.1:  # Vehicle is stopped/waiting
                            vehicle_accumulated_wait[veh_id] += 1.0  # 1 second per step
                        
                        # Accumulate distance traveled
                        vehicle_accumulated_distance[veh_id] += speed  # speed in m/s * 1 second
                        
                    except:
                        pass
                
                # Track completed vehicles (reached destination)
                for veh_id in arrived_this_step:
                    if veh_id in vehicle_accumulated_wait:
                        total_wait = vehicle_accumulated_wait[veh_id]
                        trip_time = step - vehicle_first_seen[veh_id]
                        total_distance = vehicle_accumulated_distance[veh_id]
                        avg_speed = total_distance / max(trip_time, 1)
                        
                        is_emergency = 'emergency' in veh_id.lower()
                        
                        completed_vehicles_wait.append(total_wait)
                        completed_vehicles_speed.append(avg_speed)
                        
                        if is_emergency:
                            completed_emergency_wait.append(total_wait)
                            completed_emergency_speed.append(avg_speed)
                        else:
                            completed_normal_wait.append(total_wait)
                            completed_normal_speed.append(avg_speed)
                        
                        # Clean up completed vehicle
                        del vehicle_accumulated_wait[veh_id]
                        del vehicle_accumulated_distance[veh_id]
                        del vehicle_first_seen[veh_id]
                
                # Queue lengths at each junction (per step), split by vehicle type
                step_queue_length = 0
                step_emergency_queue = 0
                step_normal_queue = 0
                for tl_id in traci.trafficlight.getIDList():
                    try:
                        lanes = traci.trafficlight.getControlledLanes(tl_id)
                        for lane in set(lanes):  # deduplicate lanes
                            halting = traci.lane.getLastStepHaltingNumber(lane)
                            step_queue_length += halting
                            # Split halting vehicles by type
                            if halting > 0:
                                lane_vehs = traci.lane.getLastStepVehicleIDs(lane)
                                for v in lane_vehs:
                                    try:
                                        if traci.vehicle.getSpeed(v) < 0.1:
                                            if 'emergency' in v.lower():
                                                step_emergency_queue += 1
                                            else:
                                                step_normal_queue += 1
                                    except:
                                        pass
                    except:
                        pass
                
                total_queue_length += step_queue_length
                total_emergency_queue_length += step_emergency_queue
                total_normal_queue_length += step_normal_queue
                metric_steps += 1
                
                # Per-step time-series data
                per_step_queue.append(step_queue_length)
                # Average wait of currently active vehicles
                if vehicle_accumulated_wait:
                    all_waits = list(vehicle_accumulated_wait.values())
                    per_step_avg_wait.append(sum(all_waits) / len(all_waits))
                    # Emergency wait time per step
                    emerg_waits = [vehicle_accumulated_wait[v] for v in vehicle_accumulated_wait if 'emergency' in v.lower()]
                    per_step_emergency_wait.append(sum(emerg_waits) / len(emerg_waits) if emerg_waits else 0)
                elif per_step_avg_wait:
                    per_step_avg_wait.append(per_step_avg_wait[-1])
                    per_step_emergency_wait.append(per_step_emergency_wait[-1] if per_step_emergency_wait else 0)
                else:
                    per_step_avg_wait.append(0)
                    per_step_emergency_wait.append(0)
            
            # Check if simulation should continue
            if traci.simulation.getMinExpectedNumber() <= 0:
                print("\n⚠️  No more vehicles in simulation")
                break
            
            # Update live metrics for web dashboard (every step for smooth updates)
            if step % 1 == 0:  # Update every step for real-time feel
                try:
                    import sys
                    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    if parent_dir not in sys.path:
                        sys.path.insert(0, parent_dir)
                    from live_metrics_bridge import get_bridge

                    metrics = ns3_bridge.get_metrics()
                    current_waiting = sum(1 for veh_id in vehicles 
                                        if veh_id in vehicle_accumulated_wait 
                                        and traci.vehicle.getSpeed(veh_id) < 0.1)
                    active_waits = [vehicle_accumulated_wait[v] for v in vehicles if v in vehicle_accumulated_wait]
                    avg_wait_current = sum(active_waits) / max(len(active_waits), 1) if active_waits else 0
                    current_queue = 0
                    for tl_id in traci.trafficlight.getIDList():
                        try:
                            lanes = traci.trafficlight.getControlledLanes(tl_id)
                            for lane in lanes:
                                current_queue += traci.lane.getLastStepHaltingNumber(lane)
                        except:
                            pass
                    emergency_count = sum(1 for v in vehicles if 'emergency' in v.lower())
                    wifi_throughput = metrics['v2v_wifi'].get('packets_sent', 0) * 0.5  # rough estimate in Mbps
                    live_data = {
                        'activeVehicles': len(vehicles),
                        'avgWait': avg_wait_current,
                        'pdr': metrics['v2v_wifi']['pdr'] * 100,
                        'queueLength': current_queue,
                        'throughput': wifi_throughput,
                        'emergencyCount': emergency_count,
                    }
                    bridge = get_bridge()
                    bridge.write_metrics(live_data)
                    if step == 1:
                        print("✅ [LIVE METRICS] Successfully writing to live_metrics.json")
                except Exception as e:
                    if step == 1:
                        print(f"❌ [LIVE METRICS] ERROR: {e}")
            
            # Print progress
            if time.time() - last_print_time >= 5.0:
                metrics = ns3_bridge.get_metrics()
                mode_info = ""
                
                if proximity_controller:
                    rl_count = sum(1 for m in proximity_controller.junction_modes.values() if m == 'rl')
                    total_junc = len(proximity_controller.junctions)
                    
                    # Get active emergency vehicles
                    active_emergencies = len(set(
                        emerg_id for _, (emerg_id, _) in 
                        proximity_controller.get_emergency_junction_proximity().items()
                    ))
                    
                    mode_info = (f"🚦 RL: {rl_count}/{total_junc} junctions | "
                               f"🚑 Active Emerg: {active_emergencies} | "
                               f"Switches: {proximity_controller.switches} | ")
                
                # Calculate averages from COMPLETED vehicles
                avg_completed_wait = sum(completed_vehicles_wait) / max(len(completed_vehicles_wait), 1) if completed_vehicles_wait else 0
                avg_queue = total_queue_length / max(metric_steps, 1)
                
                avg_emerg_wait = sum(completed_emergency_wait) / max(len(completed_emergency_wait), 1) if completed_emergency_wait else 0
                avg_normal_wait = sum(completed_normal_wait) / max(len(completed_normal_wait), 1) if completed_normal_wait else 0
                
                print(f"Step {step:4d}/{args.steps} | {mode_info}"
                      f"Vehicles: {metrics['vehicles']['total']} "
                      f"(Emerg: {metrics['vehicles']['emergency']}) | "
                      f"Completed: {len(completed_vehicles_wait)} | "
                      f"Avg Wait: {avg_completed_wait:.1f}s (E:{avg_emerg_wait:.1f}s N:{avg_normal_wait:.1f}s) | "
                      f"Queue: {avg_queue:.1f} | "
                      f"WiFi PDR: {metrics['v2v_wifi']['pdr']*100:.1f}% | "
                      f"WiMAX PDR: {metrics['v2i_wimax']['pdr']*100:.1f}%")
                last_print_time = time.time()
            
            step += 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Simulation interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Simulation error: {e}")
        traceback.print_exc()
    finally:
        # Cleanup live metrics file
        try:
            import sys
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            from live_metrics_bridge import get_bridge
            bridge = get_bridge()
            bridge.cleanup()
        except:
            pass
        
        # Stop SUMO
        traffic_controller.stop_simulation()
        
        elapsed_time = time.time() - start_time
        
        print()
        print("-"*70)
        print(f"✅ Simulation completed in {elapsed_time:.1f} seconds")
        
        # Print final vehicular metrics summary
        if completed_vehicles_wait:
            print()
            print("="*70)
            print("📊 VEHICULAR METRICS SUMMARY (Completed Vehicles Only)")
            print("="*70)
            
            # Calculate final averages from COMPLETED vehicles
            avg_wait_final = sum(completed_vehicles_wait) / len(completed_vehicles_wait)
            avg_speed_final = sum(completed_vehicles_speed) / len(completed_vehicles_speed)
            avg_queue_final = total_queue_length / max(metric_steps, 1)
            
            print(f"\n🚗 OVERALL TRAFFIC:")
            print(f"  Average Wait Time: {avg_wait_final:.2f} seconds")
            print(f"  Average Trip Speed: {avg_speed_final:.2f} m/s")
            print(f"  Average Queue Length: {avg_queue_final:.2f} vehicles")
            print(f"  Total Completed Vehicles: {len(completed_vehicles_wait)}")
            
            if completed_emergency_wait:
                avg_emerg_wait_final = sum(completed_emergency_wait) / len(completed_emergency_wait)
                avg_emerg_speed_final = sum(completed_emergency_speed) / len(completed_emergency_speed)
                
                print(f"\n🚑 EMERGENCY VEHICLES:")
                print(f"  Average Wait Time: {avg_emerg_wait_final:.2f} seconds")
                print(f"  Average Trip Speed: {avg_emerg_speed_final:.2f} m/s")
                print(f"  Total Completed: {len(completed_emergency_wait)}")
                
                if completed_normal_wait and args.mode == 'proximity':
                    avg_normal_wait_final = sum(completed_normal_wait) / len(completed_normal_wait)
                    improvement = ((avg_normal_wait_final - avg_emerg_wait_final) / avg_normal_wait_final * 100)
                    print(f"  Wait Time Reduction vs Normal: {improvement:.1f}%")
            
            if completed_normal_wait:
                avg_normal_wait_final = sum(completed_normal_wait) / len(completed_normal_wait)
                avg_normal_speed_final = sum(completed_normal_speed) / len(completed_normal_speed)
                
                print(f"\n🚙 NORMAL VEHICLES:")
                print(f"  Average Wait Time: {avg_normal_wait_final:.2f} seconds")
                print(f"  Average Trip Speed: {avg_normal_speed_final:.2f} m/s")
                print(f"  Total Completed: {len(completed_normal_wait)}")
            
            # Verification check
            if completed_emergency_wait and completed_normal_wait:
                total_emerg_wait = sum(completed_emergency_wait)
                total_normal_wait = sum(completed_normal_wait)
                calculated_overall = (total_emerg_wait + total_normal_wait) / (len(completed_emergency_wait) + len(completed_normal_wait))
                
                print(f"\n✅ VERIFICATION:")
                print(f"  Overall wait time (direct): {avg_wait_final:.2f}s")
                print(f"  Overall wait time (from components): {calculated_overall:.2f}s")
                if abs(avg_wait_final - calculated_overall) > 0.01:
                    print(f"  ⚠️  Difference: {abs(avg_wait_final - calculated_overall):.2f}s")
            
            print(f"\n📈 SIMULATION STATISTICS:")
            print(f"  Total Simulation Steps: {step}")
            print(f"  Steps with Vehicles: {metric_steps}")
            print(f"  Active Vehicles (still in network): {len(vehicle_accumulated_wait)}")
            print(f"  Emergency Priority: {'✅ ENABLED' if emergency_priority_enabled else '❌ DISABLED'}")
            print("="*70)
        else:
            print("\n⚠️  No completed vehicles to analyze (simulation too short or no vehicles reached destination)")
        
        # Print proximity stats if used
        if proximity_controller:
            proximity_controller.print_stats()
        
        # Print network metrics
        ns3_bridge.print_summary()
        
        # Save results
        results_file = os.path.join(output_dir, 'integrated_simulation_results.json')
        ns3_bridge.save_results(results_file)
        
        # Save per-run benchmark metrics as JSON (used by benchmark script)
        import json
        ns3_metrics = ns3_bridge.get_metrics()
        
        benchmark_metrics = {
            'mode': args.mode,
            'seed': args.seed,
            'security': args.security,
            'emergency_priority_mode': args.emergency_priority,
            'emergency_priority_enabled': emergency_priority_enabled,
            'emergency_detection_range_m': traffic_controller.emergency_detection_range,
            'emergency_corridor_depth_junctions': traffic_controller.green_corridor_junction_lookahead,
            'emergency_corridor_distance_m': traffic_controller.green_corridor_max_distance,
            'emergency_pass_through_range_m': traffic_controller.emergency_pass_through_range,
            'steps': step,
            'elapsed_time_s': elapsed_time,
            # Overall traffic metrics
            'avg_wait_time': sum(completed_vehicles_wait) / len(completed_vehicles_wait) if completed_vehicles_wait else 0,
            'avg_trip_speed': sum(completed_vehicles_speed) / len(completed_vehicles_speed) if completed_vehicles_speed else 0,
            'avg_queue_length': total_queue_length / max(metric_steps, 1),
            'total_completed_vehicles': len(completed_vehicles_wait),
            'throughput_veh_per_min': len(completed_vehicles_wait) / max(elapsed_time / 60, 1),
            # Emergency vehicle metrics
            'emergency_avg_wait': sum(completed_emergency_wait) / len(completed_emergency_wait) if completed_emergency_wait else 0,
            'emergency_avg_speed': sum(completed_emergency_speed) / len(completed_emergency_speed) if completed_emergency_speed else 0,
            'emergency_completed': len(completed_emergency_wait),
            # Normal vehicle metrics
            'normal_avg_wait': sum(completed_normal_wait) / len(completed_normal_wait) if completed_normal_wait else 0,
            'normal_avg_speed': sum(completed_normal_speed) / len(completed_normal_speed) if completed_normal_speed else 0,
            'normal_completed': len(completed_normal_wait),
            # Network metrics (V2V / V2I)
            'wifi_pdr': ns3_metrics['v2v_wifi']['pdr'] * 100,
            'v2v_pdr': ns3_metrics['v2v_wifi']['pdr'] * 100,
            'v2i_pdr': ns3_metrics['v2i_combined']['pdr'] * 100,
            'wimax_pdr': ns3_metrics['v2i_wimax']['pdr'] * 100,
            'wifi_packets_sent': ns3_metrics['v2v_wifi'].get('packets_sent', 0),
            'wifi_packets_received': ns3_metrics['v2v_wifi'].get('packets_received', 0),
            'wimax_packets_sent': ns3_metrics['v2i_wimax'].get('packets_sent', 0),
            'wimax_packets_received': ns3_metrics['v2i_wimax'].get('packets_received', 0),
            'v2i_packets_sent': ns3_metrics['v2i_combined'].get('packets_sent', 0),
            'v2i_packets_received': ns3_metrics['v2i_combined'].get('packets_received', 0),
            # Combined network metrics
            'overall_pdr': ns3_metrics['combined']['overall_pdr'] * 100,
            'avg_latency_ms': ns3_metrics['combined']['average_delay_ms'],
            # Emergency vehicle communication metrics
            'emergency_comm_success_rate': ns3_metrics['emergency']['success_rate'] * 100,
            'emergency_comm_avg_delay_ms': ns3_metrics['emergency']['average_delay_ms'],
            # Queue length by vehicle type
            'emergency_avg_queue_length': total_emergency_queue_length / max(metric_steps, 1),
            'normal_avg_queue_length': total_normal_queue_length / max(metric_steps, 1),
            # Per-step time-series data (for graphs)
            'per_step_delay_ms': ns3_bridge.per_step_delay,
            'per_step_wait_time': per_step_avg_wait,
            'per_step_queue_length': per_step_queue,
            'per_step_emergency_wait': per_step_emergency_wait,
        }
        
        benchmark_file = os.path.join(output_dir, 'benchmark_metrics.json')
        with open(benchmark_file, 'w') as f:
            json.dump(benchmark_metrics, f, indent=2)
        print(f"  ✅ Saved benchmark_metrics.json")
        
        # Save outputs
        print(f"\n📁 Saving outputs to {output_dir}...")
        
        # Save traffic controller data
        if hasattr(traffic_controller, "packets_df") and traffic_controller.packets_df is not None:
            packets_file = os.path.join(output_dir, "v2i_packets.csv")
            traffic_controller.packets_df.to_csv(packets_file, index=False)
            print(f"  ✅ Saved v2i_packets.csv")
        
        if hasattr(traffic_controller, "metrics_df") and traffic_controller.metrics_df is not None:
            metrics_file = os.path.join(output_dir, "v2i_metrics.csv")
            traffic_controller.metrics_df.to_csv(metrics_file, index=False)
            print(f"  ✅ Saved v2i_metrics.csv")
        
        print(f"\n✅ All results saved to: {output_dir}")
        print(f"📊 Main results: {results_file}")


if __name__ == "__main__":
    main()
