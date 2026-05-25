"""Cross-cutting helpers used by the transpiler and result objects.

Three thematic groups live here:

  - **State comparison** — `assert_equal_up_to_global_phase` compares two
    statevectors up to a global phase, the canonical Qiskit-vs-Graphix check.
  - **Layout / output ordering** — utilities that translate between Qiskit's
    decomposed-circuit qubit order, Graphix's measurement-pattern output node
    order, and any ancilla padding the transpiler introduced.
  - **Reference-state construction** — `calculate_ref_state_from_qiskit_circuit`
    reproduces the post-Graphix output state from a Qiskit circuit so callers
    can verify pattern correctness.

Anything that cannot be expressed in terms of the public Graphix / Qiskit
APIs (e.g. layout introspection that depends on `transpiled_qc.layout`) is
isolated here so the rest of the package can stay portable.
"""

from __future__ import annotations

import csv
import logging
import math
import os
from typing import Any, Iterable

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import PermutationGate
from qiskit.quantum_info import Statevector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State comparison
# ---------------------------------------------------------------------------


def assert_equal_up_to_global_phase(state1, state2, tol: float = 1e-6) -> bool:
    """Return True iff `state1` and `state2` are equal up to a global phase.

    Both inputs are normalised first, then compared via inner-product
    magnitude. An `AssertionError` is raised on failure with the diagnostic
    inner product so the caller can interpret the size of the deviation.
    """
    state1 = np.asarray(state1, dtype=complex)
    state2 = np.asarray(state2, dtype=complex)

    norm1 = np.linalg.norm(state1)
    norm2 = np.linalg.norm(state2)
    if np.isclose(norm1, 0.0, atol=tol) or np.isclose(norm2, 0.0, atol=tol):
        raise AssertionError("One of the states' norms is zero (cannot compare).")

    state1 = state1 / norm1
    state2 = state2 / norm2

    inner_product = np.vdot(state1, state2)
    magnitude = float(np.abs(inner_product))

    if not np.isclose(magnitude, 1.0, atol=tol, rtol=0.0):
        raise AssertionError(
            "States are not equal up to global phase.\n"
            f"Inner product: {inner_product}\n"
            f"Absolute value: {magnitude:.6f} (should be close to 1)"
        )
    return True


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def permute_qubits(circ: QuantumCircuit, perm: list[int]) -> QuantumCircuit:
    """Return a copy of `circ` whose qubit positions are reordered by `perm`.

    `perm` must be a permutation of `range(circ.num_qubits)`. Qubit `i` in
    the input circuit appears at position `perm[i]` in the returned circuit.
    Classical bits are preserved in their original order.
    """
    n = circ.num_qubits
    if sorted(perm) != list(range(n)):
        raise ValueError("perm must be a rearrangement of 0..n-1")

    new_circ = QuantumCircuit(n, circ.num_clbits)
    old_to_new = {old: new_circ.qubits[perm[idx]] for idx, old in enumerate(circ.qubits)}
    clbit_map = dict(zip(circ.clbits, new_circ.clbits))

    for instruction in circ.data:
        new_circ.append(
            instruction.operation,
            [old_to_new[q] for q in instruction.qubits],
            [clbit_map[c] for c in instruction.clbits],
        )
    return new_circ


def index_to_coordinates(index: int, num_cols: int) -> tuple[int, int]:
    """Map a flat node index to `(row, column)` in row-major order."""
    return divmod(index, num_cols)


def map_indices_to_coordinates(
    indices: Iterable[int], num_cols: int
) -> dict[int, tuple[int, int]]:
    """Map an iterable of flat node indices to `{index: (row, column)}`."""
    return {i: index_to_coordinates(i, num_cols) for i in indices}


def get_qubit_entries(bw_pattern):
    """Return the row indices of `bw_pattern.output_nodes` (Graphix order)."""
    if bw_pattern is None:
        raise AssertionError("bw_pattern is None")
    return [t[0] for t in bw_pattern.output_nodes]


def get_qiskit_permutation(bw_pattern) -> list[int]:
    """Return the permutation that maps Qiskit qubits to Graphix outputs.

    Graphix reports output nodes in big-endian row order. Qiskit statevectors
    are little-endian. Reversing the Graphix output rows gives the
    little-endian order; this function then returns, for every Qiskit qubit
    `j`, its position in that little-endian list.

    The permutation is independent of the Qiskit layout method because the
    decomposed/routed circuit already incorporates layout and routing
    decisions before this function is consulted.
    """
    if bw_pattern is None:
        raise AssertionError("bw_pattern is None")

    qubit_entries = [t[0] for t in bw_pattern.output_nodes]
    qubit_entries.reverse()  # Graphix big-endian -> Qiskit little-endian.

    if sorted(qubit_entries) != list(range(len(qubit_entries))):
        raise ValueError(
            f"Pattern output rows are not a full qubit permutation: {qubit_entries}"
        )
    return [qubit_entries.index(j) for j in range(len(qubit_entries))]


def permute_circuit_to_graphix_output_order(
    circuit: QuantumCircuit, bw_pattern
) -> QuantumCircuit:
    """Return `circuit` with qubits permuted to Graphix output order."""
    return permute_qubits(circuit, perm=get_qiskit_permutation(bw_pattern))


# ---------------------------------------------------------------------------
# Reference-state construction
# ---------------------------------------------------------------------------


def calculate_ref_state_from_qiskit_circuit(
    bw_pattern,
    qc: QuantumCircuit,
    transpiled_qc: QuantumCircuit,
    input_vector: Statevector,
) -> Statevector:
    """Reproduce the Graphix-pattern output state with a Qiskit reference.

    The transpiled circuit may have introduced ancilla qubits, so the input
    vector is padded with `|+>` on the high-index ancillas to match. The
    transpiled circuit is then permuted to Graphix output order and evolved
    on the padded input.
    """
    if bw_pattern is None:
        raise AssertionError("bw_pattern is None")

    extended_input_vector = pad_with_plus_for_transpiled(
        input_vector=input_vector, qc=qc, transpiled_qc=transpiled_qc
    )
    logger.debug("Extended input vector dimension: %s", extended_input_vector.dim)

    qc_perm = permute_circuit_to_graphix_output_order(transpiled_qc, bw_pattern)
    return extended_input_vector.evolve(qc_perm)


def pad_with_plus_for_transpiled(
    input_vector: Statevector, qc: QuantumCircuit, transpiled_qc: QuantumCircuit
) -> Statevector:
    """Pad `input_vector` with `|+>` on each ancilla added by transpilation.

    Ancillas are placed on higher indices to match the Qiskit transpiler's
    convention.
    """
    n_in = qc.num_qubits
    n_tr = transpiled_qc.num_qubits
    if n_tr < n_in:
        raise ValueError(
            f"Transpiled circuit has fewer qubits ({n_tr}) than original ({n_in})."
        )
    if n_tr == n_in:
        return input_vector
    anc = Statevector.from_label("+" * (n_tr - n_in))
    return anc.expand(input_vector)


# ---------------------------------------------------------------------------
# CSV buffering for benchmark scripts
# ---------------------------------------------------------------------------


class BufferedCSVWriter:
    """Append-only CSV writer that accumulates a row in memory before flush.

    Useful for benchmark scripts that produce many fields per run incrementally.
    Calling `set` records a value; `flush` writes the buffered row and resets
    the buffer. The header is written once when the file does not yet exist.
    """

    def __init__(self, filename: str | os.PathLike, headers: list[str]) -> None:
        self.filename = os.fspath(filename)
        self.headers = list(headers)
        self.row: dict[str, Any] = {}
        if not os.path.exists(self.filename):
            with open(self.filename, mode="w", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=self.headers)
                writer.writeheader()

    def set(self, key: str, value: Any) -> None:
        """Record a field for the row currently being built."""
        self.row[key] = value

    def flush(self) -> None:
        """Append the buffered row (possibly partial) and reset the buffer."""
        with open(self.filename, mode="a", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=self.headers, restval="")
            writer.writerow(self.row)
        self.row = {}


# ---------------------------------------------------------------------------
# Layout extraction (used by `result.py` for verification)
# ---------------------------------------------------------------------------


def undo_layout_on_state(
    state: Statevector | np.ndarray,
    physical_to_logical: list[int | None],
    total_qubits: int | None = None,
) -> Statevector:
    """Reorder a transpiled-circuit-order state back to logical-first order.

    `physical_to_logical[p] = j` means physical wire `p` carries logical
    qubit `j`. Wires whose value is `None` are treated as ancillas and moved
    after the logical block (positions `L`, `L+1`, ...).
    """
    if isinstance(state, Statevector):
        sv = state
        n = sv.num_qubits
    else:
        arr = np.asarray(state, dtype=complex)
        n = total_qubits if total_qubits is not None else int(round(math.log2(arr.size)))
        sv = Statevector(arr, dims=[2] * n)

    if len(physical_to_logical) != n:
        raise ValueError(
            f"physical_to_logical has length {len(physical_to_logical)}, "
            f"but state has {n} qubits. Provide a full-length map."
        )

    logical_positions = [(p, j) for p, j in enumerate(physical_to_logical) if j is not None]
    logical_count = len(logical_positions)

    perm: list[int | None] = [None] * n
    for p, j in logical_positions:
        perm[p] = j
    ancilla_positions = [p for p, j in enumerate(physical_to_logical) if j is None]
    for offset, p in enumerate(ancilla_positions):
        perm[p] = logical_count + offset

    if sorted(perm) != list(range(n)):
        raise ValueError(
            f"Invalid permutation {perm} (must be a permutation of 0..{n - 1})."
        )
    return sv.evolve(PermutationGate(perm))


def extract_logical_to_physical(
    qc_in: QuantumCircuit, qc_out: QuantumCircuit
) -> list[int]:
    """Return `physical_to_logical` for the transpiled circuit `qc_out`.

    `physical_to_logical[p] = j` means the output wire `p` of `qc_out`
    carries logical qubit `j` from `qc_in`. When `qc_out.layout` is missing
    or incomplete, the identity mapping on the common qubit count is
    returned.
    """

    def invert(pi: list[int]) -> list[int]:
        inv = [0] * len(pi)
        for j, p in enumerate(pi):
            inv[p] = j
        return inv

    layout = getattr(qc_out, "layout", None)
    logger.debug("Transpiled layout: %s", layout)

    if layout is None or getattr(layout, "initial_layout", None) is None:
        return list(range(min(qc_in.num_qubits, qc_out.num_qubits)))

    init = layout.initial_layout
    try:
        pre_route = [init[q] for q in qc_in.qubits]
    except Exception:
        logger.debug("Could not index initial_layout directly; no fallback active.")
        return list(range(min(qc_in.num_qubits, qc_out.num_qubits)))

    try:
        route = list(layout.routing_permutation())
    except Exception:
        route = list(range(qc_out.num_qubits))

    logical_to_physical = [route[p] for p in pre_route]
    return invert(logical_to_physical)
