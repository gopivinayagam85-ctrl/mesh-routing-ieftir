# backend/tests/test_compare_stats_extended.py
"""Extended deterministic tests for compare_algorithms.
Covers invalid metric handling and paired analysis statistics.
"""
import pytest

from backend.engine import compare_algorithms


@pytest.fixture(autouse=True)
def patch_run_simulation(monkeypatch):
    """Patch ``run_simulation`` to emit a mix of valid and invalid metric values.
    The values are deterministic based on the seed and algorithm name.
    """

    def deterministic_run_simulation(cfg: dict, algorithm: str):
        base = cfg.get("seed", 0)
        # Introduce different invalid cases per algorithm.
        metrics = {
            "packet_delivery_ratio": None if algorithm == "shortest" else (base % 5 + 1) / 5,
            "energy_consumed": float('nan') if algorithm == "energy" else float(base * 2 + len(algorithm)),
            "first_node_dead_round": float('inf') if algorithm == "incremental" else (base % 3) + 1,
            "half_nodes_dead_round": "not_a_number",
            "routing_recomputations": base,
            "local_route_updates": base,
            "connected_round_fraction": 1.0,
            "estimated_runtime_ms": 100.0 + base,
        }
        return {"metrics": metrics}

    monkeypatch.setattr("backend.engine.run_simulation", deterministic_run_simulation)
    yield


def test_invalid_observations_and_statistics():
    config = {
        "nodes": 5,
        "gateway": 0,
        "rounds": 1,
        "seed": 1,
        "k": 2,
        "traffic_per_round": 1,
        "failure_round": 0,
        "failure_count": 0,
        "threshold": 25.0,
        "tx_cost": 0.65,
        "rx_cost": 0.18,
        "initial_energy": 10.0,
    }
    seeds = 2
    result = compare_algorithms(config, seeds)

    # Validate that invalid observations are excluded from statistics.
    shortest = next(s for s in result["summaries"] if s["algorithm"] == "shortest")
    assert shortest["packet_delivery_ratio_count"] == 0
    energy = next(s for s in result["summaries"] if s["algorithm"] == "energy")
    assert energy["energy_consumed_count"] == 0
    inc = next(s for s in result["summaries"] if s["algorithm"] == "incremental")
    assert inc["first_node_dead_round_count"] == 0
    for s in result["summaries"]:
        assert s["half_nodes_dead_round_count"] == 0

    # Paired analysis should be present and correctly computed.
    paired = result.get("paired")
    assert paired is not None
    diff = next(p for p in paired if p["pair"] == "shortest_vs_energy")
    assert diff["routing_recomputations_diff_count"] == seeds
    assert diff["routing_recomputations_diff_mean"] == pytest.approx(0.0, rel=1e-6)
    assert diff["routing_recomputations_diff_std"] == pytest.approx(0.0, rel=1e-6)
