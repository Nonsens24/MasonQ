"""Pattern #7 — Compact quantum feature embedding (kernel only).

VEIL design pattern #7: in a quantum kernel / quantum-feature-map
classifier the part with the most semantic leverage is the *kernel* —
a small handful of basis-rotation angles that define how raw input
features get mapped into Hilbert space.  The rest of the pipeline
(state preparation, entangling fabric, measurement, postprocessing)
is generic.

The trap: it is tempting to wrap the entire embedding layer (every
RY / RZ that touches the data) inside ``sensitive(...)``.  Doing so
violates ``s << d`` once you scale to realistic feature counts.

The pattern: hide *only* the kernel-defining few parameters.  The
data may still be encoded in public RY rotations (or itself be
sensitive in a separate block, depending on the threat model), but
the angles that make the kernel *yours* — the ones a classical model
of the same shape would have learned differently — stay in a tiny
``sensitive(...)`` block.

Distinct from:

  - The naive market example ``../04_qml_kernel.py``, which hides the
    entire data-embedding layer (right idea, wrong scale).
  - Pattern ``13_state_injection.py``, which hides a whole prepared
    quantum state.  This pattern hides only kernel *parameters*, not
    the state itself.

Run with:
    python examples/cloak/patterns/16_feature_embedding.py
"""

from __future__ import annotations

from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import (
    cloak_compile,
    sensitive,
    simulate_cloaked,
    summarize_cloaked,
)


# Public input features — industry-benchmark sample data, not the IP.
PUBLIC_FEATURES = [0.45, -0.31, 0.78]

# PROPRIETARY — the few angles that make the kernel "yours".  In a real
# deployment these are learned from in-house calibration data; their
# specific values define the inductive bias the classifier exploits.
KERNEL_BASIS_ANGLES = [0.27, -0.41]


def build_circuit() -> QuantumCircuit:
    qc = QuantumCircuit(3, name="feature-embedding")

    # PUBLIC: data encoding.  Same shape every QML paper uses.
    for q, xi in enumerate(PUBLIC_FEATURES):
        qc.ry(float(xi), q)

    # PUBLIC: entangling fabric.
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.h([0, 1, 2])

    # PRIVATE: kernel-defining basis rotations — the IP.  Two angles
    # that act on two qubits.  Source-gate footprint stays constant
    # as the feature count or fabric depth grows.
    with sensitive(qc, [0, 1], label="kernel-basis") as kernel:
        for q, theta in enumerate(KERNEL_BASIS_ANGLES):
            kernel.rz(float(theta), q)

    # PUBLIC: more fabric + readout-basis preparation.
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.h([0, 1, 2])

    return qc


qc = build_circuit()


if __name__ == "__main__":
    print(summarize_cloaked(qc))
    job = cloak_compile(qc, rounds=2, seed=0)
    print(job.metadata["blind_share"].format())

    state = simulate_cloaked(qc, seed=0)
    z_expectations = []
    for q in range(qc.num_qubits):
        z = 0.0
        for i, amp in enumerate(state.data):
            bit = (i >> (qc.num_qubits - 1 - q)) & 1
            z += (1.0 if bit == 0 else -1.0) * abs(amp) ** 2
        z_expectations.append(z)
    print("\nPer-qubit <Z> (kernel-output proxy):")
    for q, z in enumerate(z_expectations):
        print(f"  q{q}: {z:+.4f}")
