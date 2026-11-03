"""Robustness, Scalability, and Statistical Validation Matrix Runner.

Executes a comprehensive experiment matrix across:
- Network sizes: 20, 50, and 100 nodes.
- Failure scenarios:
  1. "no_failure" (failure_count = 0)
  2. "random_failure" (failure_count = 1, failure_mode = "random")
  3. "articulation_failure" (failure_count = 1, failure_mode = "articulation")
- Traffic loads: Low (5 packets/round) and High (20 packets/round)
- Simulation horizons:
  - Standard horizon (30 rounds, initial_energy = 50.0)
  - Extended horizon / Lifetime exploration (120 rounds, initial_energy = 20.0, lower battery to capture node depletions)
- Algorithms: "shortest", "energy", "incremental"
- Explicit seeds: 20 seeds (1 to 20) per scenario.
"""
from __future__ import annotations
import json
import math
import os
import sys
import time
from typing import Any
import numpy as np

# Ensure backend is on import path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from engine import run_simulation


def compute_paired_stats(runs: list[dict[str, Any]], algos: list[str], fields: list[str]) -> list[dict[str, Any]]:
    # Map runs by scenario_id -> seed -> algo -> run
    grouped: dict[str, dict[int, dict[str, dict[str, Any]]]] = {}
    for r in runs:
        sc_id = r["scenario_id"]
        seed = r["seed"]
        algo = r["algorithm"]
        grouped.setdefault(sc_id, {}).setdefault(seed, {})[algo] = r

    pairs = [("shortest", "energy"), ("shortest", "incremental"), ("energy", "incremental")]
    paired_results = []

    for sc_id, seeds_map in grouped.items():
        for a, b in pairs:
            pair_entry = {
                "scenario_id": sc_id,
                "pair": f"{a}_vs_{b}",
                "comparisons": {}
            }
            common_seeds = [s for s, amap in seeds_map.items() if a in amap and b in amap]
            for f in fields:
                diffs = []
                for s in common_seeds:
                    va = seeds_map[s][a].get(f)
                    vb = seeds_map[s][b].get(f)
                    if va is not None and vb is not None:
                        try:
                            fa = float(va)
                            fb = float(vb)
                            if fa == fa and fb == fb and abs(fa) != float("inf") and abs(fb) != float("inf"):
                                diffs.append(fa - fb)
                        except (ValueError, TypeError):
                            pass
                n = len(diffs)
                if n > 0:
                    arr = np.array(diffs, dtype=float)
                    mean = float(np.mean(arr))
                    std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
                    se = std / np.sqrt(n) if n > 1 else 0.0
                    # t-critical for 95% CI
                    # For n=20, df=19, t_crit ~= 2.093; for large n, 1.96
                    t_crit = 2.093 if n == 20 else (1.96 if n > 30 else 2.262 if n == 10 else 2.093)
                    ci_low = mean - t_crit * se
                    ci_high = mean + t_crit * se
                    # t-statistic and approximate p-value
                    t_stat = mean / se if se > 1e-12 else 0.0
                    # two-sided p-value approximation via normal / t CDF
                    p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t_stat) / math.sqrt(2.0)))) if se > 1e-12 else (1.0 if mean == 0.0 else 0.0)
                    pair_entry["comparisons"][f] = {
                        "count": n,
                        "mean_diff": round(mean, 4),
                        "std_diff": round(std, 4),
                        "ci95_low": round(ci_low, 4),
                        "ci95_high": round(ci_high, 4),
                        "t_stat": round(t_stat, 4),
                        "p_value": round(p_val, 5),
                    }
                else:
                    pair_entry["comparisons"][f] = {
                        "count": 0,
                        "mean_diff": None,
                        "std_diff": None,
                        "ci95_low": None,
                        "ci95_high": None,
                        "t_stat": None,
                        "p_value": None,
                    }
            paired_results.append(pair_entry)
    return paired_results


def compute_summary_stats(values: list[float]) -> dict[str, Any]:
    n = len(values)
    if n == 0:
        return {
            "count": 0, "mean": None, "std": None, "median": None,
            "iqr": None, "min": None, "max": None, "ci95_low": None, "ci95_high": None
        }
    arr = np.array(values, dtype=float)
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    median = float(np.median(arr))
    q1 = float(np.percentile(arr, 25))
    q3 = float(np.percentile(arr, 75))
    iqr = q3 - q1
    vmin = float(arr.min())
    vmax = float(arr.max())
    se = std / np.sqrt(n) if n > 1 else 0.0
    t_crit = 2.093 if n == 20 else 1.96
    ci_low = mean - t_crit * se
    ci_high = mean + t_crit * se
    return {
        "count": n,
        "mean": round(mean, 4),
        "std": round(std, 4),
        "median": round(median, 4),
        "iqr": round(iqr, 4),
        "min": round(vmin, 4),
        "max": round(vmax, 4),
        "ci95_low": round(ci_low, 4),
        "ci95_high": round(ci_high, 4),
    }


def main():
    start_total = time.perf_counter()
    seeds = list(range(1, 21))  # 20 seeds: 1..20
    algorithms = ["shortest", "energy", "incremental"]

    # Define matrix scenarios
    scenarios = [
        # Scenario 1: Baseline N=20, random failure, standard horizon
        {
            "id": "sc1_n20_random_fail_t10_r30",
            "name": "N=20, Random Failure, Standard Horizon (30 rounds, 10 pkts/rnd)",
            "nodes": 20,
            "rounds": 30,
            "traffic_per_round": 10,
            "failure_round": 10,
            "failure_count": 1,
            "failure_mode": "random",
            "initial_energy": 50.0,
            "k": 2,
        },
        # Scenario 2: N=20, articulation point failure, standard horizon
        {
            "id": "sc2_n20_articulation_fail_t10_r30",
            "name": "N=20, Articulation Cut Failure, Standard Horizon (30 rounds, 10 pkts/rnd)",
            "nodes": 20,
            "rounds": 30,
            "traffic_per_round": 10,
            "failure_round": 10,
            "failure_count": 1,
            "failure_mode": "articulation",
            "initial_energy": 50.0,
            "k": 2,
        },
        # Scenario 3: N=20, no injected failure, high traffic (battery depletion test)
        {
            "id": "sc3_n20_no_failure_high_traffic_r30",
            "name": "N=20, No Injected Failure, High Traffic (30 rounds, 25 pkts/rnd, E=30)",
            "nodes": 20,
            "rounds": 30,
            "traffic_per_round": 25,
            "failure_round": 999,
            "failure_count": 0,
            "failure_mode": "random",
            "initial_energy": 30.0,
            "k": 2,
        },
        # Scenario 4: Scalability N=50, random failure
        {
            "id": "sc4_n50_random_fail_t15_r30",
            "name": "N=50 (Medium Scale), Random Failure (30 rounds, 15 pkts/rnd)",
            "nodes": 50,
            "rounds": 30,
            "traffic_per_round": 15,
            "failure_round": 10,
            "failure_count": 1,
            "failure_mode": "random",
            "initial_energy": 50.0,
            "k": 2,
        },
        # Scenario 5: Scalability N=50, articulation failure
        {
            "id": "sc5_n50_articulation_fail_t15_r30",
            "name": "N=50 (Medium Scale), Articulation Failure (30 rounds, 15 pkts/rnd)",
            "nodes": 50,
            "rounds": 30,
            "traffic_per_round": 15,
            "failure_round": 10,
            "failure_count": 1,
            "failure_mode": "articulation",
            "initial_energy": 50.0,
            "k": 2,
        },
        # Scenario 6: Scalability N=100 (Large scale mesh), random failure
        {
            "id": "sc6_n100_random_fail_t15_r30",
            "name": "N=100 (Large Scale), Random Failure (30 rounds, 15 pkts/rnd)",
            "nodes": 100,
            "rounds": 30,
            "traffic_per_round": 15,
            "failure_round": 10,
            "failure_count": 1,
            "failure_mode": "random",
            "initial_energy": 50.0,
            "k": 2,
        },
        # Scenario 7: Network lifetime horizon (80 rounds, battery exhaustion)
        {
            "id": "sc7_n20_lifetime_r80_t10",
            "name": "N=20, Extended Lifetime Horizon (80 rounds, E=20, 10 pkts/rnd)",
            "nodes": 20,
            "rounds": 80,
            "traffic_per_round": 10,
            "failure_round": 20,
            "failure_count": 1,
            "failure_mode": "random",
            "initial_energy": 20.0,
            "k": 2,
        },
    ]

    all_runs = []
    print(f"Starting execution of {len(scenarios)} scenarios across {len(seeds)} seeds and 3 algorithms...")

    metric_fields = [
        "packet_delivery_ratio",
        "energy_consumed",
        "routing_recomputations",
        "local_route_updates",
        "first_node_dead_round",
        "half_nodes_dead_round",
        "last_node_dead_round",
        "connected_round_fraction",
        "estimated_runtime_ms",
    ]

    total_runs_target = len(scenarios) * len(seeds) * len(algorithms)
    run_idx = 0

    for sc in scenarios:
        sc_id = sc["id"]
        sc_start = time.perf_counter()
        print(f"\n--- Scenario: {sc['name']} ({sc_id}) ---")
        base_cfg = {
            "nodes": sc["nodes"],
            "gateway": 0,
            "rounds": sc["rounds"],
            "k": sc["k"],
            "traffic_per_round": sc["traffic_per_round"],
            "failure_round": sc["failure_round"],
            "failure_count": sc["failure_count"],
            "failure_mode": sc["failure_mode"],
            "threshold": 25.0,
            "tx_cost": 0.65,
            "rx_cost": 0.18,
            "initial_energy": sc["initial_energy"],
        }

        for seed in seeds:
            cfg = dict(base_cfg)
            cfg["seed"] = seed
            for algo in algorithms:
                run_idx += 1
                res = run_simulation(cfg, algo)
                m = res["metrics"]
                failed_nodes = [e["node"] for e in res["events"] if e.get("type") == "node_failure"]
                run_record = {
                    "scenario_id": sc_id,
                    "seed": seed,
                    "algorithm": algo,
                    "failed_node_ids": failed_nodes,
                    **m,
                }
                all_runs.append(run_record)
        sc_elapsed = time.perf_counter() - sc_start
        print(f"Completed scenario {sc_id} ({len(seeds)*3} runs) in {sc_elapsed:.2f}s")

    # Aggregate summaries per scenario per algorithm
    summaries = []
    for sc in scenarios:
        sc_id = sc["id"]
        sc_runs = [r for r in all_runs if r["scenario_id"] == sc_id]
        for algo in algorithms:
            algo_runs = [r for r in sc_runs if r["algorithm"] == algo]
            summary_entry = {
                "scenario_id": sc_id,
                "scenario_name": sc["name"],
                "algorithm": algo,
                "runs": len(algo_runs),
            }
            for f in metric_fields:
                vals = []
                for r in algo_runs:
                    v = r.get(f)
                    if v is not None:
                        try:
                            fv = float(v)
                            if fv == fv and abs(fv) != float("inf"):
                                vals.append(fv)
                        except (ValueError, TypeError):
                            pass
                s_dict = compute_summary_stats(vals)
                for k, v in s_dict.items():
                    summary_entry[f"{f}_{k}"] = v
            summaries.append(summary_entry)

    # Compute paired comparisons per scenario
    paired_comparisons = compute_paired_stats(all_runs, algorithms, metric_fields)

    output_data = {
        "metadata": {
            "title": "Robustness, Scalability, and Statistical Validation Multi-Scenario Benchmark",
            "date": "2026-10-11",
            "total_runs": len(all_runs),
            "total_scenarios": len(scenarios),
            "seeds_per_scenario": len(seeds),
            "algorithms": algorithms,
            "wall_clock_seconds": round(time.perf_counter() - start_total, 2),
        },
        "scenarios": scenarios,
        "summaries": summaries,
        "paired_comparisons": paired_comparisons,
        "runs": all_runs,
    }

    out_file = "research_results/robustness_scalability.json"
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\nAll {len(all_runs)} runs completed in {time.perf_counter() - start_total:.2f}s!")
    print(f"Results saved to {out_file}")


if __name__ == "__main__":
    main()
