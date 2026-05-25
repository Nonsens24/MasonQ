"""Demo entry point for local manual runs.

Prefer module execution:

    python -m brickwork_transpiler.main

This script also supports direct execution from
`src/brickwork_transpiler/main.py` because some IDEs run files that way. In
that mode, Python puts the package directory itself on `sys.path`, which
would shadow the package import with the sibling
`brickwork_transpiler.py` module. The bootstrap below replaces that path
with the `src` directory before importing the package.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


if __package__ in {None, ""}:  # Direct file execution; rebuild sys.path safely.
    package_dir = Path(__file__).resolve().parent
    src_dir = package_dir.parent
    sys.path = [p for p in sys.path if Path(p or ".").resolve() != package_dir]
    sys.path.insert(0, str(src_dir))

# Cache locations for Numba/Matplotlib must be set before importing graphix.
os.environ.setdefault(
    "NUMBA_CACHE_DIR",
    str(Path(tempfile.gettempdir()) / "masonq_numba_cache"),
)
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "masonq_mpl_cache"),
)
os.environ.setdefault(
    "XDG_CACHE_HOME",
    str(Path(tempfile.gettempdir()) / "masonq_cache"),
)

from brickwork_transpiler import transpile


def main() -> int:

    # CLOAKED
    from brickwork_transpiler.cloak import sensitive, summarize_cloaked, cloak_compile
    from qiskit import QuantumCircuit, QuantumRegister
    from brickwork_transpiler.cloak import sensitive, draw_cloaked, summarize_cloaked

    # qc = QuantumCircuit(3, name="mixed-demo")
    # qc.h([0, 1, 2])  # 3 clear gates
    # with sensitive(qc, [0, 1, 2], label="oracle") as oracle:
    #     oracle.cx(0, 1)
    #     oracle.x(2)
    #     oracle.cx(1, 2)  # 3 blind gates
    # qc.h([0, 1, 2]);
    # qc.cx(0, 1)  # 4 more clear gates

    """One QAOA layer over a 4-asset universe.

     Public structure:
       - Hadamards on every asset qubit (uniform superposition over portfolios).
       - X-mixer with angle `2*beta` (standard QAOA mixer).

     Sensitive sub-circuit:
       - The phase separator e^{-i gamma * H_C}, where H_C is built from
         ALPHA_MATRIX.  Each entry Q[i, j] becomes the rotation angle of a
         CX-RZ-CX gadget on qubits (i, j).
     """

    import numpy as np
    from qiskit import QuantumCircuit

    from brickwork_transpiler.cloak import cloak_compile, sensitive, simulate_cloaked

    # # ---------------------------------------------------------------------------
    # # PROPRIETARY: this is the part that would never leave the fund's office.
    # # ---------------------------------------------------------------------------
    # ALPHA_MATRIX = np.array(
    #     [
    #         [0.00, 0.82, -0.31, 0.47],
    #         [0.82, 0.00, 0.18, -0.39],
    #         [-0.31, 0.18, 0.00, 0.66],
    #         [0.47, -0.39, 0.66, 0.00],
    #     ]
    # )
    # gamma: float = 0.4
    # beta: float = 0.3
    #
    # qc = QuantumCircuit(4, name="finance_qaoa")
    # qc.h([0, 1, 2, 3])
    #
    # with sensitive(qc, [0, 1, 2, 3], label="alpha-model") as cost:
    #     for i in range(4):
    #         for j in range(i + 1, 4):
    #             w = float(ALPHA_MATRIX[i, j])
    #             if w == 0.0:
    #                 continue
    #             cost.cx(i, j)
    #             cost.rz(2.0 * gamma * w, j)
    #             cost.cx(i, j)
    #
    # for q in range(4):
    #     qc.rx(2.0 * beta, q)

    # ---------------------------------------------------------------------------
    # PROPRIETARY: one- and two-electron integrals for the candidate molecule.
    # In production these come from a classical Hartree-Fock / CCSD solver and
    # are guarded behind every NDA the company has.
    # ---------------------------------------------------------------------------
    ONE_BODY = np.array([-1.252, -0.475, -0.612, -0.213])
    TWO_BODY_J = 0.674
    TROTTER_DT = 0.15

    def build_pharma_circuit(*, ansatz_theta: float = 0.42) -> QuantumCircuit:
        """4-qubit VQE: HF reference + one ansatz layer + one Trotter step.

        Public:
          - Hartree-Fock reference state (two electrons in the lowest orbitals).
          - One layer of hardware-efficient ansatz (RY rotations + entangling
            CXs).  The variational parameter `ansatz_theta` is what the
            optimiser updates each iteration; the *structure* of the ansatz is
            common knowledge.

        Sensitive sub-circuit:
          - One Trotter step exp(-i * H_mol * dt).  RZ angles carry ONE_BODY
            and TWO_BODY_J; flipping the sign of any of those angles flips an
            electron-electron interaction strength.
        """
        qc = QuantumCircuit(4, name="pharma_vqe")

        # Public Hartree-Fock reference: lowest two orbitals occupied.
        qc.x([0, 1])

        # Public hardware-efficient ansatz (one layer, single parameter for demo).
        for q in range(4):
            qc.ry(ansatz_theta, q)
        qc.cx(0, 1)
        qc.cx(2, 3)
        qc.cx(1, 2)

        # Sensitive: one Trotter step of the molecular Hamiltonian.
        with sensitive(qc, [0, 1, 2, 3], label="molecular-hamiltonian") as mol:
            # One-body diagonal Z rotations.
            for q, h in enumerate(ONE_BODY):
                mol.rz(2.0 * float(h) * TROTTER_DT, q)
            # One representative two-body Z⊗Z⊗Z⊗Z term, conjugated by CX ladder.
            mol.cx(0, 1)
            mol.cx(1, 2)
            mol.cx(2, 3)
            mol.rz(2.0 * TWO_BODY_J * TROTTER_DT, 3)
            mol.cx(2, 3)
            mol.cx(1, 2)
            mol.cx(0, 1)

        return qc

    # qc = build_pharma_circuit(ansatz_theta=0.42)

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

    def build_def_circuit(*, gamma: float = 0.5, beta: float = 0.35) -> QuantumCircuit:
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

    # qc = build_def_circuit()

    # ---------------------------------------------------------------------------
    # CONFIDENTIAL: a single query's feature vector.  In production this is the
    # input data the customer / patient / regulator paid for privacy on.
    # ---------------------------------------------------------------------------
    FEATURES = np.array([0.85, -0.42, 1.23])

    # Trained ansatz parameters — also IP, but in this example we expose them
    # to keep the demo focused on input-data privacy.
    TRAINED_THETAS = np.array([0.31, -0.55, 0.18])

    def build_qml_circuit() -> QuantumCircuit:
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

    # qc = build_qml_circuit()
    qc = build_pharma_circuit(ansatz_theta=0.42)
    print(summarize_cloaked(qc))
    job = cloak_compile(qc, rounds=3, seed=0)
    print(job.metadata["blind_share"].format())
    print(draw_cloaked(qc, output="text"))

    return 0

    """Run a small QFT example end-to-end and print summary information.

    Intended as a smoke test for local installs and as a copy-paste starting
    point for new users. Replace `circuits.qft(3)` with any
    `(QuantumCircuit, Statevector)` pair to try other examples.
    """
    qc, input_vector = circuits.qft(3)

    result = transpile(
        qc,
        input_vector,
        routing_method="sabre",
        layout_method="trivial",
        with_ancillas=True,
        fallback_opt=1,
        return_result=True,
        return_stage="sparse_matrix",
    )
    print(result)

    # The "sparse_matrix" stage stops before the Graphix pattern is built, so
    # the demo continues with a full transpile if a richer object is needed.
    full = transpile(
        qc,
        input_vector,
        routing_method="sabre",
        layout_method="trivial",
        with_ancillas=True,
        fallback_opt=1,
        return_result=True,
    )
    full.simulate()
    full.plot(show=True)

    print("pattern:         ", full.pattern)
    print("decomposed_qc:   ", full.decomposed_circuit)
    print("resources:       ", full.resources)




    return 0


if __name__ == "__main__":
    raise SystemExit(main())
