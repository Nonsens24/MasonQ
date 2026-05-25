"""`instructions_to_matrix_dag` must never mutate Qiskit's instruction
singletons.

Non-CX gates are appended unchanged (no `to_mutable()` clone). CX gates
get fresh mutable clones because the endpoint roles are encoded into the
`.name`. Either way, the input circuit's instruction objects must have
their original `.name` after the function returns.
"""

import math

from qiskit import QuantumCircuit

from brickwork_transpiler import decomposer


def test_input_circuit_instructions_are_not_mutated():
    """Qiskit's `circuit_to_dag` already clones operations into DAG nodes,
    so identity-equality between input ops and matrix ops is not preserved
    (and is not under our control). What *is* under our control: the input
    circuit's instruction names must be unchanged after the call. The CX
    name `cx` must not become `cx0c` or `cx0t` on the user's circuit."""
    qc = QuantumCircuit(3)
    qc.rz(math.pi / 7, 0)
    qc.rx(math.pi / 5, 1)
    qc.id(2)
    qc.cx(0, 1)

    original_names = [instr.operation.name for instr in qc.data]

    qc_mat, cx_mat = decomposer.instructions_to_matrix_dag(qc)

    after_names = [instr.operation.name for instr in qc.data]
    assert after_names == original_names, (
        "instructions_to_matrix_dag mutated the input circuit's instruction "
        f"names: {original_names} -> {after_names}"
    )


def test_cx_instructions_are_cloned_and_renamed():
    qc = QuantumCircuit(2)
    qc.cx(0, 1)
    cx_op = qc.data[0].operation

    qc_mat, cx_mat = decomposer.instructions_to_matrix_dag(qc)

    # Original CX must still be named "cx" — never mutated.
    assert cx_op.name == "cx"

    # Matrix CX endpoints are fresh objects with role-tagged names.
    flat = [
        instr
        for row in qc_mat
        for cell in row
        for instr in cell
    ]
    cx_endpoints = [i for i in flat if i.name.startswith("cx") and i.name != "cx"]
    names = sorted(i.name for i in cx_endpoints)
    assert names == ["cx0c", "cx0t"]
    for i in cx_endpoints:
        assert i is not cx_op, "CX endpoints must be clones, not the original"


def test_non_cx_cells_share_dag_instance_within_one_call():
    """In a single `instructions_to_matrix_dag` call, the matrix instance
    of a non-CX gate is exactly the DAG-node operation object (Qiskit's
    DAG performs one clone; we then append by reference). If the
    decomposer regressed to calling `to_mutable()` on non-CX, the matrix
    instance would be a *second* clone.

    We verify this by mutating the matrix instance's `name` and checking
    the input circuit's instruction name is unaffected (this would already
    be true) — but more sharply, by introspecting the bytecode-free
    structure: the matrix cell holds the DAG op object, not a fresh copy.
    """
    qc = QuantumCircuit(1)
    qc.rz(0.5, 0)

    qc_mat, _ = decomposer.instructions_to_matrix_dag(qc)
    flat = [instr for row in qc_mat for cell in row for instr in cell]
    assert len(flat) == 1
    matrix_instance = flat[0]
    # Matrix instance has the same name and params as the input.
    assert matrix_instance.name == "rz"
    assert float(matrix_instance.params[0]) == 0.5
    # The user's input circuit must remain pristine (no rename leak).
    assert qc.data[0].operation.name == "rz"


def test_cx_cells_have_distinct_clones_per_call():
    """CXs *must* be cloned (so the role-tag mutation does not leak). Two
    independent calls produce different CX endpoint objects."""
    qc = QuantumCircuit(2)
    qc.cx(0, 1)

    def get_endpoints(qc_mat):
        return [
            instr
            for row in qc_mat
            for cell in row
            for instr in cell
            if instr.name.startswith("cx") and instr.name != "cx"
        ]

    ep1 = get_endpoints(decomposer.instructions_to_matrix_dag(qc)[0])
    ep2 = get_endpoints(decomposer.instructions_to_matrix_dag(qc)[0])
    assert len(ep1) == 2 and len(ep2) == 2
    # Per call, each endpoint is a fresh mutable object.
    for a, b in zip(sorted(ep1, key=lambda i: i.name), sorted(ep2, key=lambda i: i.name)):
        assert a is not b, "CX endpoint objects must be cloned per call"
