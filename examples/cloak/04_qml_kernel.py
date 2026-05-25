"""QML — confidential inference with a cloaked data embedding.

A quantum kernel / variational classifier is structurally split into two
parts: a *data-encoding* unitary U_enc(x) that loads a feature vector into
the qubit register, and a *trained ansatz* U_var(theta) with learned
parameters that performs the classification.

In a deployed inference pipeline, the value the client pays to protect is
the feature vector x: it is a per-query input — a customer's transaction
history, a patient's diagnostic embedding, a defendant's risk profile.
Each x literally lives inside the rotation angles of U_enc.  Reading
those angles ≡ reading the raw input.

Cloak hides U_enc on every query while letting the cloud run the trained
ansatz, the readout, and any classical post-processing in the clear at
native speed.  When the trained weights are themselves sensitive IP, you
can wrap U_var in a second `sensitive(...)` block; cloak's Type 2
boundary handler stitches the two blinded regions correctly.

Run with:
    PYTHONPATH=src python examples/cloak/04_qml_kernel.py
"""

from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import cloak_compile, sensitive, simulate_cloaked


# ---------------------------------------------------------------------------
# CONFIDENTIAL: a single query's feature vector.  In production this is the
# input data the customer / patient / regulator paid for privacy on.
# ---------------------------------------------------------------------------
FEATURES = np.array([0.85, -0.42, 1.23])

# Trained ansatz parameters — also IP, but in this example we expose them
# to keep the demo focused on input-data privacy.
TRAINED_THETAS = np.array([0.31, -0.55, 0.18])


def build_circuit() -> QuantumCircuit:
    """3-qubit kernel-style inference circuit.

    Sensitive sub-circuit:
      - Data re-uploading layer.  Two rotation passes over the qubits, each
        carrying the per-feature angles, separated by an entangling sweep.
        The angles ARE the input data.

    Public:
      - Trained ansatz with frozen weights `TRAINED_THETAS`.  The classifier
        decision-boundary lives in these parameters; in this example we
        treat them as public to keep the focus on input-data privacy.
    """
    qc = QuantumCircuit(3, name="qml_kernel")

    with sensitive(qc, [0, 1, 2], label="data-embedding") as embed:
        # First pass — angle encoding.
        for q, xi in enumerate(FEATURES):
            embed.ry(float(xi), q)
            embed.rz(float(xi) ** 2, q)
        # Entangling sweep.
        embed.cx(0, 1)
        embed.cx(1, 2)
        # Re-uploading pass for higher expressivity.
        for q, xi in enumerate(FEATURES):
            embed.ry(float(xi), q)

    # Public trained ansatz.
    for q, theta in enumerate(TRAINED_THETAS):
        qc.ry(float(theta), q)
    qc.cx(0, 1)
    qc.cx(1, 2)

    return qc


qc = build_circuit()


if __name__ == "__main__":
    job = cloak_compile(qc, rounds=3, seed=29)
    state = simulate_cloaked(qc, seed=29)

    print("== QML: confidential kernel inference ==")
    print(f"  hidden feature dimension:  {len(FEATURES)}")
    print(f"  cloaked subs:              {job.metadata['num_subs']}")
    print(f"  trap rounds per sub:       {job.metadata['rounds']}")
    print(f"  outer (public) ops:        {len(job.outer_qhe_circuit.data)}")
    z_expectations = []
    for q in range(qc.num_qubits):
        z = 0.0
        for i, amp in enumerate(state.data):
            bit = (i >> (qc.num_qubits - 1 - q)) & 1
            z += (1.0 if bit == 0 else -1.0) * abs(amp) ** 2
        z_expectations.append(z)
    print(f"  per-qubit <Z> (classifier readout proxy):")
    for q, z in enumerate(z_expectations):
        print(f"    q{q}: {z:+.4f}")
