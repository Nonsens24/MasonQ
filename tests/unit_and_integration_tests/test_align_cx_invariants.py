"""Property tests for `align_cx_matrix` invariants.

For ~100 random small CX-only circuits the aligned matrix must satisfy:

  - rectangular shape;
  - same number of `cxNc`/`cxNt` endpoints in vs. out;
  - per-row CX order preserved (the `gid` sequence on each row matches the
    pre-alignment order);
  - top-row parity matches column parity for every aligned brick;
  - new width <= legacy gap-preserving width on every input
    (monotone-improvement check).
"""

import random
from typing import List

import pytest
from qiskit import QuantumCircuit

from brickwork_transpiler import decomposer
from brickwork_transpiler.cx_tags import cx_group_id, is_cx_endpoint


def _random_cx_circuit(n_qubits: int, n_cx: int, rng: random.Random) -> QuantumCircuit:
    qc = QuantumCircuit(n_qubits)
    for _ in range(n_cx):
        a = rng.randrange(n_qubits)
        b = rng.randrange(n_qubits)
        while b == a:
            b = rng.randrange(n_qubits)
        qc.cx(a, b)
    return qc


def _row_gid_sequence(matrix) -> List[List[str]]:
    out: List[List[str]] = []
    for row in matrix:
        seq = []
        for cell in row:
            for instr in cell:
                if is_cx_endpoint(instr.name):
                    seq.append(cx_group_id(instr.name))
        out.append(seq)
    return out


def _endpoint_count(matrix) -> int:
    return sum(
        1
        for row in matrix
        for cell in row
        for instr in cell
        if is_cx_endpoint(instr.name)
    )


@pytest.mark.parametrize("seed", list(range(50)))
def test_align_cx_invariants_random_small(seed):
    rng = random.Random(seed)
    n_qubits = rng.randint(2, 6)
    n_cx = rng.randint(1, 12)
    qc = _random_cx_circuit(n_qubits, n_cx, rng)

    decomposed = decomposer.decompose_qc_to_bricks_qiskit(
        qc, opt=3, with_ancillas=False
    )
    qc_mat, cx_mat = decomposer.instructions_to_matrix_dag(decomposed)

    aligned = decomposer.align_cx_matrix(cx_mat, orig_matrix=qc_mat)
    if not aligned:
        return

    width = len(aligned[0])
    # Rectangular
    for row in aligned:
        assert len(row) == width

    # Endpoint count preserved
    assert _endpoint_count(aligned) == _endpoint_count(cx_mat)

    # Per-row gid order preserved
    pre = _row_gid_sequence(cx_mat)
    post = _row_gid_sequence(aligned)
    assert pre == post

    # Parity invariant for every brick
    by_gid: dict = {}
    for r, row in enumerate(aligned):
        for c, cell in enumerate(row):
            for instr in cell:
                if is_cx_endpoint(instr.name):
                    by_gid.setdefault(cx_group_id(instr.name), []).append((r, c))
    for gid, locs in by_gid.items():
        cols = {c for _, c in locs}
        assert len(cols) == 1, f"gid {gid} not on a single column: {locs}"
        rows = {r for r, _ in locs}
        assert len(rows) == 2 and abs(min(rows) - max(rows)) == 1
        top = min(rows)
        col = next(iter(cols))
        assert (col & 1) == (top & 1), (
            f"gid {gid}: column parity {col & 1} != top-row parity {top & 1}"
        )


@pytest.mark.parametrize("seed", list(range(20)))
def test_align_cx_width_no_worse_than_legacy(seed):
    """The new floor must never inflate width vs the legacy gap-preserving rule."""
    rng = random.Random(seed + 1000)
    n_qubits = rng.randint(2, 6)
    n_cx = rng.randint(1, 12)
    qc = _random_cx_circuit(n_qubits, n_cx, rng)

    decomposed = decomposer.decompose_qc_to_bricks_qiskit(
        qc, opt=3, with_ancillas=False
    )
    qc_mat, cx_mat = decomposer.instructions_to_matrix_dag(decomposed)

    legacy = decomposer.align_cx_matrix(cx_mat, orig_matrix=None)
    new = decomposer.align_cx_matrix(cx_mat, orig_matrix=qc_mat)
    legacy_w = len(legacy[0]) if legacy else 0
    new_w = len(new[0]) if new else 0

    assert new_w <= legacy_w, (
        f"new width {new_w} > legacy {legacy_w} for seed={seed}"
    )
