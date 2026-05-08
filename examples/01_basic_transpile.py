"""Minimal MasonQ workflow for a Qiskit circuit."""

from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from brickwork_transpiler import transpile


qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)

input_state = Statevector.from_label("++")

result = transpile(qc, input_state, return_result=True)

print(result.resources)
print("Output nodes:", result.pattern.output_nodes)

