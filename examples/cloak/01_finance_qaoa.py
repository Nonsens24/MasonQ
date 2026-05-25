"""Finance — QAOA portfolio optimisation with a cloaked alpha model.

A hedge fund's value is its *alpha model*: the matrix Q whose entries encode
expected returns, covariances, regulatory penalties, and constraints over a
set of tradable assets.  In a QAOA-style portfolio optimiser, that matrix
is loaded into the circuit as the angles of the cost-Hamiltonian phase
separator — every entry of Q literally appears as a rotation parameter on a
ZZ gate.  Anyone with the rotation angles has the alpha model.

The mixer, the initial Hadamards, and the readout are public knowledge
(QAOA is a standard algorithm).  The *only* part that needs blinding is
the phase separator carrying Q.  Cloak lets you blind exactly that and
nothing else — so the cloud provider runs the rest of your QAOA in the
clear at full speed.

Run with:
    PYTHONPATH=src python examples/cloak/01_finance_qaoa.py
"""

from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import cloak_compile, sensitive, simulate_cloaked


# ---------------------------------------------------------------------------
# PROPRIETARY: this is the part that would never leave the fund's office.
# ---------------------------------------------------------------------------
ALPHA_MATRIX = np.array(
    [
        [0.00, 0.82, -0.31, 0.47],
        [0.82, 0.00, 0.18, -0.39],
        [-0.31, 0.18, 0.00, 0.66],
        [0.47, -0.39, 0.66, 0.00],
    ]
)


def build_circuit(*, gamma: float = 0.4, beta: float = 0.3) -> QuantumCircuit:
    """One QAOA layer over a 4-asset universe.

    Public structure:
      - Hadamards on every asset qubit (uniform superposition over portfolios).
      - X-mixer with angle `2*beta` (standard QAOA mixer).

    Sensitive sub-circuit:
      - The phase separator e^{-i gamma * H_C}, where H_C is built from
        ALPHA_MATRIX.  Each entry Q[i, j] becomes the rotation angle of a
        CX-RZ-CX gadget on qubits (i, j).
    """
    qc = QuantumCircuit(4, name="finance_qaoa")
    qc.h([0, 1, 2, 3])

    with sensitive(qc, [0, 1, 2, 3], label="alpha-model") as cost:
        for i in range(4):
            for j in range(i + 1, 4):
                w = float(ALPHA_MATRIX[i, j])
                if w == 0.0:
                    continue
                cost.cx(i, j)
                cost.rz(2.0 * gamma * w, j)
                cost.cx(i, j)

    for q in range(4):
        qc.rx(2.0 * beta, q)

    return qc


qc = build_circuit()


if __name__ == "__main__":
    job = cloak_compile(qc, rounds=2, seed=7)
    state = simulate_cloaked(qc, seed=7)

    print("== Finance: QAOA portfolio optimisation ==")
    print(f"  alpha-model rows × cols: {ALPHA_MATRIX.shape}")
    print(f"  cloaked subs:            {job.metadata['num_subs']}")
    print(f"  trap rounds per sub:     {job.metadata['rounds']}")
    print(f"  outer (public) ops:      {len(job.outer_qhe_circuit.data)}")
    print(f"  qhe mode:                {job.qhe_mode}")
    print(f"  top portfolio amplitudes (|0000>, |0001>, ..., |1111>):")
    for i, amp in enumerate(state.data):
        if abs(amp) > 0.1:
            print(f"    |{i:04b}>: {amp:+.4f}")
