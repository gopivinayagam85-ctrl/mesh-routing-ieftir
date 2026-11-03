from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set


class ValidationError(ValueError):
    """Raised when a model validation fails."""
    pass


@dataclass
class Node:
    """Represents a mesh network node.

    All validation rules are enforced in ``__post_init__``. ``neighbors`` is
    derived from the underlying graph and therefore stored as a set that can be
    updated by the simulation logic.
    """

    id: int
    type: str  # "sensor" or "gateway"
    x: float
    y: float
    initial_energy: float
    residual_energy: float = field(init=False)
    cumulative_energy: float = field(default=0.0)
    recent_energy: float = field(default=0.0)
    depletion_rate: float = field(default=0.0)
    operational: bool = field(default=True)
    neighbors: Set[int] = field(default_factory=set)
    packets_tx: int = field(default=0)
    packets_rx: int = field(default=0)
    packets_dropped: int = field(default=0)
    forward_count: int = field(default=0)

    def __post_init__(self) -> None:
        if self.initial_energy < 0:
            raise ValidationError("initial_energy must be non‑negative")
        self.residual_energy = self.initial_energy
        if self.type not in {"sensor", "gateway"}:
            raise ValidationError("type must be 'sensor' or 'gateway'")
        # Determine operational status based on initial energy
        self.operational = self.residual_energy > 0
        self._check_energy_consistency()

    def _check_energy_consistency(self) -> None:
        if self.residual_energy < 0:
            raise ValidationError("residual_energy cannot be negative")
        if self.residual_energy > self.initial_energy:
            raise ValidationError("residual_energy cannot exceed initial_energy")
        if self.cumulative_energy < 0:
            raise ValidationError("cumulative_energy cannot be negative")

    def consume(self, amount: float) -> None:
        """Consume *amount* joules of energy.

        Guarantees that residual_energy never becomes negative.
        """
        if amount < 0:
            raise ValidationError("energy consumption must be non‑negative")
        actual = min(self.residual_energy, amount)
        self.residual_energy -= actual
        self.cumulative_energy += actual
        self.recent_energy = actual
        self._check_energy_consistency()
        if self.residual_energy <= 0:
            self.operational = False

    def restore(self, amount: float) -> None:
        if amount < 0:
            raise ValidationError("restore amount must be non‑negative")
        self.residual_energy = min(self.initial_energy, self.residual_energy + amount)
        self.operational = self.residual_energy > 0


@dataclass
class Link:
    """Undirected wireless link between two nodes.

    ``endpoints`` is stored as a sorted tuple to guarantee a canonical order.
    """

    node_u: int
    node_v: int
    status: bool = field(default=True)
    distance: float = field(default=1.0)
    tx_cost: float = field(default=0.0)
    rx_cost: float = field(default=0.0)
    quality: float = field(default=1.0)
    estimated_retx_cost: float = field(default=0.0)
    latency: float | None = None

    def __post_init__(self) -> None:
        if self.node_u == self.node_v:
            raise ValidationError("self‑loops are not allowed")
        if self.distance < 0:
            raise ValidationError("distance cannot be negative")
        if self.tx_cost < 0 or self.rx_cost < 0:
            raise ValidationError("energy costs cannot be negative")
        if not (0 <= self.quality <= 1):
            raise ValidationError("quality must be between 0 and 1")
        if self.node_u > self.node_v:
            self.node_u, self.node_v = self.node_v, self.node_u

    @property
    def endpoints(self) -> tuple[int, int]:
        return (self.node_u, self.node_v)


@dataclass
class NetworkConfig:
    """Configuration for a simulation scenario.
    """

    nodes: int
    tx_range: float = 0.0
    gateway: int = 0
    area_width: float = 100.0
    area_height: float = 100.0
    initial_energy: float = 100.0
    tx_coeff: float = 0.65
    rx_coeff: float = 0.18
    tx_cost: float = 0.0
    rx_cost: float = 0.0
    link_quality: float = 1.0
    seed: int = 0
    max_attempts: int = 5

    def __post_init__(self) -> None:
        if not (1 <= self.nodes <= 150):
            raise ValidationError("nodes must be between 1 and 150")
        if not (0 <= self.gateway < self.nodes):
            raise ValidationError("gateway must be a valid node id")
        if self.initial_energy <= 0:
            raise ValidationError("initial_energy must be positive")
        if self.tx_range <= 0:
            raise ValidationError("tx_range must be positive")
        if not (0 <= self.link_quality <= 1):
            raise ValidationError("link_quality must be between 0 and 1")
        if self.max_attempts < 1:
            raise ValidationError("max_attempts must be at least 1")
