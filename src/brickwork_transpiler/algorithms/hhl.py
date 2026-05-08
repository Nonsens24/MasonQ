"""HHL reference-circuit helpers.

This module depends on the external `quantum_linear_solvers` project, which is
not part of the core transpiler dependency set. Imports are intentionally lazy
so `brickwork_transpiler.algorithms` remains importable without the HHL stack.
"""

from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit


def generate_example_hhl_QC() -> QuantumCircuit:
    try:
        import linear_solvers
    except ImportError as exc:
        raise ImportError(
            "HHL examples require the optional external `quantum_linear_solvers` "
            "package. MasonQ no longer imports Qiskit's removed QuantumInstance "
            "or qiskit.Aer APIs."
        ) from exc

    A = np.array([[1.0, 0.5], [0.5, 1.0]])
    b = np.array([1.0, 0.0])
    b = b / np.linalg.norm(b)

    try:
        hhl_solver = linear_solvers.HHL()
    except TypeError as exc:
        raise RuntimeError(
            "The installed `quantum_linear_solvers` package expects legacy "
            "Qiskit QuantumInstance APIs and is not compatible with MasonQ's "
            "Qiskit 2.x target stack."
        ) from exc
    return hhl_solver.construct_circuit(A, b)
