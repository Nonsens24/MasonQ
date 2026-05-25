"""End-to-end smoke tests for `brickwork_transpiler.noise`.

These tests have to run quickly. Graphix's density-matrix backend is the
only one that natively supports noise, and its cost is `O(2^A)` per
command where `A` is the *active* qubit count maintained in the density
matrix at simulation time. We keep `A` small by:

  * using tiny circuits (one or two logical qubits),
  * **not** calling `pattern.standardize()` before simulation (which
    would push every measurement to the end of the command sequence and
    force the simulator to hold every graph node in the density matrix
    simultaneously — exponential in the number of graph nodes).

A 1-qubit, ≤8-node brickwork pattern simulates in a few ms; a 2-qubit,
≤30-node pattern simulates in well under a second.
"""

from __future__ import annotations

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from brickwork_transpiler import (
    DepolarisingNoiseModel,
    NoiselessNoiseModel,
    density_matrix,
    simulate_with_noise,
    state_fidelity,
    transpile,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_valid_density_matrix(rho: np.ndarray, tol: float = 1e-6) -> tuple[bool, str]:
    """Return `(ok, reason)` for the density-matrix axioms."""
    if rho.ndim != 2 or rho.shape[0] != rho.shape[1]:
        return False, f"non-square shape {rho.shape}"
    if not np.allclose(rho, rho.conj().T, atol=tol):
        return False, "not Hermitian"
    trace = float(np.real(np.trace(rho)))
    if not np.isclose(trace, 1.0, atol=tol):
        return False, f"trace {trace} != 1"
    eigvals = np.linalg.eigvalsh(rho).real
    if eigvals.min() < -tol:
        return False, f"negative eigenvalue {eigvals.min()}"
    return True, "ok"


# ---------------------------------------------------------------------------
# Fixtures (kept tiny so density-matrix simulation stays fast)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def single_qubit_pattern_and_reference():
    """A 1-qubit H pattern + its `|+>`-init reference statevector.

    `H |+> = |0>`, so the noiseless DM should be `|0><0|` (up to the
    Qiskit/Graphix output-order convention captured by
    `qiskit_reference_statevector`).
    """
    qc = QuantumCircuit(1)
    qc.h(0)
    input_state = Statevector.from_label("+")
    result = transpile(qc, input_state, return_result=True)
    reference = np.asarray(
        result.qiskit_reference_statevector(
            input_state=input_state, source_circuit=qc
        ),
        dtype=complex,
    )
    return result.copy_pattern(), reference


# ---------------------------------------------------------------------------
# Zero-noise sanity: density matrix matches the pure reference
# ---------------------------------------------------------------------------


def test_noiseless_model_recovers_pure_state(single_qubit_pattern_and_reference):
    pattern, reference = single_qubit_pattern_and_reference
    state = simulate_with_noise(pattern, NoiselessNoiseModel(), seed=0)

    fidelity = state_fidelity(state, reference)
    assert fidelity >= 0.999, f"noiseless fidelity dropped to {fidelity}"

    rho = density_matrix(state)
    valid, why = _is_valid_density_matrix(rho)
    assert valid, why


def test_zero_probability_depolarising_matches_pure_state(
    single_qubit_pattern_and_reference,
):
    pattern, reference = single_qubit_pattern_and_reference
    state = simulate_with_noise(pattern, DepolarisingNoiseModel(), seed=0)

    fidelity = state_fidelity(state, reference)
    assert fidelity >= 0.999, (
        f"zero-prob depolarising should be lossless; got fidelity {fidelity}"
    )


# ---------------------------------------------------------------------------
# Non-trivial noise: density matrix is valid and fidelity drops
# ---------------------------------------------------------------------------


def test_depolarising_noise_yields_valid_density_matrix(
    single_qubit_pattern_and_reference,
):
    pattern, reference = single_qubit_pattern_and_reference
    noise = DepolarisingNoiseModel(
        prepare_error_prob=0.05,
        entanglement_error_prob=0.05,
        measure_channel_prob=0.02,
    )
    state = simulate_with_noise(pattern, noise, seed=42)

    rho = density_matrix(state)
    valid, why = _is_valid_density_matrix(rho)
    assert valid, f"density matrix invalid: {why}"

    fidelity = state_fidelity(state, reference)
    assert 0.0 <= fidelity <= 1.0
    assert fidelity < 0.999, (
        f"fidelity {fidelity} did not drop under noise — model may be inert"
    )


def test_higher_error_probabilities_reduce_fidelity_more(
    single_qubit_pattern_and_reference,
):
    """Fidelity is monotone in the noise strength (averaged over a few seeds)."""
    pattern, reference = single_qubit_pattern_and_reference

    def average_fidelity(prob: float, n_seeds: int = 5) -> float:
        fidelities = []
        for seed in range(n_seeds):
            noise = DepolarisingNoiseModel(prepare_error_prob=prob)
            state = simulate_with_noise(pattern, noise, seed=seed)
            fidelities.append(state_fidelity(state, reference))
        return float(np.mean(fidelities))

    low = average_fidelity(0.01)
    high = average_fidelity(0.20)
    assert low > high, (
        f"fidelity should drop with stronger noise; got low={low}, high={high}"
    )


# ---------------------------------------------------------------------------
# Helper-function unit tests (pure-Python, no Graphix simulation)
# ---------------------------------------------------------------------------


def test_density_matrix_promotes_pure_vector_to_outer_product():
    psi = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)

    class _State:
        pass

    s = _State()
    s.psi = psi
    rho = density_matrix(s)
    expected = np.outer(psi, psi.conj())
    assert np.allclose(rho, expected)


def test_state_fidelity_perfect_for_pure_state_against_itself():
    psi = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)

    class _State:
        pass

    s = _State()
    s.psi = psi
    assert state_fidelity(s, psi) == pytest.approx(1.0, abs=1e-12)


def test_state_fidelity_zero_for_orthogonal_states():
    psi = np.array([1, 0, 0, 0], dtype=complex)
    phi = np.array([0, 1, 0, 0], dtype=complex)

    class _State:
        pass

    s = _State()
    s.psi = psi
    assert state_fidelity(s, phi) == pytest.approx(0.0, abs=1e-12)


def test_density_matrix_rejects_unknown_object():
    with pytest.raises(TypeError):
        density_matrix(object())
