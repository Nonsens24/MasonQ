"""Structured return objects for the public API."""

from __future__ import annotations

import copy
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from . import utils
from .progress import ProgressReporter
from .resources import ResourceEstimate, estimate_resources


@dataclass(frozen=True)
class VerificationResult:
    """Numerical comparison between Qiskit and brickwork simulation outputs."""

    equivalent: bool
    fidelity: float
    inner_product: complex
    tolerance: float
    reference_state: np.ndarray
    simulated_state: np.ndarray

    def raise_for_failure(self) -> None:
        if not self.equivalent:
            raise AssertionError(
                "States are not equal up to global phase.\n"
                f"Inner product: {self.inner_product}\n"
                f"Absolute value: {self.fidelity:.6f} "
                f"(tolerance {self.tolerance})"
            )


def _plus_state(num_qubits: int) -> Statevector:
    return Statevector.from_label("+" * num_qubits)


def _reference_input(state: Any, num_qubits: int) -> Statevector:
    """Return the reference input as a `Statevector`; it must be |+>^n.

    Brickwork patterns prepare every graph qubit in |+>, so the Graphix output
    is always U|+...+>. `None` selects that state; anything else is checked
    against it.
    """
    if state is None:
        return _plus_state(num_qubits)
    sv = state if isinstance(state, Statevector) else Statevector(np.asarray(state, dtype=complex))
    if sv.num_qubits != num_qubits:
        raise ValueError(
            f"Input state has {sv.num_qubits} qubits but the circuit has {num_qubits}."
        )
    if not sv.equiv(_plus_state(num_qubits)):
        raise ValueError(
            "Brickwork patterns prepare every qubit in |+>, so the Graphix output is "
            "U|+...+>. Pass no input state (the default) or |+>^n; to start from another "
            "state, prepend the preparation gates to the circuit."
        )
    return sv


def _simulate_pattern(pattern: Any, **kwargs: Any) -> Any:
    """Run Graphix's simulator on `pattern`.

    The method is `simulate` from Graphix 0.4 and `simulate_pattern` before.
    """
    run = getattr(pattern, "simulate", None) or pattern.simulate_pattern
    return run(**kwargs)


def _flat_statevector(state: Any) -> np.ndarray:
    """Return a Graphix backend state as a flat complex NumPy vector."""
    if hasattr(state, "to_statevector"):
        return np.asarray(state.to_statevector(), dtype=complex)
    if hasattr(state, "flatten"):
        return np.asarray(state.flatten(), dtype=complex)
    return np.asarray(state, dtype=complex).reshape(-1)


@dataclass(frozen=True)
class TranspileResult:
    """Result of converting a Qiskit circuit into a brickwork pattern.

    The object is iterable for compatibility with the historical tuple return:
    `pattern, colour_map, circuit = result`.

    `input_state` is only used as the reference input of `verify()`. The
    pattern itself always starts from |+>^n, so leave it `None` or pass that
    state.
    """

    pattern: Any
    colour_map: dict
    decomposed_circuit: QuantumCircuit
    instruction_matrix: list | None = None
    source_circuit: QuantumCircuit | None = None
    input_state: Any | None = None

    @property
    def resources(self) -> ResourceEstimate | None:
        if self.instruction_matrix is None:
            return None
        return estimate_resources(self.decomposed_circuit, self.instruction_matrix)

    @property
    def transpiled_circuit(self) -> QuantumCircuit:
        """Compatibility alias for `decomposed_circuit`.

        The returned Qiskit circuit has been decomposed/routed into the brick
        basis used by the package; it is not the final MBQC pattern.
        """
        return self.decomposed_circuit

    @property
    def color_map(self) -> dict:
        """US spelling alias for `colour_map`."""
        return self.colour_map

    def copy_pattern(self):
        """Return a deep copy of the mutable Graphix pattern."""
        return copy.deepcopy(self.pattern)

    def plot(
        self,
        *,
        save_path: str | Path | None = None,
        show: bool = False,
        title: str = "Brickwork graph",
        show_angles: bool = True,
        use_node_colours: bool = True,
        close: bool = True,
        **kwargs: Any,
    ):
        """Plot the brickwork graph using safe defaults for notebooks and IDEs."""
        from . import visualiser

        return visualiser.plot_brickwork_graph_from_pattern(
            self.pattern,
            show_angles=show_angles,
            node_colours=self.colour_map,
            use_node_colours=use_node_colours,
            title=title,
            save_plot=save_path is None,
            save_path=str(save_path) if save_path is not None else None,
            show=show,
            close=close,
            **kwargs,
        )

    def simulate(
        self,
        *,
        backend: str = "tensornetwork",
        graph_prep: str = "parallel",
        standardize: bool = True,
        shift_signals: bool = True,
        rng: np.random.Generator | None = None,
        seed: int | None = 0,
        mutate: bool = False,
        progress: bool | Callable[[str], None] = False,
        **kwargs: Any,
    ):
        """Simulate the Graphix pattern and return the backend state object.

        By default this works on a copy of the pattern, so repeated calls are
        safe in notebooks. Pass `mutate=True` to run on the stored pattern.
        """
        reporter = ProgressReporter(progress)
        resources = self.resources
        if resources is not None:
            reporter.emit(
                "Preparing Graphix simulation: "
                f"{resources.graph_nodes} graph nodes, backend={backend!r}."
            )
        else:
            reporter.emit(f"Preparing Graphix simulation: backend={backend!r}.")

        with reporter.step("Preparing pattern copy.", "Pattern preparation complete"):
            pattern = self.pattern if mutate else self.copy_pattern()
            if standardize:
                pattern.standardize()
            if shift_signals:
                pattern.shift_signals()
        if rng is None and seed is not None:
            rng = np.random.default_rng(seed)

        simulate_kwargs = dict(kwargs)
        if backend in {"tensornetwork", "mps"}:
            simulate_kwargs.setdefault("graph_prep", graph_prep)
        with reporter.step("Running Graphix pattern simulation.", "Graphix simulation complete"):
            return _simulate_pattern(pattern, backend=backend, rng=rng, **simulate_kwargs)

    def simulate_statevector(self, **kwargs: Any) -> np.ndarray:
        """Simulate the Graphix pattern and return its flat output statevector."""
        return _flat_statevector(self.simulate(**kwargs))

    def output_permutation(self) -> list[int]:
        """Return the Qiskit-to-Graphix output qubit permutation.

        Apply this to the decomposed Qiskit circuit before statevector
        simulation when manually comparing against `simulate_statevector()`.
        """
        return utils.get_qiskit_permutation(self.pattern)

    def qiskit_reference_statevector(
        self,
        input_state: Any | None = None,
        source_circuit: QuantumCircuit | None = None,
    ) -> np.ndarray:
        """Return the layout-aware Qiskit reference in Graphix output order.

        The reference input is |+>^n, the state every brickwork pattern starts
        from. `input_state` is accepted only to be explicit and must equal it
        up to a global phase.
        """
        circuit = source_circuit or self.source_circuit
        if circuit is None:
            raise ValueError("qiskit_reference_statevector() needs a source circuit.")
        state = _reference_input(
            input_state if input_state is not None else self.input_state,
            circuit.num_qubits,
        )
        return np.asarray(
            utils.calculate_ref_state_from_qiskit_circuit(
                self.pattern,
                circuit,
                self.decomposed_circuit,
                state,
            ),
            dtype=complex,
        )

    def verify(
        self,
        input_state: Any | None = None,
        source_circuit: QuantumCircuit | None = None,
        *,
        tolerance: float = 1e-6,
        raise_on_failure: bool = False,
        progress: bool | Callable[[str], None] = False,
        **simulate_kwargs: Any,
    ) -> VerificationResult:
        """Compare the Graphix simulation against Qiskit's statevector result.

        Keyword arguments other than the ones named here go to `simulate()`.
        """
        circuit = source_circuit or self.source_circuit
        if circuit is None:
            raise ValueError("verify() needs a source circuit.")

        reporter = ProgressReporter(progress)
        resources = self.resources
        if resources is not None:
            reporter.emit(
                "Starting verification: "
                f"{resources.graph_nodes} graph nodes, "
                f"{self.decomposed_circuit.num_qubits} output qubits."
            )
        else:
            reporter.emit("Starting verification.")

        with reporter.step("Computing layout-aware Qiskit reference.", "Qiskit reference complete"):
            reference = self.qiskit_reference_statevector(
                input_state=input_state, source_circuit=circuit
            )
        simulated = self.simulate_statevector(progress=progress, **simulate_kwargs)
        with reporter.step(
            "Comparing statevectors up to global phase.",
            "Statevector comparison complete",
        ):
            inner_product = utils.state_overlap(reference, simulated, tol=tolerance)
            fidelity = float(abs(inner_product))
        result = VerificationResult(
            equivalent=bool(np.isclose(fidelity, 1.0, atol=tolerance, rtol=0.0)),
            fidelity=fidelity,
            inner_product=inner_product,
            tolerance=tolerance,
            reference_state=reference,
            simulated_state=simulated,
        )
        reporter.emit(
            "Verification complete: "
            f"equivalent={result.equivalent}, fidelity={result.fidelity:.12g}."
        )
        if raise_on_failure:
            result.raise_for_failure()
        return result

    def save_pattern_text(self, path: str | Path, *, limit: int | None = None) -> Path:
        """Write Graphix's text representation of the pattern to disk.

        Commands are written one per line in execution order. `limit` caps the
        number of commands written; `None` writes them all.
        """
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        text = self.pattern.to_unicode(left_to_right=True, limit=limit)
        # Graphix separates commands with spaces; node tuples contain ", ",
        # so split only on spaces outside parentheses.
        lines = re.split(r" (?![^(]*\))", text)
        output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return output

    def __iter__(self) -> Iterator[Any]:
        yield self.pattern
        yield self.colour_map
        yield self.decomposed_circuit
