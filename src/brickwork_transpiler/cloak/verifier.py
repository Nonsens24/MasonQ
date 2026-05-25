"""Planar trap & dummy embedding for verifiable BQC over MasonQ patterns.

This module implements the *planar* variant of Fitzsimons & Kashefi 2017
Protocol 3 verification.  In the original paper, soundness is amplified via
the cylinder brickwork state (paper §V); MasonQ is a strictly planar
brickwork transpiler, so we instead obtain amplification by running the
single-trap embedding for multiple independent rounds and demanding *all*
trap outcomes pass.

Per round, one non-input/non-output graph node is designated the **trap**.
All neighbours of that node (within the planar brickwork graph) become
**dummies** prepared in computational-basis eigenstates ``|0>`` or ``|1>``.
The remaining graph nodes are normal *computation* nodes prepared as
``|+_theta>`` and blinded by :mod:`brickwork_transpiler.bfk_encoder`.

The semantic guarantees:

  - Dummy qubits are eigenstates of Z, so CZ-entangling them with the trap
    only contributes a Pauli-Z phase that the client can predict from the
    dummy bits, leaving the trap qubit in ``|+_{theta_trap}>`` after
    entanglement (modulo a known Pauli).
  - Measuring the trap in the angle ``theta_trap`` basis therefore yields a
    deterministic outcome under an honest server; any single-qubit deviation
    on the trap propagates with constant detection probability.

This file provides only the *embedding* (a metadata layer on top of the
existing brickwork pattern).  The actual rewriting of preparation states is
handed off to the RSP layer, and the blinding of computation angles is
delegated to :func:`brickwork_transpiler.bfk_encoder.encode_pattern` with
the dummy/trap nodes excluded from random-theta sampling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np

from ..bfk_encoder import BFKQubitPreparation, encode_pattern


class NodeKind(str, Enum):
    """Role of a graph node in a planar trap-embedded brickwork pattern."""

    COMPUTATION = "computation"
    TRAP = "trap"
    DUMMY = "dummy"


@dataclass
class TrapEmbedding:
    """Per-round trap/dummy assignment for one brickwork pattern."""

    trap_node: Any
    """The graph node carrying the trap qubit."""

    trap_theta: float
    """Pre-randomised ``theta`` for the trap (units of pi, on the BFK grid)."""

    expected_outcome: int
    """Bit the trap measurement must return under an honest server."""

    dummy_bits: Dict[Any, int]
    """For each dummy node, the prepared computational-basis bit (0 or 1)."""

    node_kinds: Dict[Any, NodeKind]
    """Full classification of every node in the brickwork graph."""

    metadata: Dict[str, Any] = field(default_factory=dict)


def _pattern_nodes(pattern: Any) -> List[Any]:
    """Return all graph nodes used by ``pattern`` in a stable order."""
    try:
        return list(pattern.extract_nodes())
    except Exception:
        nodes = set(pattern.input_nodes) | set(pattern.output_nodes)
        for cmd in pattern._Pattern__seq:
            if hasattr(cmd, "node"):
                nodes.add(cmd.node)
            if hasattr(cmd, "nodes"):
                nodes.update(cmd.nodes)
        return sorted(nodes)


def _pattern_neighbours(pattern: Any, node: Any) -> List[Any]:
    """Best-effort neighbour lookup; covers both Graphix and adapter patterns.

    The MasonQ pipeline builds a brickwork graph alongside the pattern; this
    helper consults the pattern's underlying graph if available, and otherwise
    falls back to inspecting entanglement commands in the pattern sequence.
    """
    graph = getattr(pattern, "graph", None)
    if graph is not None and hasattr(graph, "neighbors"):
        try:
            return list(graph.neighbors(node))
        except Exception:
            pass

    neighbours: set = set()
    for cmd in getattr(pattern, "_Pattern__seq", []):
        nodes = getattr(cmd, "nodes", None)
        if nodes and node in nodes:
            neighbours.update(n for n in nodes if n != node)
    return sorted(neighbours)


def _choose_trap_node(
    pattern: Any,
    rng: np.random.Generator,
    forbid: Iterable[Any] = (),
) -> Any:
    """Pick a non-input/non-output node uniformly at random.

    For tiny graphs (where every node is either input or output), fall back
    to *any* non-input node so the embedding still has somewhere to put the
    trap; the test suite exercises this corner case.
    """
    forbid_set = set(forbid)
    inputs = set(getattr(pattern, "input_nodes", []))
    outputs = set(getattr(pattern, "output_nodes", []))

    candidates = [
        n for n in _pattern_nodes(pattern) if n not in inputs and n not in outputs and n not in forbid_set
    ]
    if not candidates:
        candidates = [n for n in _pattern_nodes(pattern) if n not in inputs and n not in forbid_set]
    if not candidates:
        raise ValueError("Pattern has no interior nodes available for a trap.")
    return candidates[int(rng.integers(0, len(candidates)))]


def embed_planar_trap(
    pattern: Any,
    *,
    rng: Optional[np.random.Generator] = None,
    trap_node: Optional[Any] = None,
) -> TrapEmbedding:
    """Pick a trap and label its neighbours as dummies.

    The pattern is *not* mutated.  The returned :class:`TrapEmbedding` is
    metadata that downstream stages (blinder, RSP, verifier) consume.
    """
    if rng is None:
        rng = np.random.default_rng()
    if trap_node is None:
        trap_node = _choose_trap_node(pattern, rng)

    neighbours = _pattern_neighbours(pattern, trap_node)
    trap_theta = float(rng.integers(0, 8)) / 4.0
    dummy_bits = {n: int(rng.integers(0, 2)) for n in neighbours}

    # Honest trap outcome: theta basis on |+_theta> after byproduct-Z
    # corrections from neighbour-dummy bits.  In units of pi, the corrected
    # measurement basis is {|+_theta>, |-_theta>}; an honest server returns
    # 0 modulo the parity of neighbour dummy bits.
    expected_outcome = sum(dummy_bits.values()) & 1

    kinds: Dict[Any, NodeKind] = {}
    for n in _pattern_nodes(pattern):
        if n == trap_node:
            kinds[n] = NodeKind.TRAP
        elif n in dummy_bits:
            kinds[n] = NodeKind.DUMMY
        else:
            kinds[n] = NodeKind.COMPUTATION

    return TrapEmbedding(
        trap_node=trap_node,
        trap_theta=trap_theta,
        expected_outcome=expected_outcome,
        dummy_bits=dummy_bits,
        node_kinds=kinds,
        metadata={"neighbours": list(neighbours)},
    )


def blind_with_trap(
    pattern: Any,
    embedding: TrapEmbedding,
    *,
    rng: Optional[np.random.Generator] = None,
) -> tuple[Any, List[BFKQubitPreparation], List[Dict[str, Any]]]:
    """Apply BFK blinding to ``pattern`` while respecting the trap embedding.

    Dummy nodes are pinned to ``theta = 0`` (they will be prepared in
    ``|0>`` or ``|1>`` by RSP rather than ``|+_theta>``); the trap node is
    pinned to its pre-chosen ``trap_theta``; remaining nodes get random
    ``theta`` via :func:`brickwork_transpiler.bfk_encoder.encode_pattern`.
    """
    if rng is None:
        rng = np.random.default_rng()

    theta_lookup: Dict[Any, float] = {}
    for node, kind in embedding.node_kinds.items():
        if kind is NodeKind.TRAP:
            theta_lookup[node] = embedding.trap_theta
        elif kind is NodeKind.DUMMY:
            theta_lookup[node] = 0.0

    blinded_pattern, info = encode_pattern(
        pattern,
        theta_lookup=theta_lookup,
        rng=rng,
    )

    preparations: List[BFKQubitPreparation] = []
    for node, kind in embedding.node_kinds.items():
        if kind is NodeKind.DUMMY:
            bit = embedding.dummy_bits[node]
            preparations.append(BFKQubitPreparation(node=node, theta=float(bit)))
        elif kind is NodeKind.TRAP:
            preparations.append(BFKQubitPreparation(node=node, theta=embedding.trap_theta))
        else:
            preparations.append(BFKQubitPreparation(node=node, theta=theta_lookup.get(node, 0.0)))

    return blinded_pattern, preparations, info


def check_trap_outcomes(
    embeddings: Sequence[TrapEmbedding],
    measured_outcomes: Sequence[Dict[Any, int]],
) -> bool:
    """Return True iff every round's trap outcome matches its prediction.

    ``measured_outcomes[i][node]`` is the bit the server reported for round
    ``i`` at graph node ``node``.  This routine is intentionally strict: a
    single mismatched trap fails the whole session, as in FK17 §VI.
    """
    if len(embeddings) != len(measured_outcomes):
        raise ValueError("rounds count mismatch between embeddings and outcomes")
    for emb, outcomes in zip(embeddings, measured_outcomes):
        if outcomes.get(emb.trap_node) != emb.expected_outcome:
            return False
    return True
