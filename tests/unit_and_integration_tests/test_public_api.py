import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from brickwork_transpiler import SparseInstructionMatrix, TranspileResult, show_versions, transpile


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


@pytest.mark.integration
def test_verify_supports_nontrivial_layout_method():
    qc = QuantumCircuit(3)
    qc.h(0)
    qc.x(1)
    qc.cx(0, 2)
    qc.z(2)

    result = transpile(
        qc,
        Statevector.from_label("+++"),
        routing_method="sabre",
        layout_method="sabre",
        return_result=True,
    )

    permutation = result.output_permutation()
    reference = result.qiskit_reference_statevector()
    verification = result.verify()

    assert sorted(permutation) == list(range(result.decomposed_circuit.num_qubits))
    assert reference.shape == (2 ** result.decomposed_circuit.num_qubits,)
    assert verification.equivalent
    assert verification.fidelity == pytest.approx(1.0)


def test_show_versions_returns_mapping(capsys):
    versions = show_versions()

    captured = capsys.readouterr()
    assert "qiskit" in versions
    assert "brickwork-transpiler" in versions
    assert "qiskit" in captured.out


def test_return_stage_resources_and_matrix_are_scientist_friendly():
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)

    resources = transpile(qc, return_stage="resources")
    matrix = transpile(qc, return_stage="matrix")
    legacy_matrix = transpile(qc, return_mat=True)

    assert resources.brick_columns == len(matrix[0])
    assert resources.graph_depth == resources.brick_columns * 4 + 1
    assert resources.graph_nodes == resources.brick_rows * resources.graph_depth
    assert matrix == legacy_matrix


def test_return_stage_sparse_matrix_round_trips_from_dense():
    qc = QuantumCircuit(3)
    qc.h(0)
    qc.cx(0, 1)
    qc.cx(1, 2)

    dense = transpile(qc, return_stage="matrix")
    sparse = transpile(qc, return_stage="sparse_matrix")
    dense_resources = transpile(qc, return_stage="resources")

    assert isinstance(sparse, SparseInstructionMatrix)
    assert sparse.shape == (len(dense), len(dense[0]))
    assert sparse.to_dense() == dense
    assert sparse.non_empty_cells > 0
    assert 0 < sparse.occupancy <= 1
    assert dense_resources.brick_rows == sparse.rows
    assert dense_resources.brick_columns == sparse.columns


def test_return_stage_decomposed_and_graph_data():
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)

    decomposed = transpile(qc, return_stage="decomposed_circuit")
    graph_data = transpile(qc, return_stage="graph_data")

    assert decomposed.num_qubits >= qc.num_qubits
    assert graph_data["height"] >= qc.num_qubits
    assert graph_data["width"] > 0
