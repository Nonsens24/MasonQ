"""Application — VEIL Quantum's v1 product: confidential optimisation runtime.

This script is the *combined* application that the strongest two design
patterns (hidden predicate + sparse penalty injection) compose into a
single coherent product story.  In the recommended v1 product framing,
a quantitative research desk runs a single workflow that integrates:

  Stage 1 — proprietary candidate selection.
      A small hidden phase oracle amplifies a target sub-region of the
      search space.  This is *pattern #10* — the oracle is the firm's
      signal-generation IP, the diffusion is generic.

  Stage 2 — proprietary constraint optimisation.
      A QAOA layer applies the public cost Hamiltonian plus the firm's
      sparse private side-constraints to the amplified state.  This is
      *pattern #11* — the side-constraints are the firm's risk-and-
      compliance IP, the public cost is a textbook objective.

  Stage 3 — public readout and post-processing.
      Standard measurement-basis rotation and (in real deployment) a
      classical aggregation pass.

The two cloaked patches together cover a small fraction of the
operation count.  The *public* structure dominates — that is the
runtime's defining property and the source of its commercial leverage:
the cloud provider pays full hardware-aware cost on the bulk of the
work, the client pays only the small overhead for the cloaked patches,
and the firm's IP never leaves the client.

Pitch line: *VEIL Quantum's runtime lets the cloud execute your
optimisation workload at full speed while keeping every parameter that
makes the workload* yours *invisible to the provider.*

Run with:
    python examples/cloak/applications/23_confidential_optimization_runtime.py
"""

from __future__ import annotations

from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import (
    cloak_compile,
    sensitive,
    simulate_cloaked,
    summarize_cloaked,
)


# 5-qubit search/optimisation register.  Same universe shared across
# both stages so the amplified state feeds directly into the QAOA layer.
N = 5


# ---------------------------------------------------------------------------
# Stage 1: amplification with proprietary signal oracle.
# ---------------------------------------------------------------------------
def _signal_oracle(sub: QuantumCircuit) -> None:
    """PRIVATE — the firm's proprietary signal-generation predicate."""
    sub.h(N - 1)
    sub.ccx(0, 2, N - 1)
    sub.h(N - 1)


def _diffusion(qc: QuantumCircuit) -> None:
    """PUBLIC — textbook Grover diffusion."""
    qc.h(range(N))
    qc.x(range(N))
    qc.h(N - 1)
    qc.mcx(list(range(N - 1)), N - 1)
    qc.h(N - 1)
    qc.x(range(N))
    qc.h(range(N))


# ---------------------------------------------------------------------------
# Stage 2: QAOA layer with proprietary side-constraints.
# ---------------------------------------------------------------------------
PUBLIC_COST_PAIRS = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)]   # public ring graph
SECRET_PENALTY_PAIRS = [(0, 3)]                                 # proprietary exclusion
LAMBDA_SECRET = 1.4
GAMMA = 0.42
BETA = 0.30


def _public_cost(qc: QuantumCircuit) -> None:
    for i, j in PUBLIC_COST_PAIRS:
        qc.cx(i, j)
        qc.rz(2.0 * GAMMA * 1.0, j)
        qc.cx(i, j)


def _private_penalty(sub: QuantumCircuit) -> None:
    for i, j in SECRET_PENALTY_PAIRS:
        sub.cx(i, j)
        sub.rz(2.0 * GAMMA * LAMBDA_SECRET, j)
        sub.cx(i, j)


def _public_mixer(qc: QuantumCircuit) -> None:
    for q in range(N):
        qc.rx(2.0 * BETA, q)


# ---------------------------------------------------------------------------
# Combined runtime.
# ---------------------------------------------------------------------------
def build_circuit(*, amplification_iterations: int = 2, qaoa_layers: int = 2) -> QuantumCircuit:
    qc = QuantumCircuit(N, name="confidential-optimisation-runtime")
    qc.h(range(N))

    # Stage 1 — amplification (hidden signal + public diffusion).
    for _ in range(amplification_iterations):
        with sensitive(qc, range(N), label="signal-oracle") as oracle:
            _signal_oracle(oracle)
        _diffusion(qc)

    # Stage 2 — QAOA with proprietary side-constraints.
    for _ in range(qaoa_layers):
        _public_cost(qc)
        with sensitive(qc, range(N), label="fund-side-constraints") as side:
            _private_penalty(side)
        _public_mixer(qc)

    return qc


qc = build_circuit()


if __name__ == "__main__":
    print(summarize_cloaked(qc))
    job = cloak_compile(qc, rounds=3, seed=0)
    print(job.metadata["blind_share"].format())

    state = simulate_cloaked(qc, seed=0)
    print("\nTop solutions after combined amplification + constrained QAOA:")
    ranked = sorted(enumerate(state.data), key=lambda kv: -abs(kv[1]) ** 2)[:6]
    for i, amp in ranked:
        bits = format(i, f"0{N}b")
        print(f"  |{bits}>: P = {abs(amp) ** 2:.4f}")
