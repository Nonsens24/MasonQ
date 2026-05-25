"""Regression tests for the VEIL Quantum pattern + application examples.

Two things matter and are asserted here:

  1. **``s << d``.** Every example under ``examples/cloak/patterns/``
     and ``examples/cloak/applications/`` is supposed to demonstrate
     the small-patch idiom.  If a future edit pushes the source-gate
     blind share above ``S_LL_D_THRESHOLD`` the test fails — the
     strategic doc ``docs/veil_opportunities.md`` and the code stay
     synchronised.

  2. **Cloak roundtrip preserves semantics.**  Each example's circuit
     simulated under ``simulate_cloaked`` must match the plaintext
     reference (the same circuit with every ``Sensitive`` instruction
     unfolded) up to floating-point error.  This guards against
     accidental semantic changes in the cloak pipeline.

The tests load each example module dynamically by path so the test
file stays unaware of new examples that get added — drop a file under
``examples/cloak/{patterns,applications}/`` with a top-level ``qc``
variable and it gets picked up automatically.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from brickwork_transpiler.cloak import (
    Sensitive,
    compute_blind_share,
    simulate_cloaked,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
PATTERNS_DIR = REPO_ROOT / "examples" / "cloak" / "patterns"
APPLICATIONS_DIR = REPO_ROOT / "examples" / "cloak" / "applications"

# Source-gate blind share above which we consider an example to have
# slipped out of the small-patch idiom.  35% is the soft cap quoted in
# the VEIL strategic doc; raise it deliberately if a future pattern
# legitimately needs more.
S_LL_D_THRESHOLD = 0.35


def _load_example(path: Path) -> ModuleType:
    """Load an example file as a module so we can pull its ``qc``."""
    spec = importlib.util.spec_from_file_location(
        f"_cloak_example_{path.stem}", str(path)
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load example {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _example_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(p for p in directory.glob("*.py") if not p.name.startswith("_"))


def _plaintext_reference(qc: QuantumCircuit) -> Statevector:
    """Inline every ``Sensitive`` instruction and evolve the result."""
    flat = QuantumCircuit(qc.num_qubits, qc.num_clbits, name=f"{qc.name}_flat")
    for instr in qc.data:
        op = instr.operation
        if isinstance(op, Sensitive):
            flat.compose(op.definition, qubits=list(instr.qubits), inplace=True)
        else:
            flat.append(op, list(instr.qubits), list(instr.clbits))
    return Statevector.from_instruction(flat)


PATTERN_FILES = _example_files(PATTERNS_DIR)
APPLICATION_FILES = _example_files(APPLICATIONS_DIR)


@pytest.mark.parametrize("path", PATTERN_FILES, ids=lambda p: p.name)
def test_pattern_example_blind_share_below_threshold(path: Path) -> None:
    module = _load_example(path)
    qc = getattr(module, "qc", None)
    assert isinstance(qc, QuantumCircuit), f"{path.name} must expose a top-level `qc`."
    share = compute_blind_share(qc)
    assert share.gates_total > 0, f"{path.name} has zero gates."
    assert share.gate_fraction <= S_LL_D_THRESHOLD, (
        f"{path.name}: source-gate blind share {share.gate_fraction:.1%} "
        f"exceeds {S_LL_D_THRESHOLD:.0%} — pattern has drifted out of the "
        f"small-patch idiom. {share.format()}"
    )


@pytest.mark.parametrize("path", APPLICATION_FILES, ids=lambda p: p.name)
def test_application_example_blind_share_below_threshold(path: Path) -> None:
    module = _load_example(path)
    qc = getattr(module, "qc", None)
    assert isinstance(qc, QuantumCircuit), f"{path.name} must expose a top-level `qc`."
    share = compute_blind_share(qc)
    assert share.gates_total > 0, f"{path.name} has zero gates."
    assert share.gate_fraction <= S_LL_D_THRESHOLD, (
        f"{path.name}: source-gate blind share {share.gate_fraction:.1%} "
        f"exceeds {S_LL_D_THRESHOLD:.0%} — application has drifted out of "
        f"the small-patch idiom. {share.format()}"
    )


@pytest.mark.slow
@pytest.mark.parametrize("path", PATTERN_FILES, ids=lambda p: p.name)
def test_pattern_example_cloak_roundtrip_matches_plaintext(path: Path) -> None:
    module = _load_example(path)
    qc = getattr(module, "qc")
    cloak_state = simulate_cloaked(qc, seed=0)
    reference = _plaintext_reference(qc)
    fidelity = float(np.abs(cloak_state.inner(reference)))
    assert fidelity > 1.0 - 1e-6, (
        f"{path.name}: cloak roundtrip fidelity {fidelity:.6f} != 1.0; "
        "cloak pipeline broke this example's semantics."
    )


def test_pattern_examples_directory_is_populated() -> None:
    """If this fails, the pattern catalogue and the test sweep are out of sync."""
    assert len(PATTERN_FILES) >= 6, (
        f"expected at least 6 pattern examples, found {len(PATTERN_FILES)}"
    )


def test_application_examples_directory_is_populated() -> None:
    assert len(APPLICATION_FILES) >= 4, (
        f"expected at least 4 application examples, found {len(APPLICATION_FILES)}"
    )
