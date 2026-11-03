from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Any

import networkx as nx

from .models import Node, NetworkConfig, ValidationError
from .topology import build_random_geometric_topology, build_grid_topology


@dataclass
class SimulationState:
    """Encapsulates the mutable state of a mesh network simulation.

    Attributes
    ----------
    cfg: NetworkConfig
        The immutable configuration for this simulation run.
    graph: nx.Graph
        NetworkX graph where each node stores a ``model`` attribute of type
        :class:`Node` and each edge stores a ``distance`` attribute.
    round: int
        Current simulation round (starting at 0).
    events: List[Dict[str, Any]]
        Chronological log of significant events (transmissions, failures,
        energy updates, etc.).
    """

    cfg: NetworkConfig
    graph: nx.Graph = field(init=False)
    round: int = field(default=0)
    events: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Deterministic topology based on the config's seed.
        # For now we default to a random geometric graph.
        self.graph = build_random_geometric_topology(self.cfg)
        # Ensure each node carries a Node model (already done by topology).

    # ---------------------------------------------------------------------
    # Helper accessors
    # ---------------------------------------------------------------------
    def node_model(self, nid: int) -> Node:
        return self.graph.nodes[nid]["model"]

    def is_alive(self, nid: int) -> bool:
        return self.node_model(nid).operational

    # ---------------------------------------------------------------------
    # Energy‑accounting primitives
    # ---------------------------------------------------------------------
    def _energy_costs(self, src: int, dst: int) -> tuple[float, float, float]:
        """Return (tx_cost, rx_cost, distance) for a transmission.

        The cost model mirrors the one used in ``engine.route_weight``.
        """
        if not self.graph.has_edge(src, dst):
            raise ValidationError(f"No link between {src} and {dst}")
        distance = float(self.graph[src][dst].get("distance", 1.0))
        tx = self.cfg.tx_cost * (1.0 + distance * distance)
        rx = self.cfg.rx_cost
        return tx, rx, distance

    def transmit(self, src: int, dst: int) -> None:
        """Simulate a single packet transmission from *src* to *dst*.

        Energy is deducted from both the sender (TX) and the receiver (RX).
        If a node runs out of energy it becomes non‑operational; the event is
        still recorded.
        """
        if not (self.is_alive(src) and self.is_alive(dst)):
            raise ValidationError("Both endpoints must be operational")
        tx, rx, distance = self._energy_costs(src, dst)
        sender = self.node_model(src)
        receiver = self.node_model(dst)
        sender.consume(tx)
        receiver.consume(rx)
        self.events.append({
            "type": "transmit",
            "round": self.round,
            "src": src,
            "dst": dst,
            "distance": distance,
            "tx": tx,
            "rx": rx,
        })

    # ---------------------------------------------------------------------
    # Round management
    # ---------------------------------------------------------------------
    def next_round(self) -> None:
        self.round += 1

    # ---------------------------------------------------------------------
    # Snapshot / serialization helpers (delegated to ``serialization`` module)
    # ---------------------------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        """Return a JSON‑compatible snapshot of the current simulation state.

        The structure mirrors the ``run_simulation`` output for the ``network``
        field, making it easy to plug into existing APIs.
        """
        nodes = [
            {
                "id": nid,
                "x": float(data["pos"][0]),
                "y": float(data["pos"][1]),
                "energy": round(self.node_model(nid).residual_energy, 2),
                "dead": not self.is_alive(nid),
                "gateway": nid == self.cfg.gateway,
            }
            for nid, data in self.graph.nodes(data=True)
        ]
        edges = [
            {
                "source": int(u),
                "target": int(v),
                "distance": round(float(d.get("distance", 1)), 3),
            }
            for u, v, d in self.graph.edges(data=True)
        ]
        return {"nodes": nodes, "edges": edges, "round": self.round}
