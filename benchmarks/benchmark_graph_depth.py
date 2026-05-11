"""Benchmark MasonQ graph-depth behaviour on simple CX workloads.

This is not a correctness test and should not be part of the default pytest
loop. It is a lightweight command-line tool for comparing decomposition choices
and scheduler changes.

Usage:

    python benchmarks/benchmark_graph_depth.py
"""

from __future__ import annotations

from dataclasses import asdict
from time import perf_counter

from qiskit import QuantumCircuit

from brickwork_transpiler import decomposer
from brickwork_transpiler.resources import estimate_resources


def chain_cx(num_qubits: int, layers: int) -> QuantumCircuit:
    qc = QuantumCircuit(num_qubits)
    for _ in range(layers):
        for i in range(num_qubits - 1):
            qc.cx(i, i + 1)
    return qc


def staggered_cx(num_qubits: int, layers: int) -> QuantumCircuit:
    qc = QuantumCircuit(num_qubits)
    for _ in range(layers):
        for i in range(0, num_qubits - 1, 2):
            qc.cx(i, i + 1)
        for i in range(1, num_qubits - 1, 2):
            qc.cx(i, i + 1)
    return qc


def run_case(name: str, qc: QuantumCircuit) -> dict[str, float | int | str]:
    t0 = perf_counter()
    decomposed = decomposer.decompose_qc_to_bricks_qiskit(
        qc,
        opt=1,
        fallback_opt=None,
        with_ancillas=False,
    )
    t1 = perf_counter()
    original_matrix, cx_matrix = decomposer.instructions_to_matrix_dag(decomposed)
    t2 = perf_counter()
    matrix = decomposer.align_bricks(cx_matrix, original_matrix)
    t3 = perf_counter()
    resources = estimate_resources(decomposed, matrix)
    t4 = perf_counter()

    data = asdict(resources)
    data.update(
        {
            "case": name,
            "input_qubits": qc.num_qubits,
            "input_gates": sum(qc.count_ops().values()),
            "decomposed_cx": decomposed.count_ops().get("cx", 0),
            "matrix_rows": len(matrix),
            "matrix_columns": len(matrix[0]) if matrix else 0,
            "decompose_seconds": t1 - t0,
            "matrix_build_seconds": t2 - t1,
            "align_seconds": t3 - t2,
            "resources_seconds": t4 - t3,
        }
    )
    return data


def main() -> None:
    cases = []
    for num_qubits in (4, 8, 12, 16, 20):
        cases.append((f"chain_n{num_qubits}", chain_cx(num_qubits, layers=4)))
        cases.append((f"staggered_n{num_qubits}", staggered_cx(num_qubits, layers=4)))

    headers = [
        "case",
        "input_qubits",
        "input_gates",
        "decomposed_cx",
        "brick_columns",
        "graph_depth",
        "graph_nodes",
        "decompose_seconds",
        "matrix_build_seconds",
        "align_seconds",
        "resources_seconds",
    ]
    print(",".join(headers))
    for name, qc in cases:
        row = run_case(name, qc)
        print(",".join(str(row[key]) for key in headers))


if __name__ == "__main__":
    main()
