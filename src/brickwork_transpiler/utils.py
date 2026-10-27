"""Cross-cutting helpers used by the transpiler, the result objects and the tests.

Three thematic groups live here:

  - **State comparison** — `state_overlap` and `assert_equal_up_to_global_phase`
    compare two statevectors up to a global phase, the canonical
    Qiskit-vs-Graphix check.
  - **Layout / output ordering** — utilities that translate between Qiskit's
    decomposed-circuit qubit order, Graphix's measurement-pattern output node
    order, and any ancilla padding the transpiler introduced.
  - **Reference-state construction** — `calculate_ref_state_from_qiskit_circuit`
    reproduces the post-Graphix output state from a Qiskit circuit so callers
    can verify pattern correctness.
"""

from __future__ import annotations

import logging
import math

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import PermutationGate
from qiskit.quantum_info import Statevector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State comparison
# ---------------------------------------------------------------------------


def _as_vector(state) -> np.ndarray:
    if isinstance(state, Statevector):
        state = state.data
    return np.asarray(state, dtype=complex).reshape(-1)


def state_overlap(state1, state2, *, tol: float = 1e-6) -> complex:
    """Inner product of the two states after normalisation.

    Its magnitude is 1 iff the states are equal up to a global phase. Raises
    `ValueError` when either state has (numerically) zero norm.
    """
    state1 = _as_vector(state1)
    state2 = _as_vector(state2)
    norm1 = np.linalg.norm(state1)
    norm2 = np.linalg.norm(state2)
    if np.isclose(norm1, 0.0, atol=tol) or np.isclose(norm2, 0.0, atol=tol):
        raise ValueError("One of the states' norms is zero (cannot compare).")
    return complex(np.vdot(state1 / norm1, state2 / norm2))


def assert_equal_up_to_global_phase(state1, state2, tol: float = 1e-6) -> bool:
    """Return True iff `state1` and `state2` are equal up to a global phase.

    An `AssertionError` is raised on failure with the diagnostic inner
    product so the caller can interpret the size of the deviation.
    """
    try:
        inner_product = state_overlap(state1, state2, tol=tol)
    except ValueError as exc:
        raise AssertionError(str(exc)) from None
    magnitude = abs(inner_product)
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


# ---------------------------------------------------------------------------
# Reference-state construction
# ---------------------------------------------------------------------------


def calculate_ref_state_from_qiskit_circuit(
    bw_pattern,
    qc: QuantumCircuit,
    transpiled_qc: QuantumCircuit,
    input_vector,
) -> Statevector:
    """Reproduce the Graphix-pattern output state with a Qiskit reference.

    The transpiled circuit may have introduced ancilla qubits, so the input
    vector is padded with `|+>` on the high-index ancillas to match. The
    transpiled circuit is then permuted to Graphix output order and evolved
    on the padded input. `input_vector` may be a `Statevector` or any
    array-like of amplitudes.
    """
    if bw_pattern is None:
        raise AssertionError("bw_pattern is None")

    extended_input_vector = pad_with_plus_for_transpiled(
        input_vector=input_vector, qc=qc, transpiled_qc=transpiled_qc
    )
    qc_perm = permute_qubits(transpiled_qc, perm=get_qiskit_permutation(bw_pattern))
    return extended_input_vector.evolve(qc_perm)


def pad_with_plus_for_transpiled(
    input_vector, qc: QuantumCircuit, transpiled_qc: QuantumCircuit
) -> Statevector:
    """Pad `input_vector` with `|+>` on each ancilla added by transpilation.

    Ancillas are placed on higher indices to match the Qiskit transpiler's
    convention. A `Statevector` input is returned unchanged when no padding
    is needed; other array-likes are converted first.
    """
    if not isinstance(input_vector, Statevector):
        input_vector = Statevector(np.asarray(input_vector, dtype=complex))
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
# Layout extraction (used by the system tests)
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
