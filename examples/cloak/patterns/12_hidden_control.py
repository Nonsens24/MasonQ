"""Hidden adaptive control — proprietary stopping / branching criterion.

VEIL design pattern #3: ``if hidden_metric(state): branch()``.  The
*predicate* that decides whether to keep going, take a different path,
or update a reinforcement target encodes proprietary policy. The
*action* once branched is public algorithmic machinery.

In a unitary circuit we express this as a tiny flag-flipper that
entangles a single ancilla with the public state.  Downstream public
gates condition their action on the flag.  Cloaking only the
flag-flipper means the server learns the algorithm's outer shape but
not the policy that drives it.

Run with:
    python examples/cloak/patterns/12_hidden_control.py
"""

from __future__ import annotations

from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import (
    cloak_compile,
    sensitive,
    simulate_cloaked,
    summarize_cloaked,
)


def build_circuit() -> QuantumCircuit:
    """Three data qubits + one hidden-policy flag qubit (#3)."""
    qc = QuantumCircuit(4, name="hidden-control")

    # PUBLIC: prepare a candidate state that the policy will evaluate.
    qc.h([0, 1, 2])
    for q in range(3):
        qc.ry(0.4, q)

    # PRIVATE: tiny flag-flipper encoding the proprietary policy.
    # The flag (qubit 3) goes |1> only when the policy predicate fires;
    # in this toy example the predicate is "q0 AND q1", but in production
    # this is the part that carries the trade secret.
    with sensitive(qc, [0, 1, 2, 3], label="hidden-policy") as policy:
        policy.ccx(0, 1, 3)

    # PUBLIC: branch action conditioned on the flag — generic adaptation
    # machinery that the cloud provider can compile for any policy.
    qc.cry(0.5, 3, 0)
    qc.cry(0.5, 3, 1)
    qc.cry(0.5, 3, 2)
    qc.h([0, 1, 2])

    return qc


qc = build_circuit()


if __name__ == "__main__":
    print(summarize_cloaked(qc))
    job = cloak_compile(qc, rounds=2, seed=0)
    print(job.metadata["blind_share"].format())

    state = simulate_cloaked(qc, seed=0)
    flag_marginal_p1 = sum(
        abs(amp) ** 2 for i, amp in enumerate(state.data) if (i >> 0) & 1
    )
    print(f"\nPolicy-flag activation probability P(flag=1): {flag_marginal_p1:.4f}")
