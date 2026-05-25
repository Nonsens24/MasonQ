"""Diagnostic helpers that print Graphix's own pattern transpilation.

These functions exist as sanity checks: they let a developer compare the
measurement-angle layout MasonQ produces against Graphix's reference
transpilation of the same circuit. Not used by the public API.
"""

import numpy as np
from graphix.transpiler import Circuit


def _build_demo_circuit() -> Circuit:
    """Return the small reference circuit used by both diagnostics."""
    circuit = Circuit(2)
    circuit.rz(0, np.pi / 4)
    circuit.rx(0, np.pi / 8)
    circuit.rz(0, np.pi / 16)
    return circuit


def print_pattern() -> None:
    """Print Graphix's raw transpiled pattern (no standardisation)."""
    print("Graphix angle transpilation (no optimisation):")
    pattern = _build_demo_circuit().transpile().pattern
    pattern.print_pattern()


def print_standard_pattern() -> None:
    """Print Graphix's transpiled pattern after `standardize` + `shift_signals`."""
    print("Graphix angle transpilation (with optimisation):")
    pattern = _build_demo_circuit().transpile().pattern
    pattern.standardize()
    pattern.shift_signals()
    pattern.print_pattern()
