import os
import sys
import unittest

# Ensure the backend package is on the import path
backend_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(backend_dir)

from fastapi.testclient import TestClient
from main import app

class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertIn("service", data)

    def test_simulate_shortest(self):
        payload = {
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
        resp = self.client.post("/api/simulate?algorithm=shortest", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("algorithm"), "shortest")
        self.assertIn("metrics", data)

    def test_simulate_energy_and_global(self):
        payload = {
            "nodes": 5,
            "gateway": 0,
            "rounds": 1,
            "seed": 2,
            "k": 2,
            "traffic_per_round": 1,
            "failure_round": 0,
            "failure_count": 0,
            "threshold": 25.0,
            "tx_cost": 0.65,
            "rx_cost": 0.18,
            "initial_energy": 10.0,
        }
        # energy algorithm
        resp_e = self.client.post("/api/simulate?algorithm=energy", json=payload)
        self.assertEqual(resp_e.status_code, 200)
        self.assertEqual(resp_e.json().get("algorithm"), "energy")
        # global_energy maps to energy
        resp_g = self.client.post("/api/simulate?algorithm=global_energy", json=payload)
        self.assertEqual(resp_g.status_code, 200)
        self.assertEqual(resp_g.json().get("algorithm"), "energy")

    def test_simulate_invalid_algorithm(self):
        payload = {
            "nodes": 5,
            "gateway": 0,
            "rounds": 1,
            "seed": 3,
            "k": 2,
            "traffic_per_round": 1,
            "failure_round": 0,
            "failure_count": 0,
            "threshold": 25.0,
            "tx_cost": 0.65,
            "rx_cost": 0.18,
            "initial_energy": 10.0,
        }
        resp = self.client.post("/api/simulate?algorithm=unknown", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("unsupported algorithm", resp.json().get("detail", ""))

    def test_simulate_incremental(self):
        payload = {
            "nodes": 5,
            "gateway": 0,
            "rounds": 1,
            "seed": 5,
            "k": 2,
            "traffic_per_round": 1,
            "failure_round": 0,
            "failure_count": 0,
            "threshold": 25.0,
            "tx_cost": 0.65,
            "rx_cost": 0.18,
            "initial_energy": 10.0,
        }
        resp = self.client.post("/api/simulate?algorithm=incremental", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("algorithm"), "incremental")
        self.assertIn("metrics", data)
        self.assertIn("history", data)
        self.assertIn("network", data)

    def test_simulate_default_algorithm(self):
        payload = {
            "nodes": 5,
            "gateway": 0,
            "rounds": 1,
            "seed": 6,
            "k": 2,
            "traffic_per_round": 1,
            "failure_round": 0,
            "failure_count": 0,
            "threshold": 25.0,
            "tx_cost": 0.65,
            "rx_cost": 0.18,
            "initial_energy": 10.0,
        }
        # Omitting algorithm query parameter defaults to incremental
        resp = self.client.post("/api/simulate", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("algorithm"), "incremental")

    def test_simulate_invalid_gateway(self):
        payload = {
            "nodes": 5,
            "gateway": 5,  # gateway >= nodes is invalid
            "rounds": 1,
            "seed": 7,
            "k": 2,
            "traffic_per_round": 1,
            "failure_round": 0,
            "failure_count": 0,
            "threshold": 25.0,
            "tx_cost": 0.65,
            "rx_cost": 0.18,
            "initial_energy": 10.0,
        }
        resp = self.client.post("/api/simulate?algorithm=incremental", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("gateway must be less than node count", resp.json().get("detail", ""))

    def test_simulate_invalid_parameter_ranges(self):
        # nodes < 5
        resp_nodes = self.client.post("/api/simulate", json={"nodes": 3, "gateway": 0, "rounds": 1})
        self.assertEqual(resp_nodes.status_code, 422)

        # rounds < 1
        resp_rounds = self.client.post("/api/simulate", json={"nodes": 10, "gateway": 0, "rounds": 0})
        self.assertEqual(resp_rounds.status_code, 422)

        # k > 4
        resp_k = self.client.post("/api/simulate", json={"nodes": 10, "gateway": 0, "rounds": 1, "k": 5})
        self.assertEqual(resp_k.status_code, 422)

    def test_compare_endpoint(self):
        payload = {
            "nodes": 5,
            "gateway": 0,
            "rounds": 1,
            "seed": 4,
            "k": 2,
            "traffic_per_round": 1,
            "failure_round": 0,
            "failure_count": 0,
            "threshold": 25.0,
            "tx_cost": 0.65,
            "rx_cost": 0.18,
            "initial_energy": 10.0,
            "seeds": 2,
        }
        resp = self.client.post("/api/compare", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("summaries", data)
        self.assertEqual(len(data["summaries"]), 3)

    def test_compare_invalid_gateway_and_seeds(self):
        # Invalid gateway
        payload_gw = {
            "nodes": 5,
            "gateway": 5,
            "rounds": 1,
            "seeds": 2,
        }
        resp_gw = self.client.post("/api/compare", json=payload_gw)
        self.assertEqual(resp_gw.status_code, 400)
        self.assertIn("gateway must be less than node count", resp_gw.json().get("detail", ""))

        # Invalid seeds (> 30)
        payload_seeds = {
            "nodes": 5,
            "gateway": 0,
            "rounds": 1,
            "seeds": 50,
        }
        resp_seeds = self.client.post("/api/compare", json=payload_seeds)
        self.assertEqual(resp_seeds.status_code, 422)

    def test_cors_headers(self):
        resp = self.client.options(
            "/api/simulate",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("access-control-allow-origin"), "http://localhost:5173")

    def test_simulate_node_failure_route_recovery(self):
        payload = {
            "nodes": 20,
            "gateway": 0,
            "rounds": 15,
            "seed": 42,
            "k": 2,
            "traffic_per_round": 5,
            "failure_round": 5,
            "failure_count": 2,
            "threshold": 25.0,
            "tx_cost": 0.65,
            "rx_cost": 0.18,
            "initial_energy": 100.0,
        }
        for algo in ["incremental", "energy", "shortest"]:
            resp = self.client.post(f"/api/simulate?algorithm={algo}", json=payload)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            metrics = data.get("metrics", {})
            self.assertIn("routing_recomputations", metrics)
            self.assertIn("packet_delivery_ratio", metrics)
            failure_events = [e for e in data.get("events", []) if e.get("type") == "node_failure"]
            self.assertEqual(len(failure_events), 2)
            if algo == "incremental":
                self.assertGreater(metrics.get("local_route_updates", 0), 0)

    def test_simulate_partition_unreachable(self):
        payload = {
            "nodes": 8,
            "gateway": 0,
            "rounds": 10,
            "seed": 11,
            "k": 1,
            "traffic_per_round": 5,
            "failure_round": 2,
            "failure_count": 5,
            "threshold": 25.0,
            "tx_cost": 0.65,
            "rx_cost": 0.18,
            "initial_energy": 50.0,
        }
        resp = self.client.post("/api/simulate?algorithm=incremental", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        metrics = data.get("metrics", {})
        self.assertFalse(metrics.get("final_connected"))

    def test_reroute_analysis_success(self):
        payload = {
            "nodes": 12,
            "gateway": 0,
            "rounds": 10,
            "seed": 42,
            "k": 2,
            "traffic_per_round": 5,
            "failure_round": 2,
            "failure_count": 1,
            "threshold": 25.0,
            "tx_cost": 0.65,
            "rx_cost": 0.18,
            "initial_energy": 100.0,
        }
        resp = self.client.post("/api/reroute", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("before", data)
        self.assertIn("after", data)
        self.assertIn("source", data)
        self.assertIn("failed_node", data)
        self.assertIn("route_repair_time_ms", data)
        self.assertIn("routing_updates_count", data)
        self.assertIn("initial_route", data)
        self.assertIn("replacement_route", data)
        self.assertIn("available_sources", data)

        # Before snapshot should have failed_node as None and no dead nodes
        self.assertIsNone(data["before"]["failed_node"])
        before_dead = [n for n in data["before"]["network"]["nodes"] if n["dead"]]
        self.assertEqual(len(before_dead), 0)

        # After snapshot should record the target failed node
        self.assertEqual(data["after"]["failed_node"], data["failed_node"])
        after_dead = [n for n in data["after"]["network"]["nodes"] if n["dead"]]
        self.assertEqual(len(after_dead), 1)
        self.assertEqual(after_dead[0]["id"], data["failed_node"])

        # Positions must be identical in before and after snapshots
        before_pos = {n["id"]: (n["x"], n["y"]) for n in data["before"]["network"]["nodes"]}
        after_pos = {n["id"]: (n["x"], n["y"]) for n in data["after"]["network"]["nodes"]}
        self.assertEqual(before_pos, after_pos)

    def test_reroute_analysis_no_replacement_path(self):
        # Line topology 0 - 1 - 2. If node 1 fails, node 2 has no replacement path
        import networkx as nx
        def custom_path_topology(n, seed, k):
            G = nx.path_graph(n)
            pos = {i: (float(i) * 0.2, 0.5) for i in range(n)}
            nx.set_node_attributes(G, pos, "pos")
            for u, v in G.edges:
                G[u][v]["distance"] = 1.0
            return G

        payload = {
            "nodes": 5,
            "gateway": 0,
            "rounds": 10,
            "seed": 1,
            "k": 1,
            "source_node": 2,
            "failed_node_id": 1,
            "custom_build": custom_path_topology,
        }
        # Run via direct function to test custom_build injection and then API
        from engine import rerun_reroute_analysis
        data = rerun_reroute_analysis(payload, source_node=2, failed_node_id=1)
        self.assertEqual(data["repair_status"], "no_replacement_path")
        self.assertFalse(data["repair_success"])
        self.assertIsNone(data["replacement_route"])
        self.assertEqual(data["replacement_hop_count"], 0)
        self.assertFalse(data["final_connectivity"])

    def test_reroute_analysis_specific_intermediate_node(self):
        payload = {
            "nodes": 15,
            "gateway": 0,
            "rounds": 10,
            "seed": 7,
            "k": 2,
            "traffic_per_round": 5,
            "failure_round": 2,
            "failure_count": 1,
            "threshold": 25.0,
            "tx_cost": 0.65,
            "rx_cost": 0.18,
            "initial_energy": 100.0,
        }
        # First query to get a multi-hop route
        resp1 = self.client.post("/api/reroute", json=payload)
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()
        initial_route = data1["initial_route"]
        if initial_route and len(initial_route) > 2:
            intermediate = initial_route[1]
            src = data1["source"]
            payload["source_node"] = src
            payload["failed_node_id"] = intermediate
            resp2 = self.client.post("/api/reroute", json=payload)
            self.assertEqual(resp2.status_code, 200)
            data2 = resp2.json()
            self.assertEqual(data2["failed_node"], intermediate)
            self.assertEqual(data2["source"], src)
            if data2["repair_success"]:
                self.assertNotIn(intermediate, data2["replacement_route"])

if __name__ == "__main__":
    unittest.main()
