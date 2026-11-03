import unittest
import math
import networkx as nx
from simulation.models import Node, NetworkConfig, ValidationError, Link
from simulation.topology import build_random_geometric_topology, build_grid_topology
from simulation.state import SimulationState

class TestSimulationModels(unittest.TestCase):
    def test_valid_node_creation(self):
        node = Node(id=1, type="sensor", x=0.5, y=0.5, initial_energy=10.0)
        self.assertEqual(node.id, 1)
        self.assertEqual(node.type, "sensor")
        self.assertEqual(node.residual_energy, 10.0)
        self.assertTrue(node.operational)

    def test_invalid_node_energy(self):
        with self.assertRaises(ValidationError):
            Node(id=1, type="sensor", x=0.0, y=0.0, initial_energy=-5)
        node = Node(id=2, type="sensor", x=0.0, y=0.0, initial_energy=0)
        self.assertEqual(node.residual_energy, 0)
        self.assertFalse(node.operational)

    def test_invalid_node_type(self):
        with self.assertRaises(ValidationError):
            Node(id=1, type="invalid", x=0.0, y=0.0, initial_energy=5)

    def test_network_config_validation(self):
        cfg = NetworkConfig(nodes=10, gateway=0, tx_range=0.5, initial_energy=20)
        self.assertEqual(cfg.nodes, 10)
        self.assertEqual(cfg.gateway, 0)
        with self.assertRaises(ValidationError):
            NetworkConfig(nodes=4, gateway=0)
        with self.assertRaises(ValidationError):
            NetworkConfig(nodes=10, gateway=10)
        with self.assertRaises(ValidationError):
            NetworkConfig(nodes=10, gateway=0, tx_range=-1)

    def test_random_geometric_topology(self):
        cfg = NetworkConfig(nodes=5, gateway=0, tx_range=0.3, seed=42)
        G = build_random_geometric_topology(cfg)
        self.assertEqual(len(G.nodes), 5)
        for _, data in G.nodes(data=True):
            x, y = data["pos"]
            self.assertTrue(0.0 <= x <= 1.0)
            self.assertTrue(0.0 <= y <= 1.0)
        G2 = build_random_geometric_topology(cfg)
        self.assertTrue(nx.is_isomorphic(
            G, G2,
            edge_match=lambda a, b: math.isclose(a.get('distance', 0), b.get('distance', 0))
        ))

    def test_grid_topology(self):
        cfg = NetworkConfig(nodes=9, gateway=0, tx_range=1.5, seed=1)
        G = build_grid_topology(cfg)
        self.assertEqual(len(G.nodes), 9)
        side = math.ceil(math.sqrt(9))
        expected_edges = (side * (side - 1)) * 2
        self.assertEqual(len(G.edges), expected_edges)
        positions = {data["pos"] for _, data in G.nodes(data=True)}
        self.assertEqual(len(positions), 9)

    def test_communication_range_constraint(self):
        cfg = NetworkConfig(nodes=3, gateway=0, tx_range=0.1, seed=0)
        G = build_random_geometric_topology(cfg)
        for _, _, d in G.edges(data=True):
            self.assertLessEqual(d.get('distance', 0), cfg.tx_range)

    def test_energy_consumption_and_dead_flag(self):
        node = Node(id=1, type="sensor", x=0, y=0, initial_energy=5)
        node.consume(3)
        self.assertEqual(node.residual_energy, 2)
        self.assertTrue(node.operational)
        node.consume(5)
        self.assertEqual(node.residual_energy, 0)
        self.assertFalse(node.operational)

    def test_simulation_state_transmit(self):
        cfg = NetworkConfig(nodes=2, gateway=0, tx_range=1.0, seed=0, tx_cost=0.5, rx_cost=0.2)
        state = SimulationState(cfg)
        self.assertTrue(state.graph.has_edge(0, 1))
        sender = state.node_model(0)
        receiver = state.node_model(1)
        init_sender = sender.residual_energy
        init_receiver = receiver.residual_energy
        state.transmit(0, 1)
        self.assertLess(sender.residual_energy, init_sender)
        self.assertLess(receiver.residual_energy, init_receiver)
        self.assertEqual(len(state.events), 1)
        ev = state.events[0]
        self.assertEqual(ev["type"], "transmit")
        self.assertEqual(ev["src"], 0)
        self.assertEqual(ev["dst"], 1)

    def test_snapshot_structure(self):
        cfg = NetworkConfig(nodes=3, gateway=0, tx_range=1.0, seed=1)
        state = SimulationState(cfg)
        snap = state.snapshot()
        self.assertIn("nodes", snap)
        self.assertIn("edges", snap)
        self.assertEqual(len(snap["nodes"]), 3)
        for n in snap["nodes"]:
            self.assertIn("energy", n)
            self.assertIn("dead", n)
            self.assertIn("gateway", n)
        for e in snap["edges"]:
            self.assertIsInstance(e["distance"], float)

    def test_death_round_metrics(self):
        from engine import run_simulation
        # Network where nodes fail and battery exhausts to verify first, half, and last node death round tracking
        cfg = {
            "nodes": 6,
            "gateway": 0,
            "rounds": 30,
            "seed": 1,
            "k": 3,
            "traffic_per_round": 10,
            "failure_round": 5,
            "failure_count": 3,
            "initial_energy": 50.0,
            "tx_cost": 1.0,
            "rx_cost": 0.5,
        }
        res = run_simulation(cfg, "shortest")
        metrics = res["metrics"]
        self.assertIsNotNone(metrics["first_node_dead_round"])
        self.assertIsNotNone(metrics["half_nodes_dead_round"])
        self.assertIsNotNone(metrics["last_node_dead_round"])
        self.assertLessEqual(metrics["first_node_dead_round"], metrics["half_nodes_dead_round"])
        self.assertLessEqual(metrics["half_nodes_dead_round"], metrics["last_node_dead_round"])
        self.assertGreaterEqual(metrics["energy_consumed"], 0.0)
        self.assertGreaterEqual(metrics["packets_sent"], metrics["packets_delivered"])
        self.assertAlmostEqual(metrics["packet_delivery_ratio"], metrics["packets_delivered"] / metrics["packets_sent"], places=4)

if __name__ == "__main__":
    unittest.main()
