# Mesh Routing Research — Project Context

## Current status
- Core simulation and baseline routing are present.
- FastAPI endpoints are implemented in `backend/main.py` (`/api/health`, `/api/simulate`, `/api/compare`).
- Connectivity audit fix applied to backend metrics and frontend final-connectivity display.
- **Module 08: End-to-End API Integration** fully implemented and verified.

## Connectivity behavior
- `measure_connectivity(graph, k)` measures ordinary connectivity and edge connectivity on the graph passed to it without mutating the graph.
- Empty or disconnected graphs report `connected=false`, `edge_connectivity=0`, and `connectivity_target_met=false`.
- A connected graph satisfies the target only if its measured edge connectivity is at least the requested `k`.
- The UI now distinguishes `Disconnected`, `Connected — target not met`, and `Target satisfied`.
- A graph can be connected with edge connectivity 1; this is not enough to satisfy k=2.

## Module 08: End-to-End API Integration Implementation
- **Algorithm Selection**:
  - Added dedicated routing algorithm selectors (`incremental`, `energy`, `shortest`) in both the hero actions bar and simulation controls grid in [main.jsx](file:///c:/Project%20files/mesh-routing-research/frontend/src/main.jsx).
  - Default algorithm is `incremental` (IEFT-IR).
  - The API request passes `algorithm` as query parameter matching backend endpoint specifications.
- **Form Controls & Gateway Configuration**:
  - Added explicit gateway node configuration input bound to `config.gateway` (range `0` to `nodes - 1`).
  - Parameter controls cover all `SimRequest` fields: `nodes`, `gateway`, `rounds`, `k`, `traffic_per_round`, `failure_round`, `failure_count`, `threshold`, and `seed`.
- **Validation & Loading States**:
  - Added frontend pre-flight validation preventing invalid submissions (`gateway >= nodes`, node count 5–150, round ranges, etc.).
  - Added live execution status indicator and banner during simulation (`busy` state) displaying the running algorithm.
  - Enhanced error handling parsing backend validation error lists (`detail` array) and backend error strings with a dismissible UI banner.
- **Real Metrics & Topology Display**:
  - Frontend renders real backend response objects: Packet Delivery Ratio, Energy Consumed, Routing Recomputations, Local Route Updates, and Edge Connectivity.
  - Interactive SVG topology map displays real nodes, links, active routes, and failed/dead nodes.
  - Line charts display round-by-round mean energy depletion and cumulative PDR history.

## Research Validation & Reproducible Benchmarking
- **Metric Formula Auditing (`backend/engine.py`)**:
  - `packet_delivery_ratio`: Measured as `packets_delivered / packets_sent`. Confirmed that only packets successfully reaching the gateway across active, non-depleted edges increment `packets_delivered`.
  - `energy_consumed`: Measured per traversed hop based on transmitter cost $E_{\text{tx}} = \text{tx\_cost} \times (1 + d^2)$ and receiver cost $E_{\text{rx}} = \text{rx\_cost}$, deducting energy directly from node residual batteries.
  - `routing_recomputations`: Tracks path recalculation calls. Increments by 1 per source route recomputed (for global recalculations) or per affected route repaired (for incremental recalculations). Explicitly distinguished from physical radio frame overhead.
  - `local_route_updates`: Tracks targeted route recalculations in `incremental` mode when affected routes traverse failed or depleted nodes.
  - `first_node_dead_round`, `half_nodes_dead_round`, `last_node_dead_round`: Audited round tracking. Added support and regression tests for `last_node_dead_round`.
  - `connectivity` & `edge_connectivity`: Evaluated non-destructively via `measure_connectivity(active, k)` using NetworkX edge connectivity algorithms.
- **Reproducible Multi-Seed Benchmark (`seeds=[1, 2, 3, 4, 5]`)**:
  - Executed identical initial network topologies, seed sequences, and traffic demands across `shortest`, `energy`, and `incremental`.
  - Raw results and paired difference statistics saved to [`research_results/ieftir_comparison.json`](file:///c:/Project%20files/mesh-routing-research/research_results/ieftir_comparison.json).
  - Generated Markdown benchmark report at [`research_results/ieftir_comparison_report.md`](file:///c:/Project%20files/mesh-routing-research/research_results/ieftir_comparison_report.md).
- **Core Experimental Findings**:
  - `incremental` reduced routing recomputations by **79.1%** relative to `energy` (mean $442.6 \pm 402.5$ vs. $2121.2 \pm 50.7$, paired difference $p < 0.001$).
  - Energy-aware methods significantly delayed first node death from round $14.2 \pm 2.28$ (`shortest`) to round $21.8 \pm 5.22$ (`energy`) and $22.0 \pm 5.20$ (`incremental`), demonstrating avoidance of shortest-hop relay hotspots.
  - Identical PDR across seeds 2–5 ($0.3861$) explained by physical topological partitioning: when an articulation point fails at round 25, no alternate path exists to the gateway regardless of routing strategy.

## Changed files
- `backend/engine.py`: Added `last_node_dead_round` tracking and exposed it in metrics and summary statistics.
- `backend/test_simulation.py`: Added `test_death_round_metrics` validating node death rounds, battery exhaustion, and delivery ratios.
- `backend/test_incremental.py`: Added `test_paired_seeds_equivalent_initial_conditions` verifying identical initial topologies across algorithms on paired seeds.
- `research_results/ieftir_comparison.json`: Updated with full 5-seed benchmark results, paired statistics, and confidence intervals.
- `research_results/ieftir_comparison_report.md`: Created detailed Markdown evaluation report.
- `research_results/robustness_scalability.json`: Multi-scenario benchmark results dataset (420 runs across 7 scenarios, 20 seeds, 3 algorithms).
- `research_results/robustness_scalability_report.md`: Comprehensive robustness, scalability, and statistical validation report.
- `generate_robustness_report.py`: Reproducible report generator script.

## Robustness, Scalability, and Statistical Validation Stage
- **Experiment Scope & Verification**:
  - **420 controlled runs** executed and verified in [`research_results/robustness_scalability.json`](file:///c:/Project%20files/mesh-routing-research/research_results/robustness_scalability.json).
  - 7 diverse scenarios: $N=20$ (random failure, articulation failure, high traffic, extended lifetime horizon), $N=50$ (random failure, articulation failure), and $N=100$ (large-scale random failure).
  - 20 random seeds per scenario (seeds 1–20) evaluated under identical initial topology and traffic requests for `shortest`, `energy`, and `incremental`.
  - 0 failed runs, 0 missing metric values.
- **Statistical Findings**:
  - **Recomputation Reduction ($p < 10^{-15}$ across all scenarios)**:
    - IEFT-IR (`incremental`) consistently reduces routing recomputations by **63.67% to 77.89%** compared to `energy` across all scenarios.
    - Global mean recomputations across 140 paired runs: `energy` = 1,359.92 vs. `incremental` = **382.56** (**71.87% global reduction**, saving 136,831 recomputation events overall).
    - At $N=100$ nodes, recomputations dropped from 3,195.1 to 706.5 (**77.89% reduction**; saving >2,488 route recomputation events per 30-round run).
  - **Delivery Ratio (PDR) Preservation**:
    - Global mean PDR: `energy` = 0.6151 vs. `incremental` = 0.6167.
    - Paired differences in 4 of 7 scenarios were exactly 0.0000 ($p = 1.0$), with all others showing no statistically significant difference ($\alpha = 0.05$). Local route repairs preserve routing fidelity.
  - **Energy Footprint Equivalence**:
    - Global mean energy consumed: `energy` = 490.09 vs. `incremental` = 493.12 (net difference $< 1.2\%$). Local repairs avoid inefficient routing detours.
  - **Execution Runtime Acceleration**:
    - IEFT-IR achieves a **2.61x overall runtime speedup** over `energy` (mean execution time 425.94 ms vs. 1,109.72 ms).
    - At $N=100$, runtime dropped from 5,695.0 ms to 1,870.2 ms (**3.04x speedup**).
- **Artifacts**:
  - Detailed Markdown report compiled at [`research_results/robustness_scalability_report.md`](file:///c:/Project%20files/mesh-routing-research/research_results/robustness_scalability_report.md).

## Automatic Rerouting Verification Stage
- **Deterministic Multi-Path Topology Demonstration**:
  - Defined topology with Gateway 0, Sensor S1 (node 1) with dual paths to gateway (via Relay 2 and backup Relay 3), Sensor S2 (node 4) with direct route [4, 0], and Sensor S3 (node 5) with single route [5, 2, 0].
  - **Unit Test (`test_automatic_rerouting_after_node_failure`)**: Demonstrates the 7-step algorithmic sequence isolated at the method level.
  - **Production Simulation Integration Test (`test_automatic_rerouting_simulation_integration`)**:
    - Executes the actual `run_simulation()` production engine flow end-to-end.
    - Pre-failure rounds (0 and 1): Sensor 1 routes via `[1, 2, 0]` and delivers 12/12 packets with 5 initial recomputations and 0 local updates.
    - Real failure injection at round 2: Simulation engine detects Relay 2 failure and logs `{"round": 2, "type": "node_failure", "node": 2}`.
    - Production cache invalidation and incremental repair: Sensor 1 automatically switches to alternative route `[1, 3, 0]`.
    - Post-failure delivery (rounds 2 and 3): Sensor 1 delivers 12/12 subsequent packets via `[1, 3, 0]` with 0 packet loss (PDR = 1.0).
    - Unaffected route preservation: Direct route `[4, 0]` is preserved intact across all rounds without recomputation.
    - Unreachable destination marking: Sensor 5 is marked `None` (unreachable) by the engine.
    - Recomputations instrumented at actual execution points: Exactly 8 total recomputations (5 initial + 3 local repairs) and 1 full recomputation.

## Scientific Validation & Reproducibility Audit Stage
- **Full Dataset Audit**:
  - Validated 420 run records in [`research_results/robustness_scalability.json`](file:///c:/Project%20files/mesh-routing-research/research_results/robustness_scalability.json): 0 missing values, 0 failed runs, 0 duplicates, 0 invalid numbers.
  - Initial topology edge connectivity matched 100% across all 140 paired seed configurations.
  - Energy vs. Incremental node failure selection matched identically in 140/140 runs.
  - Recalculated sample mean, standard deviation, and paired Student's $t$ statistics from raw observations with zero discrepancies.
- **Independent Reproducibility Verification**:
  - Smoke check (6 runs), Scenario 1 (60 runs), and Scenario 2 (60 runs) reproduced independently without modifying existing artifacts.
  - Confirmed 100% bit-for-bit numerical reproducibility across all deterministic metrics (`packet_delivery_ratio`, `packets_sent`, `packets_delivered`, `energy_consumed`, `routing_recomputations`, `local_route_updates`, `failed_node_ids`, `initial_edge_connectivity`).
  - Saved audit evidence in [`research_results/reproducibility_audit/`](file:///c:/Project%20files/mesh-routing-research/research_results/reproducibility_audit/) and compiled comprehensive audit report at [`research_results/scientific_validation_audit_report.md`](file:///c:/Project%20files/mesh-routing-research/research_results/scientific_validation_audit_report.md).

## Control-Plane Overhead Modeling Stage & Scientific Audit
- **Model Formulas & Specifications (`backend/engine.py`)**:
  - Control radio energy cost per hop:
    $$E_{\text{ctrl}} = \kappa_{\text{ctrl}} \times \left[ C_{\text{tx}} \times (1 + d^2) + C_{\text{rx}} \right]$$
    where $\kappa_{\text{ctrl}} = 0.5$ (scaling factor for compact control frames relative to MTU data frames), $C_{\text{tx}} = 0.65\text{ J}$ (transmitter base cost), $C_{\text{rx}} = 0.18\text{ J}$ (receiver cost), and $d$ is Euclidean link distance in $[0, 1]^2$.
  - Control message payload sizes:
    - Route advertisement frame (`ROUTE_ADV`): 32 bytes (B) default.
    - Local failure notification frame (`FAIL_NOTIF`): 16 bytes (B) default.
  - Accounting rules:
    - Setup (round 0): All operational nodes advertise paths hop-by-hop toward Gateway 0.
    - Subsequent rounds: `shortest` and `energy` perform global network-wide recomputation and re-advertisement; `incremental` triggers re-advertisements **only** for routes traversing failed or depleted nodes.
    - Failure notifications: 1-hop physical neighbors of failed nodes broadcast a 16 B notification frame identically across all algorithms.
    - Strict decoupling: `routing_recomputations` (CPU operations), `ctrl_messages_sent`, `ctrl_bytes_sent`, `ctrl_energy_consumed` (control radio energy in J), and `data_energy_consumed` (data-plane energy in J) are tracked independently.
- **Independently Verified Benchmark Findings ($n = 20$ seeds per scenario)**:
  - **Comparison 1: `energy − incremental`**:
    - $N=20$, random failure: 64.51% control message reduction (+659.20 msgs), 65.02% control byte reduction (+21,100.00 B), 64.05% control energy reduction (+292.57 J), $p < 10^{-15}$.
    - $N=20$, articulation cut: 63.23% control message reduction (+635.20 msgs), 63.80% control byte reduction (+20,348.80 B), 62.72% control energy reduction (+281.71 J), $p < 10^{-15}$.
    - $N=50$, random failure: 49.02% control message reduction (+2,001.35 msgs), 49.12% control byte reduction (+64,029.60 B), 48.91% control energy reduction (+858.90 J), $p < 10^{-15}$.
  - **Comparison 2: `shortest − incremental`**:
    - $N=20$, random failure: 64.99% control message reduction (+673.30 msgs), 65.38% control byte reduction (+21,435.20 B), 64.53% control energy reduction (+298.71 J), $p < 10^{-15}$.
    - $N=20$, articulation cut: 63.88% control message reduction (+653.40 msgs), 64.31% control byte reduction (+20,803.20 B), 63.41% control energy reduction (+290.25 J), $p < 10^{-15}$.
    - $N=50$, random failure: 54.01% control message reduction (+2,444.10 msgs), 54.02% control byte reduction (+77,901.60 B), 53.86% control energy reduction (+1,047.47 J), $p < 10^{-15}$.
  - **Data-Plane Invariance**:
    - PDR and data packet energy remain preserved across all scenarios with no statistically significant differences ($p > 0.05$ across all tests).
  - **Sensitivity Analysis Invariance**:
    - Across Lightweight (16 B / 8 B / 0.3x), Standard (32 B / 16 B / 0.5x), and Heavy (64 B / 32 B / 0.8x) frame profiles, percentage reductions remain constant: **65.71% control byte reduction**, **64.83% control energy reduction**, and **65.25% control message reduction**.
- **Model Assumptions & Experimental Limitations**:
  - Modeled radio overhead represents analytical simulation accounting rather than physical testbed hardware captures.
  - Radio model energy scales with distance squared ($1 + d^2$) and transceiver constant, decoupled from frame byte payload size.
  - Baselines perform global recomputation every round, which maximally penalizes periodic recomputation strategies and isolates the structural advantage of localized repair.
  - MAC contention, channel backoff, frame collisions, and retransmissions are not simulated.
- **Verified Deliverables & Manifest**:
  - `research_results/control_plane_audit/control_plane_benchmark.json`: Raw experimental dataset (180 runs).
  - `research_results/control_plane_audit/control_plane_verified_results.json`: Recalculated metrics for both `energy − incremental` and `shortest − incremental`, with verified sensitivity analysis and units.
  - `research_results/control_plane_audit/control_plane_validation_tests.txt`: Backend test output transcript (55 passed, exit code 0).
  - `research_results/control_plane_audit/control_plane_implementation_audit.md`: Formal implementation audit documenting error analysis and verified statistics.
  - `research_results/control_plane_audit/control_plane_report.md`: Formal research report with corrected standard deviations, separate baseline comparisons, and explicit units.

## Verification Results
1. **Backend Tests**:
   - Command: `.\.venv\Scripts\python -m pytest -v backend`
   - Result: `55 passed in 0.97s` (exit code 0), documented in `research_results/control_plane_audit/control_plane_validation_tests.txt`.
2. **Frontend Production Build**:
   - Command: `npm run build` from `frontend/`
   - Result: Vite v6.4.4 production build succeeded in 4.13s (exit code 0; `dist/index.html` 0.41 kB, `dist/assets/index-DGd1dWui.css` 11.21 kB, `dist/assets/index-CstuGF5C.js` 565.17 kB).
3. **Live HTTP API Verification**:
   - Verified against running FastAPI server (`http://localhost:8000`) for all three algorithms (`shortest`, `energy`, `incremental`).

## Remaining Limitations & Next Steps
- Energy savings represent modeled simulation calculations and should not be claimed as physical hardware energy measurements.
- Future work: Port topology traces to discrete-event network simulators (e.g., ns-3, Cooja, or OMNeT++) with realistic IEEE 802.15.4 MAC layer, CSMA-CA/TSCH channel contention, and physical frame drop dynamics.
