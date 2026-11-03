# backend/simulation/routing.py
"""Baseline routing algorithms for the mesh simulation.

Provides three deterministic routing functions that operate on a
`networkx.Graph` without mutating it:

* ``shortest_path`` – selects the route with the smallest hop count
  (or, when edge weights are present, the smallest sum of ``distance``).
* ``energy_aware_path`` – selects a route that minimises a cost function
  incorporating transmission energy and the residual energy of each
  intermediate node. The cost function matches the one used in
  ``engine.compute_path`` when ``mode='energy'``.
* ``global_energy_routing`` – identical to ``energy_aware_path`` but
  conceptually represents the *global recomputation* policy used by the
  simulation engine. It simply forwards to ``energy_aware_path``; the
  engine decides when to call it.

All functions return ``list[int] | None`` where ``None`` indicates that a
path cannot be found (e.g., source or gateway missing, graph disconnected,
or a dead node on the route). The implementation does **not** mutate the
graph.
"""

from __future__ import annotations

from typing import List, Optional, Set, Dict

import networkx as nx

# The core cost function lives in ``engine.compute_path``.  We import it to
# guarantee identical behaviour between the routing helpers and the
# simulation engine.
from engine import compute_path, Config


def _validate_nodes(
    G: nx.Graph, source: int, gateway: int, dead: Set[int]
) -> bool:
    """Return ``True`` if ``source`` and ``gateway`` are usable.

    A node is unusable if it is absent from the graph or listed in the
    ``dead`` set.  The function deliberately performs *no* side‑effects.
    """
    if source not in G or gateway not in G:
        return False
    if source in dead or gateway in dead:
        return False
    return True


def shortest_path(
    G: nx.Graph,
    source: int,
    gateway: int,
    energies: Dict[int, float] | None = None,
    depletion: Dict[int, float] | None = None,
    cfg: Config | None = None,
    dead: Set[int] | None = None,
) -> Optional[List[int]]:
    """Return the hop‑minimal path from ``source`` to ``gateway``.

    The function forwards to :func:`engine.compute_path` with ``mode='shortest'``.
    ``energies``/``depletion``/``cfg`` are required by ``compute_path`` but are
    ignored for the hop‑count metric; callers may pass empty dictionaries.
    ``dead`` is a set of nodes that must not appear on the path.
    """
    dead = dead or set()
    if not _validate_nodes(G, source, gateway, dead):
        return None
    path = compute_path(
        G, source, gateway, "shortest", energies or {}, depletion or {}, cfg or Config()
    )
    if path and any(node in dead for node in path):
        return None
    return path


def energy_aware_path(
    G: nx.Graph,
    source: int,
    gateway: int,
    energies: Dict[int, float],
    depletion: Dict[int, float],
    cfg: Config,
    dead: Set[int] | None = None,
) -> Optional[List[int]]:
    """Return a path that minimises the energy‑aware cost function.

    The cost function matches ``engine.route_weight`` when ``mode='energy'``.
    Nodes listed in ``dead`` are treated as unavailable; the function will
    return ``None`` if the resulting path would have to traverse a dead node.
    """
    dead = dead or set()
    if not _validate_nodes(G, source, gateway, dead):
        return None
    path = compute_path(G, source, gateway, "energy", energies, depletion, cfg)
    if path and any(node in dead for node in path):
        return None
    return path


def global_energy_routing(
    G: nx.Graph,
    source: int,
    gateway: int,
    energies: Dict[int, float],
    depletion: Dict[int, float],
    cfg: Config,
    dead: Set[int] | None = None,
) -> Optional[List[int]]:
    """Alias for :func:`energy_aware_path`.

    In the current architecture the simulation engine decides *when* to call
    this function (i.e., after any state change). The function itself does not
    perform any additional recomputation logic; it simply forwards to the
    energy‑aware implementation to keep the cost model consistent.
    """
    return energy_aware_path(G, source, gateway, energies, depletion, cfg, dead)
