"""Application — Hedge-fund constrained portfolio optimisation (pattern #11).

Production framing of `patterns/11_sparse_penalty.py`.

A quantitative hedge fund optimises a 6-asset portfolio using QAOA. The
public cost Hamiltonian is the standard Markowitz min-variance objective
over an asset universe whose covariance matrix is in the public record
(an index-provider product, a published factor model — every fund in
the field has the same one). Their *edge* is a small set of
proprietary side-constraints they add on top:

  - **ESG exclusions** — three asset pairs the fund's mandate forbids
    from simultaneous long positions (carbon-heavy / arms / similar).
  - **Regulator-imposed weight caps** — two assets that internal risk
    flags from a confidential model as concentration-risk candidates.
  - **One internal concentration penalty** — derived from a
    proprietary stress-test pipeline.

Everything else — the asset list, the public covariance, the QAOA
mixer, the depth — is what every QAOA implementation in the field
already runs. Cloak hides only the side-constraint terms. Source-gate
blind share lands in the 15–25% band for ``p = 3`` QAOA layers, and
stays bounded as you add layers because the cloaked region is constant
per layer.

Pitch line: *your quants get to express custom constraints in the cost
Hamiltonian without ever revealing them to the cloud provider.*

Run with:
    python examples/cloak/applications/20_hedge_fund_constrained_qaoa.py
"""

from __future__ import annotations

from itertools import combinations
from typing import Iterable

from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import (
    cloak_compile,
    sensitive,
    simulate_cloaked,
    summarize_cloaked,
)


N_ASSETS = 6

# ---------------------------------------------------------------------------
# PUBLIC: covariance off-diagonals from a published factor model.  Every
# fund in the field has this.  Values picked to look plausibly market-like.
# ---------------------------------------------------------------------------
PUBLIC_COVARIANCE = {
    (0, 1): 0.18, (0, 2): 0.09, (0, 3): 0.15, (0, 4): 0.04, (0, 5): 0.11,
    (1, 2): 0.21, (1, 3): 0.05, (1, 4): 0.13, (1, 5): 0.07,
    (2, 3): 0.10, (2, 4): 0.16, (2, 5): 0.06,
    (3, 4): 0.08, (3, 5): 0.19,
    (4, 5): 0.12,
}

# ---------------------------------------------------------------------------
# PROPRIETARY: side-constraints.  This is the IP the fund hides.
# ---------------------------------------------------------------------------
ESG_EXCLUSION_PAIRS = [(0, 4), (2, 5), (1, 3)]
WEIGHT_CAP_ASSETS = [1, 4]
CONCENTRATION_TRIPLE = (0, 2, 5)
LAMBDA_EXCLUSION = 1.6
LAMBDA_CAP = 0.9
LAMBDA_CONCENTRATION = 1.2


def _zz_cost(qc: QuantumCircuit, i: int, j: int, gamma: float, weight: float) -> None:
    qc.cx(i, j)
    qc.rz(2.0 * gamma * weight, j)
    qc.cx(i, j)


def build_circuit(*, p: int = 3, gamma: float = 0.45, beta: float = 0.32) -> QuantumCircuit:
    """Build a ``p``-layer QAOA with hidden side-constraints per layer."""
    qc = QuantumCircuit(N_ASSETS, name=f"hedge-fund-qaoa-p{p}")
    qc.h(range(N_ASSETS))

    for _ in range(p):
        # PUBLIC: Markowitz off-diagonal covariance terms.
        for (i, j), cov in PUBLIC_COVARIANCE.items():
            _zz_cost(qc, i, j, gamma, cov)

        # PRIVATE: sparse proprietary penalties.  Re-applied every layer
        # so they participate in the QAOA fixed-point search alongside
        # the public cost — this is what makes them *constraints*, not
        # one-shot post-processing.
        with sensitive(qc, range(N_ASSETS), label="fund-side-constraints") as side:
            for i, j in ESG_EXCLUSION_PAIRS:
                side.cx(i, j)
                side.rz(2.0 * gamma * LAMBDA_EXCLUSION, j)
                side.cx(i, j)
            for q in WEIGHT_CAP_ASSETS:
                side.rz(2.0 * gamma * LAMBDA_CAP, q)
            i, j, k = CONCENTRATION_TRIPLE
            side.cx(i, j)
            side.cx(j, k)
            side.rz(2.0 * gamma * LAMBDA_CONCENTRATION, k)
            side.cx(j, k)
            side.cx(i, j)

        # PUBLIC mixer.
        for q in range(N_ASSETS):
            qc.rx(2.0 * beta, q)

    return qc


qc = build_circuit()


if __name__ == "__main__":
    print(summarize_cloaked(qc))
    job = cloak_compile(qc, rounds=2, seed=0)
    print(job.metadata["blind_share"].format())

    state = simulate_cloaked(qc, seed=0)
    print("\nTop portfolio bitstrings (post-cloak roundtrip):")
    ranked = sorted(enumerate(state.data), key=lambda kv: -abs(kv[1]) ** 2)[:6]
    for i, amp in ranked:
        held = [q for q in range(N_ASSETS) if (i >> (N_ASSETS - 1 - q)) & 1]
        print(f"  hold {held}: P = {abs(amp) ** 2:.4f}")
