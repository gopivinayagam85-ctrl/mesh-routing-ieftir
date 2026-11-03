import unittest
import networkx as nx
from simulation.routing import shortest_path, energy_aware_path, global_energy_routing
from simulation.models import NetworkConfig, ValidationError
from engine import Config

class TestRouting(unittest.TestCase):
    def setUp(self):
        # Simple line graph 0-1-2-3, gateway at node 3
        self.cfg = NetworkConfig(nodes=4, gateway=3, tx_range=1.0, seed=0, tx_cost=1.0, rx_cost=0.5, initial_energy=10.0)
        self.graph = nx.path_graph(4)
        for nid in self.graph.nodes:
            self.graph.nodes[nid]["pos"] = (0.0, 0.0)
            # placeholder model; not needed for routing tests
            self.graph.nodes[nid]["model"] = None
        self.energies = {i: 10.0 for i in range(4)}
        self.depletion = {i: 0.0 for i in range(4)}
        self.cfg_obj = Config()

    def test_shortest_path_basic(self):
        path = shortest_path(self.graph, source=0, gateway=3, energies={}, depletion={}, cfg=self.cfg_obj, dead=set())
        self.assertEqual(path, [0, 1, 2, 3])

    def test_shortest_path_dead_node(self):
        path = shortest_path(self.graph, source=0, gateway=3, energies={}, depletion={}, cfg=self.cfg_obj, dead={2})
        self.assertIsNone(path)

    def test_energy_aware_path_basic(self):
        path = energy_aware_path(self.graph, source=0, gateway=3, energies=self.energies, depletion=self.depletion, cfg=self.cfg_obj, dead=set())
        self.assertEqual(path, [0, 1, 2, 3])

    def test_energy_aware_path_dead_node(self):
        path = energy_aware_path(self.graph, source=0, gateway=3, energies=self.energies, depletion=self.depletion, cfg=self.cfg_obj, dead={1})
        self.assertIsNone(path)

    def test_unreachable_destination(self):
        # Remove edge to isolate gateway
        self.graph.remove_edge(2, 3)
        path = shortest_path(self.graph, source=0, gateway=3, energies={}, depletion={}, cfg=self.cfg_obj, dead=set())
        self.assertIsNone(path)
        # restore for next check
        self.graph.add_edge(2, 3)
        path = energy_aware_path(self.graph, source=0, gateway=3, energies=self.energies, depletion=self.depletion, cfg=self.cfg_obj, dead=set())
        self.assertEqual(path, [0, 1, 2, 3])

    def test_global_energy_routing_alias(self):
        p1 = energy_aware_path(self.graph, source=0, gateway=3, energies=self.energies, depletion=self.depletion, cfg=self.cfg_obj, dead=set())
        p2 = global_energy_routing(self.graph, source=0, gateway=3, energies=self.energies, depletion=self.depletion, cfg=self.cfg_obj, dead=set())
        self.assertEqual(p1, p2)

    def test_no_graph_mutation(self):
        original_edges = set(self.graph.edges())
        _ = shortest_path(self.graph, source=0, gateway=3, energies={}, depletion={}, cfg=self.cfg_obj, dead=set())
        _ = energy_aware_path(self.graph, source=0, gateway=3, energies=self.energies, depletion=self.depletion, cfg=self.cfg_obj, dead=set())
        self.assertEqual(set(self.graph.edges()), original_edges)

if __name__ == "__main__":
    unittest.main()
