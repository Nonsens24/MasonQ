"""Measurement-angle concealment — a few hidden angles, a big entangled fabric.

VEIL design pattern #5: in MBQC, the computational semantics live in
the *measurement angles*.  A tiny set of hidden angles can completely
change the meaning of a much larger entangled-graph computation.
Cloak the angles, leave the entangling fabric public.

This is the most natural fit for MasonQ's brickwork pipeline: the
brickwork graph is built deterministically from the gate structure, but
the measurement angles are precisely what cloak's BFK encoder
randomises.  The customer-side semantic payload is therefore minimal —
``O(k)`` hidden rotation angles for an ``O(k · d)`` public lattice.

Run with:
    python examples/cloak/patterns/14_angle_concealment.py
"""

from __future__ import annotations

from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import (
    cloak_compile,
    sensitive,
    simulate_cloaked,
    summarize_cloaked,
)


# Four rotation angles control the semantics of the whole circuit.
HIDDEN_ANGLES = [0.42, -0.31, 0.18, -0.55]


def build_circuit(*, fabric_layers: int = 3) -> QuantumCircuit:
    qc = QuantumCircuit(4, name="angle-concealment")
    qc.h([0, 1, 2, 3])

    # PUBLIC: entangling fabric.  Generic, well-studied, the structure
    # leaks nothing about what the circuit computes — because the
    # answer depends entirely on the angles applied at the boundary.
    for _ in range(fabric_layers):
        qc.cx(0, 1)
        qc.cx(2, 3)
        qc.cx(1, 2)
        qc.h([0, 1, 2, 3])

    # PRIVATE: the proprietary angle set.  Four rotation parameters
    # determine the readout distribution over the entire fabric.
    with sensitive(qc, [0, 1, 2, 3], label="hidden-angles") as angles:
        for q, theta in enumerate(HIDDEN_ANGLES):
            angles.rz(theta, q)

    return qc


qc = build_circuit()


if __name__ == "__main__":
    print(summarize_cloaked(qc))
    job = cloak_compile(qc, rounds=2, seed=0)
    print(job.metadata["blind_share"].format())

    state = simulate_cloaked(qc, seed=0)
    print("\nPer-qubit <Z> after fabric + hidden angles:")
    for q in range(qc.num_qubits):
        z = 0.0
        for i, amp in enumerate(state.data):
            bit = (i >> (qc.num_qubits - 1 - q)) & 1
            z += (1.0 if bit == 0 else -1.0) * abs(amp) ** 2
        print(f"  q{q}: {z:+.4f}")
