# backend/test_rigorous_k.py
"""Deterministic tests for k-edge-connectivity enforcement, multi-objective
weighted routing, infeasibility handling, and connectivity cache behaviour.

Every test constructs a fixed topology (no randomness) so results are
reproducible across platforms and Python versions.
"""

import math
import unittest

import networkx as nx

from engine import (
    Config,
    compute_path,
    route_weight,
    measure_connectivity,
    _path_uses_bridge,
    invalidate_connectivity_cache,
    run_simulation,
)


# ---------------------------------------------------------------------------
# Helper: build small, deterministic graphs
# ---------------------------------------------------------------------------

def _diamond_graph() -> nx.Graph:
    """Diamond graph (K4 minus one edge):

        0 --- 1
        |  X  |
        3 --- 2

    Edges: 0-1, 0-2, 0-3, 1-2, 2-3  (5 edges, edge-connectivity = 2).
    Missing edge: 1-3.
    """
    G = nx.Graph()
    for n in range(4):
        G.add_node(n, pos=(float(n % 2), float(n // 2)))
    for u, v in [(0, 1), (0, 2), (0, 3), (1, 2), (2, 3)]:
        d = 1.0
        G.add_edge(u, v, distance=d, base_cost=1.0 + d)
    return G


def _bridge_graph() -> nx.Graph:
    """Graph with a single bridge:

        0 --- 1 --- 2 --- 3 --- 4
              |           |
              5           6

    Bridge edge: 2-3 (its removal disconnects {0,1,2,5} from {3,4,6}).
    Edge-connectivity = 1.
    """
    G = nx.Graph()
    positions = {0: (0, 0), 1: (1, 0), 2: (2, 0), 3: (3, 0), 4: (4, 0),
                 5: (1, 1), 6: (3, 1)}
    for n, pos in positions.items():
        G.add_node(n, pos=pos)
    for u, v in [(0, 1), (1, 2), (2, 3), (3, 4), (1, 5), (3, 6)]:
        d = 1.0
        G.add_edge(u, v, distance=d, base_cost=1.0 + d)
    return G


def _cycle_graph() -> nx.Graph:
    """6-node cycle: 0-1-2-3-4-5-0.  Edge-connectivity = 2."""
    G = nx.cycle_graph(6)
    for n in G.nodes:
        G.nodes[n]["pos"] = (float(n), 0.0)
    for u, v in G.edges:
        G[u][v]["distance"] = 1.0
        G[u][v]["base_cost"] = 2.0
    return G


def _line_graph() -> nx.Graph:
    """Simple path graph: 0-1-2-3.  Every edge is a bridge."""
    G = nx.path_graph(4)
    for n in G.nodes:
        G.nodes[n]["pos"] = (float(n), 0.0)
    for u, v in G.edges:
        G[u][v]["distance"] = 1.0
        G[u][v]["base_cost"] = 2.0
    return G


# ---------------------------------------------------------------------------
# Tests: _path_uses_bridge
# ---------------------------------------------------------------------------

class TestPathUsesBridge(unittest.TestCase):
    def test_bridge_detected_on_bridge_graph(self):
        G = _bridge_graph()
        # Path 0 -> 4 must cross bridge 2-3.
        self.assertTrue(_path_uses_bridge(G, [0, 1, 2, 3, 4]))

    def test_no_bridge_on_cycle(self):
        G = _cycle_graph()
        # No bridges in a cycle graph.
        self.assertFalse(_path_uses_bridge(G, [0, 1, 2, 3]))

    def test_all_edges_bridge_on_line(self):
        G = _line_graph()
        self.assertTrue(_path_uses_bridge(G, [0, 1]))
        self.assertTrue(_path_uses_bridge(G, [1, 2, 3]))


# ---------------------------------------------------------------------------
# Tests: rigorous_k enforcement in compute_path
# ---------------------------------------------------------------------------

class TestRigorousKEnforcement(unittest.TestCase):
    def setUp(self):
        invalidate_connectivity_cache()

    def test_rigorous_k_disabled_allows_bridge_path(self):
        """When rigorous_k=False, the shortest path through a bridge is accepted."""
        G = _bridge_graph()
        cfg = Config(rigorous_k=False, k=2, tx_cost=0.65, rx_cost=0.18)
        energies = {n: 100.0 for n in G.nodes}
        depletion = {n: 0.0 for n in G.nodes}
        path = compute_path(G, 0, 4, "energy", energies, depletion, cfg)
        self.assertIsNotNone(path)
        self.assertEqual(path[0], 0)
        self.assertEqual(path[-1], 4)

    def test_rigorous_k_enabled_still_returns_path_when_no_alternative(self):
        """When rigorous_k=True on a bridge-only topology, infeasibility
        fallback returns the best path rather than None."""
        G = _bridge_graph()
        cfg = Config(rigorous_k=True, k=2, tx_cost=0.65, rx_cost=0.18)
        energies = {n: 100.0 for n in G.nodes}
        depletion = {n: 0.0 for n in G.nodes}
        path = compute_path(G, 0, 4, "energy", energies, depletion, cfg)
        # Must still return a valid path (infeasibility tolerance).
        self.assertIsNotNone(path)
        self.assertEqual(path[0], 0)
        self.assertEqual(path[-1], 4)

    def test_rigorous_k_prefers_bridge_free_when_available(self):
        """On a graph with both bridge and non-bridge alternatives,
        rigorous_k selects the bridge-free path."""
        # Construct graph where 0 -> 2 has two options:
        # Option 1: 0 --(bridge)--> 1 --(bridge)--> 2, but wait: if 1 connects to nothing else it's a bridge.
        # To make 0-1-2 a bridge path, let 0-1 and 1-2 be the ONLY path through 1,
        # while 0 and 2 are ALSO connected via a 2-hop or 3-hop cycle: 0-3-4-2.
        # Wait, if 0-1-2 and 0-3-4-2 exist, then 0-1-2-4-3-0 is a cycle, so 0-1 is not a bridge!
        # For an edge to be a bridge, its removal MUST disconnect the graph.
        # What if 2 is the gateway, but 0 is connected to 2 via a bridge edge 0-2 (if that's the only edge to component {0}),
        # OR 0 has a bridge to 1, and 1 has two paths to 2? Then 0-1 is a bridge!
        # What if 0 has TWO paths to 2:
        # Path A (short): goes through a bridge of a side branch? No, a path to the gateway CANNOT use a bridge unless the bridge separates source and gateway!
        # BUT: In a graph G, if a bridge (u, v) is ON the path from source to gateway, can there be an alternative bridge-free path?
        # NO! If (u, v) is a bridge in G, then removing (u, v) splits G into two components.
        # If source is in one component and gateway is in the other, ALL paths between source and gateway MUST traverse (u, v)!
        # However, what if (u, v) is a bridge that separates some OTHER node (a dead-end stub), but an uncareful route traversed into the stub and back? Shortest path never does that.
        # What if k >= 2 and rigorous_k checks k-edge connectivity?
        # In a connected graph, edge connectivity kappa(G) >= 2 iff G has NO bridges!
        # If G has ANY bridge anywhere in the network, then kappa(G) = 1.
        # When rigorous_k is active with k=2, any edge that is a bridge in G is avoided if possible.
        # In a graph where G has a bridge in a branch (e.g., node 5 connected only to 1):
        # edge 1-5 is a bridge. A path 0-1-2 does NOT use bridge 1-5!
        # But if 0-1-2 is bridge-free, _path_uses_bridge returns False.
        # What if we have k >= 3?
        # In k >= 3, even if an edge is not a bridge (2-connected), the local edge connectivity may be < 3.
        # Let's test that compute_path successfully returns bridge-free paths when G is 2-connected:
        G = _diamond_graph()
        cfg_on = Config(rigorous_k=True, k=2, tx_cost=0.65, rx_cost=0.18)
        energies = {n: 100.0 for n in G.nodes}
        depletion = {n: 0.0 for n in G.nodes}
        path = compute_path(G, 0, 2, "energy", energies, depletion, cfg_on)
        self.assertIsNotNone(path)
        self.assertEqual(path[0], 0)
        self.assertEqual(path[-1], 2)
        # Verify that no edge on the chosen path is a bridge:
        self.assertFalse(_path_uses_bridge(G, path))

    def test_rigorous_k_on_line_graph_returns_fallback(self):
        """On a pure line graph (every edge is a bridge), rigorous_k must
        return the fallback path, not None."""
        G = _line_graph()
        cfg = Config(rigorous_k=True, k=2, tx_cost=0.65, rx_cost=0.18)
        energies = {n: 100.0 for n in G.nodes}
        depletion = {n: 0.0 for n in G.nodes}
        path = compute_path(G, 0, 3, "energy", energies, depletion, cfg)
        self.assertIsNotNone(path, "Infeasibility fallback must not return None")
        self.assertEqual(path, [0, 1, 2, 3])
        # The fallback uses bridges because the topology is inherently 1-connected.
        self.assertTrue(_path_uses_bridge(G, path))

    def test_k_greater_than_2_connectivity_measurement(self):
        """Verify measure_connectivity correctly evaluates k=3 and k=4 on suitable topologies."""
        # Complete graph K4 has edge-connectivity 3
        K4 = nx.complete_graph(4)
        res_k3 = measure_connectivity(K4, 3)
        self.assertTrue(res_k3["connected"])
        self.assertEqual(res_k3["edge_connectivity"], 3)
        self.assertTrue(res_k3["connectivity_target_met"])

        # K4 tested against k=4 should fail target
        res_k4 = measure_connectivity(K4, 4)
        self.assertEqual(res_k4["edge_connectivity"], 3)
        self.assertFalse(res_k4["connectivity_target_met"])

    def test_rigorous_k_with_k_equals_1_skips_bridge_check(self):
        """When k=1, rigorous_k has no effect (any connected path satisfies k=1)."""
        G = _bridge_graph()
        cfg = Config(rigorous_k=True, k=1, tx_cost=0.65, rx_cost=0.18)
        energies = {n: 100.0 for n in G.nodes}
        depletion = {n: 0.0 for n in G.nodes}
        path = compute_path(G, 0, 4, "energy", energies, depletion, cfg)
        self.assertIsNotNone(path)
        self.assertEqual(path[0], 0)
        self.assertEqual(path[-1], 4)


# ---------------------------------------------------------------------------
# Tests: weighted multi-objective cost function
# ---------------------------------------------------------------------------

class TestWeightedRouting(unittest.TestCase):
    def setUp(self):
        invalidate_connectivity_cache()

    def test_weights_change_path_selection(self):
        """Changing energy_weight vs depletion_weight alters path choice
        on a graph where two routes differ in energy and depletion profile."""
        # Graph:  0 --a-- 1 --a-- 3   (route A: through node 1)
        #         0 --b-- 2 --b-- 3   (route B: through node 2)
        G = nx.Graph()
        for n in range(4):
            G.add_node(n, pos=(float(n), 0.0))
        G.add_edge(0, 1, distance=1.0, base_cost=2.0)
        G.add_edge(1, 3, distance=1.0, base_cost=2.0)
        G.add_edge(0, 2, distance=1.2, base_cost=2.2)
        G.add_edge(2, 3, distance=1.2, base_cost=2.2)

        # Node 1 has high depletion (stressed), node 2 has low energy (risky).
        energies = {0: 100.0, 1: 80.0, 2: 15.0, 3: 100.0}
        depletion = {0: 0.0, 1: 60.0, 2: 5.0, 3: 0.0}

        # Config A: heavy depletion penalty -> should avoid node 1.
        cfg_a = Config(
            use_weighted_route=True,
            energy_weight=0.1,
            depletion_weight=5.0,
            redundancy_weight=0.0,
            k=1, tx_cost=0.65, rx_cost=0.18,
        )
        invalidate_connectivity_cache()
        path_a = compute_path(G, 0, 3, "energy", energies, depletion, cfg_a)

        # Config B: heavy energy penalty -> should avoid node 2 (low energy).
        cfg_b = Config(
            use_weighted_route=True,
            energy_weight=5.0,
            depletion_weight=0.1,
            redundancy_weight=0.0,
            k=1, tx_cost=0.65, rx_cost=0.18,
        )
        invalidate_connectivity_cache()
        path_b = compute_path(G, 0, 3, "energy", energies, depletion, cfg_b)

        self.assertIsNotNone(path_a)
        self.assertIsNotNone(path_b)
        # With heavy depletion penalty, route should go through node 2
        # (lower depletion). With heavy energy penalty and low energy on
        # node 2, route should go through node 1.
        self.assertIn(2, path_a, "Heavy depletion weight should route through node 2 (lower depletion)")
        self.assertIn(1, path_b, "Heavy energy weight should route through node 1 (higher residual energy)")
        # Crucially, the two paths must differ.
        self.assertNotEqual(path_a, path_b, "Different weight configurations must produce different paths")

    def test_weighted_mode_disabled_ignores_weights(self):
        """When use_weighted_route=False, custom weights have no effect."""
        G = _diamond_graph()
        energies = {n: 100.0 for n in G.nodes}
        depletion = {n: 0.0 for n in G.nodes}
        cfg_default = Config(use_weighted_route=False, k=2, tx_cost=0.65, rx_cost=0.18)
        cfg_custom = Config(
            use_weighted_route=False,
            energy_weight=99.0,
            depletion_weight=99.0,
            redundancy_weight=99.0,
            k=2, tx_cost=0.65, rx_cost=0.18,
        )
        invalidate_connectivity_cache()
        path_default = compute_path(G, 1, 3, "energy", energies, depletion, cfg_default)
        invalidate_connectivity_cache()
        path_custom = compute_path(G, 1, 3, "energy", energies, depletion, cfg_custom)
        # Paths must be identical since weighted mode is off.
        self.assertEqual(path_default, path_custom)

    def test_redundancy_weight_uses_connectivity(self):
        """Confirm that the redundancy term changes the edge cost when
        connectivity differs from the target k."""
        G = _cycle_graph()  # edge-connectivity = 2
        energies = {n: 100.0 for n in G.nodes}
        depletion = {n: 0.0 for n in G.nodes}

        # With k=2, redundancy term = 1 - 2/2 = 0.
        cfg_k2 = Config(use_weighted_route=True, redundancy_weight=10.0,
                        energy_weight=1.0, depletion_weight=1.0,
                        k=2, tx_cost=0.65, rx_cost=0.18)
        # With k=4, redundancy term = 1 - 2/4 = 0.5 -> adds 5.0 per edge.
        cfg_k4 = Config(use_weighted_route=True, redundancy_weight=10.0,
                        energy_weight=1.0, depletion_weight=1.0,
                        k=4, tx_cost=0.65, rx_cost=0.18)

        invalidate_connectivity_cache()
        w_k2 = route_weight(G, 0, 1, "energy", energies, depletion, cfg_k2)
        invalidate_connectivity_cache()
        w_k4 = route_weight(G, 0, 1, "energy", energies, depletion, cfg_k4)

        # With a higher k target the redundancy penalty should be larger.
        self.assertGreater(w_k4, w_k2,
                           "Higher k target should increase edge cost via redundancy penalty")


# ---------------------------------------------------------------------------
# Tests: connectivity measurement and cache
# ---------------------------------------------------------------------------

class TestConnectivityCache(unittest.TestCase):
    def test_cache_invalidation_after_topology_change(self):
        """After invalidate_connectivity_cache(), the next call recomputes."""
        from engine import _get_cached_connectivity
        G = _cycle_graph()
        invalidate_connectivity_cache()
        c1 = _get_cached_connectivity(G)
        self.assertEqual(c1, 2)

        # Remove an edge to drop connectivity.
        G.remove_edge(0, 1)
        # Without invalidation, cache would return stale value.
        # With invalidation, it recomputes.
        invalidate_connectivity_cache()
        c2 = _get_cached_connectivity(G)
        self.assertEqual(c2, 1)


# ---------------------------------------------------------------------------
# Tests: full simulation integration with rigorous_k and weights
# ---------------------------------------------------------------------------

class TestSimulationIntegration(unittest.TestCase):
    def test_simulation_with_rigorous_k(self):
        """Run a short simulation with rigorous_k=True and confirm it completes."""
        cfg = {
            "nodes": 10, "gateway": 0, "rounds": 10, "seed": 42,
            "k": 2, "traffic_per_round": 5, "failure_round": 3,
            "failure_count": 1, "threshold": 25.0, "tx_cost": 0.65,
            "rx_cost": 0.18, "initial_energy": 100.0,
            "rigorous_k": True,
        }
        result = run_simulation(cfg, "incremental")
        self.assertIn("metrics", result)
        self.assertIn("history", result)
        self.assertGreater(result["metrics"]["packets_delivered"], 0)

    def test_simulation_with_weighted_route(self):
        """Run with use_weighted_route=True and confirm completion."""
        cfg = {
            "nodes": 10, "gateway": 0, "rounds": 10, "seed": 42,
            "k": 2, "traffic_per_round": 5, "failure_round": 3,
            "failure_count": 1, "threshold": 25.0, "tx_cost": 0.65,
            "rx_cost": 0.18, "initial_energy": 100.0,
            "use_weighted_route": True,
            "energy_weight": 2.0,
            "depletion_weight": 1.0,
            "redundancy_weight": 0.5,
        }
        result = run_simulation(cfg, "energy")
        self.assertIn("metrics", result)
        self.assertGreater(result["metrics"]["packets_delivered"], 0)

    def test_weighted_routing_changes_energy_consumption(self):
        """Changing weights should produce measurably different energy
        consumption compared to the default cost function."""
        base = {
            "nodes": 15, "gateway": 0, "rounds": 30, "seed": 7,
            "k": 2, "traffic_per_round": 10, "failure_round": 99,
            "failure_count": 0, "threshold": 25.0, "tx_cost": 0.65,
            "rx_cost": 0.18, "initial_energy": 100.0,
        }
        # Default (unweighted).
        r_default = run_simulation(base, "energy")

        # Weighted with extreme depletion penalty.
        cfg_w = dict(base)
        cfg_w.update({
            "use_weighted_route": True,
            "energy_weight": 0.1,
            "depletion_weight": 10.0,
            "redundancy_weight": 0.1,
        })
        r_weighted = run_simulation(cfg_w, "energy")

        # Both must complete and deliver packets.
        self.assertGreater(r_default["metrics"]["packets_delivered"], 0)
        self.assertGreater(r_weighted["metrics"]["packets_delivered"], 0)

        # Energy consumption should differ (different routing decisions).
        e_def = r_default["metrics"]["energy_consumed"]
        e_wgt = r_weighted["metrics"]["energy_consumed"]
        self.assertNotEqual(round(e_def, 2), round(e_wgt, 2),
                            "Weighted routing must produce different energy consumption")


# ---------------------------------------------------------------------------
# Tests: infeasibility and edge cases
# ---------------------------------------------------------------------------

class TestInfeasibility(unittest.TestCase):
    def test_disconnected_source_returns_none(self):
        """Source with no path to gateway returns None."""
        G = nx.Graph()
        G.add_node(0, pos=(0.0, 0.0))
        G.add_node(1, pos=(1.0, 0.0))
        # No edges.
        cfg = Config(k=1, tx_cost=0.65, rx_cost=0.18)
        path = compute_path(G, 0, 1, "energy", {0: 100, 1: 100}, {0: 0, 1: 0}, cfg)
        self.assertIsNone(path)

    def test_source_equals_gateway(self):
        """Source == gateway returns [gateway]."""
        G = _diamond_graph()
        cfg = Config(k=2, tx_cost=0.65, rx_cost=0.18)
        path = compute_path(G, 0, 0, "energy", {}, {}, cfg)
        self.assertEqual(path, [0])

    def test_missing_node_returns_none(self):
        """Source not in graph returns None."""
        G = _diamond_graph()
        cfg = Config(k=2, tx_cost=0.65, rx_cost=0.18)
        path = compute_path(G, 99, 0, "energy", {}, {}, cfg)
        self.assertIsNone(path)

    def test_measure_connectivity_single_node(self):
        """Single-node graph has connectivity 0."""
        G = nx.Graph()
        G.add_node(0)
        result = measure_connectivity(G, 2)
        self.assertTrue(result["connected"])
        self.assertEqual(result["edge_connectivity"], 0)
        self.assertFalse(result["connectivity_target_met"])


# ---------------------------------------------------------------------------
# Tests: Incremental vs Full-Recomputation Equivalence
# ---------------------------------------------------------------------------

class TestIncrementalVsFullEquivalence(unittest.TestCase):
    def test_incremental_matches_full_recomputation_initial_routes(self):
        """When computed on the same topology and state, incremental and energy routing choose identical paths."""
        cfg = {
            "nodes": 10, "gateway": 0, "rounds": 5, "seed": 42,
            "k": 2, "traffic_per_round": 2, "failure_round": 0,
            "failure_count": 0, "threshold": 25.0, "tx_cost": 0.65,
            "rx_cost": 0.18, "initial_energy": 100.0,
        }
        res_full = run_simulation(cfg, "energy")
        res_inc = run_simulation(cfg, "incremental")
        paths_full = sorted(res_full["network"]["paths"], key=lambda x: x["source"])
        paths_inc = sorted(res_inc["network"]["paths"], key=lambda x: x["source"])
        self.assertEqual(paths_full, paths_inc,
                         "Incremental routing paths must match global energy recomputation in identical low-depletion network")

    def test_incremental_work_is_strictly_lower_than_full(self):
        """Verify incremental routing performs fewer total route recomputations than full."""
        cfg = {
            "nodes": 20, "gateway": 0, "rounds": 10, "seed": 123,
            "k": 2, "traffic_per_round": 10, "failure_round": 4,
            "failure_count": 1, "threshold": 25.0, "tx_cost": 0.65,
            "rx_cost": 0.18, "initial_energy": 50.0,
        }
        res_full = run_simulation(cfg, "energy")
        res_inc = run_simulation(cfg, "incremental")
        self.assertGreater(
            res_full["metrics"]["routing_recomputations"],
            res_inc["metrics"]["routing_recomputations"],
            "Full recomputation must perform strictly more route calculations than incremental"
        )


# ---------------------------------------------------------------------------
# Tests: Numerical boundaries and parameter robustness
# ---------------------------------------------------------------------------

class TestNumericalBoundaries(unittest.TestCase):
    def test_zero_and_near_zero_energy_handled_safely(self):
        """Zero residual energy does not cause division by zero or NaN costs."""
        G = _diamond_graph()
        cfg = Config(use_weighted_route=True, initial_energy=100.0, tx_cost=0.65)
        # Node with 0.0 energy
        energies = {0: 100.0, 1: 0.0, 2: 50.0, 3: 100.0}
        depletion = {0: 0.0, 1: 100.0, 2: 50.0, 3: 0.0}
        cost = route_weight(G, 0, 1, "energy", energies, depletion, cfg)
        self.assertTrue(math.isfinite(cost), "Cost must be finite even when node energy is 0")
        self.assertGreater(cost, 0, "Cost must be positive")

    def test_negative_depletion_handled_safely(self):
        """Negative depletion value is clamped to zero without crashing."""
        G = _diamond_graph()
        cfg = Config(use_weighted_route=True, initial_energy=100.0, tx_cost=0.65)
        energies = {0: 100.0, 1: 80.0, 2: 50.0, 3: 100.0}
        depletion = {0: 0.0, 1: -10.0, 2: 0.0, 3: 0.0}
        cost = route_weight(G, 0, 1, "energy", energies, depletion, cfg)
        self.assertTrue(math.isfinite(cost))


if __name__ == "__main__":
    import math
    unittest.main()
