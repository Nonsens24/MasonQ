"""Sparse verification anchors — hidden integrity probes.

VEIL design pattern #6: insert small confidential anchors into an
otherwise public computation so that a server who tampers with the
result cannot fabricate a consistent output.  The anchors are tiny
sub-circuits whose expected post-state is known only to the client;
when the server deviates, anchor outcomes drift away from prediction.

Cloak's planar trap embedding already implements an analogous idea at
the *brickwork-graph* level (the `rounds=k` soundness amplifier).  This
example shows the user-circuit-level analogue: sparse client-private
anchors woven into a larger public computation.  The two layers
compose — graph-level traps catch server-side measurement deviations,
user-level anchors catch deviations at the circuit-semantic level.

Run with:
    python examples/cloak/patterns/15_verification_anchors.py
"""

from __future__ import annotations

from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import (
    cloak_compile,
    sensitive,
    simulate_cloaked,
    summarize_cloaked,
)


ANCHOR_COMMITMENT = 0.61  # angle known only to the client


def build_circuit() -> QuantumCircuit:
    qc = QuantumCircuit(4, name="verification-anchors")  # 3 compute + 1 anchor

    # PUBLIC computation — the workload the cloud is paid to run.
    qc.h([0, 1, 2])
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.ry(0.30, 0)
    qc.ry(0.30, 1)
    qc.ry(0.30, 2)
    qc.h([0, 1, 2])

    # PRIVATE: sparse hidden anchor.  Entangles a client-only commitment
    # angle into the computation; the client checks the anchor qubit's
    # expected statistics on return.
    with sensitive(qc, [2, 3], label="hidden-anchor") as anchor:
        anchor.cx(0, 1)
        anchor.rz(ANCHOR_COMMITMENT, 1)
        anchor.cx(0, 1)

    return qc


qc = build_circuit()


if __name__ == "__main__":
    print(summarize_cloaked(qc))
    job = cloak_compile(qc, rounds=3, seed=0)
    print(job.metadata["blind_share"].format())

    state = simulate_cloaked(qc, seed=0)
    anchor_p1 = sum(
        abs(amp) ** 2 for i, amp in enumerate(state.data) if (i >> 0) & 1
    )
    print(f"\nAnchor qubit P(|1>): {anchor_p1:.4f} (client-known expectation)")
