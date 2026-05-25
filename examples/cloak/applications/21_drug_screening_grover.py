"""Application — Pharma proprietary hit-criterion screen (pattern #10).

Production framing of `patterns/10_hidden_predicate.py`.

A drug-screening startup wants to run amplitude amplification over a
catalogue of 32 candidate molecules (encoded as 5 qubits ``q0..q4``).
The molecules themselves are public knowledge — anyone can look them up
in PubChem.  The *hit criterion* is not.  It is a learned predicate
their classical pipeline distilled out of years of in-house assay data:

    "the bit pattern of the molecule index satisfies the conditions
     I encoded into this oracle."

The structural form (Grover diffusion, the 5-qubit Hadamard prep, the
3 amplification iterations) is identical to every Grover-search paper
in the literature.  The cloud provider can compile, schedule, and
execute it natively.  Only the oracle — a tiny phase-flip circuit — is
proprietary and gets cloaked.

Source-gate blind share stays in the single digits at any iteration
count because the oracle is constant-size: one CCZ-shaped pattern per
iteration, no matter how many iterations you do.  This is the cleanest
``s << d`` story in the entire example set.

Pitch line: *cloud-run quantum search for the proprietary thing you're
looking for, without revealing what you're looking for.*

Run with:
    python examples/cloak/applications/21_drug_screening_grover.py
"""

from __future__ import annotations

import math

from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import (
    cloak_compile,
    sensitive,
    simulate_cloaked,
    summarize_cloaked,
)


N_QUBITS = 5  # 32 candidate molecules


def _diffusion(qc: QuantumCircuit, qubits: list[int]) -> None:
    """Standard Grover diffusion operator over ``qubits`` — public textbook."""
    qc.h(qubits)
    qc.x(qubits)
    qc.h(qubits[-1])
    qc.mcx(qubits[:-1], qubits[-1])
    qc.h(qubits[-1])
    qc.x(qubits)
    qc.h(qubits)


def _hit_oracle(sub: QuantumCircuit) -> None:
    """PRIVATE hit-criterion oracle.

    In production this is whatever the screening team's pipeline emits
    — a phase flip on the subset of molecule indices the learned
    pharmacophore considers active.  The exact internal structure
    (which qubits couple, the chain of XOR / AND patterns) IS the
    trade secret.  Cloud provider never sees this body.
    """
    sub.cx(2, 0)
    sub.h(4)
    sub.ccx(0, 2, 4)
    sub.h(4)
    sub.cx(2, 0)


def build_circuit(*, iterations: int | None = None) -> QuantumCircuit:
    """5-qubit Grover with a cloaked hit oracle.

    The default iteration count is the textbook optimum
    ``floor((pi / 4) * sqrt(N))`` for ``N = 32`` ≈ 4.
    """
    if iterations is None:
        iterations = int(math.floor((math.pi / 4) * math.sqrt(2**N_QUBITS)))

    qc = QuantumCircuit(N_QUBITS, name=f"drug-screening-grover-{iterations}")
    qc.h(range(N_QUBITS))

    for _ in range(iterations):
        # PRIVATE: the proprietary hit criterion.
        with sensitive(qc, range(N_QUBITS), label="hit-oracle") as oracle:
            _hit_oracle(oracle)

        # PUBLIC: textbook diffusion.
        _diffusion(qc, list(range(N_QUBITS)))

    return qc


qc = build_circuit()


if __name__ == "__main__":
    print(summarize_cloaked(qc))
    job = cloak_compile(qc, rounds=3, seed=0)
    print(job.metadata["blind_share"].format())

    state = simulate_cloaked(qc, seed=0)
    print("\nTop candidate molecules by amplified probability:")
    ranked = sorted(enumerate(state.data), key=lambda kv: -abs(kv[1]) ** 2)[:6]
    for i, amp in ranked:
        bits = format(i, f"0{N_QUBITS}b")
        print(f"  molecule #{i:2d} ({bits}): P = {abs(amp) ** 2:.4f}")
