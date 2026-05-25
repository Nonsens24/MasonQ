"""End-to-end honest-server simulation of a cloak job.

The cloak layer separates a circuit into ``Sensitive`` subs (handed off as
brickwork patterns) and an unprotected outer skeleton.  In production the
subs are simulated by an untrusted server running on Graphix; the outer
skeleton runs locally on Qiskit.  When you just want a quick check that
your cloaked workflow returns the right answer, you can collapse the whole
thing into a single Qiskit simulation:

  - For each sub, take the MasonQ-decomposed circuit recorded on the
    :class:`~brickwork_transpiler.cloak.blinder.BlindedSub` (the brickwork
    pattern's *semantic* equivalent under an honest server).
  - Splice those decomposed sub-circuits back into the outer skeleton at
    the same splice points the slicer made.
  - Evolve the resulting circuit on a Qiskit ``Statevector``.

This gives the exact same final state the original (uncloaked) circuit
would produce, modulo the brickwork basis lowering that MasonQ performs on
each sub.  It is a *smoke test* of the cloak round-trip, not a test of the
server-side blinding semantics (those require actually running the blinded
Graphix patterns, which is a follow-on milestone).
"""

from __future__ import annotations

from typing import Optional

from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from .blinder import CloakedJob, cloak_compile
from .rsp import RSPClient


def assemble_honest_circuit(job: CloakedJob) -> QuantumCircuit:
    """Reconstruct the equivalent plaintext circuit from a cloak job.

    The output uses each sub's *decomposed* circuit (in the rz/rx/cx/id
    brickwork basis) rather than its original definition.  This matches
    what an honest server's brickwork-pattern execution would produce.
    """
    outer = job.outer_qhe_circuit
    out = QuantumCircuit(outer.num_qubits, outer.num_clbits, name=f"{outer.name}_honest")

    sub_by_id = {sub.slice_id: sub for sub in job.subs}

    for instr in outer.data:
        op = instr.operation
        label = op.label or ""
        if op.name == "barrier" and label.startswith("cloak_sub_"):
            slice_id = int(label.removeprefix("cloak_sub_"))
            sub = sub_by_id[slice_id]
            target_qubits = list(instr.qubits)
            # Map sub-local 0..n-1 onto the global qubits the barrier names.
            out.compose(sub.decomposed_circuit, qubits=target_qubits, inplace=True)
        else:
            out.append(op, list(instr.qubits), list(instr.clbits))
    return out


def simulate_cloaked(
    qc: QuantumCircuit,
    *,
    input_state: Optional[Statevector] = None,
    rsp: Optional[RSPClient] = None,
    rounds: int = 1,
    seed: Optional[int] = None,
    qhe: str = "off",
) -> Statevector:
    """Cloak-compile ``qc`` then simulate it under an honest server.

    Returns the final :class:`~qiskit.quantum_info.Statevector`.  Use this
    to verify your annotated circuit still computes what you expect before
    sending the cloak job to a real server.

    The simulation is honest-only: trap qubits are not exercised, blinded
    measurement angles are not re-derived, and the QOTP keys are passed
    through.  For trap-soundness experiments and pattern-level simulation,
    use the per-sub :meth:`~brickwork_transpiler.result.TranspileResult.simulate_statevector`
    in combination with :func:`~brickwork_transpiler.cloak.verify_session`.
    """
    job = cloak_compile(qc, rsp=rsp, rounds=rounds, seed=seed, qhe=qhe)  # type: ignore[arg-type]
    honest = assemble_honest_circuit(job)
    if input_state is None:
        return Statevector.from_instruction(honest)
    return input_state.evolve(honest)
