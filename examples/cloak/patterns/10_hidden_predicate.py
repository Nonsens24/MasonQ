"""Hidden predicate kernel — a tiny secret oracle drives a large search.

VEIL design pattern #1: ``if secret_condition(x): amplify()``.

The only proprietary piece is the predicate. Grover amplification,
mixers, diffusion operators — all public, well-studied, hardware-aware.
Cloak hides the few-gate oracle and leaves everything else in the clear,
so the blind share stays tiny while the secret controls the *meaning*
of the entire amplification process.

This is the small-patch idiom in its purest form: ``s << d`` because
the secret has constant gate count while the public scaffolding scales
with the number of Grover iterations.

Run with:
    python examples/cloak/patterns/10_hidden_predicate.py
"""

from __future__ import annotations

from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import (
    cloak_compile,
    sensitive,
    simulate_cloaked,
    summarize_cloaked,
)


def build_circuit(*, iterations: int = 2) -> QuantumCircuit:
    """3-qubit Grover with a cloaked phase-flip oracle.

    The oracle marks one basis state via a single CZ — that is the entire
    confidential payload. The diffusion operator is the public textbook
    construction; running for more iterations grows ``d`` while ``s``
    stays constant.
    """
    qc = QuantumCircuit(3, name="hidden-predicate")
    qc.h([0, 1, 2])

    for _ in range(iterations):
        # PRIVATE: which basis state we are searching for is the secret.
        with sensitive(qc, [0, 1, 2], label="secret-predicate") as oracle:
            oracle.cz(0, 1)  # ← marks |11x>; one gate carries the secret

        # PUBLIC: textbook diffusion operator.
        qc.h([0, 1, 2])
        qc.x([0, 1, 2])
        qc.h(2)
        qc.ccx(0, 1, 2)
        qc.h(2)
        qc.x([0, 1, 2])
        qc.h([0, 1, 2])

    return qc


qc = build_circuit()


if __name__ == "__main__":
    print(summarize_cloaked(qc))
    job = cloak_compile(qc, rounds=3, seed=0)
    print(job.metadata["blind_share"].format())

    state = simulate_cloaked(qc, seed=0)
    print("\nGrover amplitudes after cloaked roundtrip:")
    for i, amp in enumerate(state.data):
        if abs(amp) ** 2 > 0.05:
            print(f"  |{i:03b}>: P = {abs(amp) ** 2:.4f}")
