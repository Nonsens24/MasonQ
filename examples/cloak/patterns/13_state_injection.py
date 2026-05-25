"""Secure state injection — hide the resource state, not the consumer.

VEIL design pattern #4: rather than hiding the algorithm that processes
quantum data, hide the *prepared state itself*.  Magic states,
domain-specific ansatz initialisations, proprietary resource graphs —
each is small in qubit count but carries substantial structure.  The
public workflow then operates on whatever state was injected.

This is the cleanest conceptual fit for Remote State Preparation: the
cloak layer's :class:`BFKQubitPreparation` list emitted for the
injected block IS the RSP plan.  A real RSP backend would prepare those
qubits remotely and hand them to the server; the server never sees the
state's structure.

Run with:
    python examples/cloak/patterns/13_state_injection.py
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
    qc = QuantumCircuit(4, name="state-injection")

    # PRIVATE: prepare a 2-qubit proprietary resource state.  The
    # particular shape (angles, entanglement pattern) is the trade
    # secret; the consuming workflow does not need to know it.
    with sensitive(qc, [0, 1], label="injected-resource") as inject:
        inject.h(0)
        inject.cx(0, 1)
        inject.ry(0.73, 0)
        inject.rz(-0.42, 1)

    # PUBLIC: workflow that consumes the injected state — generic,
    # could be a measurement protocol, a teleportation gadget, or part
    # of a larger published algorithm.
    qc.cx(0, 2)
    qc.cx(1, 3)
    qc.h([2, 3])
    qc.cx(2, 3)
    qc.h([0, 1, 2, 3])

    return qc


qc = build_circuit()


if __name__ == "__main__":
    print(summarize_cloaked(qc))
    job = cloak_compile(qc, rounds=2, seed=0)
    print(job.metadata["blind_share"].format())

    # The RSP plan emitted by cloak_compile names exactly the
    # |+_theta> preparations a remote backend would deliver.
    print(f"\nRSP preparation handles emitted: {len(job.rsp_plan)}")
    if job.rsp_plan:
        sample = job.rsp_plan[0]
        print(f"  first handle: {sample.handle_id}, qubits = {sample.num_qubits}")

    state = simulate_cloaked(qc, seed=0)
    print(
        f"\n<Z_0> after workflow: "
        f"{sum((1 if (i >> 3) & 1 == 0 else -1) * abs(amp) ** 2 for i, amp in enumerate(state.data)):+.4f}"
    )
