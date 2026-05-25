"""How much of the circuit actually runs blindly?

When you cloak a circuit, the resource that matters to a customer is
*the fraction of the work that ends up on the brickwork graph under UBQC*.
Cloak's pitch is "small patches, cheap", and this module is what lets a
user check whether their annotation actually matches that promise.

Two numbers are reported:

  - **Gate share** — what fraction of the user's *source* circuit ended
    up inside a ``Sensitive`` block.  Counted as
    ``gates_in_sensitive_blocks / total_gates_after_unfolding``.  This is
    the easy-to-interpret headline: "62% of your circuit is hidden".

  - **Brickwork-graph share** — what fraction of the *server-side cost*
    (measured in brickwork-graph nodes × trap rounds) is blind work.
    Gate counts are not comparable to graph-node counts directly because
    every blinded gate explodes into roughly ``4 * brick_columns + 1``
    measurement layers, so this lets you see the real cloud bill.

Both numbers are exposed:

  - As a :class:`BlindShare` dataclass returned by
    :func:`compute_blind_share`.
  - Stored on :class:`CloakedJob.metadata['blind_share']` so the CLI and
    downstream tooling can print it.
  - Included as a human-readable line in
    :func:`brickwork_transpiler.cloak.summarize_cloaked`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Union

from qiskit import QuantumCircuit

from .annotations import Sensitive


@dataclass(frozen=True)
class BlindShare:
    """Fraction of work that runs blindly under UBQC on the brickwork graph."""

    gates_blind: int
    """Gates that live inside a ``Sensitive`` block in the source circuit."""

    gates_clear: int
    """Source-circuit gates that run unprotected on the server."""

    @property
    def gates_total(self) -> int:
        return self.gates_blind + self.gates_clear

    @property
    def gate_fraction(self) -> float:
        """``gates_blind / gates_total``; ``0.0`` for an empty circuit."""
        total = self.gates_total
        return float(self.gates_blind) / total if total else 0.0

    # Optional brickwork-graph cost breakdown (only populated post-compile).
    graph_nodes_per_sub: List[int] = field(default_factory=list)
    """Brickwork graph nodes for each sensitive sub, one round each."""

    rounds: int = 1
    """Trap-round multiplier; total blind nodes = sum(graph_nodes_per_sub) * rounds."""

    @property
    def graph_nodes_total(self) -> int:
        return sum(self.graph_nodes_per_sub) * self.rounds

    def format(self) -> str:
        """Return a one-line human-readable summary."""
        pct = 100.0 * self.gate_fraction
        line = (
            f"blind share: {pct:5.1f}% of source gates "
            f"({self.gates_blind}/{self.gates_total})"
        )
        if self.graph_nodes_per_sub:
            line += (
                f"; {self.graph_nodes_total} brickwork-graph nodes total "
                f"across {len(self.graph_nodes_per_sub)} sub(s) × {self.rounds} round(s)"
            )
        return line


def _count_source_gates(qc: QuantumCircuit) -> tuple[int, int]:
    """Return ``(gates_blind, gates_clear)`` for a source circuit.

    ``Sensitive`` blocks contribute their *inner* gate count to ``blind``;
    every other top-level instruction contributes one to ``clear``.
    """
    blind = 0
    clear = 0
    for instr in qc.data:
        op = instr.operation
        if isinstance(op, Sensitive):
            # Count the inner body's gates as the "blind work".
            blind += len(op.sensitive_body.data)
        else:
            clear += 1
    return blind, clear


def compute_blind_share(
    target: Union[QuantumCircuit, "CloakedJob"],  # noqa: F821 — avoid cycle
) -> BlindShare:
    """Compute the blind share for either a source circuit or a CloakedJob.

    The source-circuit form is cheap and uses only the gate-count heuristic.
    The CloakedJob form additionally reports brickwork-graph node counts
    from MasonQ's :class:`~brickwork_transpiler.resources.ResourceEstimate`
    when those are available.
    """
    if isinstance(target, QuantumCircuit):
        blind, clear = _count_source_gates(target)
        return BlindShare(gates_blind=blind, gates_clear=clear)

    # CloakedJob path — we accept by duck typing to avoid a circular import.
    job = target
    blind = sum(len(sub.decomposed_circuit.data) for sub in job.subs)

    # Count outer ops, excluding our own placeholder barriers.
    clear = 0
    for instr in job.outer_qhe_circuit.data:
        op = instr.operation
        if op.name == "barrier" and (op.label or "").startswith("cloak_sub_"):
            continue
        clear += 1

    graph_nodes: List[int] = []
    for sub in job.subs:
        res = _sub_graph_nodes(sub)
        if res is not None:
            graph_nodes.append(res)

    rounds = int(job.metadata.get("rounds", 1)) if hasattr(job, "metadata") else 1

    return BlindShare(
        gates_blind=blind,
        gates_clear=clear,
        graph_nodes_per_sub=graph_nodes,
        rounds=rounds,
    )


def _sub_graph_nodes(sub: "BlindedSub") -> Optional[int]:  # noqa: F821
    """Best-effort lookup of brickwork-graph node count from a BlindedSub.

    We avoid re-transpiling: if the sub does not already carry a resource
    estimate, return ``None`` rather than pay that cost again.
    """
    res = getattr(sub, "resources", None)
    if res is None:
        return None
    return int(getattr(res, "graph_nodes", 0)) or None
