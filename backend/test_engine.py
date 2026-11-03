import unittest
from engine import build_network, run_simulation
import networkx as nx

class MeshEngineTests(unittest.TestCase):
    def test_network_connected(self):
        g = build_network(20, 3, 2)
        self.assertTrue(nx.is_connected(g))

    def test_reproducible_metrics(self):
        cfg = {"nodes": 12, "rounds": 8, "seed": 22, "failure_round": 4, "traffic_per_round": 4}
        a = run_simulation(cfg, "incremental")
        b = run_simulation(cfg, "incremental")
        self.assertEqual(a["metrics"]["packets_sent"], b["metrics"]["packets_sent"])
        self.assertEqual(a["metrics"]["packets_delivered"], b["metrics"]["packets_delivered"])

    def test_metrics_ranges(self):
        r = run_simulation({"nodes": 10, "rounds": 5, "traffic_per_round": 3}, "energy")
        self.assertGreaterEqual(r["metrics"]["packet_delivery_ratio"], 0)
        self.assertLessEqual(r["metrics"]["packet_delivery_ratio"], 1)

if __name__ == "__main__":
    unittest.main()
