import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from brickwork_transpiler import transpile, utils


def _simulate_pattern_statevector(pattern):
    pattern.standardize()
    pattern.shift_signals()
    tn = pattern.simulate_pattern(
        backend="tensornetwork",
        graph_prep="parallel",
        rng=np.random.default_rng(0),
    )
    return tn.to_statevector()


def test_output_permutation_reorders_qiskit_reference_to_graphix_order():
    input_vec = Statevector.from_label("+++")

    qc = QuantumCircuit(3)
    qc.rz(0.2, 0)
    qc.rx(0.4, 1)
    qc.rz(1.1, 2)
    qc.cx(0, 1)

    result = transpile(
        qc,
        input_vec,
        routing_method="sabre",
        layout_method="trivial",
        with_ancillas=False,
        return_result=True,
    )

    psi = _simulate_pattern_statevector(result.copy_pattern())
    reference_output = result.qiskit_reference_statevector()
    unpermuted_output = utils.pad_with_plus_for_transpiled(
        input_vec,
        qc,
        result.decomposed_circuit,
    ).evolve(result.decomposed_circuit)

    assert result.output_permutation() == [2, 1, 0]
    assert utils.assert_equal_up_to_global_phase(psi, reference_output)
    assert not Statevector(psi).equiv(unpermuted_output)


def test_output_permutation_supports_sabre_layout_verification():
    input_vec = Statevector.from_label("+++")

    qc = QuantumCircuit(3)
    qc.h(0)
    qc.x(1)
    qc.cx(0, 2)
    qc.rz(0.37, 2)

    result = transpile(
        qc,
        input_vec,
        routing_method="sabre",
        layout_method="sabre",
        with_ancillas=False,
        return_result=True,
    )

    psi = _simulate_pattern_statevector(result.copy_pattern())
    reference_output = result.qiskit_reference_statevector()
    verification = result.verify()

    assert result.output_permutation() == [2, 1, 0]
    assert utils.assert_equal_up_to_global_phase(psi, reference_output)
    assert verification.equivalent


def test_output_permutation_supports_sabre_layout_verification_with_ancillae():
    input_vec = Statevector.from_label("+++")

    qc = QuantumCircuit(3)
    qc.h(0)
    qc.x(1)
    qc.cx(0, 2)
    qc.rz(0.37, 2)

    result = transpile(
        qc,
        input_vec,
        routing_method="sabre",
        layout_method="sabre",
        with_ancillas=True,
        return_result=True,
    )

    psi = _simulate_pattern_statevector(result.copy_pattern())
    reference_output = result.qiskit_reference_statevector()
    verification = result.verify()

    assert result.output_permutation() == [2, 1, 0]
    assert utils.assert_equal_up_to_global_phase(psi, reference_output)
    assert verification.equivalent

def test_output_permutation_BQRS():
    import brickwork_transpiler.circuits as circuits

    qc, input_vec = circuits.minimal_qrs([0, 0])

    result = transpile(
        qc,
        input_vec,
        routing_method="sabre",
        layout_method="sabre",
        with_ancillas=True,
        return_result=True,
    )

    psi = _simulate_pattern_statevector(result.copy_pattern())
    reference_output = result.qiskit_reference_statevector()
    unpermuted_output = utils.pad_with_plus_for_transpiled(
        input_vec,
        qc,
        result.decomposed_circuit,
    ).evolve(result.decomposed_circuit)
    verification = result.verify()

    permutation = result.output_permutation()
    assert sorted(permutation) == list(range(result.decomposed_circuit.num_qubits))
    assert permutation != list(range(result.decomposed_circuit.num_qubits))
    assert utils.assert_equal_up_to_global_phase(psi, reference_output)
    assert not Statevector(psi).equiv(unpermuted_output)
    assert verification.equivalent
