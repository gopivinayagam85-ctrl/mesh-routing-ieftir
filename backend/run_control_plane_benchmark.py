"""Multi-seed benchmark and sensitivity analysis for routing control-plane overhead.

Executes across:
- Algorithms: shortest, energy, incremental
- Seeds: 1..20
- Network sizes: N=20 (Scenario 1 & 2) and N=50 (Scenario 4)
- Control Packet Sensitivity:
  Baseline: 32 bytes ctrl packet, 16 bytes notification, factor=0.5
  Lightweight: 16 bytes ctrl packet, 8 bytes notification, factor=0.3
  Heavy/Full: 64 bytes ctrl packet, 32 bytes notification, factor=0.8
"""
import json
import math
import os
import sys
import time
import numpy as np

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from engine import run_simulation


def compute_paired_diff(arr_a, arr_b):
    diffs = np.array(arr_a, dtype=float) - np.array(arr_b, dtype=float)
    n = len(diffs)
    mean = float(np.mean(diffs))
    std = float(np.std(diffs, ddof=1)) if n > 1 else 0.0
    se = std / np.sqrt(n) if n > 1 else 0.0
    t_stat = mean / se if se > 1e-12 else 0.0
    # 2-sided normal/t approximation
    p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t_stat) / math.sqrt(2.0)))) if se > 1e-12 else (1.0 if mean == 0.0 else 0.0)
    ci_low = mean - 2.093 * se
    ci_high = mean + 2.093 * se
    return {
        "mean_diff": round(mean, 4),
        "std_diff": round(std, 4),
        "ci95_low": round(ci_low, 4),
        "ci95_high": round(ci_high, 4),
        "t_stat": round(t_stat, 4),
        "p_value": round(p_val, 6),
    }


def run_benchmark():
    t_start = time.perf_counter()
    seeds = list(range(1, 21))
    algorithms = ["shortest", "energy", "incremental"]

    scenarios = [
        {
            "id": "cp_n20_random_fail_t10_r30",
            "name": "N=20, Random Failure (30 rounds, 10 pkts/rnd)",
            "nodes": 20,
            "rounds": 30,
            "traffic_per_round": 10,
            "failure_round": 10,
            "failure_count": 1,
            "failure_mode": "random",
            "initial_energy": 50.0,
            "k": 2,
        },
        {
            "id": "cp_n20_articulation_fail_t10_r30",
            "name": "N=20, Articulation Cut Failure (30 rounds, 10 pkts/rnd)",
            "nodes": 20,
            "rounds": 30,
            "traffic_per_round": 10,
            "failure_round": 10,
            "failure_count": 1,
            "failure_mode": "articulation",
            "initial_energy": 50.0,
            "k": 2,
        },
        {
            "id": "cp_n50_random_fail_t15_r30",
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
    ]

    all_results = []
    print(f"Executing Control-Plane Overhead Benchmark across {len(scenarios)} scenarios, 20 seeds, 3 algorithms...")

    for sc in scenarios:
        sc_id = sc["id"]
        for seed in seeds:
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
                "seed": seed,
            }
            for algo in algorithms:
                res = run_simulation(base_cfg, algo)
                m = res["metrics"]
                all_results.append({
                    "scenario_id": sc_id,
                    "seed": seed,
                    "algorithm": algo,
                    "routing_recomputations": m["routing_recomputations"],
                    "local_route_updates": m["local_route_updates"],
                    "ctrl_messages_sent": m["ctrl_messages_sent"],
                    "ctrl_bytes_sent": m["ctrl_bytes_sent"],
                    "ctrl_energy_consumed": m["ctrl_energy_consumed"],
                    "data_energy_consumed": m["data_energy_consumed"],
                    "packet_delivery_ratio": m["packet_delivery_ratio"],
                })

    # Summary by scenario and algorithm
    summaries = []
    for sc in scenarios:
        sc_id = sc["id"]
        sc_runs = [r for r in all_results if r["scenario_id"] == sc_id]
        for algo in algorithms:
            algo_runs = [r for r in sc_runs if r["algorithm"] == algo]
            summaries.append({
                "scenario_id": sc_id,
                "algorithm": algo,
                "recomputations_mean": float(np.mean([r["routing_recomputations"] for r in algo_runs])),
                "recomputations_std": float(np.std([r["routing_recomputations"] for r in algo_runs], ddof=1)),
                "ctrl_messages_mean": float(np.mean([r["ctrl_messages_sent"] for r in algo_runs])),
                "ctrl_messages_std": float(np.std([r["ctrl_messages_sent"] for r in algo_runs], ddof=1)),
                "ctrl_bytes_mean": float(np.mean([r["ctrl_bytes_sent"] for r in algo_runs])),
                "ctrl_bytes_std": float(np.std([r["ctrl_bytes_sent"] for r in algo_runs], ddof=1)),
                "ctrl_energy_mean": float(np.mean([r["ctrl_energy_consumed"] for r in algo_runs])),
                "ctrl_energy_std": float(np.std([r["ctrl_energy_consumed"] for r in algo_runs], ddof=1)),
                "data_energy_mean": float(np.mean([r["data_energy_consumed"] for r in algo_runs])),
                "data_energy_std": float(np.std([r["data_energy_consumed"] for r in algo_runs], ddof=1)),
                "pdr_mean": float(np.mean([r["packet_delivery_ratio"] for r in algo_runs])),
                "pdr_std": float(np.std([r["packet_delivery_ratio"] for r in algo_runs], ddof=1)),
            })

    # Paired comparisons (energy vs incremental)
    paired_comparisons = []
    for sc in scenarios:
        sc_id = sc["id"]
        sc_runs = [r for r in all_results if r["scenario_id"] == sc_id]
        grouped = {r["seed"]: {} for r in sc_runs}
        for r in sc_runs:
            grouped[r["seed"]][r["algorithm"]] = r

        seeds_sorted = sorted(grouped.keys())
        en_runs = [grouped[s]["energy"] for s in seeds_sorted]
        inc_runs = [grouped[s]["incremental"] for s in seeds_sorted]

        paired_comparisons.append({
            "scenario_id": sc_id,
            "recomputations": compute_paired_diff(
                [r["routing_recomputations"] for r in en_runs],
                [r["routing_recomputations"] for r in inc_runs]
            ),
            "ctrl_messages": compute_paired_diff(
                [r["ctrl_messages_sent"] for r in en_runs],
                [r["ctrl_messages_sent"] for r in inc_runs]
            ),
            "ctrl_bytes": compute_paired_diff(
                [r["ctrl_bytes_sent"] for r in en_runs],
                [r["ctrl_bytes_sent"] for r in inc_runs]
            ),
            "ctrl_energy": compute_paired_diff(
                [r["ctrl_energy_consumed"] for r in en_runs],
                [r["ctrl_energy_consumed"] for r in inc_runs]
            ),
            "data_energy": compute_paired_diff(
                [r["data_energy_consumed"] for r in en_runs],
                [r["data_energy_consumed"] for r in inc_runs]
            ),
            "pdr": compute_paired_diff(
                [r["packet_delivery_ratio"] for r in en_runs],
                [r["packet_delivery_ratio"] for r in inc_runs]
            ),
        })

    # Sensitivity Analysis across control message profiles
    sensitivity_profiles = [
        {"profile": "Lightweight (16B / 8B / 0.3x)", "pkt_bytes": 16, "notif_bytes": 8, "cost_factor": 0.3},
        {"profile": "Standard / Default (32B / 16B / 0.5x)", "pkt_bytes": 32, "notif_bytes": 16, "cost_factor": 0.5},
        {"profile": "Heavy / Full Frame (64B / 32B / 0.8x)", "pkt_bytes": 64, "notif_bytes": 32, "cost_factor": 0.8},
    ]

    sensitivity_results = []
    # Test on Scenario 1 across 10 seeds
    sc_test = scenarios[0]
    for prof in sensitivity_profiles:
        p_name = prof["profile"]
        en_msgs, inc_msgs = [], []
        en_bytes, inc_bytes = [], []
        en_energy, inc_energy = [], []
        for seed in range(1, 11):
            base_cfg = {
                "nodes": sc_test["nodes"],
                "gateway": 0,
                "rounds": sc_test["rounds"],
                "k": sc_test["k"],
                "traffic_per_round": sc_test["traffic_per_round"],
                "failure_round": sc_test["failure_round"],
                "failure_count": sc_test["failure_count"],
                "failure_mode": sc_test["failure_mode"],
                "threshold": 25.0,
                "initial_energy": sc_test["initial_energy"],
                "seed": seed,
                "ctrl_packet_bytes": prof["pkt_bytes"],
                "ctrl_notification_bytes": prof["notif_bytes"],
                "ctrl_tx_cost_factor": prof["cost_factor"],
            }
            r_en = run_simulation(base_cfg, "energy")["metrics"]
            r_inc = run_simulation(base_cfg, "incremental")["metrics"]
            en_msgs.append(r_en["ctrl_messages_sent"])
            inc_msgs.append(r_inc["ctrl_messages_sent"])
            en_bytes.append(r_en["ctrl_bytes_sent"])
            inc_bytes.append(r_inc["ctrl_bytes_sent"])
            en_energy.append(r_en["ctrl_energy_consumed"])
            inc_energy.append(r_inc["ctrl_energy_consumed"])

        msg_red_pct = (np.mean(en_msgs) - np.mean(inc_msgs)) / np.mean(en_msgs) * 100.0
        byte_red_pct = (np.mean(en_bytes) - np.mean(inc_bytes)) / np.mean(en_bytes) * 100.0
        energy_red_pct = (np.mean(en_energy) - np.mean(inc_energy)) / np.mean(en_energy) * 100.0

        sensitivity_results.append({
            "profile": p_name,
            "ctrl_packet_bytes": prof["pkt_bytes"],
            "ctrl_notification_bytes": prof["notif_bytes"],
            "cost_factor": prof["cost_factor"],
            "energy_mean_ctrl_bytes": float(np.mean(en_bytes)),
            "incremental_mean_ctrl_bytes": float(np.mean(inc_bytes)),
            "byte_reduction_pct": round(byte_red_pct, 2),
            "energy_mean_ctrl_energy": float(np.mean(en_energy)),
            "incremental_mean_ctrl_energy": float(np.mean(inc_energy)),
            "energy_reduction_pct": round(energy_red_pct, 2),
            "msg_reduction_pct": round(msg_red_pct, 2),
        })

    elapsed = time.perf_counter() - t_start

    output_payload = {
        "metadata": {
            "title": "Control-Plane Overhead Model & Statistical Validation",
            "date": "2026-10-11",
            "total_runs": len(all_results),
            "wall_clock_seconds": round(elapsed, 2),
            "scenarios_evaluated": len(scenarios),
            "seeds": seeds,
            "algorithms": algorithms,
        },
        "scenarios": scenarios,
        "summaries": summaries,
        "paired_comparisons": paired_comparisons,
        "sensitivity_analysis": sensitivity_results,
        "runs": all_results,
    }

    out_dir = "research_results/control_plane_audit"
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "control_plane_benchmark.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)

    print(f"Benchmark finished in {elapsed:.2f}s. Results written to {out_file}")
    return output_payload


if __name__ == "__main__":
    run_benchmark()
