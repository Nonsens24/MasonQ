"""Transpile, save a graph plot, and verify against Qiskit."""

from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from brickwork_transpiler import transpile


qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)

input_state = Statevector.from_label("++")
result = transpile(qc, input_state, return_result=True)

result.plot(save_path="images/graphs/example_brickwork.pdf", show=False)

verification = result.verify()
print(f"Equivalent: {verification.equivalent}")
print(f"Fidelity: {verification.fidelity:.12f}")

