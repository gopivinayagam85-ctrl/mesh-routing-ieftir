import unittest
import networkx as nx
from engine import measure_connectivity

class TestConnectivityMetrics(unittest.TestCase):
    def test_connected_graph_edge_connectivity_one_does_not_meet_k_two(self):
        graph = nx.path_graph(4)
        result = measure_connectivity(graph, 2)
        self.assertTrue(result["connected"])
        self.assertEqual(result["edge_connectivity"], 1)
        self.assertFalse(result["connectivity_target_met"])

    def test_cycle_meets_k_two(self):
        graph = nx.cycle_graph(4)
        result = measure_connectivity(graph, 2)
        self.assertTrue(result["connected"])
        self.assertEqual(result["edge_connectivity"], 2)
        self.assertTrue(result["connectivity_target_met"])

    def test_disconnected_graph_does_not_meet_target(self):
        graph = nx.Graph([(0, 1), (2, 3)])
        result = measure_connectivity(graph, 2)
        self.assertFalse(result["connected"])
        self.assertEqual(result["edge_connectivity"], 0)
        self.assertFalse(result["connectivity_target_met"])

    def test_empty_graph_is_handled(self):
        result = measure_connectivity(nx.Graph(), 1)
        self.assertFalse(result["connected"])
        self.assertEqual(result["edge_connectivity"], 0)
        self.assertFalse(result["connectivity_target_met"])

if __name__ == "__main__":
    unittest.main()
