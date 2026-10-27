"""BFK Protocol-1 encoding of a whole brickwork pattern.

Alice prepares every graph qubit as |+_theta> with theta drawn from the
pi/4 grid and blinds each measurement angle phi to delta = phi + theta + r
(mod 2, in units of pi). The returned pattern carries Bob's blinded angles;
the metadata records Alice's theta and r and the copied dependency domains.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
from graphix import Pattern
from graphix.command import M, X, Z
from graphix.measurements import Measurement

THETA_GRID = tuple(k / 4.0 for k in range(8))


@dataclass(frozen=True)
class BFKQubitPreparation:
    """Alice's Protocol-1 qubit preparation, with angles in units of pi."""

    node: Any
    theta: float

    @property
    def theta_radians(self) -> float:
        return float(np.pi * self.theta)

    @property
    def state_label(self) -> str:
        return f"|+_{{{self.theta}pi}}>"

    def as_dict(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "theta": self.theta,
            "theta_radians": self.theta_radians,
            "state": self.state_label,
        }


def _is_grid_angle(theta: Any, *, tol: float = 1e-12) -> bool:
    theta_mod = float(theta) % 2.0
    return any(abs(theta_mod - grid_theta) < tol for grid_theta in THETA_GRID)


def _validate_theta_lookup(theta_lookup: dict[Any, float]) -> None:
    invalid = {node: theta for node, theta in theta_lookup.items() if not _is_grid_angle(theta)}
    if invalid:
        raise ValueError(
            "BFK preparation angles must be multiples of pi/4 in units of pi. "
            f"Invalid theta values: {invalid}"
        )


def _command_nodes(cmd: Any) -> Iterable[Any]:
    if hasattr(cmd, "node"):
        yield cmd.node
    if hasattr(cmd, "nodes"):
        yield from cmd.nodes


def _pattern_nodes(pattern: Pattern) -> list[Any]:
    """Return the nodes of `pattern`.

    For a pattern built by Graphix these are its prepared nodes. A hand-built
    pattern without N commands falls back to every node its inputs, outputs
    or commands mention.
    """
    prepared_nodes = getattr(pattern, "nodes", None) or pattern.extract_nodes  # renamed in Graphix 0.4
    try:
        nodes = prepared_nodes()
    except Exception:  # hand-built patterns may hold commands Graphix does not know
        nodes = set()
    if nodes or len(pattern) == 0:
        return list(nodes)

    nodes = set(pattern.input_nodes) | set(pattern.output_nodes)
    for cmd in pattern:
        nodes.update(_command_nodes(cmd))
    return sorted(nodes)


def _blinded_m(cmd: M, delta: float) -> M:
    """Copy of the measurement command `cmd` with its angle replaced by `delta`."""
    plane = cmd.measurement.to_bloch().plane
    measurement = getattr(Measurement, plane.name)(delta)
    return M(cmd.node, measurement, set(cmd.s_domain), set(cmd.t_domain))


def sample_qubit_preparations(
    pattern: Pattern,
    theta_lookup: dict[Any, float] | None = None,
    rng: np.random.Generator | None = None,
    *,
    quantum_outputs: bool = False,
    validate_theta_grid: bool = True,
) -> list[BFKQubitPreparation]:
    """Sample Alice's BFK qubit encodings for the graph qubits.

    Protocol 1 prepares every graph qubit as ``|+_theta>`` with theta chosen
    uniformly from ``{0, pi/4, ..., 7pi/4}``.  If ``quantum_outputs`` is true,
    output nodes are prepared as ``|+>`` as in Protocol 3.
    """
    if rng is None:
        rng = np.random.default_rng()
    if theta_lookup is None:
        theta_lookup = {}
    if validate_theta_grid:
        _validate_theta_lookup(theta_lookup)

    output_nodes = set(pattern.output_nodes) if quantum_outputs else set()
    preparations: list[BFKQubitPreparation] = []
    for node in _pattern_nodes(pattern):
        if node in output_nodes:
            theta_lookup[node] = 0.0
        elif node not in theta_lookup:
            theta_lookup[node] = float(rng.integers(0, 8) / 4.0)
        preparations.append(BFKQubitPreparation(node=node, theta=float(theta_lookup[node]) % 2.0))
    return preparations


def encode_pattern(
    pattern: Pattern,
    theta_lookup: dict[Any, float] | None = None,
    rng: np.random.Generator | None = None,
    remove_dependencies: bool = False,
    *,
    return_metadata: bool = False,
    quantum_outputs: bool = False,
    validate_theta_grid: bool = True,
):
    """
    Blind each measurement angle δ = φ' + θ + r (mod 2), all in units of π.

    The returned pattern contains Bob's blinded measurement angles.  The
    measurement log records Alice's sampled ``r`` bit, the prepared
    ``|+_theta>`` state for that node, and copied dependency domains.  When
    ``return_metadata`` is true, the second return value is a dictionary with
    both ``"preparations"`` and ``"measurements"`` entries.
    """
    if rng is None:
        rng = np.random.default_rng()
    if theta_lookup is None:
        theta_lookup = {}
    if validate_theta_grid:
        _validate_theta_lookup(theta_lookup)

    preparations = sample_qubit_preparations(
        pattern,
        theta_lookup=theta_lookup,
        rng=rng,
        quantum_outputs=quantum_outputs,
        validate_theta_grid=False,
    )
    preparation_by_node = {prep.node: prep for prep in preparations}

    new_pat = deepcopy(pattern)
    new_seq: list[Any] = []
    info_list: list[dict[str, Any]] = []

    for cmd in new_pat:
        if isinstance(cmd, M):
            phi = float(cmd.measurement.to_bloch().angle)  # φ, or an already-adapted φ′
            theta = preparation_by_node[cmd.node].theta
            r = int(rng.integers(0, 2))  # {0,1}
            delta = ((phi % 2.0) + theta + r) % 2.0

            new_seq.append(_blinded_m(cmd, delta))
            info_list.append(
                dict(
                    node=cmd.node,
                    phi=phi,
                    theta=theta,
                    r=r,
                    delta=delta,
                    preparation=preparation_by_node[cmd.node].as_dict(),
                    outcome_flip=r,
                    x_byproducts=set(),
                    z_byproducts=set(),
                    s_domain=set(cmd.s_domain),
                    t_domain=set(cmd.t_domain),
                )
            )

        elif isinstance(cmd, X):
            if info_list:
                info_list[-1]["x_byproducts"].add(cmd.node)
            if not remove_dependencies:
                new_seq.append(cmd)

        elif isinstance(cmd, Z):
            if info_list:
                info_list[-1]["z_byproducts"].add(cmd.node)
            if not remove_dependencies:
                new_seq.append(cmd)

        else:
            new_seq.append(cmd)

    # Graphix offers no public way to replace the command list without
    # re-validating it against the prepared nodes, so write the private field.
    new_pat._Pattern__seq = new_seq
    if return_metadata:
        return new_pat, {
            "preparations": [prep.as_dict() for prep in preparations],
            "measurements": info_list,
        }
    return new_pat, info_list
