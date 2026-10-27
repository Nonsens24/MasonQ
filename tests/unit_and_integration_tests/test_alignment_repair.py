"""Regression tests for the alignment analysis in Appendix A.3/A.4.

These pin the properties the manuscript relies on:

  * the former per-row gap bound does NOT hold in general;
  * place(B) <= 2*ocol(B) + 1 does, hence the aligned extent is at most 2d;
  * the doubling map is a feasible placement (existence form of Theorem 1);
  * the implemented placement is pointwise minimal among feasible placements;
  * rotation insertion preserves per-row operation order for any row-isolated
    input, not only for the contiguous runs produced by the scheduler;
  * every single-qubit cell is mapped to a brick implementing the same unitary.
"""

import itertools
import random

import numpy as np
import pytest
from qiskit import QuantumCircuit

from brickwork_transpiler import decomposer, pattern_converter
from brickwork_transpiler.cx_tags import cx_group_id, is_cx_endpoint
from brickwork_transpiler.decomposer import (
    align_cx_matrix,
    insert_rotations_adjacent_to_cx,
    instructions_to_matrix_dag,
)


class _Op:
    def __init__(self, name, params=()):
        self.name = name
        self.params = list(params)


def _build(nrows, ncols, bricks, rotations):
    orig = [[[] for _ in range(ncols)] for _ in range(nrows)]
    for gid, top, col in bricks:
        orig[top][col].append(_Op(f"cx{gid}c"))
        orig[top + 1][col].append(_Op(f"cx{gid}t"))
    for row, col in rotations:
        orig[row][col].append(_Op("rz", [0.1]))
    cx = [[[i for i in cell if is_cx_endpoint(i.name)] for cell in row] for row in orig]
    return orig, cx


def _random_instance(rng, nrows, ncols, p_cx=0.5, p_rot=0.5):
    bricks, rotations, gid = [], [], 0
    for col in range(ncols):
        row = 0
        while row < nrows:
            if row + 1 < nrows and rng.random() < p_cx:
                bricks.append((gid, row, col))
                gid += 1
                row += 2
            else:
                if rng.random() < p_rot:
                    rotations.append((row, col))
                row += 1
    return _build(nrows, ncols, bricks, rotations)


def _bricks(cx):
    info = {}
    for r, row in enumerate(cx):
        for c, cell in enumerate(row):
            for instr in cell:
                if is_cx_endpoint(instr.name):
                    entry = info.setdefault(cx_group_id(instr.name), {"rows": set(), "ocol": c})
                    entry["rows"].add(r)
    return info


def _placements(mat):
    return {
        cx_group_id(i.name): c
        for row in mat
        for c, cell in enumerate(row)
        for i in cell
        if is_cx_endpoint(i.name)
    }


def _chi(orig, row, lo, hi):
    return int(any(not is_cx_endpoint(i.name) for c in range(lo + 1, hi) for i in orig[row][c]))


def _feasible(pl, info, orig):
    """Definition 5: parity, base column, and separation from left neighbours."""
    last = {}
    for g in sorted(info, key=lambda g: (info[g]["ocol"], int(g))):
        rows, ocol = info[g]["rows"], info[g]["ocol"]
        top = min(rows)
        base = ocol if ocol % 2 == top % 2 else ocol + 1
        if pl[g] % 2 != top % 2 or pl[g] < base:
            return False
        for r in rows:
            if r in last and pl[g] < pl[last[r][0]] + 1 + _chi(orig, r, last[r][1], ocol):
                return False
        for r in rows:
            last[r] = (g, ocol)
    return True


def _row_order(mat):
    return [[id(i) for cell in row for i in cell] for row in mat]


def _has_mixed_cell(mat):
    return any(
        any(is_cx_endpoint(i.name) for i in cell) and any(not is_cx_endpoint(i.name) for i in cell)
        for row in mat
        for cell in row
    )


def _rz(t):
    return np.array([[np.exp(-0.5j * t), 0], [0, np.exp(0.5j * t)]])


def _rx(t):
    c, s = np.cos(t / 2), np.sin(t / 2)
    return np.array([[c, -1j * s], [-1j * s, c]])


def _unitary(cell):
    u = np.eye(2, dtype=complex)
    for i in cell:
        u = (_rz if i.name == "rz" else _rx)(float(i.params[0])) @ u
    return u


def _brick(angles):
    th = [-a * np.pi for a in angles]
    return _rz(th[2]) @ _rx(th[1]) @ _rz(th[0])


def _same_up_to_phase(a, b):
    return abs(abs(np.trace(a.conj().T @ b)) - 2) < 1e-9


# ---------------------------------------------------------------------------
# CX alignment
# ---------------------------------------------------------------------------


def test_row_gap_bound_fails_but_column_bound_holds():
    # Rows (0,1) carry a same-parity chain that accumulates delay; C couples it
    # into row 2, where B and C are consecutive with original gap 1.
    orig, cx = _build(4, 4, [(1, 0, 0), (2, 0, 1), (3, 0, 2), (4, 2, 2), (5, 1, 3)], [])
    pl = _placements(align_cx_matrix(cx, orig_matrix=orig))
    assert pl == {"1": 0, "2": 2, "3": 4, "4": 2, "5": 5}
    assert pl["5"] - pl["4"] == 3  # exceeds the former bound gap + 1 = 2
    info = _bricks(cx)
    assert all(pl[g] <= 2 * info[g]["ocol"] + 1 for g in info)


@pytest.mark.parametrize("seed", range(20))
def test_column_bound_feasibility_and_doubling(seed):
    rng = random.Random(seed)
    for _ in range(50):
        nrows, ncols = rng.randint(2, 7), rng.randint(1, 9)
        orig, cx = _random_instance(rng, nrows, ncols)
        info = _bricks(cx)
        if not info:
            continue
        aligned = align_cx_matrix(cx, orig_matrix=orig)
        pl = _placements(aligned)
        assert _feasible(pl, info, orig)
        assert all(pl[g] <= 2 * info[g]["ocol"] + 1 for g in info)
        assert len(aligned[0]) <= 2 * ncols
        doubling = {g: 2 * info[g]["ocol"] + min(info[g]["rows"]) % 2 for g in info}
        assert _feasible(doubling, info, orig)


def test_alignment_is_pointwise_minimal():
    rng = random.Random(1)
    checked = 0
    while checked < 120:
        nrows, ncols = rng.randint(2, 5), rng.randint(1, 3)
        orig, cx = _random_instance(rng, nrows, ncols)
        info = _bricks(cx)
        if not info or len(info) > 4:
            continue
        checked += 1
        pl = _placements(align_cx_matrix(cx, orig_matrix=orig))
        gids = sorted(info, key=lambda g: (info[g]["ocol"], int(g)))
        best = {}
        for combo in itertools.product(range(2 * ncols + 2), repeat=len(gids)):
            cand = dict(zip(gids, combo))
            if _feasible(cand, info, orig):
                for g in gids:
                    best[g] = min(best.get(g, cand[g]), cand[g])
        assert best == {g: pl[g] for g in gids}


# ---------------------------------------------------------------------------
# Rotation insertion
# ---------------------------------------------------------------------------


def test_rotation_between_cx_without_adjacent_neighbour():
    # Row 0: cx0 | . | rz | . | cx1 -- the rotation touches neither CX cell.
    orig, cx = _build(2, 5, [(0, 0, 0), (1, 0, 4)], [(0, 2)])
    fin = insert_rotations_adjacent_to_cx(align_cx_matrix(cx, orig_matrix=orig), orig)
    assert _row_order(fin) == _row_order(orig)
    assert not _has_mixed_cell(fin)


def test_trailing_rotations_after_nonadjacent_cx():
    # Row 0: cx0 | cx1 | . | rz | . | rz
    orig, cx = _build(2, 6, [(0, 0, 0), (1, 0, 1)], [(0, 3), (0, 5)])
    fin = insert_rotations_adjacent_to_cx(align_cx_matrix(cx, orig_matrix=orig), orig)
    assert _row_order(fin) == _row_order(orig)
    assert not _has_mixed_cell(fin)


@pytest.mark.parametrize("seed", range(10))
def test_rotation_insertion_preserves_order_random(seed):
    rng = random.Random(100 + seed)
    for _ in range(100):
        nrows, ncols = rng.randint(2, 6), rng.randint(2, 9)
        orig, cx = _random_instance(rng, nrows, ncols)
        fin = insert_rotations_adjacent_to_cx(align_cx_matrix(cx, orig_matrix=orig), orig)
        assert _row_order(fin) == _row_order(orig)
        assert not _has_mixed_cell(fin)
        assert len(fin[0]) <= 2 * ncols


# ---------------------------------------------------------------------------
# Single-qubit brick mapping
# ---------------------------------------------------------------------------


def test_parse_euler_angles_rx_rz_rx():
    cell = [_Op("rx", [0.4]), _Op("rz", [1.1]), _Op("rx", [-0.7])]
    assert _same_up_to_phase(_unitary(cell), _brick(pattern_converter.parse_euler_angles(cell)))


def test_parse_euler_angles_random_sequences():
    rng = np.random.default_rng(5)
    for _ in range(500):
        cell = [
            _Op(str(rng.choice(["rz", "rx"])), [rng.uniform(-np.pi, np.pi)])
            for _ in range(int(rng.integers(1, 8)))
        ]
        assert _same_up_to_phase(_unitary(cell), _brick(pattern_converter.parse_euler_angles(cell)))


def test_parse_euler_angles_direct_forms_unchanged():
    a, b, c = 0.3, -1.2, 2.0
    zxz = [_Op("rz", [a]), _Op("rx", [b]), _Op("rz", [c])]
    assert pattern_converter.parse_euler_angles(zxz) == [-a / np.pi, -b / np.pi, -c / np.pi, 0.0]
    xz = [_Op("rx", [b]), _Op("rz", [c])]
    assert pattern_converter.parse_euler_angles(xz) == [0.0, -b / np.pi, -c / np.pi, 0.0]


def _random_circuit(rng, n, m):
    qc = QuantumCircuit(n)
    for _ in range(m):
        k = rng.random()
        q = rng.randrange(n)
        if k < 0.35 and n > 1:
            a, b = rng.sample(range(n), 2)
            rng.choice([qc.cx, qc.cz, qc.swap])(a, b)
        elif k < 0.40 and n > 2:
            qc.ccx(*rng.sample(range(n), 3))
        else:
            gate = rng.choice(["h", "s", "t", "sdg", "x", "rx", "ry", "rz"])
            if gate in ("rx", "ry", "rz"):
                getattr(qc, gate)(rng.uniform(-np.pi, np.pi), q)
            else:
                getattr(qc, gate)(q)
    return qc


def test_pipeline_cell_in_rx_rz_rx_form():
    # Before the fix this circuit compiled to a pattern with Graphix/Qiskit
    # fidelity 0.805: Qiskit emitted an Rx Rz Rx cell and the second Rx
    # overwrote the first. If a future Qiskit stops emitting that form here,
    # the direct unit tests above still cover the mapping.
    qc = QuantumCircuit(3)
    qc.t(0)
    qc.sdg(2)
    qc.sdg(0)
    qc.s(0)
    qc.swap(1, 2)
    qc.rz(-0.5329977435806663, 1)
    qc.cz(0, 2)
    qc.cz(2, 1)
    qc.ccx(2, 0, 1)
    qc.sdg(0)
    qc.cz(2, 0)
    qc.s(1)
    dec = decomposer.decompose_qc_to_bricks_qiskit(
        qc, opt=3, routing_method="basic", layout_method="trivial", with_ancillas=True
    )
    qm, cxm = instructions_to_matrix_dag(dec)
    fin = insert_rotations_adjacent_to_cx(align_cx_matrix(cxm, orig_matrix=qm), qm)
    for row in fin:
        for cell in row:
            if cell and not any(is_cx_endpoint(i.name) for i in cell):
                angles = pattern_converter.parse_euler_angles(cell)
                assert _same_up_to_phase(_unitary(cell), _brick(angles))


@pytest.mark.parametrize("seed", range(4))
def test_pipeline_bricks_implement_their_cells(seed):
    rng = random.Random(seed)
    for _ in range(12):
        qc = _random_circuit(rng, rng.randint(2, 5), rng.randint(5, 25))
        dec = decomposer.decompose_qc_to_bricks_qiskit(
            qc, opt=3, routing_method="basic", layout_method="trivial", with_ancillas=True
        )
        qm, cxm = instructions_to_matrix_dag(dec)
        fin = insert_rotations_adjacent_to_cx(align_cx_matrix(cxm, orig_matrix=qm), qm)
        assert _row_order(fin) == _row_order(qm)
        for row in fin:
            for cell in row:
                if cell and not any(is_cx_endpoint(i.name) for i in cell):
                    angles = pattern_converter.parse_euler_angles(cell)
                    assert _same_up_to_phase(_unitary(cell), _brick(angles))
