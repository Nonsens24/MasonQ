"""The new alignment must never produce a *larger* brickwork graph than
the legacy gap-preserving alignment for any of the circuits exercised in
the existing graph-shape tests.

This is the regression bound. If a circuit's graph shrinks, the test in
`test_graphs.py` already pins the new (smaller) expected count and the
shrinkage is the desired optimization.
"""

import numpy as np
import pytest
from qiskit import QuantumCircuit

from brickwork_transpiler import decomposer, graph_builder


def _graph_node_count_new(qc: QuantumCircuit) -> int:
    decomposed = decomposer.decompose_qc_to_bricks_qiskit(
        qc, opt=3, with_ancillas=False
    )
    qc_mat, cx_mat = decomposer.instructions_to_matrix_dag(decomposed)
    aligned = decomposer.align_bricks(cx_mat, qc_mat)
    bw = graph_builder.generate_brickwork_graph_from_instruction_matrix(aligned)
    return bw["height"] * bw["width"]


def _graph_node_count_legacy(qc: QuantumCircuit) -> int:
    decomposed = decomposer.decompose_qc_to_bricks_qiskit(
        qc, opt=3, with_ancillas=False
    )
    qc_mat, cx_mat = decomposer.instructions_to_matrix_dag(decomposed)
    # Force the legacy gap-preserving fallback by passing orig_matrix=None.
    cx_aligned = decomposer.align_cx_matrix(cx_mat, orig_matrix=None)
    final = decomposer.insert_rotations_adjacent_to_cx(cx_aligned, qc_mat)
    bw = graph_builder.generate_brickwork_graph_from_instruction_matrix(final)
    return bw["height"] * bw["width"]


CASES = [
    # (label, builder)
    ("two_even_cx", lambda: _two_even_cx()),
    ("two_disjoint_cx_5q", lambda: _two_disjoint_cx_5q()),
    ("shift_chain_x3", lambda: _shift_chain_x3()),
    ("ten_qubit_disjoint", lambda: _ten_qubit_disjoint()),
    ("zigzag_11q", lambda: _zigzag_11q()),
]


def _two_even_cx():
    qc = QuantumCircuit(5)
    qc.h(0); qc.h(3); qc.cx(2, 3)
    return qc


def _two_disjoint_cx_5q():
    qc = QuantumCircuit(5)
    qc.cx(1, 0); qc.cx(3, 4)
    return qc


def _shift_chain_x3():
    qc = QuantumCircuit(3)
    for _ in range(3):
        qc.cx(1, 2); qc.h(1); qc.cx(0, 1)
    return qc


def _ten_qubit_disjoint():
    qc = QuantumCircuit(10)
    qc.cx(0, 1); qc.cx(3, 4); qc.cx(6, 5); qc.cx(8, 9)
    return qc


def _zigzag_11q():
    qc = QuantumCircuit(11)
    qc.cx(0, 1); qc.cx(3, 4); qc.cx(6, 7); qc.cx(9, 10)
    return qc


@pytest.mark.parametrize("label,builder", CASES, ids=[c[0] for c in CASES])
def test_new_graph_no_larger_than_legacy(label, builder):
    qc = builder()
    new = _graph_node_count_new(qc)
    legacy = _graph_node_count_legacy(qc)
    assert new <= legacy, (
        f"{label}: new graph ({new} nodes) is LARGER than legacy ({legacy})."
    )
