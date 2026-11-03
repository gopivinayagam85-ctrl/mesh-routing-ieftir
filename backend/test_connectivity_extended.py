import unittest
import networkx as nx
from engine import measure_connectivity, compute_path, Config, run_simulation

class TestConnectivityExtended(unittest.TestCase):
    def test_k_edge_connectivity_three_met(self):
        """A complete graph of 4 nodes has edge connectivity 3, meeting k=3."""
        graph = nx.complete_graph(4)
        result = measure_connectivity(graph, 3)
        self.assertTrue(result["connected"])
        self.assertEqual(result["edge_connectivity"], 3)
        self.assertTrue(result["connectivity_target_met"])

    def test_node_failure_partition(self):
        """Removing a middle node from a path graph creates two components, edge connectivity 0."""
        G = nx.path_graph(4)  # nodes 0-1-2-3
        G.remove_node(1)  # partition: {0} and {2,3}
        result = measure_connectivity(G, 2)
        self.assertFalse(result["connected"])
        self.assertEqual(result["edge_connectivity"], 0)
        self.assertFalse(result["connectivity_target_met"])

    def test_unreachable_destination_after_node_failure(self):
        """After removing a node, compute_path should return None for sources separated from gateway."""
        G = nx.path_graph(4)  # 0-1-2-3, gateway = 0
        G.remove_node(2)  # now 0-1 and 3 isolated
        cfg = Config(nodes=4, gateway=0, k=2)
        energies = {n: cfg.initial_energy for n in G.nodes}
        depletion = {n: 0.0 for n in G.nodes}
        path = compute_path(G, 3, cfg.gateway, "shortest", energies, depletion, cfg)
        self.assertIsNone(path)
        path1 = compute_path(G, 1, cfg.gateway, "shortest", energies, depletion, cfg)
        self.assertIsNotNone(path1)
        self.assertEqual(path1, [1, 0])

    def test_connectivity_metrics_after_failure_via_simulation(self):
        """Run a small simulation with a deterministic node failure that partitions the graph and verify metrics."""
        cfg = {
            "nodes": 5,
            "gateway": 0,
            "rounds": 3,
            "seed": 42,
            "k": 2,
            "failure_round": 1,
            "failure_count": 1,
            "gateway_failure_round": None,
        }
        # custom build to guarantee a path topology
        def custom_build_network(n, seed, k):
            G = nx.path_graph(n)
            pos = {i: (i, 0) for i in range(n)}
            nx.set_node_attributes(G, pos, "pos")
            return G
        # monkey patch build_network used by run_simulation
        import builtins
        original_build = getattr(builtins, 'build_network', None)
        try:
            builtins.build_network = custom_build_network
            result = run_simulation(cfg, algorithm="incremental")
        finally:
            if original_build is not None:
                builtins.build_network = original_build
            else:
                del builtins.build_network
        history = result["history"]
        round1 = next(item for item in history if item["round"] == 1)
        self.assertFalse(round1["connected"])
        self.assertEqual(round1["edge_connectivity"], 0)
        self.assertFalse(round1["connected"] and round1["edge_connectivity"] >= cfg["k"])

if __name__ == "__main__":
    unittest.main()
