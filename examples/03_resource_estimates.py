"""Inspect resource estimates without manual matrix handling."""

from brickwork_transpiler import circuits, transpile


qc, input_state = circuits.qft(2)
result = transpile(qc, input_state, return_result=True)

resources = result.resources
print(f"Qubits: {resources.qubits}")
print(f"Qiskit depth after decomposition: {resources.qiskit_depth}")
print(f"CX gates: {resources.cx_gates}")
print(f"Brickwork rows x columns: {resources.brick_rows} x {resources.brick_columns}")
print(f"Graph nodes: {resources.graph_nodes}")

