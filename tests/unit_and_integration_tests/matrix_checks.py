"""Version-independent checks for aligned brick matrices, shared by the tests.

Layout snapshots pinned Qiskit's exact synthesis output, which changes between
Qiskit releases: 2.4 and 2.6 pick different Euler forms for the same gates, and
2.6 commutes an Rz through a CX control. These checks state what the alignment
must guarantee instead: every CX pair shares a column on adjacent rows at the
parity its top row demands, no instruction moves on its wire, and the matrix
implements the routed circuit.
"""

from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import random_statevector

from brickwork_transpiler.cx_tags import cx_group_id, cx_role, is_cx_endpoint
from brickwork_transpiler.validation import validate_instruction_matrix


def circuit_from_matrix(matrix) -> QuantumCircuit:
    """Replay an aligned brick matrix column by column as a Qiskit circuit."""
    qc = QuantumCircuit(len(matrix))
    for c in range(len(matrix[0])):
        groups: dict[str, dict[str, int]] = {}
        for r, row in enumerate(matrix):
            for ins in row[c]:
                if is_cx_endpoint(ins.name):
                    groups.setdefault(cx_group_id(ins.name), {})[cx_role(ins.name)] = r
                elif ins.name != "id":
                    getattr(qc, ins.name)(float(ins.params[0]), r)
        for ends in groups.values():
            qc.cx(ends["c"], ends["t"])
    return qc


def cx_groups(matrix) -> dict[str, dict[str, tuple[int, int]]]:
    """Map CX group id -> role -> (row, column) for every endpoint in `matrix`."""
    groups: dict[str, dict[str, tuple[int, int]]] = {}
    for r, row in enumerate(matrix):
        for c, cell in enumerate(row):
            for ins in cell:
                if is_cx_endpoint(ins.name):
                    groups.setdefault(cx_group_id(ins.name), {})[cx_role(ins.name)] = (r, c)
    return groups


def cx_columns(matrix, row: int) -> list[int]:
    """Columns of `row` that hold a CX endpoint."""
    return [c for c, cell in enumerate(matrix[row]) if any(is_cx_endpoint(i.name) for i in cell)]


def rotation_columns(matrix, row: int) -> list[int]:
    """Columns of `row` that hold rotations."""
    return [
        c
        for c, cell in enumerate(matrix[row])
        if cell and not any(is_cx_endpoint(i.name) for i in cell)
    ]


def wire_sequences_from_matrix(matrix) -> list[list[tuple]]:
    """Per row, the instructions in column order; a CX appears as ('cx', role, partner row)."""
    groups = cx_groups(matrix)
    sequences = []
    for row in matrix:
        sequence = []
        for cell in row:
            for ins in cell:
                if is_cx_endpoint(ins.name):
                    role = cx_role(ins.name)
                    partner = groups[cx_group_id(ins.name)]["t" if role == "c" else "c"][0]
                    sequence.append(("cx", role, partner))
                elif ins.name != "id":
                    sequence.append((ins.name, float(ins.params[0])))
        sequences.append(sequence)
    return sequences


def wire_sequences_from_circuit(circuit: QuantumCircuit) -> list[list[tuple]]:
    """Per qubit, the instructions in circuit order, encoded as in `wire_sequences_from_matrix`."""
    index = {q: i for i, q in enumerate(circuit.qubits)}
    sequences: list[list[tuple]] = [[] for _ in circuit.qubits]
    for inst in circuit.data:
        op = inst.operation
        qubits = [index[q] for q in inst.qubits]
        if op.name == "cx":
            control, target = qubits
            sequences[control].append(("cx", "c", target))
            sequences[target].append(("cx", "t", control))
        elif op.name != "id":
            sequences[qubits[0]].append((op.name, float(op.params[0])))
    return sequences


def min_overlap(circuit_a: QuantumCircuit, circuit_b: QuantumCircuit, seeds=range(3)) -> float:
    """Smallest |<a|b>|^2 over random input states; 1 iff the circuits agree up to a phase."""
    worst = 1.0
    for seed in seeds:
        psi = random_statevector(2**circuit_a.num_qubits, seed=seed)
        a, b = psi.evolve(circuit_a), psi.evolve(circuit_b)
        worst = min(worst, abs(np.vdot(a.data, b.data)) ** 2)
    return worst


def check_aligned_matrix(matrix, decomposed: QuantumCircuit, *, tol: float = 1e-9) -> None:
    """Assert the invariants an aligned brick matrix must satisfy for the routed circuit."""
    validate_instruction_matrix(matrix)  # rectangular, CX pairs adjacent in one column, no mixed cells
    assert len(matrix) == decomposed.num_qubits
    for gid, ends in cx_groups(matrix).items():
        top_row = min(ends["c"][0], ends["t"][0])
        column = ends["c"][1]
        assert top_row % 2 == column % 2, f"CX group {gid} on column {column} breaks the parity rule"
    assert wire_sequences_from_matrix(matrix) == wire_sequences_from_circuit(decomposed), (
        "an instruction moved on its wire"
    )
    overlap = min_overlap(circuit_from_matrix(matrix), decomposed)
    assert overlap > 1 - tol, f"matrix does not implement the routed circuit (overlap {overlap})"
