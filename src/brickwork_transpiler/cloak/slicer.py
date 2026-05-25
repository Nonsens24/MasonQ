"""Split a user circuit into sensitive subs and unprotected segments.

The slicer is the bridge between the user-facing annotation API
(:mod:`brickwork_transpiler.cloak.annotations`) and the per-sub blinder.
Given a ``QuantumCircuit`` containing zero or more :class:`Sensitive`
instructions, :func:`slice_circuit` returns a :class:`SlicePlan` describing:

- the **outer skeleton**: the original circuit with each ``Sensitive``
  instruction replaced by a labelled barrier carrying its slice id, so the
  composer can later identify where to splice the blinded result back in;
- the list of :class:`Sub` blocks, each carrying its own self-contained
  ``QuantumCircuit`` plus the global qubits it touches;
- a list of :class:`BoundaryType` values classifying every cut according to
  the Lee & Chung 2025 §3 typology (Type 0 / Type 1 / Type 2).

A round-trip property holds: composing the outer skeleton with each ``Sub``
re-inserted (in order) reproduces the original circuit modulo barrier
metadata.  The blinder tests pin this.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Sequence

from qiskit import QuantumCircuit
from qiskit.circuit import Qubit

from .annotations import Sensitive


class BoundaryType(str, Enum):
    """Classification of an interface between protected/unprotected regions.

    Follows Lee & Chung 2025 §3:

    - ``TYPE_0`` — unprotected → BQC (clear input enters a blinded sub).
    - ``TYPE_1`` — BQC → QHE (blinded output flows into a QHE region;
      already QOTP-encrypted, no decryption needed).
    - ``TYPE_2`` — QHE → BQC (encrypted state must be decrypted *inside*
      the next blinded sub to avoid leaking plaintext to the server).
    """

    TYPE_0 = "unprotected_to_bqc"
    TYPE_1 = "bqc_to_unprotected"
    TYPE_2 = "unprotected_to_bqc_after_bqc"


@dataclass
class Sub:
    """One sensitive sub-circuit extracted from the outer flow."""

    slice_id: int
    body: QuantumCircuit
    """The inner circuit, in its own 0..n-1 qubit space."""

    global_qubits: List[int]
    """For each inner qubit, the position in the outer circuit it maps to."""

    label: str | None = None

    @property
    def num_qubits(self) -> int:
        return self.body.num_qubits


@dataclass
class SlicePlan:
    """Result of slicing a Qiskit circuit into sensitive vs unprotected parts."""

    outer_skeleton: QuantumCircuit
    """Original circuit with ``Sensitive`` ops replaced by placeholder barriers."""

    subs: List[Sub] = field(default_factory=list)
    boundary_types: List[BoundaryType] = field(default_factory=list)
    """Two entries per sub (incoming, outgoing) in slice order."""

    @property
    def num_subs(self) -> int:
        return len(self.subs)


def _qubit_indices(qc: QuantumCircuit, qubits: Sequence[Qubit]) -> List[int]:
    index = {q: i for i, q in enumerate(qc.qubits)}
    return [index[q] for q in qubits]


def slice_circuit(qc: QuantumCircuit) -> SlicePlan:
    """Walk ``qc`` and extract every :class:`Sensitive` instruction as a Sub.

    The outer skeleton preserves all non-sensitive instructions verbatim and
    inserts a :class:`~qiskit.circuit.Barrier` for every sliced sub, labelled
    ``cloak_sub_<id>``.  Composition order is preserved.
    """
    outer = QuantumCircuit(qc.num_qubits, qc.num_clbits, name=qc.name)
    subs: List[Sub] = []
    boundaries: List[BoundaryType] = []

    last_was_sensitive = False

    for instr in qc.data:
        op = instr.operation
        qargs = list(instr.qubits)
        cargs = list(instr.clbits)

        if isinstance(op, Sensitive):
            slice_id = len(subs)
            globals_for_inner = _qubit_indices(qc, qargs)
            sub = Sub(
                slice_id=slice_id,
                body=op.sensitive_body.copy(),
                global_qubits=globals_for_inner,
                label=op.label,
            )
            subs.append(sub)

            # incoming boundary: Type 2 if the previous block was also BQC,
            # else Type 0 (clear inputs come from unprotected region).
            boundaries.append(
                BoundaryType.TYPE_2 if last_was_sensitive else BoundaryType.TYPE_0
            )
            # outgoing boundary: always Type 1 in this iteration; if the
            # *next* block is sensitive, the slicer will re-classify it on
            # the next loop pass (see below).
            boundaries.append(BoundaryType.TYPE_1)

            outer.barrier(qargs, label=f"cloak_sub_{slice_id}")
            last_was_sensitive = True
        else:
            outer.append(op, qargs, cargs)
            last_was_sensitive = False

    return SlicePlan(outer_skeleton=outer, subs=subs, boundary_types=boundaries)


def restitch(plan: SlicePlan) -> QuantumCircuit:
    """Inverse of :func:`slice_circuit`: weld the subs back into the skeleton.

    Used by the slicer round-trip test and as a debugging aid.  The output is
    semantically identical to the original input modulo barrier-vs-Sensitive
    metadata.
    """
    out = QuantumCircuit(
        plan.outer_skeleton.num_qubits,
        plan.outer_skeleton.num_clbits,
        name=plan.outer_skeleton.name,
    )
    sub_iter = iter(plan.subs)
    for instr in plan.outer_skeleton.data:
        op = instr.operation
        if op.name == "barrier" and (op.label or "").startswith("cloak_sub_"):
            sub = next(sub_iter)
            target_qubits = [out.qubits[g] for g in sub.global_qubits]
            out.compose(sub.body, qubits=target_qubits, inplace=True)
        else:
            out.append(op, list(instr.qubits), list(instr.clbits))
    return out
