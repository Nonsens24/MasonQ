"""Pharma / materials — VQE with a cloaked molecular Hamiltonian.

In a Variational Quantum Eigensolver workflow, a public ansatz |psi(theta)>
is repeatedly applied while the client requests expectation values
<psi| H_mol |psi> against a *molecular Hamiltonian* H_mol.  The Hamiltonian
encodes the geometry and electronic structure of the drug candidate or
exotic material under study — these are the one- and two-electron
integrals h_pp and h_pqrs, computed offline from a classical structure
solver and *never* shared with the cloud.

When the cloud server measures expectation values term-by-term, each
Trotter step rotates the qubits by an angle proportional to one of those
integrals.  Reading the rotation angles ≡ recovering the molecule.

Cloak lets the client hide the Hamiltonian terms while letting the cloud
run the ansatz, the parameter optimisation rounds, and the readout in the
clear.  The ansatz (typically UCCSD-like) is public IP, hardware-aware,
and benefits from running at native speed.

Run with:
    PYTHONPATH=src python examples/cloak/02_pharma_vqe.py
"""

from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import cloak_compile, sensitive, simulate_cloaked


# ---------------------------------------------------------------------------
# PROPRIETARY: one- and two-electron integrals for the candidate molecule.
# In production these come from a classical Hartree-Fock / CCSD solver and
# are guarded behind every NDA the company has.
# ---------------------------------------------------------------------------
ONE_BODY = np.array([-1.252, -0.475, -0.612, -0.213])
TWO_BODY_J = 0.674
TROTTER_DT = 0.15


def build_circuit(*, ansatz_theta: float = 0.42) -> QuantumCircuit:
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


qc = build_circuit()


if __name__ == "__main__":
    job = cloak_compile(qc, rounds=2, seed=11)
    state = simulate_cloaked(qc, seed=11)

    print("== Pharma: VQE molecular ground-state estimation ==")
    print(f"  one-body integrals (hidden): {len(ONE_BODY)} values")
    print(f"  two-body J (hidden):         {TWO_BODY_J}")
    print(f"  Trotter step dt (public):    {TROTTER_DT}")
    print(f"  cloaked subs:                {job.metadata['num_subs']}")
    print(f"  trap rounds per sub:         {job.metadata['rounds']}")
    print(f"  outer (public) ops:          {len(job.outer_qhe_circuit.data)}")
    print(f"  Trotter-evolved energy proxy <Z_0>:")
    z0 = sum(
        (1.0 if (i >> 3) & 1 == 0 else -1.0) * abs(amp) ** 2
        for i, amp in enumerate(state.data)
    )
    print(f"    {z0:+.6f}")
