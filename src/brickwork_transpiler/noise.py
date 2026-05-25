"""Noisy simulation of MasonQ brickwork patterns.

This module is a thin, opinionated layer over Graphix's first-class noise
infrastructure. It re-exports the relevant Graphix classes and provides
one helper that wires a `Pattern`, a `NoiseModel`, and Graphix's
`PatternSimulator` together correctly.

Backend choice
--------------
Of Graphix's three simulator backends, **only `densitymatrix` implements
`apply_noise`**. `tensornetwork` and `statevector` raise
`NoiseNotSupportedError` when handed a `noise_model`. So
`simulate_with_noise` always uses the density-matrix backend.

Why we do **not** standardize before noisy sims
------------------------------------------------
`pattern.standardize()` reorders every command into NEEM normal form
(all N before all E before all M). That is great for tensor-network
contraction and analytic standardisation, but disastrous for density
matrix simulation: every prepared qubit must remain in the density
matrix until *all* measurements happen at the end. For a pattern with
`N` graph nodes that means peak DM dimension `2^N` — exponential in the
graph, not in the logical qubit count.

In their native NEEM-interleaved order (what MasonQ produces) qubits are
measured shortly after they are entangled, so the simulator can trace
them out promptly. Peak active-qubit count stays small (≈ row count +
local interaction degree). The defaults below reflect this.

Quick usage::

    from brickwork_transpiler import transpile
    from brickwork_transpiler.noise import (
        DepolarisingNoiseModel,
        simulate_with_noise,
        density_matrix,
        state_fidelity,
    )

    result = transpile(qc, input_state, return_result=True)
    noise = DepolarisingNoiseModel(
        prepare_error_prob=0.01,
        entanglement_error_prob=0.02,
        measure_channel_prob=0.01,
    )
    state = simulate_with_noise(result.pattern, noise, seed=0)

    rho = density_matrix(state)                       # numpy ndarray, trace 1
    fid = state_fidelity(state, qiskit_reference)     # in [0, 1]
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import numpy as np
from graphix.noise_models.depolarising import DepolarisingNoiseModel
from graphix.noise_models.noise_model import (
    ComposeNoiseModel,
    NoiseModel,
    NoiselessNoiseModel,
)
from graphix.pattern import Pattern
from graphix.simulator import PatternSimulator

__all__ = [
    "DepolarisingNoiseModel",
    "NoiseModel",
    "NoiselessNoiseModel",
    "ComposeNoiseModel",
    "simulate_with_noise",
    "density_matrix",
    "state_fidelity",
]


def simulate_with_noise(
    pattern: Pattern,
    noise_model: NoiseModel,
    *,
    input_state: Any | None = None,
    rng: np.random.Generator | None = None,
    seed: int | None = None,
    standardize: bool = False,
    shift_signals: bool = False,
    mutate: bool = False,
) -> Any:
    """Simulate `pattern` under `noise_model` using Graphix's DM backend.

    The pattern is deep-copied by default so repeated calls in notebooks
    remain idempotent. Pass `mutate=True` to operate on the original
    pattern (slightly faster, but `standardize=True` would mutate it in
    place).

    Parameters
    ----------
    pattern:
        The Graphix pattern to simulate (e.g. `result.pattern` from
        `brickwork_transpiler.transpile(..., return_result=True)`).
    noise_model:
        Any concrete subclass of `graphix.noise_models.noise_model.NoiseModel`
        — typically `DepolarisingNoiseModel` from this module.
    input_state:
        Optional input state passed straight to Graphix. `None` (the
        default) tells Graphix to seed every input node with the `|+>`
        state, matching how MasonQ patterns are normally consumed.
    rng:
        Optional `numpy.random.Generator`. If `None` and `seed` is given,
        a fresh generator is built from `seed`. If both are `None`, a
        non-deterministic default generator is used.
    seed:
        Convenience: pass an integer instead of constructing an RNG.
    standardize, shift_signals:
        **Both default to `False`** for noisy simulation, the opposite of
        the noiseless path. Standardising NEEM-reorders every measurement
        to the end of the pattern, which forces the density matrix to
        hold every prepared qubit at once and makes peak memory scale as
        `2^(graph nodes)` instead of `2^(local interaction degree)`. Only
        enable these if you have already proven your pattern is tiny.
    mutate:
        When `False` (default) operate on a deep copy of `pattern`.

    Returns
    -------
    A Graphix `DensityMatrix` (with `.rho` attribute). Use
    `density_matrix(state)` for a plain `numpy.ndarray` view.
    """
    if rng is None and seed is not None:
        rng = np.random.default_rng(seed)

    target = pattern if mutate else deepcopy(pattern)
    if standardize:
        target.standardize()
    if shift_signals:
        target.shift_signals()

    # `densitymatrix` is the only Graphix backend with native noise
    # support; `tensornetwork` and `statevector` raise
    # NoiseNotSupportedError when handed an `apply_noise` command.
    simulator = PatternSimulator(target, backend="densitymatrix", noise_model=noise_model)
    if input_state is None:
        simulator.run(rng=rng)
    else:
        simulator.run(input_state, rng=rng)
    return simulator.backend.state


def density_matrix(state: Any) -> np.ndarray:
    """Return the density matrix of a Graphix simulation result as a 2-D array.

    Works for both density-matrix and statevector backends. Statevectors
    are promoted to a pure-state density matrix `|psi><psi|`.
    """
    rho = getattr(state, "rho", None)
    if rho is not None:
        return np.asarray(rho, dtype=complex)

    psi = getattr(state, "psi", None)
    if psi is None and hasattr(state, "flatten"):
        psi = state.flatten()
    if psi is None and hasattr(state, "to_statevector"):
        psi = state.to_statevector()
    if psi is None:
        raise TypeError(
            f"Cannot extract a density matrix from object of type {type(state).__name__}; "
            "expected a Graphix DensityMatrix or Statevec result."
        )
    psi = np.asarray(psi, dtype=complex).reshape(-1)
    return np.outer(psi, psi.conj())


def state_fidelity(state: Any, reference: np.ndarray | Any) -> float:
    """Fidelity `<psi| rho |psi>` between a noisy state and a pure reference.

    Both pure (statevector) and mixed (density-matrix) `state` are
    accepted. `reference` may be a numpy 1-D vector, a Qiskit
    `Statevector`, or anything coercible to one.

    Returns the real fidelity in `[0, 1]` (clamped against tiny numerical
    overshoot from the trace).
    """
    rho = density_matrix(state)

    if hasattr(reference, "data"):  # Qiskit Statevector
        psi = np.asarray(reference.data, dtype=complex).reshape(-1)
    else:
        psi = np.asarray(reference, dtype=complex).reshape(-1)

    norm = np.linalg.norm(psi)
    if norm == 0:
        raise ValueError("Reference state has zero norm.")
    psi = psi / norm

    if rho.shape[0] != psi.shape[0]:
        raise ValueError(
            f"Dimension mismatch: density matrix is {rho.shape[0]}x{rho.shape[0]} "
            f"but reference state has dimension {psi.shape[0]}."
        )

    fidelity = float(np.real(psi.conj() @ rho @ psi))
    # Numerical clamp: tiny negative or >1 values come from finite precision.
    return max(0.0, min(1.0, fidelity))
