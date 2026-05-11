"""Resource accounting for decomposed brickwork outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qiskit import QuantumCircuit

from .sparse import SparseInstructionMatrix


@dataclass(frozen=True)
class ResourceEstimate:
    qubits: int
    qiskit_depth: int
    qiskit_gates: int
    cx_gates: int
    brick_rows: int
    brick_columns: int
    graph_depth: int
    graph_nodes: int


def estimate_resources(
    decomposed_circuit: QuantumCircuit,
    instruction_matrix: list[list[list[Any]]] | SparseInstructionMatrix,
) -> ResourceEstimate:
    if isinstance(instruction_matrix, SparseInstructionMatrix):
        brick_rows = instruction_matrix.rows
        brick_columns = instruction_matrix.columns
    else:
        brick_rows = len(instruction_matrix)
        brick_columns = len(instruction_matrix[0]) if instruction_matrix else 0
    graph_depth = brick_columns * 4 + 1
    counts = decomposed_circuit.count_ops()
    return ResourceEstimate(
        qubits=decomposed_circuit.num_qubits,
        qiskit_depth=decomposed_circuit.depth(),
        qiskit_gates=sum(counts.values()),
        cx_gates=counts.get("cx", 0),
        brick_rows=brick_rows,
        brick_columns=brick_columns,
        graph_depth=graph_depth,
        graph_nodes=brick_rows * graph_depth,
    )
