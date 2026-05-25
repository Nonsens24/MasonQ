"""Pattern #8 — Hidden parameter injection / schedule.

VEIL design pattern #8: the public circuit *structure* (the ansatz) is
well-known, but the *schedule* of parameter updates over training or
optimisation steps is the IP.  Each step's parameters are hidden; the
ansatz between them is the generic public version.

This pattern hides the **training trajectory**, with each step being
one cloaked patch in time.  In production this is what a variational
training loop looks like — the cloud server compiles the public
ansatz once and runs it many times, while the client feeds in
proprietary parameters each iteration.  Each parameter set is a tiny
cloaked patch; the cumulative IP across the schedule can be enormous.

Distinct from:

  - Pattern ``14_angle_concealment.py``, which hides a single fixed
    angle set on a fixed circuit.  Pattern #8 hides the *update
    trajectory* across multiple time steps.
  - Pattern ``13_state_injection.py``, which hides a prepared state
    rather than per-step parameter values.

Run with:
    python examples/cloak/patterns/17_parameter_schedule.py
"""

from __future__ import annotations

from typing import Sequence

from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import (
    cloak_compile,
    sensitive,
    simulate_cloaked,
    summarize_cloaked,
)


# Proprietary parameter trajectory — values updated each optimisation
# step.  In production these arrive from the client's classical
# optimiser (Adam, COBYLA, gradient descent) and reflect everything
# the optimiser has learned about the loss landscape so far.  None of
# this is shared with the cloud provider.
HIDDEN_SCHEDULE: list[list[float]] = [
    [0.31, -0.42, 0.18],   # step 1
    [0.45, -0.20, 0.30],   # step 2
    [0.50, -0.15, 0.35],   # step 3
    [0.52, -0.13, 0.37],   # step 4 — converging
]


def _public_ansatz_layer(qc: QuantumCircuit) -> None:
    """PUBLIC: one layer of generic hardware-efficient ansatz."""
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.h([0, 1, 2])


def _step(qc: QuantumCircuit, params: Sequence[float], step_index: int) -> None:
    """One iteration: public ansatz layer + cloaked parameter update."""
    _public_ansatz_layer(qc)

    with sensitive(qc, [0, 1, 2], label=f"params-step-{step_index}") as block:
        for q, theta in enumerate(params):
            block.rz(float(theta), q)


def build_circuit() -> QuantumCircuit:
    qc = QuantumCircuit(3, name="parameter-schedule")
    qc.h([0, 1, 2])
    for step, params in enumerate(HIDDEN_SCHEDULE):
        _step(qc, params, step)
    return qc


qc = build_circuit()


if __name__ == "__main__":
    print(summarize_cloaked(qc))
    job = cloak_compile(qc, rounds=2, seed=0)
    print(job.metadata["blind_share"].format())

    state = simulate_cloaked(qc, seed=0)
    print(f"\nAnsatz layers   (public): {len(HIDDEN_SCHEDULE)}")
    print(f"Parameter steps (hidden): {len(HIDDEN_SCHEDULE)}")
    print(f"Hidden parameter count  : {sum(len(p) for p in HIDDEN_SCHEDULE)}")
    print("\nFinal-step per-qubit <Z>:")
    for q in range(qc.num_qubits):
        z = 0.0
        for i, amp in enumerate(state.data):
            bit = (i >> (qc.num_qubits - 1 - q)) & 1
            z += (1.0 if bit == 0 else -1.0) * abs(amp) ** 2
        print(f"  q{q}: {z:+.4f}")
