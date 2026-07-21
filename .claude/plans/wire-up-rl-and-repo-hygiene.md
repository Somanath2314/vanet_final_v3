# Plan: Wire up RL for real + repo hygiene

## Context

This VANET capstone simulates emergency-vehicle-aware traffic control, combining SUMO, an analytical NS3 network model, a trained DQN, edge computing, and RSA security, fronted by a React/Flask dashboard. Two problems block it from doing what it claims:

1. **The trained DQN never runs.** `load_trained_model()` loads the model, but every control mode (`rule`/`rl`/`hybrid`/`proximity`) falls through to density-based control. `ProximityHybridController.step()` only *monitors* proximity and switches a `junction_modes` flag, then unconditionally calls `traffic_controller.run_simulation_step()` (density). The RL "headline feature" is not wired in — a code comment at [run_complete_integrated.py:212-214](../../sumo_simulation/run_complete_integrated.py#L212-L214) even admits it.

2. **Repo hygiene.** No root `requirements.txt`; `backend/requirements.txt` is empty (0 bytes) though the README points installers there. Only [rl_module/requirements.txt](../../rl_module/requirements.txt) has real deps and it omits `flask`, `flask-cors`, `stable-baselines3`, `cryptography`. `.gitignore`'s output rules are commented out, so generated artifacts get tracked.

Outcome: the trained DQN actually controls traffic lights in `rl`/`hybrid`/`proximity` modes, with a clean fall-back to density control, and the repo has working dependency files. **Per user decision: no git removal/history rewrite** — only add requirements + `.gitignore` rules for future files.

## Key facts driving the design

- **Use the latest trained model: [`rl_module/trained_models/dqn_traffic_20260304_222100/dqn_traffic_final.zip`](../../rl_module/trained_models/dqn_traffic_20260304_222100/dqn_traffic_final.zip)** (200,000 timesteps, 200 episodes, final avg reward ~296k). Ignore `archive_v3/` — the training path in use is [`rl_module/train.py:142-184`](../../rl_module/train.py#L142-L184).
- The model was trained with `beta=20` and `action_spec` built from `traci.trafficlight.getAllProgramLogics(tl_id)[0].phases` for **all** TLs. The sumocfg loads [`maps/simple_network.net.xml`](../../sumo_simulation/maps/simple_network.net.xml), whose TL logic is **J2 (4 phases) × J3 (4 phases) = 16 discrete actions** (a *joint* controller over both junctions, not per-junction). State strings are **6-char** (`"GGGrrr"`). Observation dim = `7*20 + 12 + 2 = 154` (verified directly from the model zip: `action_space.n=16`, `observation_space._shape=[154]`).
- Note `maps/tls.tll.xml` (8 phases, 4-char states) is **NOT referenced by the sumocfg** — it's a stale standalone file. The live TL logic comes from the net file. Ignore it.
- **Must not reuse** `traffic_controller.default_phases` — although the states there are also 6-char, the **phase ordering differs** (net file: `GGGrrr, yyyrrr, rrrGGG, rrryyy`; default_phases: `rrrGGG, rrryyy, GGGrrr, yyyrrr`), which would scramble the action-index→phase mapping the model learned. Always rebuild `action_spec` live from `getAllProgramLogics`, exactly like `train.py`.
- **Double-step hazard:** both `VANETTrafficEnv.step()` ([vanet_env.py:670](../../rl_module/vanet_env.py#L670)) and `traffic_controller.run_simulation_step()` ([traffic_controller.py:584](../../sumo_simulation/traffic_controller.py#L584)) call `traci.simulationStep()`. Invariant to hold: **`run_simulation_step()` is the sole SUMO stepper; `env.step()` is never called.**
- `run_simulation_step()` skips ALL its own TL control when `self.mode == "rl"` ([traffic_controller.py:594](../../sumo_simulation/traffic_controller.py#L594)) — so setting `mode='rl'` lets RL fully own the lights while the controller still steps SUMO + does edge/security/metrics.
- Reusable env helpers that do **not** step SUMO: `get_state()` (:338), `_apply_rl_actions()` (:295), `_update_obs_wait_steps()` (:309), `_increment_obs_tl_wait_steps()` (:333), `_update_obs_veh_acc()` (:144).

## Implementation

All RL changes are in **[sumo_simulation/run_complete_integrated.py](../../sumo_simulation/run_complete_integrated.py)** (no edits needed to `vanet_env.py` or `traffic_controller.py` — we reuse their existing methods).

### 1. New helper functions (near top, after `load_trained_model`)

- `build_rl_action_spec()` — after SUMO connects, build `{tl_id: [phase.state for phase in getAllProgramLogics(tl_id)[0].phases]}` for all TLs, exactly like training.
- `create_rl_env(action_spec)` — instantiate `VANETTrafficEnv({'beta':20, 'action_spec':action_spec, 'tl_constraint_min':5, 'tl_constraint_max':60, 'sim_step':1.0, 'algorithm':'DQN', 'horizon':1000})`.
- `validate_model_env(model, env)` — compare `model.observation_space.shape[0]` vs `env.observation_space.shape[0]` (154) and `model.action_space.n` vs `env.action_space.n` (16). Return bool.
- `rl_inference_step(env, model, tc)` — the per-iteration RL step, ordering:
  1. `obs = env.get_state()`
  2. `action, _ = model.predict(obs, deterministic=True)`
  3. `env._apply_rl_actions(int(action))` (before the step, so the phase is in effect during `simulationStep`)
  4. `tc.run_simulation_step()` (the single SUMO step; requires `tc.mode == 'rl'`)
  5. tracking updates: `_update_obs_wait_steps()`, `_increment_obs_tl_wait_steps()`, `_update_obs_veh_acc()`
  - Wrap 1-3 in try/except; on error set `tc.mode='density'` for that step but **still** call `run_simulation_step()` exactly once + tracking (preserves single-step invariant).

### 2. `main()` wiring (after `connect_to_sumo` + security init, ~line 445)

- Extend model-loading + `--model`-required validation ([:314-323](../../sumo_simulation/run_complete_integrated.py#L314-L323), [:344-351](../../sumo_simulation/run_complete_integrated.py#L344-L351)) to include `hybrid`.
- Build `action_spec` and `env` only when `mode in {rl,hybrid,proximity}` and a model loaded.
- `rl_enabled = model and env and validate_model_env(model, env)`. On failure: warn and hard-fall-back to density (`rl_enabled=False`, keep `mode` density).

### 3. `ProximityHybridController`

- `__init__` gains `env=None` param, stored as `self.env`; passed at call site ([:425-429](../../sumo_simulation/run_complete_integrated.py#L425-L429)).
- Rewrite `step()` ([:162-215](../../sumo_simulation/run_complete_integrated.py#L162-L215)): keep proximity detection + stats, but replace the unconditional `run_simulation_step()` at [:215](../../sumo_simulation/run_complete_integrated.py#L215) with:
  - `use_rl = len(rl_junctions) > 0 and self.model and self.env`
  - if `use_rl`: `tc.mode='rl'`, `rl_inference_step(self.env, self.model, tc)`
  - else: `tc.mode='density'`, `tc.run_simulation_step()` + env tracking updates
- Keep `junction_modes` for stats only (joint controller = intersection-wide RL when any junction is in proximity — Option A).

### 4. Main-loop dispatch ([:479-500](../../sumo_simulation/run_complete_integrated.py#L479-L500))

- `proximity`: `proximity_controller.step()` (unchanged call).
- `rl`: `tc.mode='rl'`; `rl_inference_step(env, model, tc)` if `rl_enabled` else `run_simulation_step()`.
- `hybrid`: `emergency_present = any('emergency' in v.lower() for v in traci.vehicle.getIDList())`; RL when present & `rl_enabled`, else density. Always run the 3 env tracking updates so timers stay coherent. Drop the no-op `step % 5` gate.
- `rule`: unchanged.

### 5. Repo hygiene

- Update **[`server.py:154`](../../server.py#L154)** — the `rl` method still hardcodes the old `dqn_traffic_20251108_130019` model. Point it at the latest `dqn_traffic_20260304_222100/dqn_traffic_final.zip` so the frontend runs the current model.
- Create root **`requirements.txt`**: merge `rl_module/requirements.txt` deps + `flask`, `flask-cors`, `stable-baselines3`, `cryptography` (+ any others confirmed by imports). Keep version pins consistent with existing pins.
- Populate **`backend/requirements.txt`** (or make README point to root) — align with what README instructs.
- Uncomment/add **`.gitignore`** rules for generated outputs going forward: `sumo_simulation/output*/`, `*.log`, `live_metrics.json`, `rl_module/trained_models/*/tensorboard/`. (No `git rm` — existing tracked files stay per user decision.)

## Known caveats (documented, not blocking)

- On rl→density transitions, `intersections[tl]["current_phase"]/"time_in_phase"` are stale (RL wrote states directly), so the first density step may jump phase — cosmetic/transient. Optional resync from `traci.trafficlight.getPhase(tl)`.
- In `rl` mode the controller's own emergency priority ([:591](../../sumo_simulation/traffic_controller.py#L591)) is skipped; emergency handling relies on the (emergency-reward-shaped) trained policy — consistent with "RL owns the TLs".

## Verification

1. **Static check:** grep to confirm exactly one `run_simulation_step()` per loop iteration in each branch and zero `env.step()` calls.
2. **Rule mode still works (regression):** `bash run_integrated_sumo_ns3.sh --steps 200` (no GUI) → completes, prints vehicular metrics summary.
3. **RL proximity mode runs the model:** `bash run_integrated_sumo_ns3.sh --proximity 250 --model rl_module/trained_models/dqn_traffic_20260304_222100/dqn_traffic_final.zip --steps 300` → console shows RL activations near emergencies AND no double-speed simulation (sim time advances 1s/step). Confirm no `model.predict` shape errors.
4. **Dim-mismatch fallback:** temporarily point `--model` at a bad/mismatched zip → confirm clean warning + density fallback, no crash.
5. **Deps install clean:** in a fresh venv, `pip install -r requirements.txt` succeeds and `python server.py` imports without ModuleNotFoundError.
