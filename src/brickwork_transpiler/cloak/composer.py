"""Stitch blinded sub-patterns and unprotected segments into one job.

The composer walks the outer skeleton produced by
:func:`~brickwork_transpiler.cloak.slicer.slice_circuit`, classifies every
boundary (Type 0 / Type 1 / Type 2 per Lee & Chung 2025 §3), and assembles
the unprotected gate flow.

**QHE is opt-in.** Cloak's product story is "blind only the sensitive
patches, leave the rest cheap" — so by default the composer does *not* track
QOTP keys through the unprotected segment.  In ``qhe="off"`` mode the
server simply sees those gates in the clear and the client treats the
sub-circuit boundary outputs as plaintext.  In ``qhe="qotp"`` mode the
composer threads classical Pauli keys through every Clifford gate (cheap:
just XOR updates; see Lee & Chung Table 1) so the server learns the
*gates* but not the *qubit states* in the unprotected region.  Full QHE
with ``T``-gadgets (one auxiliary qubit + one round-trip per ``T``) is
deliberately not the default — it is what you opt into when even the data
flowing through the unprotected gates must be hidden.

Boundary handling at each splice point is otherwise unchanged: Type 0
folds incoming QOTP keys into the next sub's first measurement layer,
Type 1 passes the sub's output QOTP forward, Type 2 bundles QHE
decryption into the next sub at slice time.
"""

from __future__ import annotations

from typing import List, Literal, Optional, Tuple

import numpy as np
from qiskit import QuantumCircuit

from .qhe import QOTPState, track_qotp_through
from .slicer import SlicePlan

QHEMode = Literal["off", "qotp"]


def compose_outer(
    plan: SlicePlan,
    blinded_subs: List["BlindedSub"],  # noqa: F821 — avoid circular import
    *,
    qotp: QOTPState,
    rng: Optional[np.random.Generator] = None,
    qhe: QHEMode = "off",
) -> Tuple[QuantumCircuit, QOTPState]:
    """Walk the outer skeleton; optionally track QOTP through unprotected gates.

    With ``qhe="off"`` (the default) the unprotected segment is appended
    verbatim and the QOTP state is propagated only through the sensitive
    subs.  With ``qhe="qotp"`` the composer additionally updates the keys
    per Clifford gate; non-Clifford gates in the unprotected segment will
    raise ``NotImplementedError`` in that mode — slice them into a
    ``sensitive(...)`` block or extend :class:`QOTPState`.
    """
    if rng is None:
        rng = np.random.default_rng()

    outer = QuantumCircuit(
        plan.outer_skeleton.num_qubits,
        plan.outer_skeleton.num_clbits,
        name=f"{plan.outer_skeleton.name}_cloak_outer",
    )

    sub_iter = iter(blinded_subs)
    pending_segment = QuantumCircuit(outer.num_qubits, outer.num_clbits)

    def flush_segment(qotp_state: QOTPState) -> QOTPState:
        if len(pending_segment.data) == 0:
            return qotp_state
        if qhe == "qotp":
            plan_out = track_qotp_through(pending_segment, qotp_state, rng=rng)
            new_state = plan_out.final_state
        else:
            new_state = qotp_state
        outer.compose(pending_segment, inplace=True)
        pending_segment.data.clear()
        return new_state

    for instr in plan.outer_skeleton.data:
        op = instr.operation
        if op.name == "barrier" and (op.label or "").startswith("cloak_sub_"):
            qotp = flush_segment(qotp)
            sub = next(sub_iter)
            outer.barrier(instr.qubits, label=f"cloak_sub_{sub.slice_id}")
            qotp = sub.output_qotp
        else:
            pending_segment.append(op, list(instr.qubits), list(instr.clbits))

    qotp = flush_segment(qotp)
    return outer, qotp
