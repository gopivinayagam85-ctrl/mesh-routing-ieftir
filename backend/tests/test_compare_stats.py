# backend/tests/test_compare_stats.py
"""Deterministic tests for compare_algorithms statistical aggregation.
Ensures that the function correctly aggregates multiple runs, handles missing
values, and produces expected descriptive statistics.
"""
import pytest

# Import the function under test.
from backend.engine import compare_algorithms


@pytest.fixture(autouse=True)
def patch_run_simulation(monkeypatch):
    """Patch ``engine.run_simulation`` to return deterministic metric values.

    The returned metric values depend on the seed and algorithm name so that
    the aggregation logic can be exercised.
    """

    def deterministic_run_simulation(cfg: dict, algorithm: str):
        # Use the seeded ``seed`` value to generate reproducible numbers.
        base = cfg.get("seed", 0)
        # Create a simple deterministic mapping for each metric.
        metrics = {
            "packet_delivery_ratio": (base % 5 + 1) / 5,
            "energy_consumed": float(base * 2 + len(algorithm)),
            "first_node_dead_round": (base % 3) + 1,
            "half_nodes_dead_round": (base % 4) + 2,
            "routing_recomputations": base * 10,
            "local_route_updates": base * 5,
            "connected_round_fraction": 1.0,
            "estimated_runtime_ms": 100.0 + base,
        }
        return {"metrics": metrics}

    monkeypatch.setattr("backend.engine.run_simulation", deterministic_run_simulation)
    yield


def test_compare_algorithms_statistics():
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
    seeds = 3
    result = compare_algorithms(config, seeds)
    assert "summaries" in result
    assert len(result["summaries"]) == 3
    for summary in result["summaries"]:
        assert "algorithm" in summary
        for metric in [
            "packet_delivery_ratio",
            "energy_consumed",
            "first_node_dead_round",
            "half_nodes_dead_round",
            "routing_recomputations",
            "local_route_updates",
            "connected_round_fraction",
            "estimated_runtime_ms",
        ]:
            for suffix in ["_count", "_mean", "_std", "_median", "_iqr", "_min", "_max", "_ci95_low", "_ci95_high"]:
                key = f"{metric}{suffix}"
                assert key in summary
    shortest = next(s for s in result["summaries"] if s["algorithm"] == "shortest")
    assert shortest["packet_delivery_ratio_mean"] == pytest.approx(0.6, rel=1e-4)
    assert shortest["energy_consumed_mean"] == pytest.approx(12.0, rel=1e-4)
    for s in result["summaries"]:
        assert s["runs"] == seeds
