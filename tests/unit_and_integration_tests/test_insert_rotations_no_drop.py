"""`insert_rotations_adjacent_to_cx` must never drop a rotation.

For random small circuits, the multiset of rotation `(name, params)` pairs
on each row in the input must equal the multiset on the same row in the
output, even though the column they land in may differ.
"""

import math
import random
from collections import Counter

import pytest
from qiskit import QuantumCircuit

from brickwork_transpiler import decomposer
from brickwork_transpiler.decomposer import _is_cx_endpoint


def _row_rotation_multiset(matrix):
    out = []
    for row in matrix:
        ms: Counter = Counter()
        for cell in row:
            for instr in cell:
                if _is_cx_endpoint(instr.name):
                    continue
                key = (
                    instr.name,
                    tuple(round(float(p), 12) for p in (instr.params or [])),
                )
                ms[key] += 1
        out.append(ms)
    return out


def _row_cx_endpoint_multiset(matrix):
    out = []
    for row in matrix:
        ms: Counter = Counter()
        for cell in row:
            for instr in cell:
                if _is_cx_endpoint(instr.name):
                    ms[instr.name] += 1
        out.append(ms)
    return out


@pytest.mark.parametrize("seed", list(range(40)))
def test_random_small_circuit_no_rotation_dropped(seed):
    rng = random.Random(seed)
    n_qubits = rng.randint(2, 5)
    n_gates = rng.randint(1, 12)

    qc = QuantumCircuit(n_qubits)
    for _ in range(n_gates):
        op = rng.choice(["rz", "rx", "h", "cx", "cx", "rz", "rx"])
        if op == "cx":
            a = rng.randrange(n_qubits)
            b = rng.randrange(n_qubits)
            while b == a:
                b = rng.randrange(n_qubits)
            qc.cx(a, b)
        elif op == "h":
            qc.h(rng.randrange(n_qubits))
        else:
            theta = rng.uniform(-math.pi, math.pi)
            getattr(qc, op)(theta, rng.randrange(n_qubits))

    decomposed = decomposer.decompose_qc_to_bricks_qiskit(
        qc, opt=3, with_ancillas=False
    )
    qc_mat, cx_mat = decomposer.instructions_to_matrix_dag(decomposed)
    aligned_cx = decomposer.align_cx_matrix(cx_mat, orig_matrix=qc_mat)
    final = decomposer.insert_rotations_adjecant_to_cx(aligned_cx, qc_mat)

    rotations_in = _row_rotation_multiset(qc_mat)
    rotations_out = _row_rotation_multiset(final)
    assert rotations_in == rotations_out, (
        f"rotation multiset changed for seed={seed}\n"
        f"  in:  {rotations_in}\n"
        f"  out: {rotations_out}"
    )

    cx_in = _row_cx_endpoint_multiset(cx_mat)
    cx_out = _row_cx_endpoint_multiset(final)
    assert cx_in == cx_out, (
        f"CX endpoints changed for seed={seed}\n"
        f"  in:  {cx_in}\n"
        f"  out: {cx_out}"
    )


def test_no_mixed_cx_rotation_cell_after_insertion():
    """An invariant relied on by `pattern_converter.to_pattern`: no cell
    may contain both a CX endpoint and a rotation."""
    rng = random.Random(2026)
    for _ in range(20):
        n_qubits = rng.randint(2, 5)
        qc = QuantumCircuit(n_qubits)
        for _ in range(rng.randint(2, 10)):
            if rng.random() < 0.4:
                a = rng.randrange(n_qubits)
                b = rng.randrange(n_qubits)
                while b == a:
                    b = rng.randrange(n_qubits)
                qc.cx(a, b)
            else:
                qc.h(rng.randrange(n_qubits))

        decomposed = decomposer.decompose_qc_to_bricks_qiskit(
            qc, opt=3, with_ancillas=False
        )
        qc_mat, cx_mat = decomposer.instructions_to_matrix_dag(decomposed)
        final = decomposer.align_bricks(cx_mat, qc_mat)
        for r, row in enumerate(final):
            for c, cell in enumerate(row):
                names = [i.name for i in cell]
                has_cx = any(_is_cx_endpoint(n) for n in names)
                has_rot = any(not _is_cx_endpoint(n) for n in names)
                assert not (has_cx and has_rot), (
                    f"mixed CX/rotation cell at ({r},{c}): {names}"
                )
