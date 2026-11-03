from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Tuple, Dict

import networkx as nx

from .models import Node, NetworkConfig, ValidationError


def _add_node_to_graph(G: nx.Graph, node_id: int, cfg: NetworkConfig) -> None:
    """Add a node with random position to the graph.

    The position is stored under the ``pos`` attribute as a ``(x, y)`` tuple.
    """
    # Deterministic positions using the global random module (seed already set by caller)
    x = random.random()
    y = random.random()
    G.add_node(node_id, pos=(x, y))
    # Store a Node model instance for later state handling
    G.nodes[node_id]["model"] = Node(
        id=node_id,
        type="gateway" if node_id == cfg.gateway else "sensor",
        x=x,
        y=y,
        initial_energy=cfg.initial_energy,
    )


def build_random_geometric_topology(cfg: NetworkConfig) -> nx.Graph:
    """Create a random geometric graph.

    * All ``cfg.nodes`` nodes are placed uniformly in the unit square.
    * An edge is added when Euclidean distance ≤ ``cfg.tx_range``.
    * ``cfg.seed`` is used to seed the global ``random`` module for reproducibility.
    * Returned graph has node attribute ``pos`` (tuple) and ``model`` (Node).
    """
    if cfg.nodes < 1:
        raise ValidationError("At least one node required")
    random.seed(cfg.seed)
    G = nx.Graph()
    for nid in range(cfg.nodes):
        _add_node_to_graph(G, nid, cfg)
    # Add edges based on distance
    nodes = list(G.nodes(data=True))
    for i, (u, data_u) in enumerate(nodes):
        for v, data_v in nodes[i + 1 :]:
            ux, uy = data_u["pos"]
            vx, vy = data_v["pos"]
            d = math.dist((ux, uy), (vx, vy))
            if d <= cfg.tx_range:
                G.add_edge(u, v, distance=d)
    return G


def build_grid_topology(cfg: NetworkConfig) -> nx.Graph:
    """Create a rectangular grid topology.

    Nodes are placed on a square lattice whose side length is ``ceil(sqrt(nodes))``.
    Adjacent nodes (horizontal/vertical) are connected if the Euclidean distance
    does not exceed ``cfg.tx_range`` (which defaults to a large value for a grid).
    The positions are normalized to the unit square.
    """
    if cfg.nodes < 1:
        raise ValidationError("At least one node required")
    random.seed(cfg.seed)  # deterministic but not used for positions
    side = math.ceil(math.sqrt(cfg.nodes))
    G = nx.Graph()
    # Place nodes on a grid; spacing of 1/side to stay inside unit square
    spacing = 1.0 / max(side - 1, 1)
    nid = 0
    positions: List[Tuple[float, float]] = []
    for row in range(side):
        for col in range(side):
            if nid >= cfg.nodes:
                break
            x = col * spacing
            y = row * spacing
            G.add_node(nid, pos=(x, y))
            G.nodes[nid]["model"] = Node(
                id=nid,
                type="gateway" if nid == cfg.gateway else "sensor",
                x=x,
                y=y,
                initial_energy=cfg.initial_energy,
            )
            positions.append((x, y))
            nid += 1
        if nid >= cfg.nodes:
            break
    # Connect orthogonal neighbours
    spacing = 1.0 / max(side - 1, 1)
    for u in G.nodes:
        ux, uy = G.nodes[u]["pos"]
        for v in G.nodes:
            if u >= v:
                continue
            vx, vy = G.nodes[v]["pos"]
            d = math.dist((ux, uy), (vx, vy))
            # Add edge only for immediate orthogonal neighbours (distance equals spacing) and within tx_range
            if d <= cfg.tx_range and (
                (math.isclose(ux, vx) and math.isclose(d, spacing))
                or (math.isclose(uy, vy) and math.isclose(d, spacing))
            ):
                G.add_edge(u, v, distance=d)
    return G
