# IEFT-IR Abstract Alignment & Implementation Audit Report

**Date:** 2026-10-11
**Project:** System and Method for Incremental Energy-Aware Fault-Tolerant Routing in Low-Power Mesh Networks (IEFT-IR)
**Location:** `C:\Project files\mesh-routing-research`
**Status:** Implementation Complete & Empirically Verified (77/77 tests passing, Frontend production build clean)

---

## 1. Executive Summary

This audit documents the implementation and verification of the two research-critical mechanisms specified in the research abstract:
1. **Rigorous k-Edge Connectivity (`rigorous_k`):** Explicit bridge detection and bridge-avoidance routing for $k \ge 2$, with topology cache invalidation, fallback on infeasibility, and graph-wide connectivity tracking.
2. **Configurable Multi-Objective Routing Cost Function (`use_weighted_route`):** Normalized multi-criteria routing function balancing transmission cost, residual energy risk, cumulative depletion/drain, and graph edge redundancy.

Both features have been implemented with backward-compatible defaults, validated with comprehensive deterministic unit/integration test suites, exposed via the FastAPI backend API schemas, wired into the React frontend controls, and verified through both backend test runs (77/77 passing) and frontend production builds (`npm run build`).

---

## 2. Implementation Findings & Code Changes

### A. Backend Routing Engine (`backend/engine.py`)
- **Cached Edge Connectivity:** Added `_cached_edge_connectivity` dictionary and `_get_cached_connectivity(G)` helper along with `invalidate_connectivity_cache()`. Instead of recomputing `nx.edge_connectivity(G)` (an expensive network-flow computation) on every candidate edge during Dijkstra/shortest-path evaluations, connectivity is cached by graph instance ID.
- **Cache Invalidation Lifecycle:** `invalidate_connectivity_cache()` is triggered explicitly at every topology-altering milestone:
  1. Initial active graph copy creation.
  2. Gateway node failure/removal.
  3. Injected sensor node failure/removal.
  4. Battery depletion node death.
- **Bridge Detection & Avoidance (`_path_uses_bridge`):** Uses Tarjan's bridge-finding algorithm via `nx.bridges(G)` to identify single-point-of-failure edges.
- **Rigorous k-Edge Path Selection (`compute_path`):** When `cfg.rigorous_k = True` and $k \ge 2$, candidate paths that traverse bridges are rejected. Up to `cfg.rigorous_k_max_alternatives` (default 5) penalty-based alternative paths are evaluated. If no bridge-free route exists (e.g., line graph or topologically isolated component), the simulator gracefully falls back to the best available path rather than unnecessarily dropping packets.
- **Multi-Objective Cost Formulation (`route_weight`):** Aligned terms with physical meanings:
  $$C(u, v) = T(u, v) + w_E \cdot 2.4 \cdot \frac{1}{e_v} + w_D \cdot 3.0 \cdot D_v + w_R \cdot \left(1 - \frac{\kappa}{k}\right)$$
  - $T(u, v) = \text{tx\_cost} \cdot (1 + d^2)$: link transmission energy.
  - $e_v = \max(0.02, E_v / E_{\text{init}})$: normalized residual energy of receiving node $v$. Lower energy yields hyperbolic penalty, weighted by $w_E$ (`energy_weight`).
  - $D_v = \text{depletion}_v / E_{\text{init}}$: normalized cumulative energy drain of node $v$, weighted by $w_D$ (`depletion_weight`).
  - $\kappa = \lambda(G)$: active graph edge connectivity relative to target $k$, weighted by $w_R$ (`redundancy_weight`).
- **Legacy Fallback:** When `use_weighted_route = False`, the exact original unweighted cost formula is evaluated, preserving 100% regression compatibility for previous experiments.

### B. Backend API Integration (`backend/main.py`)
- Updated `SimRequest` schema with backward-compatible defaults:
  - `use_weighted_route: bool = False`
  - `energy_weight: float = Field(1.0, ge=0, le=100)`
  - `depletion_weight: float = Field(1.0, ge=0, le=100)`
  - `redundancy_weight: float = Field(1.0, ge=0, le=100)`
  - `rigorous_k: bool = False`
- Inherited automatically by `CompareRequest` for multi-algorithm benchmark comparisons.

### C. Frontend Dashboard (`frontend/src/main.jsx`)
- Added state variables to `initial` config object:
  - `use_weighted_route: false`, `energy_weight: 1.0`, `depletion_weight: 1.0`, `redundancy_weight: 1.0`, `rigorous_k: false`.
- Updated `update()` helper to handle boolean toggle values.
- Extended client-side `validate()` for weight boundaries $[0, 100]$.
- Added interactive controls to `control-grid`:
  - Rigorous k-edge safety toggle (`rigorous_k`).
  - Weighted multi-objective toggle (`use_weighted_route`).
  - Conditional sliders for $w_E$, $w_D$, and $w_R$ when multi-objective routing is active.

---

## 3. Verification Test Suite & Results

### Backend Test Execution
- **Command:** `& ".venv/Scripts/python.exe" -m pytest -v` (in `backend/`)
- **Total Tests Collected:** 77
- **Total Tests Passed:** 77
- **Total Tests Failed:** 0
- **Execution Time:** ~1.25 seconds

#### Test Breakdown by Module:
1. `test_rigorous_k.py` (**19 tests**):
   - `TestPathUsesBridge` (3 tests): Bridge detection verified on line graphs, cycles, and bridge topologies.
   - `TestRigorousKEnforcement` (5 tests): Verified that $k \ge 2$ avoids bridges, falls back on infeasible graphs, and bypasses checks when $k=1$ or disabled.
   - `TestWeightedRouting` (3 tests): Verified that changing $w_E$ vs. $w_D$ switches route selection between energy-constrained and depletion-stressed paths; verified default unweighted behavior when disabled; verified redundancy term uses active connectivity.
   - `TestConnectivityCache` (1 test): Verified cache invalidation after topology mutations.
   - `TestSimulationIntegration` (3 tests): Verified end-to-end simulation runs with rigorous $k$ and weighted routing; verified distinct energy consumption profiles under weighted routing.
   - `TestInfeasibility` (4 tests): Verified handling of disconnected source, missing nodes, source = gateway, and single-node edge-connectivity measurements.
2. `test_incremental.py` (**14 tests**): Verified incremental rerouting, control-plane overhead models, failure recovery, reproducibility across paired seeds.
3. `test_api.py` (**13 tests**): Verified health, simulation, comparison, parameter validations, CORS headers.
4. `test_simulation.py` (**11 tests**): Verified simulation models, energy states, geometric/grid topologies.
5. `test_routing.py` (**7 tests**): Verified shortest vs. energy routing, dead-node avoidance, immutability.
6. `test_connectivity.py` & `test_connectivity_extended.py` (**8 tests**): Verified edge-connectivity metrics, partitions, unreachable targets.
7. `test_engine.py` (**3 tests**): Verified metric ranges, baseline connectivity, reproducibility.
8. `tests/test_compare_stats*.py` (**2 tests**): Verified statistical comparison functions.

### Frontend Production Build
- **Command:** `npm run build` (in `frontend/`)
- **Result:** Exit code 0 (Success)
- **Output:**
  - `dist/index.html` (0.47 kB)
  - `dist/assets/index-DGd1dWui.css` (11.21 kB)
  - `dist/assets/index-CBAExkTD.js` (567.97 kB)
  - 645 modules transformed in 10.40s with zero errors or warnings.

---

## 4. Scientific Grounding & Feature Status Matrix

| Abstract Mechanism | Implementation Status | Verification Status | Notes |
| :--- | :--- | :--- | :--- |
| **k-Edge Connectivity ($\lambda(G) \ge k$)** | **Implemented** | **Verified** | Evaluates active network edge connectivity; avoids bridges on route paths when $k \ge 2$; falls back gracefully on infeasible graphs. |
| **Multi-Objective Cost ($J(P)$)** | **Implemented** | **Verified** | Jointly evaluates transmission cost, residual energy penalty ($w_E$), cumulative depletion ($w_D$), and redundancy deficiency ($w_R$). Route choice changes measurably with weight adjustments. |
| **Incremental Local Rerouting** | **Implemented** | **Verified** | Refreshes only routes traversing affected or depleted nodes upon fault injection or battery warnings. |
| **Control-Plane Overhead Accounting** | **Implemented** | **Verified** | Accounts for notification packets, advertisement frames, and control packet transmissions. |
| **API & Dashboard Integration** | **Implemented** | **Verified** | Full backward-compatible parameters exposed across FastAPI and React UI. |

---

## 5. Limitations & Experimental Scope

1. **Topological Infeasibility:** If the underlying random geometric network contains physical cut-edges (bridges) due to node dispersion, no local routing algorithm can create redundant physical paths without topological link augmentation. The simulator correctly reports achieved connectivity vs. requested target $k$ and falls back to single-path delivery rather than dropping routes.
2. **Macroscopic Energy & Radio Models:** The energy model simulates transmission and reception costs using distance-based power dissipation and packet counts. Physical layer effects such as channel fading, MAC layer packet collisions/backoff, and asynchronous duty cycling are simulated as discrete-event approximations.
3. **Claim Boundaries:** These results demonstrate algorithmic correctness and simulation repeatability. They do not claim physical wireless testbed deployment or formal mathematical proof that local rerouting alone guarantees graph-wide $k$-edge connectivity without topological edge additions.
