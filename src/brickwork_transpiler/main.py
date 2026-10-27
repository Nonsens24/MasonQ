"""Demo entry point: transpile a small circuit and check it against Qiskit.

Prefer module execution:

    python -m brickwork_transpiler.main

The console script `masonq-demo` runs the same function after `pip install -e .`.

Direct file execution (`python src/brickwork_transpiler/main.py`) puts the
package directory itself on `sys.path`, where the sibling module
`brickwork_transpiler.py` would shadow the package. The bootstrap below
replaces that path entry with the `src` directory.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

if __package__ in {None, ""}:  # Direct file execution; rebuild sys.path safely.
    package_dir = Path(__file__).resolve().parent
    sys.path = [p for p in sys.path if Path(p or ".").resolve() != package_dir]
    sys.path.insert(0, str(package_dir.parent))

# Cache locations for Numba/Matplotlib must be set before importing graphix.
for _var, _dir in (
    ("NUMBA_CACHE_DIR", "masonq_numba_cache"),
    ("MPLCONFIGDIR", "masonq_mpl_cache"),
    ("XDG_CACHE_HOME", "masonq_cache"),
):
    os.environ.setdefault(_var, str(Path(tempfile.gettempdir()) / _dir))

from qiskit import QuantumCircuit  # noqa: E402
from qiskit.quantum_info import Statevector  # noqa: E402

from brickwork_transpiler import transpile  # noqa: E402


def build_demo_circuit() -> QuantumCircuit:
    """Three qubits with rotations, two CX gates and a Toffoli."""
    qc = QuantumCircuit(3, name="demo")
    qc.h(0)
    qc.cx(0, 1)
    qc.ry(0.3, 2)
    qc.cx(1, 2)
    qc.rz(0.7, 0)
    qc.ccx(0, 1, 2)
    return qc


def main() -> int:
    """Transpile the demo circuit, print its resources and verify the pattern."""
    qc = build_demo_circuit()
    # Brickwork patterns start every qubit in |+>, so that is the reference input.
    input_state = Statevector.from_label("+" * qc.num_qubits)

    result = transpile(qc, input_state, return_result=True, progress=True)
    print(result.resources)
    print("Pattern output nodes:", result.pattern.output_nodes)

    verification = result.verify(progress=True)
    print(f"Graphix matches Qiskit: {verification.equivalent} (fidelity {verification.fidelity:.6f})")
    return 0 if verification.equivalent else 1


if __name__ == "__main__":
    raise SystemExit(main())
