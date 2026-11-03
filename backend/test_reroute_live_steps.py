"""Regression tests for the live failure-injection -> IEFT-IR repair flow."""
from fastapi.testclient import TestClient

from engine import rerun_reroute_analysis
from main import app


CONFIG = {
    "nodes": 28,
    "gateway": 0,
    "rounds": 80,
    "seed": 7,
    "k": 2,
    "traffic_per_round": 18,
    "failure_round": 25,
    "failure_count": 1,
    "threshold": 25,
    "tx_cost": 0.65,
    "rx_cost": 0.18,
    "initial_energy": 100,
    "use_weighted_route": False,
    "energy_weight": 1.0,
    "depletion_weight": 1.0,
    "redundancy_weight": 1.0,
    "rigorous_k": False,
}


def _route_and_failure():
    baseline = rerun_reroute_analysis(CONFIG)
    assert baseline["initial_route"] and len(baseline["initial_route"]) > 2
    return baseline["source"], baseline["initial_route"][1]


def test_failure_injection_returns_failed_topology_without_repair():
    source, failed = _route_and_failure()
    result = rerun_reroute_analysis(
        CONFIG, source_node=source, failed_node_id=failed, repair=False
    )

    assert result["repair_performed"] is False
    assert result["repair_status"] == "failure_injected"
    assert result["replacement_route"] is None
    assert result["after"]["network"]["nodes"][failed]["dead"] is True
    assert all(
        edge["source"] != failed and edge["target"] != failed
        for edge in result["after"]["network"]["active_edges"]
    )
    assert result["route_recomputations"] == 0


def test_ieftir_repair_returns_real_route_avoiding_failed_node():
    source, failed = _route_and_failure()
    result = rerun_reroute_analysis(
        CONFIG, source_node=source, failed_node_id=failed, repair=True
    )

    assert result["repair_performed"] is True
    if result["repair_success"]:
        assert result["replacement_route"][0] == source
        assert result["replacement_route"][-1] == CONFIG["gateway"]
        assert failed not in result["replacement_route"]
    else:
        assert result["replacement_route"] is None


def test_api_exposes_separate_failure_and_repair_steps():
    client = TestClient(app)
    source, failed = _route_and_failure()
    response = client.post(
        "/api/reroute",
        json={**CONFIG, "source_node": source, "failed_node_id": failed, "repair": False},
    )
    assert response.status_code == 200
    assert response.json()["repair_status"] == "failure_injected"

    repaired = client.post(
        "/api/reroute",
        json={**CONFIG, "source_node": source, "failed_node_id": failed, "repair": True},
    )
    assert repaired.status_code == 200
    assert repaired.json()["repair_performed"] is True
