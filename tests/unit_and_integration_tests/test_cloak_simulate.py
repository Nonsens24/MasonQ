"""End-to-end honest-server simulation: cloak roundtrip preserves semantics."""

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from brickwork_transpiler.cloak import sensitive, simulate_cloaked


def _bell_pair_with_sensitive_oracle() -> QuantumCircuit:
    qc = QuantumCircuit(2)
    qc.h(0)
    with sensitive(qc, [0, 1], label="bell-oracle") as oracle:
        oracle.cx(0, 1)
    return qc


def _plaintext(qc: QuantumCircuit) -> Statevector:
    """Strip the Sensitive wrapper and evolve normally — the reference state."""
    flat = QuantumCircuit(qc.num_qubits, qc.num_clbits, name=f"{qc.name}_flat")
    for instr in qc.data:
        op = instr.operation
        if op.name == "sensitive":
            flat.compose(op.definition, qubits=list(instr.qubits), inplace=True)
        else:
            flat.append(op, list(instr.qubits), list(instr.clbits))
    return Statevector.from_instruction(flat)


@pytest.mark.slow
def test_simulate_cloaked_matches_plaintext_for_simple_bell_oracle():
    qc = _bell_pair_with_sensitive_oracle()
    cloak_state = simulate_cloaked(qc, seed=1)
    reference = _plaintext(qc)

    fidelity = float(np.abs(cloak_state.inner(reference)))
    assert fidelity > 1.0 - 1e-6, f"fidelity={fidelity}"


@pytest.mark.slow
def test_simulate_cloaked_with_clear_diffusion_layer():
    qc = QuantumCircuit(2)
    qc.h([0, 1])
    with sensitive(qc, [0, 1], label="oracle") as oracle:
        oracle.cx(0, 1)
    qc.h([0, 1])

    cloak_state = simulate_cloaked(qc, seed=2)
    reference = _plaintext(qc)

    fidelity = float(np.abs(cloak_state.inner(reference)))
    assert fidelity > 1.0 - 1e-6, f"fidelity={fidelity}"


@pytest.mark.slow
def test_simulate_cloaked_qhe_off_preserves_non_clifford_outer_gate():
    """qhe='off' should not raise on RY in the unprotected segment."""
    qc = QuantumCircuit(2)
    qc.ry(0.7, 0)
    with sensitive(qc, [0, 1]) as oracle:
        oracle.cx(0, 1)

    state = simulate_cloaked(qc, seed=3, qhe="off")
    reference = _plaintext(qc)
    fidelity = float(np.abs(state.inner(reference)))
    assert fidelity > 1.0 - 1e-6, f"fidelity={fidelity}"
