"""Slicer round-trip & boundary-classification tests."""

import pytest
from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import sensitive
from brickwork_transpiler.cloak.slicer import (
    BoundaryType,
    SlicePlan,
    restitch,
    slice_circuit,
)


def _build_qc_with_one_oracle() -> QuantumCircuit:
    qc = QuantumCircuit(3)
    qc.h([0, 1, 2])
    with sensitive(qc, [0, 1, 2], label="oracle") as oracle:
        oracle.cx(0, 1)
        oracle.x(2)
    qc.h([0, 1, 2])
    return qc


def test_slice_produces_skeleton_with_barrier_placeholder():
    qc = _build_qc_with_one_oracle()
    plan = slice_circuit(qc)

    assert plan.num_subs == 1
    skel_names = [instr.operation.name for instr in plan.outer_skeleton.data]
    assert skel_names.count("barrier") == 1
    assert skel_names.count("sensitive") == 0
    # H layer before and after the placeholder.
    assert skel_names == ["h", "h", "h", "barrier", "h", "h", "h"]


def test_slice_then_restitch_preserves_gate_sequence():
    qc = _build_qc_with_one_oracle()
    plan = slice_circuit(qc)
    rebuilt = restitch(plan)

    original_names = [
        instr.operation.name for instr in qc.data if instr.operation.name != "sensitive"
    ]
    # The body of the sensitive block contributes ['cx', 'x'] in place.
    original_names = ["h", "h", "h", "cx", "x", "h", "h", "h"]
    rebuilt_names = [instr.operation.name for instr in rebuilt.data]
    assert rebuilt_names == original_names


def test_boundary_types_for_single_sub_are_type0_then_type1():
    qc = _build_qc_with_one_oracle()
    plan = slice_circuit(qc)
    assert plan.boundary_types == [BoundaryType.TYPE_0, BoundaryType.TYPE_1]


def test_back_to_back_sensitive_blocks_emit_type2_on_second_incoming():
    qc = QuantumCircuit(2)
    with sensitive(qc, [0, 1], label="first") as first:
        first.cx(0, 1)
    with sensitive(qc, [0, 1], label="second") as second:
        second.h(0)
    plan = slice_circuit(qc)
    # boundary list: (incoming first, outgoing first, incoming second, outgoing second)
    assert plan.boundary_types == [
        BoundaryType.TYPE_0,
        BoundaryType.TYPE_1,
        BoundaryType.TYPE_2,
        BoundaryType.TYPE_1,
    ]


def test_slice_records_global_qubit_mapping():
    qc = QuantumCircuit(4)
    with sensitive(qc, [1, 3]) as inner:
        inner.cx(0, 1)
    plan = slice_circuit(qc)
    assert plan.num_subs == 1
    assert plan.subs[0].global_qubits == [1, 3]
    assert plan.subs[0].num_qubits == 2
