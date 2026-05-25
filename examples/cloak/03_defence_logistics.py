"""Defence — QAOA target-assignment with a cloaked capability graph.

A defence-logistics optimiser turns a quantum cost function into a QAOA
phase separator.  The cost function over (asset, target) pairs is built
from a *capability graph*: nodes are platforms / sensors / weapons,
edges are weighted by classified capability scores (sensor range,
all-aspect detection probability, kinematic envelope, ROE compliance).

The graph itself is the part that must never leak.  The mixer (driving
exploration of the assignment space), the initial Hadamards, the readout
basis — all of those are public algorithmic structure and run faster on
hardware when the cloud server can compile them natively.

This example uses a small 4-node graph to keep the demo tractable.  In
the production version, the same pattern extends to dozens of nodes by
chaining multiple Sensitive blocks.  The boundary classification
(Type 0 / Type 1) means the cloud sees the *block boundaries* but not the
edge weights inside them.

Run with:
    PYTHONPATH=src python examples/cloak/03_defence_logistics.py
"""

from __future__ import annotations

from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import cloak_compile, sensitive, simulate_cloaked


# ---------------------------------------------------------------------------
# CLASSIFIED: capability-graph edge weights.
# Each (i, j, w) entry encodes the joint mission utility of pairing asset i
# with asset / target j; the magnitudes reflect classified capability data.
# ---------------------------------------------------------------------------
CAPABILITY_EDGES = [
    (0, 1, 0.92),
    (0, 2, 0.55),
    (0, 3, 0.31),
    (1, 2, 0.41),
    (1, 3, 0.78),
    (2, 3, 0.69),
]


def build_circuit(*, gamma: float = 0.5, beta: float = 0.35) -> QuantumCircuit:
    """One QAOA layer over the classified capability graph."""
    qc = QuantumCircuit(4, name="defence_logistics")
    qc.h([0, 1, 2, 3])

    with sensitive(qc, [0, 1, 2, 3], label="capability-graph") as mission:
        for i, j, w in CAPABILITY_EDGES:
            mission.cx(i, j)
            mission.rz(2.0 * gamma * w, j)
            mission.cx(i, j)

    for q in range(4):
        qc.rx(2.0 * beta, q)

    return qc


qc = build_circuit()


if __name__ == "__main__":
    job = cloak_compile(qc, rounds=4, seed=23)
    state = simulate_cloaked(qc, seed=23)

    print("== Defence: capability-graph QAOA ==")
    print(f"  classified edges:          {len(CAPABILITY_EDGES)}")
    print(f"  cloaked subs:              {job.metadata['num_subs']}")
    print(f"  trap rounds per sub:       {job.metadata['rounds']}")
    print(f"  outer (public) ops:        {len(job.outer_qhe_circuit.data)}")
    print(f"  boundary types:            {[bt.value for bt in job.boundary_types]}")
    print(f"  top assignment amplitudes:")
    ranked = sorted(
        enumerate(state.data),
        key=lambda kv: -abs(kv[1]),
    )[:4]
    for i, amp in ranked:
        print(f"    |{i:04b}>: {amp:+.4f}  (|amp|^2 = {abs(amp) ** 2:.4f})")
