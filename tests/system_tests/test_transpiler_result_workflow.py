import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from brickwork_transpiler import SparseInstructionMatrix, TranspileResult, transpile, utils


def test_result_workflow_verifies_without_legacy_tuple_unpacking():
    input_vec = Statevector.from_label("+++")

    qc = QuantumCircuit(3)
    qc.h(0)
    qc.cx(0, 2)
    qc.rz(0.37, 1)

    result = transpile(
        qc,
        input_vec,
        routing_method="sabre",
        layout_method="sabre",
        with_ancillas=False,
        return_result=True,
    )

    verification = result.verify(seed=0)

    assert isinstance(result, TranspileResult)
    assert result.pattern.output_nodes
    assert result.decomposed_circuit.num_qubits == qc.num_qubits
    assert result.resources.graph_depth == result.resources.brick_columns * 4 + 1
    assert verification.equivalent
    assert verification.fidelity == pytest.approx(1.0)


def test_result_reference_statevector_is_in_graphix_output_order():
    input_vec = Statevector.from_label("+++")

    qc = QuantumCircuit(3)
    qc.rx(0.2, 0)
    qc.rz(0.4, 1)
    qc.cx(0, 1)

    result = transpile(
        qc,
        input_vec,
        routing_method="sabre",
        layout_method="trivial",
        with_ancillas=False,
        return_result=True,
    )

    graphix_state = result.simulate_statevector(
        backend="tensornetwork",
        graph_prep="parallel",
        seed=0,
    )
    reference_state = result.qiskit_reference_statevector()
    raw_qiskit_state = utils.pad_with_plus_for_transpiled(
        input_vec,
        qc,
        result.decomposed_circuit,
    ).evolve(result.decomposed_circuit)

    assert result.output_permutation() == [2, 1, 0]
    assert utils.assert_equal_up_to_global_phase(graphix_state, reference_state)
    assert not Statevector(graphix_state).equiv(raw_qiskit_state)


def test_sparse_stage_matches_system_resource_matrix_shape():
    qc = QuantumCircuit(4)
    qc.h(0)
    qc.cx(0, 1)
    qc.cx(2, 3)
    qc.rz(0.25, 2)

    resources = transpile(
        qc,
        routing_method="sabre",
        layout_method="trivial",
        with_ancillas=False,
        return_stage="resources",
    )
    sparse = transpile(
        qc,
        routing_method="sabre",
        layout_method="trivial",
        with_ancillas=False,
        return_stage="sparse_matrix",
    )

    assert isinstance(sparse, SparseInstructionMatrix)
    assert sparse.shape == (resources.brick_rows, resources.brick_columns)
    assert sparse.non_empty_cells > 0
    assert 0.0 < sparse.occupancy <= 1.0

    for row, column, instructions in sparse.iter_non_empty():
        assert sparse.cell(row, column) == instructions
        assert all(hasattr(instruction, "name") for instruction in instructions)


def test_result_simulation_uses_copy_by_default():
    input_vec = Statevector.from_label("++")

    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)

    result = transpile(
        qc,
        input_vec,
        routing_method="sabre",
        layout_method="trivial",
        with_ancillas=False,
        return_result=True,
    )

    original_command_count = len(result.pattern._Pattern__seq)

    first = result.simulate_statevector(
        backend="tensornetwork",
        graph_prep="parallel",
        rng=np.random.default_rng(0),
    )
    second = result.simulate_statevector(
        backend="tensornetwork",
        graph_prep="parallel",
        rng=np.random.default_rng(0),
    )

    assert len(result.pattern._Pattern__seq) == original_command_count
    assert utils.assert_equal_up_to_global_phase(first, second)
