from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from .pattern_converter import _prepare_graphix_runtime

_prepare_graphix_runtime()

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

    def as_dict(self) -> Dict[str, Any]:
        return {
            "node": self.node,
            "theta": self.theta,
            "theta_radians": self.theta_radians,
            "state": self.state_label,
        }


def _as_float(value: Any) -> float:
    return float(value)


def _is_grid_angle(theta: Any, *, tol: float = 1e-12) -> bool:
    theta_mod = _as_float(theta) % 2.0
    return any(abs(theta_mod - grid_theta) < tol for grid_theta in THETA_GRID)


def _validate_theta_lookup(theta_lookup: Dict[Any, float]) -> None:
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


def _pattern_nodes(pattern: Pattern) -> List[Any]:
    try:
        nodes = list(pattern.extract_nodes())
        if nodes or not pattern._Pattern__seq:
            return nodes
    except Exception:
        pass

    nodes = set(pattern.input_nodes) | set(pattern.output_nodes)
    for cmd in pattern._Pattern__seq:
        nodes.update(_command_nodes(cmd))
    return sorted(nodes)


def _measurement_angle(cmd: M) -> float:
    if hasattr(cmd, "angle"):
        return _as_float(cmd.angle)
    return _as_float(cmd.measurement.angle)


def _measurement_plane(cmd: M) -> Any:
    if hasattr(cmd, "plane"):
        return cmd.plane
    return cmd.measurement.plane


def _blinded_measurement(plane: Any, angle: float) -> Any:
    if isinstance(plane, str):
        plane_name = plane
    else:
        plane_name = plane.name
    return getattr(Measurement, plane_name)(angle)


def _make_m_command(cmd: M, angle: float) -> M:
    plane = _measurement_plane(cmd)
    try:
        return M(cmd.node, _blinded_measurement(plane, angle), set(cmd.s_domain), set(cmd.t_domain))
    except TypeError:
        return M(cmd.node, plane, angle, set(cmd.s_domain), set(cmd.t_domain))


def sample_qubit_preparations(
    pattern: Pattern,
    theta_lookup: Optional[Dict[Any, float]] = None,
    rng: Optional[np.random.Generator] = None,
    *,
    quantum_outputs: bool = False,
    validate_theta_grid: bool = True,
) -> List[BFKQubitPreparation]:
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
    preparations: List[BFKQubitPreparation] = []
    for node in _pattern_nodes(pattern):
        if node in output_nodes:
            theta_lookup[node] = 0.0
        elif node not in theta_lookup:
            theta_lookup[node] = float(rng.integers(0, 8) / 4.0)
        preparations.append(BFKQubitPreparation(node=node, theta=_as_float(theta_lookup[node]) % 2.0))
    return preparations


def encode_pattern(pattern: Pattern,
                theta_lookup: Optional[Dict[Any, float]] = None,
                rng: Optional[np.random.Generator] = None,
                remove_dependencies: bool = False,
                *,
                return_metadata: bool = False,
                quantum_outputs: bool = False,
                validate_theta_grid: bool = True):
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
    new_seq: List[Any] = []
    info_list: List[Dict[str, Any]] = []

    for cmd in new_pat._Pattern__seq:
        if isinstance(cmd, M):
            phi = _measurement_angle(cmd)  # treat as given (φ or already-adapted φ′)

            theta = preparation_by_node[cmd.node].theta

            r = int(rng.integers(0, 2))  # {0,1}

            # compute blinded angle δ in units of π (mod 2)
            delta = (((phi % 2.0) + theta + r)) % 2.0

            # write blinded command with δ
            new_seq.append(_make_m_command(cmd, delta))

            # record metadata (include δ for convenience)
            info_list.append(dict(
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
            ))

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

    new_pat._Pattern__seq = new_seq
    if return_metadata:
        return new_pat, {
            "preparations": [prep.as_dict() for prep in preparations],
            "measurements": info_list,
        }
    return new_pat, info_list
