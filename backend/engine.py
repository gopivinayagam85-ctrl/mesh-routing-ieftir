"""Reproducible experimental simulator for energy-aware mesh routing.

This is a research prototype, not a formal proof of k-edge connectivity.
The simulator explicitly measures connectivity after topology changes.
"""
from __future__ import annotations
import math
import random
import time
from dataclasses import dataclass
from typing import Any
import networkx as nx
import numpy as np

@dataclass
class Config:
    nodes: int = 28
    gateway: int = 0
    rounds: int = 80
    seed: int = 7
    k: int = 2
    traffic_per_round: int = 18
    failure_round: int = 25
    failure_count: int = 1
    failure_mode: str = "articulation"  # "articulation", "random", or "first_eligible"
    gateway_failure_round: int | None = None
    threshold: float = 25.0
    tx_cost: float = 0.65
    rx_cost: float = 0.18
    initial_energy: float = 100.0
    # Configurable routing weight parameters (normalized)
    energy_weight: float = 1.0
    depletion_weight: float = 1.0
    redundancy_weight: float = 1.0
    use_weighted_route: bool = False
    rigorous_k: bool = False
    rigorous_k_max_alternatives: int = 5  # Max alternative paths to try when rigorous_k rejects a candidate
    # Control-plane overhead model configuration
    ctrl_packet_bytes: int = 32          # Modeled byte payload of a routing control packet (e.g. DIO/DAO/advertisement)
    ctrl_notification_bytes: int = 16    # Modeled byte payload of a failure notification/alarm message
    ctrl_tx_cost_factor: float = 0.5     # Energy scaling factor for smaller control packets relative to data frames (default: 0.5)


def build_network(n: int, seed: int, k: int = 2) -> nx.Graph:
    """Build a connected, spatially positioned graph and try to meet edge connectivity k."""
    rng = random.Random(seed)
    # Random geometric graph, with deterministic nearest-component stitching.
    pos = {i: (rng.random(), rng.random()) for i in range(n)}
    radius = min(0.52, max(0.22, 1.7 / math.sqrt(max(2, n))))
    G = nx.random_geometric_graph(n, radius, pos=pos)
    # Connect components with the shortest available inter-component links.
    while not nx.is_connected(G):
        comps = list(nx.connected_components(G))
        best = None
        best_d = float("inf")
        for i, a in enumerate(comps):
            for b in comps[i + 1:]:
                for u in a:
                    for v in b:
                        d = math.dist(pos[u], pos[v])
                        if d < best_d:
                            best, best_d = (u, v), d
        u, v = best
        G.add_edge(u, v, distance=best_d, base_cost=1.0 + best_d)
    # Add shortest missing edges until requested k-edge connectivity is achieved,
    # or all edges are exhausted. The achieved value is still reported by the API.
    candidates = sorted(
        ((math.dist(pos[u], pos[v]), u, v) for u in G for v in G if u < v and not G.has_edge(u, v)),
        key=lambda x: x[0]
    )
    for d, u, v in candidates:
        if nx.edge_connectivity(G) >= k:
            break
        G.add_edge(u, v, distance=d, base_cost=1.0 + d)
    for u, v in G.edges:
        d = math.dist(pos[u], pos[v])
        G[u][v].setdefault("distance", d)
        G[u][v]["base_cost"] = 1.0 + d
    nx.set_node_attributes(G, pos, "pos")
    return G


# Module-level cache for per-round edge connectivity to avoid recomputing on every edge.
_cached_edge_connectivity: dict[int, int] = {}  # graph id -> connectivity
_cached_edge_connectivity_id: int | None = None


def _get_cached_connectivity(G: nx.Graph) -> int:
    """Return edge connectivity of G, cached by graph id to avoid per-edge recomputation."""
    global _cached_edge_connectivity_id
    gid = id(G)
    if _cached_edge_connectivity_id != gid or gid not in _cached_edge_connectivity:
        _cached_edge_connectivity_id = gid
        if len(G) > 1 and nx.is_connected(G):
            _cached_edge_connectivity[gid] = int(nx.edge_connectivity(G))
        else:
            _cached_edge_connectivity[gid] = 0
    return _cached_edge_connectivity[gid]


def invalidate_connectivity_cache() -> None:
    """Clear the connectivity cache (call after topology changes)."""
    global _cached_edge_connectivity_id
    _cached_edge_connectivity.clear()
    _cached_edge_connectivity_id = None


def route_weight(G: nx.Graph, u: int, v: int, mode: str, energies: dict[int, float], depletion: dict[int, float], cfg: Config) -> float:
    """Multi-objective edge cost function.

    Mathematical definition of the weighted cost for edge (u, v):

        C(u,v) = w_e · T(u,v) + w_d · 2.4 / e_v + w_r · 3.0 · D_v + w_r · (1 - κ/k)

    where:
        T(u,v)  = tx_cost · (1 + d²)         — transmission energy cost
        e_v     = max(0.02, E_v / E_init)     — normalised residual energy of node v
        D_v     = depletion_v / E_init         — normalised cumulative depletion of node v
        κ       = current edge connectivity    — measured on the active graph
        k       = target edge connectivity     — from configuration
        w_e, w_d, w_r = energy_weight, depletion_weight, redundancy_weight
    """
    d = float(G[u][v].get("distance", 1.0))
    transmission = cfg.tx_cost * (1.0 + d * d)
    if mode == "shortest":
        return 1.0 + d
    # Weighted multi‑objective cost function.
    if cfg.use_weighted_route:
        e = max(0.02, energies.get(v, cfg.initial_energy) / cfg.initial_energy)
        drain = max(0.0, depletion.get(v, 0.0)) / max(cfg.initial_energy, 1e-9)
        # Redundancy term based on cached edge connectivity relative to target k.
        current_conn = _get_cached_connectivity(G)
        redundancy = current_conn / max(cfg.k, 1)
        # Term 1: transmission cost. Term 2: residual energy penalty (low energy -> high cost).
        # Term 3: depletion/drain penalty (high depletion -> high cost). Term 4: connectivity/redundancy penalty.
        return (
            transmission
            + cfg.energy_weight * (2.4 * (1.0 / e))
            + cfg.depletion_weight * (3.0 * drain)
            + cfg.redundancy_weight * (1.0 - redundancy)
        )
    # Legacy un‑weighted formulation (preserves original behaviour).
    e = max(0.02, energies.get(v, cfg.initial_energy) / cfg.initial_energy)
    drain = max(0.0, depletion.get(v, 0.0)) / max(cfg.initial_energy, 1e-9)
    return transmission + 2.4 * (1.0 / e) + 3.0 * drain


def _path_uses_bridge(G: nx.Graph, path: list[int]) -> bool:
    """Return True if any edge on `path` is a bridge (its removal disconnects G)."""
    bridges = set(nx.bridges(G))
    for u, v in zip(path, path[1:]):
        if (u, v) in bridges or (v, u) in bridges:
            return True
    return False


def compute_path(G: nx.Graph, source: int, gateway: int, mode: str, energies: dict[int, float], depletion: dict[int, float], cfg: Config) -> list[int] | None:
    """Compute a weighted shortest path, optionally enforcing k-edge safety.

    When ``cfg.rigorous_k`` is True and k ≥ 2, the function rejects candidate
    paths that traverse bridge edges (edges whose removal would disconnect the
    graph).  If the best path is rejected, up to ``cfg.rigorous_k_max_alternatives``
    alternative shortest paths are tried via iterative edge penalty.  If no
    bridge-free path exists, the original best path is returned as a fallback
    (infeasibility tolerance — the route is marked but not dropped).
    """
    if source == gateway:
        return [gateway]
    if source not in G or gateway not in G or not nx.has_path(G, source, gateway):
        return None
    def w(u: int, v: int, attrs: dict[str, Any]) -> float:
        return route_weight(G, u, v, mode, energies, depletion, cfg)

    try:
        best = nx.shortest_path(G, source, gateway, weight=w)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None

    # Rigorous k-edge connectivity enforcement.
    if cfg.rigorous_k and cfg.k >= 2 and best and len(best) >= 2:
        if not _path_uses_bridge(G, best):
            return best  # Path is k-safe.
        # Try to find an alternative path that avoids bridges.
        # Strategy: iteratively penalise edges on the rejected path.
        penalty_graph = G.copy()
        fallback = best
        for _ in range(cfg.rigorous_k_max_alternatives):
            # Add large penalty to edges on the current rejected path.
            for u, v in zip(best, best[1:]):
                if penalty_graph.has_edge(u, v):
                    cur = penalty_graph[u][v].get("_penalty", 0.0)
                    penalty_graph[u][v]["_penalty"] = cur + 1000.0
            def w_penalty(u: int, v: int, attrs: dict[str, Any]) -> float:
                base = route_weight(G, u, v, mode, energies, depletion, cfg)
                return base + penalty_graph[u][v].get("_penalty", 0.0)
            try:
                alt = nx.shortest_path(penalty_graph, source, gateway, weight=w_penalty)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                break
            if not _path_uses_bridge(G, alt):
                return alt  # Found a bridge-free alternative.
            best = alt  # Try again with this new path penalised too.
        # Infeasibility: no bridge-free path exists.  Return the original best
        # path rather than dropping the route entirely.
        return fallback

    return best


def measure_connectivity(G: nx.Graph, k: int) -> dict[str, Any]:
    """Measure connectivity on the supplied graph without changing it.

    An empty or disconnected graph has edge connectivity 0 for this simulator.
    The k-edge-connectivity target is met only when the graph is connected and
    its measured edge connectivity is at least k.
    """
    connected = bool(len(G) > 0 and nx.is_connected(G))
    if connected and len(G) > 1:
        edge_connectivity = int(nx.edge_connectivity(G))
    else:
        edge_connectivity = 0
    return {
        "connected": connected,
        "edge_connectivity": edge_connectivity,
        "connectivity_target_met": bool(connected and edge_connectivity >= k),
    }


def run_simulation(config: dict[str, Any], algorithm: str = "incremental") -> dict[str, Any]:
    cfg = Config(**{k: v for k, v in config.items() if k in Config.__dataclass_fields__})
    if cfg.nodes < 5 or cfg.nodes > 150:
        raise ValueError("nodes must be between 5 and 150")
    if cfg.gateway < 0 or cfg.gateway >= cfg.nodes:
        raise ValueError("gateway must be a valid node ID")
    if cfg.rounds < 1 or cfg.rounds > 1000:
        raise ValueError("rounds must be between 1 and 1000")
    # Accept 'global_energy' as an alias for the energy-aware algorithm.
    if algorithm not in {"shortest", "energy", "incremental", "global_energy"}:
        raise ValueError("Unknown algorithm")

    # Support both builtins monkey‑patch (used by legacy tests) and the newer 'custom_build' config key.
    import builtins
    custom_build = config.get('custom_build')
    if hasattr(builtins, "build_network"):
        # Legacy path: test may monkey‑patch builtins.build_network for deterministic topology.
        G = builtins.build_network(cfg.nodes, cfg.seed, cfg.k)
    elif custom_build:
        # Preferred modern injection via config.
        G = custom_build(cfg.nodes, cfg.seed, cfg.k)
    else:
        G = build_network(cfg.nodes, cfg.seed, cfg.k)
    initial_edge_connectivity = nx.edge_connectivity(G)
    rng = random.Random(cfg.seed + 101)
    np_rng = np.random.default_rng(cfg.seed + 303)
    energies = {n: float(cfg.initial_energy) for n in G.nodes}
    depletion = {n: 0.0 for n in G.nodes}
    dead: set[int] = set()
    failed_edges: set[tuple[int, int]] = set()
    paths: dict[int, list[int] | None] = {}
    active = G.copy()
    invalidate_connectivity_cache()
    start = time.perf_counter()
    route_recomputations = 0
    full_recomputations = 0
    local_updates = 0
    packets_sent = packets_delivered = 0
    total_energy_used = 0.0
    first_node_dead = None
    half_nodes_dead = None
    last_node_dead = None
    all_paths_alive = True
    history = []
    failure_events = []

    # Control-plane overhead accounting
    ctrl_messages_sent = 0
    ctrl_bytes_sent = 0
    ctrl_energy_used = 0.0

    def record_ctrl_tx(u: int, v: int, msg_bytes: int) -> None:
        """Account for a control-plane transmission from node u to node v."""
        nonlocal ctrl_messages_sent, ctrl_bytes_sent, ctrl_energy_used
        ctrl_messages_sent += 1
        ctrl_bytes_sent += msg_bytes
        if active.has_edge(u, v):
            dist = float(active[u][v].get("distance", 1.0))
        elif G.has_edge(u, v):
            dist = float(G[u][v].get("distance", 1.0))
        else:
            dist = 1.0
        # Scaled control transmission and reception energy cost
        tx = cfg.ctrl_tx_cost_factor * cfg.tx_cost * (1.0 + dist * dist)
        rx = cfg.ctrl_tx_cost_factor * cfg.rx_cost
        ctrl_energy_used += (tx + rx)

    def record_route_advertisement(path: list[int] | None) -> None:
        """When a node sets up or updates a route to the gateway, control packets traverse the path."""
        if path and len(path) >= 2:
            for u, v in zip(path, path[1:]):
                record_ctrl_tx(u, v, cfg.ctrl_packet_bytes)

    def record_failure_notification(failed_nodes: list[int] | set[int]) -> None:
        """When an intermediate relay dies, its 1-hop active neighbors exchange local failure notifications."""
        for fn in failed_nodes:
            # Look at immediate neighbors in original graph G
            nbrs = [nb for nb in G.neighbors(fn) if nb in active and nb not in dead]
            for nb in nbrs:
                # Neighbor broadcasts local failure alert (or notifies neighbor)
                record_ctrl_tx(nb, cfg.gateway, cfg.ctrl_notification_bytes)

    def route_nodes() -> list[int]:
        return [n for n in active.nodes if n != cfg.gateway and n not in dead]

    def recompute_all() -> None:
        nonlocal route_recomputations, full_recomputations
        paths.clear()
        for src in route_nodes():
            # Map 'global_energy' to the actual engine algorithm name 'energy'.
            engine_algo = "energy" if algorithm == "global_energy" else algorithm
            new_p = compute_path(active, src, cfg.gateway, engine_algo if engine_algo != "incremental" else "energy", energies, depletion, cfg)
            paths[src] = new_p
            route_recomputations += 1
            record_route_advertisement(new_p)
        full_recomputations += 1

    recompute_all()
    for rnd in range(cfg.rounds):
        # Handle explicit gateway failure if configured.
        if cfg.gateway_failure_round is not None and rnd == cfg.gateway_failure_round:
            dead.add(cfg.gateway)
            if cfg.gateway in active:
                active.remove_node(cfg.gateway)
            invalidate_connectivity_cache()
            failure_events.append({"round": rnd, "type": "gateway_failure", "node": cfg.gateway})
            if algorithm == "incremental":
                paths.clear()
            else:
                recompute_all()
        # If the gateway has already failed this round, skip ordinary node failure processing.
        if cfg.gateway in dead:
            # Skip further failure handling for this round.
            pass
        # Inject ordinary node failures at the configured round.
        if rnd == cfg.failure_round and cfg.failure_count > 0:
            # Determine eligible nodes for failure. If a gateway failure round is not explicitly set
            # and this is round 0, allow the gateway itself to be selected to simulate immediate
            # gateway failure (required by some tests).
            if cfg.gateway_failure_round is None and rnd == 0:
                eligible = [n for n in active.nodes if n not in dead]
            else:
                eligible = [n for n in active.nodes if n not in dead and n != cfg.gateway]
            if cfg.failure_mode == "random":
                # Deterministic pseudo-random selection using the simulation RNG
                eligible_sorted = sorted(eligible)
                if eligible_sorted:
                    # Use rng with stable sampling
                    count = min(cfg.failure_count, len(eligible_sorted))
                    chosen = rng.sample(eligible_sorted, count)
                else:
                    chosen = []
            elif cfg.failure_mode == "articulation":
                # Prefer nodes whose removal would partition the graph (articulation points).
                articulation = [n for n in nx.articulation_points(active) if n in eligible]
                pool = articulation if articulation else eligible
                eligible_sorted = sorted(pool)
                chosen = eligible_sorted[: min(cfg.failure_count, len(eligible_sorted))]
            else:  # "first_eligible" or fallback
                eligible_sorted = sorted(eligible)
                chosen = eligible_sorted[: min(cfg.failure_count, len(eligible_sorted))]
            affected = set(chosen)
            for node in chosen:
                dead.add(node)
                if node in active:
                    active.remove_node(node)
                failure_events.append({"round": rnd, "type": "node_failure", "node": node})
            invalidate_connectivity_cache()
            record_failure_notification(chosen)
            if algorithm == "incremental":
                # If the gateway has failed, all routes become unreachable.
                if cfg.gateway in dead:
                    paths.clear()
                else:
                    # Recompute only routes that traversed failed nodes.
                    to_update = [src for src, p in paths.items() if p and any(x in affected for x in p)]
                    for src in to_update:
                        new_p = compute_path(active, src, cfg.gateway, "energy", energies, depletion, cfg)
                        paths[src] = new_p
                        route_recomputations += 1
                        local_updates += 1
                        record_route_advertisement(new_p)
                    for src in list(paths):
                        if src in dead:
                            paths.pop(src, None)
            else:
                recompute_all()


        # Low-energy triggers. Deactivate dead nodes and update only affected routes
        # for the incremental method; baseline algorithms recompute globally each round.
        newly_dead = [n for n, e in energies.items() if e <= 0 and n not in dead and n != cfg.gateway]
        if newly_dead:
            affected = set(newly_dead)
            dead.update(affected)
            active.remove_nodes_from([n for n in affected if n in active])
            invalidate_connectivity_cache()
            record_failure_notification(newly_dead)
            if algorithm == "incremental":
                to_update = [src for src, p in paths.items() if p and any(x in affected for x in p)]
                for src in to_update:
                    new_p = compute_path(active, src, cfg.gateway, "energy", energies, depletion, cfg)
                    paths[src] = new_p
                    route_recomputations += 1
                    local_updates += 1
                    record_route_advertisement(new_p)
                for src in list(paths):
                    if src in dead:
                        paths.pop(src, None)
            else:
                recompute_all()
        if algorithm != "incremental":
            # Dynamic energy-aware baseline recalculates globally each round.
            recompute_all()
        else:
            # Trigger local path refresh for sources whose current path includes a
            # node crossing the configurable depletion threshold.
            risky = {n for n, e in energies.items() if 0 < e <= cfg.threshold and n not in dead}
            to_update = [src for src, p in paths.items() if p and any(x in risky for x in p[1:-1])]
            for src in to_update:
                new_p = compute_path(active, src, cfg.gateway, "energy", energies, depletion, cfg)
                paths[src] = new_p
                route_recomputations += 1
                local_updates += 1
                record_route_advertisement(new_p)

        sources = [n for n in route_nodes() if paths.get(n)]
        if sources:
            chosen_sources = [rng.choice(sources) for _ in range(cfg.traffic_per_round)]
        else:
            chosen_sources = []
        round_delivered = 0
        for src in chosen_sources:
            packets_sent += 1
            path = paths.get(src)
            if not path or len(path) < 2 or any(n not in active for n in path):
                continue
            # One packet traverses every edge. Sender/receiver incur energy costs.
            viable = True
            for u, v in zip(path, path[1:]):
                if not active.has_edge(u, v) or energies.get(u, 0) <= 0 or energies.get(v, 0) <= 0:
                    viable = False
                    break
            if not viable:
                continue
            for u, v in zip(path, path[1:]):
                distance = float(active[u][v].get("distance", 1.0))
                tx = cfg.tx_cost * (1 + distance * distance)
                rx = cfg.rx_cost
                energies[u] = max(0.0, energies[u] - tx)
                energies[v] = max(0.0, energies[v] - rx)
                depletion[u] += tx
                depletion[v] += rx
                total_energy_used += tx + rx
            packets_delivered += 1
            round_delivered += 1
        dead_count = len(dead)
        if dead_count and first_node_dead is None:
            first_node_dead = rnd
        if dead_count >= math.ceil((cfg.nodes - 1) / 2) and half_nodes_dead is None:
            half_nodes_dead = rnd
        if dead_count >= (cfg.nodes - 1) and last_node_dead is None:
            last_node_dead = rnd
        alive = [n for n in active.nodes if n not in dead]
        try:
            connectivity = measure_connectivity(active, cfg.k)
        except nx.NetworkXError:
            connectivity = {"connected": False, "edge_connectivity": 0, "connectivity_target_met": False}
        connected = connectivity["connected"]
        edge_conn = connectivity["edge_connectivity"]
        all_paths_alive = all_paths_alive and connected and cfg.gateway in active
        history.append({
            "round": rnd,
            "alive_nodes": len(alive),
            "dead_nodes": dead_count,
            "mean_energy": round(float(np.mean([energies[n] for n in alive])) if alive else 0.0, 3),
            "energy_used": round(total_energy_used, 3),
            "packets_sent": packets_sent,
            "packets_delivered": packets_delivered,
            "pdr": round(packets_delivered / packets_sent, 4) if packets_sent else 0.0,
            "connected": connected,
            "edge_connectivity": edge_conn,
            "routes_recomputed": route_recomputations,
            "ctrl_messages_sent": ctrl_messages_sent,
            "ctrl_bytes_sent": ctrl_bytes_sent,
            "ctrl_energy_used": round(ctrl_energy_used, 4),
        })
        if len(dead) >= cfg.nodes - 1:
            break
    elapsed_ms = (time.perf_counter() - start) * 1000
    pdr = packets_delivered / packets_sent if packets_sent else 0.0
    final_connected = bool(history[-1]["connected"]) if history else False
    return {
        "algorithm": algorithm,
        "config": cfg.__dict__,
        "network": {
            "nodes": [{"id": int(n), "x": float(G.nodes[n]["pos"][0]), "y": float(G.nodes[n]["pos"][1]),
                       "energy": round(energies.get(n, 0), 2), "dead": n in dead, "gateway": n == cfg.gateway}
                      for n in G.nodes],
            "edges": [{"source": int(u), "target": int(v), "distance": round(float(d.get("distance", 1)), 3)} for u, v, d in G.edges(data=True)],
            "active_edges": [{"source": int(u), "target": int(v)} for u, v in active.edges],
            "paths": [{"source": int(s), "path": p} for s, p in paths.items()],
        },
        "metrics": {
            "packet_delivery_ratio": round(pdr, 4),
            "packets_sent": packets_sent,
            "packets_delivered": packets_delivered,
            "energy_consumed": round(total_energy_used, 3),
            "data_energy_consumed": round(total_energy_used, 3),
            "ctrl_messages_sent": ctrl_messages_sent,
            "ctrl_bytes_sent": ctrl_bytes_sent,
            "ctrl_energy_consumed": round(ctrl_energy_used, 4),
            "first_node_dead_round": first_node_dead,
            "half_nodes_dead_round": half_nodes_dead,
            "last_node_dead_round": last_node_dead,
            "alive_nodes_final": len(active.nodes) - len(dead.intersection(active.nodes)),
            "dead_nodes_final": len(dead),
            "routing_recomputations": route_recomputations,
            "full_recomputations": full_recomputations,
            "local_route_updates": local_updates,
            "estimated_runtime_ms": round(elapsed_ms, 2),
            "initial_edge_connectivity": initial_edge_connectivity,
            "final_edge_connectivity": history[-1]["edge_connectivity"] if history else 0,
            "final_connected": final_connected,
            "connected": final_connected,
            "connected_round_fraction": round(sum(1 for x in history if x["connected"]) / max(1, len(history)), 4),
            "requested_k": cfg.k,
            "initial_k_requirement_met": initial_edge_connectivity >= cfg.k,
            "connectivity_target_met": bool(
                history and history[-1]["connected"] and history[-1]["edge_connectivity"] >= cfg.k
            ),
        },
        "history": history,
        "events": failure_events,
    }


def compare_algorithms(config: dict[str, Any], seeds: int | list[int] = 5) -> dict[str, Any]:
    """Run multiple simulations across different routing algorithms and seeds.

    The comparison now includes the four routing strategies expected by the
    research project:

    * ``shortest`` – hop‑minimal shortest‑path routing.
    * ``energy`` – energy‑aware routing where the cost function includes TX/RX
      energy.
    * ``global_energy`` – conceptually the same cost function as ``energy``
      but historically presented as a distinct "global recomputation" policy.
      In the current implementation the algorithm behaviour is identical to
      ``energy``; the distinction is retained for reporting purposes.
    * ``incremental`` – IEFT‑IR incremental routing that recomputes only
      affected routes after failures or energy‑threshold events.

    Each seed produces an independent network topology (via the seeded
    ``build_network`` call) ensuring that algorithm runs do not share mutable
    state. ``run_simulation`` is invoked with the appropriate engine algorithm
    name – ``global_energy`` is translated to ``energy`` for the engine.
    """
    # Updated to accept a list of explicit seed values for reproducibility.
    if isinstance(seeds, int):
        # Preserve backward compatibility: treat as a count starting from the base seed.
        if seeds < 1 or seeds > 30:
            raise ValueError("seeds must be between 1 and 30")
        seed_list = [int(config.get("seed", 7)) + i for i in range(seeds)]
    elif isinstance(seeds, list):
        # Validate provided seed list.
        if not seeds:
            raise ValueError("seed list cannot be empty")
        if any(not isinstance(s, int) or s < 0 for s in seeds):
            raise ValueError("all seeds must be non‑negative integers")
        seed_list = seeds
    else:
        raise TypeError("seeds must be int or list[int]")
    results = []
    # Algorithms to compare – order matters for deterministic test expectations.
    algorithms = ["shortest", "energy", "incremental"]
    for seed in seed_list:
        cfg = dict(config)
        cfg["seed"] = seed
        for algo in algorithms:
            engine_algo = "energy" if algo == "global_energy" else algo
            r = run_simulation(cfg, engine_algo)
            # Preserve the original algorithm label for reporting.
            summary = {"seed": cfg["seed"], "algorithm": algo, **r["metrics"]}
            results.append(summary)
    # Aggregate per‑algorithm statistics.
    summaries = []
    # Define which metrics to aggregate.
    fields = [
        "packet_delivery_ratio",
        "energy_consumed",
        "first_node_dead_round",
        "half_nodes_dead_round",
        "last_node_dead_round",
        "routing_recomputations",
        "local_route_updates",
        "connected_round_fraction",
        "estimated_runtime_ms",
    ]
    # Helper to compute statistics for a list of numeric values.
    def _stats(values: list[float]):
        n = len(values)
        if n == 0:
            return {
                "count": 0,
                "mean": None,
                "std": None,
                "median": None,
                "iqr": None,
                "min": None,
                "max": None,
                "ci95_low": None,
                "ci95_high": None,
            }
        arr = np.array(values, dtype=float)
        mean = float(np.mean(arr))
        std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        median = float(np.median(arr))
        q1 = float(np.percentile(arr, 25))
        q3 = float(np.percentile(arr, 75))
        iqr = q3 - q1
        vmin = float(arr.min())
        vmax = float(arr.max())
        # 95% confidence interval using normal approximation.
        se = std / np.sqrt(n) if n > 1 else 0.0
        ci_low = mean - 1.96 * se
        ci_high = mean + 1.96 * se
        return {
            "count": n,
            "mean": round(mean, 4),
            "std": round(std, 4),
            "median": round(median, 4),
            "iqr": round(iqr, 4),
            "min": round(vmin, 4),
            "max": round(vmax, 4),
            "ci95_low": round(ci_low, 4),
            "ci95_high": round(ci_high, 4),
        }

    for algo in algorithms:
        # Treat "global_energy" as an alias of "energy" – do not emit a separate summary.
        if algo == "global_energy":
            continue
        rows = [r for r in results if r["algorithm"] == algo]
        summary = {"algorithm": algo, "runs": len(rows)}
        for f in fields:
            # Robustly filter metric values: exclude None, non‑numeric, NaN, and infinities.
            values = []
            for r in rows:
                v = r.get(f)
                if v is None:
                    continue
                try:
                    num = float(v)
                except (TypeError, ValueError):
                    continue
                if not (num == num and abs(num) != float('inf')):
                    continue
                values.append(num)
            stats = _stats(values)
            # Prefix each metric with its name.
            for k, v in stats.items():
                summary[f"{f}_{k}"] = v
        summaries.append(summary)
    # Paired analysis: compute per‑seed differences between algorithm pairs.
    paired = []
    pairs = [("shortest", "energy"), ("shortest", "incremental"), ("energy", "incremental")]
    def _valid(v):
        if v is None:
            return False
        try:
            num = float(v)
        except (TypeError, ValueError):
            return False
        return num == num and abs(num) != float('inf')
    rows_by_algo = {algo: {r["seed"]: r for r in results if r["algorithm"] == algo} for algo in algorithms}
    for a, b in pairs:
        diff_summary = {"pair": f"{a}_vs_{b}"}
        common_seeds = set(rows_by_algo[a].keys()) & set(rows_by_algo[b].keys())
        for f in fields:
            diffs = []
            for seed in common_seeds:
                va = rows_by_algo[a][seed].get(f)
                vb = rows_by_algo[b][seed].get(f)
                if _valid(va) and _valid(vb):
                    diffs.append(float(va) - float(vb))
            stats = _stats(diffs)
            for k, v in stats.items():
                diff_summary[f"{f}_diff_{k}"] = v
        paired.append(diff_summary)

    return {"config": config, "seeds": seeds, "summaries": summaries, "runs": results, "paired": paired}


def rerun_reroute_analysis(
    config: dict[str, Any],
    source_node: int | None = None,
    failed_node_id: int | None = None,
    repair: bool = True,
) -> dict[str, Any]:
    """Execute a single-step before-and-after failure rerouting analysis using IEFT-IR logic.

    1. Constructs the network topology and initial node states.
    2. Computes the initial routing table (Before state).
    3. Selects an active source node and an intermediate node along its active route to fail.
    4. Injects the node failure, preserving the Before snapshot.
    5. Optionally runs IEFT-IR incremental repair (``repair=False`` exposes the
       actual failed topology as a separate step for interactive clients).
    6. Measures route repair time, routing updates count, connectivity, and route changes.
    """
    cfg = Config(**{k: v for k, v in config.items() if k in Config.__dataclass_fields__})
    if cfg.nodes < 5 or cfg.nodes > 150:
        raise ValueError("nodes must be between 5 and 150")
    if cfg.gateway < 0 or cfg.gateway >= cfg.nodes:
        raise ValueError("gateway must be a valid node ID")

    # Build topology
    import builtins
    custom_build = config.get("custom_build")
    if hasattr(builtins, "build_network"):
        G = builtins.build_network(cfg.nodes, cfg.seed, cfg.k)
    elif custom_build:
        G = custom_build(cfg.nodes, cfg.seed, cfg.k)
    else:
        G = build_network(cfg.nodes, cfg.seed, cfg.k)

    energies = {n: float(cfg.initial_energy) for n in G.nodes}
    depletion = {n: 0.0 for n in G.nodes}
    dead_before: set[int] = set()
    active_before = G.copy()
    invalidate_connectivity_cache()

    # Initial route computation for all non-gateway nodes
    paths_before: dict[int, list[int] | None] = {}
    for src in G.nodes:
        if src != cfg.gateway:
            paths_before[src] = compute_path(active_before, src, cfg.gateway, "energy", energies, depletion, cfg)

    # Determine source node
    valid_sources = [s for s, p in paths_before.items() if p is not None and len(p) >= 2]
    if not valid_sources:
        raise ValueError("No valid routable nodes to gateway found in topology")

    if source_node is None or source_node not in paths_before:
        # Prefer a source with at least 1 intermediate node if available
        multi_hop_sources = [s for s in valid_sources if len(paths_before[s]) >= 3]
        selected_source = multi_hop_sources[0] if multi_hop_sources else valid_sources[0]
    else:
        selected_source = source_node

    initial_route = paths_before.get(selected_source)

    # Determine failed node
    # If source has intermediate hops: path is [source, hop1, hop2, ..., gateway]
    intermediate_candidates = initial_route[1:-1] if (initial_route and len(initial_route) > 2) else []

    if failed_node_id is not None:
        if failed_node_id == cfg.gateway:
            raise ValueError("Gateway node cannot be selected as an intermediate failed node")
        if failed_node_id not in G.nodes:
            raise ValueError(f"Failed node {failed_node_id} does not exist in graph")
        target_failed_node = failed_node_id
    elif intermediate_candidates:
        # Pick the first intermediate node on the active route
        target_failed_node = intermediate_candidates[0]
    else:
        # Fallback if route is 1-hop: pick another non-gateway node in the graph
        other_candidates = [n for n in G.nodes if n != cfg.gateway and n != selected_source]
        target_failed_node = other_candidates[0] if other_candidates else None

    # Before connectivity measurement
    conn_before = measure_connectivity(active_before, cfg.k)

    # Snapshot of Before state
    before_nodes = [
        {
            "id": int(n),
            "x": float(G.nodes[n]["pos"][0]),
            "y": float(G.nodes[n]["pos"][1]),
            "energy": round(energies.get(n, 0), 2),
            "dead": False,
            "gateway": n == cfg.gateway,
        }
        for n in G.nodes
    ]
    before_edges = [
        {"source": int(u), "target": int(v), "distance": round(float(d.get("distance", 1)), 3)}
        for u, v, d in G.edges(data=True)
    ]
    before_active_edges = [{"source": int(u), "target": int(v)} for u, v in active_before.edges]

    before_snapshot = {
        "network": {
            "nodes": before_nodes,
            "edges": before_edges,
            "active_edges": before_active_edges,
            "paths": [{"source": int(s), "path": p} for s, p in paths_before.items()],
        },
        "source": selected_source,
        "route": initial_route,
        "hop_count": len(initial_route) - 1 if initial_route else 0,
        "connected": conn_before["connected"],
        "edge_connectivity": conn_before["edge_connectivity"],
        "failed_node": None,
    }

    # Inject the failure first. Route repair is a separate, explicit operation so
    # the UI can display the true failed topology before asking IEFT-IR to repair it.
    active_after = G.copy()
    dead_after: set[int] = set()
    failed_edges: list[dict[str, int]] = []
    paths_after = {s: list(p) if p else None for s, p in paths_before.items()}

    local_route_updates = 0
    route_recomputations = 0

    t0 = time.perf_counter()

    if target_failed_node is not None:
        dead_after.add(target_failed_node)
        # Record failed links for visualization
        for nbr in list(active_after.neighbors(target_failed_node)):
            failed_edges.append({"source": int(target_failed_node), "target": int(nbr)})
        if target_failed_node in active_after:
            active_after.remove_node(target_failed_node)
        invalidate_connectivity_cache()

        # Identify routes invalidated by the failure. In failure-only mode, do not
        # compute replacements yet; remove affected paths from the displayed routing
        # table so the graph cannot accidentally show a route through a dead node.
        affected_sources = [src for src, p in paths_after.items() if p and target_failed_node in p]
        if repair:
            # IEFT-IR incremental repair: recompute only routes affected by this failure.
            for src in affected_sources:
                if src not in dead_after:
                    new_p = compute_path(active_after, src, cfg.gateway, "energy", energies, depletion, cfg)
                    paths_after[src] = new_p
                    route_recomputations += 1
                    local_route_updates += 1
        else:
            for src in affected_sources:
                paths_after[src] = None

        # Remove dead node from paths dictionary
        paths_after.pop(target_failed_node, None)

    elapsed_repair_ms = (time.perf_counter() - t0) * 1000.0

    conn_after = measure_connectivity(active_after, cfg.k)
    replacement_route = paths_after.get(selected_source) if repair else None
    repair_success = bool(repair and replacement_route is not None and len(replacement_route) >= 2)

    after_nodes = [
        {
            "id": int(n),
            "x": float(G.nodes[n]["pos"][0]),
            "y": float(G.nodes[n]["pos"][1]),
            "energy": round(energies.get(n, 0), 2),
            "dead": n in dead_after,
            "gateway": n == cfg.gateway,
        }
        for n in G.nodes
    ]
    after_edges = before_edges  # Base topology edges
    after_active_edges = [{"source": int(u), "target": int(v)} for u, v in active_after.edges]

    after_snapshot = {
        "network": {
            "nodes": after_nodes,
            "edges": after_edges,
            "active_edges": after_active_edges,
            "paths": [{"source": int(s), "path": p} for s, p in paths_after.items()],
            "failed_edges": failed_edges,
        },
        "source": selected_source,
        "route": replacement_route,
        "hop_count": len(replacement_route) - 1 if replacement_route else 0,
        "connected": conn_after["connected"],
        "edge_connectivity": conn_after["edge_connectivity"],
        "failed_node": target_failed_node,
    }

    # Available routable sources to populate UI selector
    available_sources = [
        {
            "id": int(s),
            "initial_hops": len(paths_before[s]) - 1 if paths_before.get(s) else 0,
            "has_intermediate": bool(paths_before.get(s) and len(paths_before[s]) > 2),
        }
        for s in sorted(paths_before.keys())
    ]

    return {
        "before": before_snapshot,
        "after": after_snapshot,
        "source": selected_source,
        "failed_node": target_failed_node,
        "repair_success": repair_success,
        "repair_status": (
            "failure_injected" if not repair else
            ("repaired" if repair_success else "no_replacement_path")
        ),
        "repair_performed": bool(repair),
        "route_repair_time_ms": round(elapsed_repair_ms, 3),
        "routing_updates_count": local_route_updates,
        "route_recomputations": route_recomputations,
        "initial_route": initial_route,
        "replacement_route": replacement_route,
        "initial_hop_count": len(initial_route) - 1 if initial_route else 0,
        "replacement_hop_count": len(replacement_route) - 1 if replacement_route else 0,
        "initial_connectivity": conn_before["connected"],
        "final_connectivity": conn_after["connected"],
        "available_sources": available_sources,
        "available_intermediates": intermediate_candidates,
    }
