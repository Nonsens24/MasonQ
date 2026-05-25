"""Sparse penalty injection — H_total = H_public + λ · H_secret.

VEIL design pattern #2: most of the optimisation cost is a commodity
Hamiltonian everyone in the field has (MaxCut on a known graph, a
textbook portfolio-variance term, a published scheduling model).  What
*you* know — the proprietary regulatory exclusion, the customer-
specific risk side-constraint, the classified ROE penalty — lives in a
handful of extra terms that get cloaked.

Public structure scales with the problem size; the secret penalty
scales with how unusual your constraints are.  In practice that means
``|secret_pairs| << |public_pairs|``, which is the small-patch idiom.

Run with:
    python examples/cloak/patterns/11_sparse_penalty.py
"""

from __future__ import annotations

from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import (
    cloak_compile,
    sensitive,
    simulate_cloaked,
    summarize_cloaked,
)


# Public MaxCut graph: a 4-node ring; every paper in the field uses it.
PUBLIC_EDGES = [(0, 1), (1, 2), (2, 3), (3, 0)]

# Proprietary penalty pair — e.g. "assets 0 and 2 must not co-occur in
# the portfolio under the new regulation". One pair, large effect.
SECRET_PENALTY_PAIRS = [(0, 2)]
SECRET_LAMBDA = 0.85


def build_circuit(*, gamma: float = 0.45, beta: float = 0.30) -> QuantumCircuit:
    qc = QuantumCircuit(4, name="sparse-penalty")
    qc.h([0, 1, 2, 3])

    # PUBLIC cost: standard MaxCut ZZ phases on the published edge set.
    for i, j in PUBLIC_EDGES:
        qc.cx(i, j)
        qc.rz(2.0 * gamma * 1.0, j)
        qc.cx(i, j)

    # PRIVATE: sparse penalty terms — proprietary side-constraints.
    with sensitive(qc, [0, 1, 2, 3], label="hidden-penalty") as penalty:
        for i, j in SECRET_PENALTY_PAIRS:
            penalty.cx(i, j)
            penalty.rz(2.0 * gamma * SECRET_LAMBDA, j)
            penalty.cx(i, j)

    # PUBLIC mixer.
    for q in range(4):
        qc.rx(2.0 * beta, q)

    return qc


qc = build_circuit()


if __name__ == "__main__":
    print(summarize_cloaked(qc))
    job = cloak_compile(qc, rounds=2, seed=0)
    print(job.metadata["blind_share"].format())

    state = simulate_cloaked(qc, seed=0)
    print("\nTop bitstring amplitudes (post-cloak roundtrip):")
    ranked = sorted(enumerate(state.data), key=lambda kv: -abs(kv[1]) ** 2)[:4]
    for i, amp in ranked:
        print(f"  |{i:04b}>: P = {abs(amp) ** 2:.4f}")
