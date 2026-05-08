import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from brickwork_transpiler import TranspileResult, show_versions, transpile


@pytest.mark.integration
def test_transpile_result_verify_h_cx_public_api():
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)

    result = transpile(qc, Statevector.from_label("++"), return_result=True)

    assert isinstance(result, TranspileResult)
    assert result.resources is not None
    assert result.decomposed_circuit is result.transpiled_circuit
    verification = result.verify()
    assert verification.equivalent
    assert verification.fidelity == pytest.approx(1.0)


@pytest.mark.integration
def test_tuple_unpacking_remains_compatible():
    qc = QuantumCircuit(1)
    qc.h(0)

    pattern, colour_map, decomposed_qc = transpile(qc, Statevector.from_label("+"))

    assert pattern.output_nodes
    assert isinstance(colour_map, dict)
    assert decomposed_qc.num_qubits >= qc.num_qubits


def test_show_versions_returns_mapping(capsys):
    versions = show_versions()

    captured = capsys.readouterr()
    assert "qiskit" in versions
    assert "brickwork-transpiler" in versions
    assert "qiskit" in captured.out
