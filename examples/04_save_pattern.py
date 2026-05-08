"""Save the generated Graphix pattern for inspection or archiving."""

from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from brickwork_transpiler import transpile


qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)

result = transpile(qc, Statevector.from_label("++"), return_result=True)
path = result.save_pattern_text("outputs/example_pattern.txt")

print(f"Pattern written to {path}")
