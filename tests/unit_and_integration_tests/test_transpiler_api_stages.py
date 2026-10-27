import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from brickwork_transpiler import (
    SparseInstructionMatrix,
    TranspileResult,
    VerificationResult,
    transpile,
)


def _small_circuit() -> QuantumCircuit:
    qc = QuantumCircuit(3)
    qc.h(0)
    qc.cx(0, 1)
    qc.rz(0.25, 2)
    return qc


def test_return_result_exposes_new_names_and_legacy_tuple_compatibility():
    qc = _small_circuit()
    result = transpile(qc, Statevector.from_label("+++"), return_result=True)

    pattern, colour_map, decomposed_circuit = result

    assert isinstance(result, TranspileResult)
    assert pattern is result.pattern
    assert colour_map is result.colour_map
    assert result.color_map is result.colour_map
    assert decomposed_circuit is result.decomposed_circuit
    assert result.transpiled_circuit is result.decomposed_circuit
    assert result.instruction_matrix
    assert result.resources is not None


def test_transpile_return_result_does_not_simulate_automatically(monkeypatch):
    from graphix import Pattern

    def fail_if_called(*args, **kwargs):
        raise AssertionError("transpile(..., return_result=True) must not simulate automatically")

    for name in ("simulate", "simulate_pattern"):  # Graphix 0.4 renamed simulate_pattern
        if hasattr(Pattern, name):
            monkeypatch.setattr(Pattern, name, fail_if_called)

    qc = _small_circuit()
    result = transpile(qc, Statevector.from_label("+++"), return_result=True)

    assert isinstance(result, TranspileResult)
    assert result.pattern.output_nodes


def test_verify_returns_structured_verification_result():
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)

    result = transpile(qc, Statevector.from_label("++"), return_result=True)
    verification = result.verify()

    assert isinstance(verification, VerificationResult)
    assert verification.equivalent
    assert verification.fidelity == pytest.approx(1.0)
    assert verification.reference_state.shape == verification.simulated_state.shape


def test_return_stage_matrix_aliases_are_identical():
    qc = _small_circuit()

    matrix = transpile(qc, return_stage="matrix")
    instruction_matrix = transpile(qc, return_stage="instruction_matrix")

    assert matrix == instruction_matrix


def test_return_stage_sparse_matrix_cell_api_and_resources_match():
    qc = _small_circuit()

    dense = transpile(qc, return_stage="matrix")
    sparse = transpile(qc, return_stage="sparse_matrix")
    resources = transpile(qc, return_stage="resources")

    assert isinstance(sparse, SparseInstructionMatrix)
    assert sparse.shape == (resources.brick_rows, resources.brick_columns)
    assert sparse.to_dense() == dense
    assert sparse.non_empty_cells == sum(1 for _ in sparse.iter_non_empty())

    row, column, instructions = next(sparse.iter_non_empty())
    assert sparse.cell(row, column) == instructions

    with pytest.raises(IndexError):
        sparse.cell(sparse.rows, 0)
    with pytest.raises(IndexError):
        sparse.cell(0, sparse.columns)


def test_return_stage_graph_data_and_networkx_graph_are_consistent():
    qc = _small_circuit()

    graph_data = transpile(qc, return_stage="graph_data")
    graph = transpile(qc, return_stage="networkx_graph")

    assert graph_data["height"] > 0
    assert graph_data["width"] > 0
    assert graph.number_of_nodes() == graph_data["height"] * graph_data["width"]
    assert graph.number_of_edges() > 0


def test_transpile_progress_output_is_clear(capsys):
    qc = _small_circuit()

    resources = transpile(qc, return_stage="resources", progress=True)

    captured = capsys.readouterr()
    assert resources.graph_depth > 0
    assert "[MasonQ] Starting transpilation:" in captured.out
    assert "Qiskit decomposition complete" in captured.out
    assert "Returning resource estimate." in captured.out


def test_verify_progress_output_is_clear(capsys):
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)

    result = transpile(qc, Statevector.from_label("++"), return_result=True)
    verification = result.verify(progress=True)

    captured = capsys.readouterr()
    assert verification.equivalent
    assert "[MasonQ] Starting verification:" in captured.out
    assert "Graphix simulation complete" in captured.out
    assert "Verification complete:" in captured.out


def test_progress_callback_receives_messages():
    qc = QuantumCircuit(1)
    qc.h(0)
    messages: list[str] = []

    transpile(qc, return_stage="decomposed_circuit", progress=messages.append)

    assert messages
    assert messages[0].startswith("[MasonQ] Starting transpilation:")
    assert any("Returning decomposed circuit." in message for message in messages)


def test_unknown_return_stage_fails_before_pipeline_work():
    qc = _small_circuit()

    with pytest.raises(ValueError, match="return_stage"):
        transpile(qc, return_stage="not_a_stage")
