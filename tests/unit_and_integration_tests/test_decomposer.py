import numpy as np
import pytest
import unittest
from collections import defaultdict
from qiskit.quantum_info import Statevector
from math import pi

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit.library import MCXGate, PhaseGate

try:
    from qiskit.circuit.library import MCXRecursive
except ImportError:  # Qiskit versions that removed the legacy class.
    MCXRecursive = None

from brickwork_transpiler import (visualiser, decomposer, brickwork_transpiler)
from brickwork_transpiler.decomposer import instructions_to_matrix_dag, align_cx_matrix, \
    insert_rotations_adjacent_to_cx, linearise_multi_ctrl, align_bricks
from matrix_checks import check_aligned_matrix, cx_columns, cx_groups, rotation_columns


# Dummy instruction class for testing
class DummyInstr:
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return f"DummyInstr('{self.name}')"


def mk_matrix(n_qubits, columns):
    """
    Build an n_qubits × n_columns instruction matrix from a list of columns,
    where each column is a list of length n_qubits of instruction-name lists.
    """
    n_cols = len(columns)
    matrix = [[[] for _ in range(n_cols)] for _ in range(n_qubits)]
    for c, col in enumerate(columns):
        if len(col) != n_qubits:
            raise ValueError(f"Column {c} must have {n_qubits} entries, got {len(col)}")
        for q, names in enumerate(col):
            for name in names:
                if name:  # skip empty strings
                    matrix[q][c].append(DummyInstr(name))
    return matrix


def names(matrix):
    """Extract instruction names from the (n_qubits×n_cols) matrix for assertions."""
    # matrix is a list of lists: matrix[q][c] is a list of instrs
    n_q = len(matrix)
    n_c = len(matrix[0]) if n_q>0 else 0
    names_mat = [[None]*n_c for _ in range(n_q)]
    for q in range(n_q):
        for c in range(n_c):
            names_mat[q][c] = [instr.name for instr in matrix[q][c]]
    return names_mat

def pipeline_matrices(qc):
    """Decompose, schedule and align `qc`; also return the routed circuit."""
    decomposed_qc = decomposer.decompose_qc_to_bricks_qiskit(qc, opt=3, with_ancillas=False)
    qc_mat, cx_mat = decomposer.instructions_to_matrix_dag(decomposed_qc)
    qc_mat_aligned = decomposer.align_bricks(cx_mat, qc_mat)
    return decomposed_qc, qc_mat, cx_mat, qc_mat_aligned


def get_matrices(qc):
    return pipeline_matrices(qc)[1:]

class TestBrickAlignment(unittest.TestCase):

    def test_no_cx_only_rotations(self):
        # cols = [
        #     [['rz','rx'], ['rz'], ['rx']],
        #     [['rz'], ['rx','rz'], ['rz','rx','rz']],
        # ]

        qc = QuantumCircuit(3)
        qc.rz(np.pi/2, 0)
        qc.rx(np.pi / 3, 0)
        qc.rz(np.pi / 4, 1)
        qc.rz(np.pi / 5, 2)

        qc.rz(np.pi / 6, 0)
        qc.rx(np.pi / 7, 1)
        qc.rz(np.pi / 8, 1)
        qc.rz(np.pi / 9, 2)
        qc.rx(np.pi / 7, 2)
        qc.rz(np.pi / 8, 2)

        qc_mat, cx_mat, qc_mat_aligned = get_matrices(qc)

        # No padding: same number of columns
        assert len(qc_mat_aligned[0]) == 1
        # Check content matches input
        for col_id, col in enumerate(zip(*qc_mat_aligned)):
            for row in col:
                for instr in row:
                    assert instr.name.startswith('r')


    def test_pure_even_cx_alignment_target_bot(self):
        # Single column with cx on qubits 0-1 (even parity)
        qc = QuantumCircuit(3)
        qc.cx(0, 1)

        qc_mat, cx_mat, qc_mat_aligned = get_matrices(qc)

        assert len(qc_mat[0]) == 1
        # First brick should be identity
        # Second brick has CXs on qubits 1 and 2
        assert names(qc_mat)[0][0] == ['cx0c']
        assert names(qc_mat)[1][0] == ['cx0t']

        assert len(cx_mat[0]) == 1
        # First brick should be identity
        assert all(cell == [] for cell in cx_mat[2][0])
        # Second brick has CXs on qubits 1 and 2
        assert names(cx_mat)[0][0] == ['cx0c']
        assert names(cx_mat)[1][0] == ['cx0t']

        # initial brick_idx=0 (even), needs odd -> one pad, then CX brick
        assert len(qc_mat_aligned[0]) == 1
        # First brick should be identity
        assert all(cell == [] for cell in qc_mat_aligned[2][0])
        # Second brick has CXs on qubits 1 and 2
        assert names(qc_mat_aligned)[0][0] == ['cx0c']
        assert names(qc_mat_aligned)[1][0] == ['cx0t']


    def test_pure_even_cx_alignment2(self):
        # Single column with cx on qubits 0-1 (even parity)
        qc = QuantumCircuit(3)
        qc.cx(1, 0)

        qc_mat, cx_mat, qc_mat_aligned = get_matrices(qc)

        assert len(qc_mat[0]) == 1
        # First brick should be identity
        # Second brick has CXs on qubits 1 and 2
        assert names(qc_mat)[0][0] == ['cx0t']
        assert names(qc_mat)[1][0] == ['cx0c']

        assert len(cx_mat[0]) == 1
        # First brick should be identity
        assert all(cell == [] for cell in cx_mat[2][0])
        # Second brick has CXs on qubits 1 and 2
        assert names(cx_mat)[0][0] == ['cx0t']
        assert names(cx_mat)[1][0] == ['cx0c']

        # initial brick_idx=0 (even), needs odd -> one pad, then CX brick
        assert len(qc_mat_aligned[0]) == 1
        # First brick should be identity
        assert all(cell == [] for cell in qc_mat_aligned[2][0])
        # Second brick has CXs on qubits 1 and 2
        assert names(qc_mat_aligned)[0][0] == ['cx0t']
        assert names(qc_mat_aligned)[1][0] == ['cx0c']


    def test_pure_odd_cx_alignment(self):
        # Single column with cx on qubits 1-2 (odd parity)
        qc = QuantumCircuit(3)
        qc.cx(2, 1)

        qc_mat, cx_mat, qc_mat_aligned = get_matrices(qc)
        # visualiser.print_matrix(qc_mat)

        assert len(qc_mat[0]) == 1
        # First brick should be identity
        # Second brick has CXs on qubits 1 and 2
        assert names(qc_mat)[1][0] == ['cx0t']
        assert names(qc_mat)[2][0] == ['cx0c']

        assert len(cx_mat[0]) == 1
        # First brick should be identity
        assert all(cell == [] for cell in cx_mat[0][0:1])
        # Second brick has CXs on qubits 1 and 2
        assert names(cx_mat)[1][0] == ['cx0t']
        assert names(cx_mat)[2][0] == ['cx0c']

        # initial brick_idx=0 (even), needs odd -> one pad, then CX brick
        assert len(qc_mat_aligned[0]) == 2
        # First brick should be identity
        assert all(cell == [] for cell in qc_mat_aligned[0][0:1])
        # Second brick has CXs on qubits 1 and 2
        assert names(qc_mat_aligned)[1][1] == ['cx0t']
        assert names(qc_mat_aligned)[2][1] == ['cx0c']


    def test_mixed_same_parity_cx(self):
        # Two independent CNOTs on (0,1) and (2,3), both even parity and non-adjacent
        qc = QuantumCircuit(4)
        qc.cx(1, 0)
        qc.cx(3, 2)

        qc_mat, cx_mat, qc_mat_aligned = get_matrices(qc)

        # Both CNOTs should be in a single brick without padding

        assert len(qc_mat[0]) == 1

        # Check cx(0,1)
        assert 'cx0t' in qc_mat[0][0][0].name and 'cx0c' in qc_mat[1][0][0].name
        # Check cx(3,4)
        assert 'cx1t' in qc_mat[2][0][0].name and 'cx1c' in qc_mat[3][0][0].name


        assert len(cx_mat[0]) == 1

        # Check cx(0,1)
        assert 'cx0t' in cx_mat[0][0][0].name and 'cx0c' in cx_mat[1][0][0].name
        # Check cx(3,4)
        assert 'cx1t' in cx_mat[2][0][0].name and 'cx1c' in cx_mat[3][0][0].name


        assert len(qc_mat_aligned[0]) == 1

        # Check cx(0,1)
        assert 'cx0t' in qc_mat_aligned[0][0][0].name and 'cx0c' in qc_mat_aligned[1][0][0].name
        # Check cx(3,4)
        assert 'cx1t' in qc_mat_aligned[2][0][0].name and 'cx1c' in qc_mat_aligned[3][0][0].name



    def test_mixed_diff_parity_cx(self):

        qc = QuantumCircuit(5)
        qc.cx(1, 0)
        qc.cx(3, 4)

        qc_mat, cx_mat, qc_mat_aligned = get_matrices(qc)

        # visualiser.print_matrix(qc_mat)
        # visualiser.print_matrix(cx_mat)
        # visualiser.print_matrix(qc_mat_aligned)

        # Test before shift
        assert len(qc_mat[0]) == 1
        # First brick handles cx(0,1)
        assert 'cx0t' in names(qc_mat)[0][0]
        assert 'cx0c' in names(qc_mat)[1][0]
        assert names(qc_mat)[2][0] == []
        # Second brick handles cx(3,4)
        assert 'cx1c' in names(qc_mat)[3][0]
        assert 'cx1t' in names(qc_mat)[4][0]

        # Test after shift
        assert len(qc_mat_aligned[0]) == 2
        # First brick handles cx(0,1)
        assert 'cx0t' in names(qc_mat_aligned)[0][0]
        assert 'cx0c' in names(qc_mat_aligned)[1][0]
        assert names(qc_mat_aligned)[3][0] == []
        # Second brick handles cx(3,4)
        assert 'cx1c' in names(qc_mat_aligned)[3][1]
        assert 'cx1t' in names(qc_mat_aligned)[4][1]


    def test_rotations_with_cx(self):
        # Rotations on every qubit and one CX(1, 0). Whatever Euler forms Qiskit
        # chooses, the aligned matrix must implement the routed circuit, keep the
        # CX brick on an even column (its top row is 0), place every rotation on
        # the CX rows next to the CX, and leave the rotations of the other rows
        # in the leading column.
        qc = QuantumCircuit(4)
        qc.rz(np.pi / 3, 0)
        qc.rx(np.pi / 4, 1)
        qc.rz(np.pi / 5, 2)
        qc.cx(1, 0)
        qc.rz(np.pi / 3, 3)

        decomposed, qc_mat, cx_mat, aligned = pipeline_matrices(qc)
        check_aligned_matrix(aligned, decomposed)

        groups = cx_groups(aligned)
        self.assertEqual(len(groups), 1)
        (ends,) = groups.values()
        self.assertEqual({ends['c'][0], ends['t'][0]}, {0, 1})
        column = ends['c'][1]
        self.assertEqual(column % 2, 0)
        for row in (0, 1):
            for c in rotation_columns(aligned, row):
                self.assertEqual(abs(c - column), 1, f'row {row}: rotation at {c} is not next to the CX at {column}')
        for row in (2, 3):
            self.assertEqual(cx_columns(aligned, row), [])
            self.assertEqual(rotation_columns(aligned, row), [0])



class TestInstructionsToMatrixDAG(unittest.TestCase):

    def test_single_qubit_rotations(self):
        qc = QuantumCircuit(2)
        qc.rz(0.5, 0)
        qc.rx(1.0, 1)
        qc_mat, cx_mat = instructions_to_matrix_dag(qc)

        self.assertEqual(len(qc_mat), 2)
        # Expect one column
        self.assertEqual(len(qc_mat[0]), 1)
        self.assertEqual(len(qc_mat[1]), 1)

        instr0 = qc_mat[0][0][0]
        instr1 = qc_mat[1][0][0]
        self.assertIn(instr0.name, ['rz'])
        self.assertIn(instr1.name, ['rx'])


    def test_single_cx_gate(self):
        qc = QuantumCircuit(2)
        qc.cx(0, 1)
        qc_mat, cx_mat = instructions_to_matrix_dag(qc)

        # Should produce one column
        self.assertEqual(len(qc_mat[0]), 1)
        self.assertEqual(len(qc_mat[1]), 1)

        names = {instr.name for instr in qc_mat[0][0]} | {instr.name for instr in qc_mat[1][0]}
        self.assertIn('cx0c', names)
        self.assertIn('cx0t', names)


    def test_multiple_cx_gates(self):
        qc = QuantumCircuit(3)
        qc.cx(0, 1)
        qc.cx(1, 2)
        qc_mat, cx_mat = instructions_to_matrix_dag(qc)

        # Should have at least two columns depending on atomic grouping
        # We verify the names exist with unique indices
        names = set()
        for q in qc_mat:
            for col in q:
                names |= {instr.name for instr in col}

        # Two CX pairs → should have cx0c/t and cx1c/t
        self.assertIn('cx0c', names)
        self.assertIn('cx0t', names)
        self.assertIn('cx1c', names)
        self.assertIn('cx1t', names)


    def test_single_cx_gate_rev_order(self):
        qc = QuantumCircuit(2)
        qc.cx(1, 0)
        qc_mat, cx_mat = instructions_to_matrix_dag(qc)

        # Should produce one column
        self.assertEqual(len(qc_mat[0]), 1)
        self.assertEqual(len(qc_mat[1]), 1)

        names = {instr.name for instr in qc_mat[0][0]} | {instr.name for instr in qc_mat[1][0]}
        self.assertIn('cx0t', names)
        self.assertIn('cx0c', names)


class TestAlignCXMatrix(unittest.TestCase):


    class DummyInstr:
        def __init__(self, name):
            self.name = name

        def __repr__(self):
            return f"<Instr {self.name}>"

    @pytest.fixture
    def instr_factory(self):
        def make(name):
            return DummyInstr(name)

        return make

    def get_cx_mat(self, qc):
        # Decompose to CX, rzrxrz, id
        decomposed_qc = decomposer.decompose_qc_to_bricks_qiskit(qc, opt=3, with_ancillas=False)

        # Optiise instruction matrix with dependency graph
        qc_mat, cx_mat = decomposer.instructions_to_matrix_dag(decomposed_qc)

        return cx_mat

    def test_empty_matrix(self):
        mat = []
        out = align_cx_matrix(mat)
        assert out == [], "Empty matrix should just return itself"

    def test_no_cx_bricks(self):
        # a matrix with only non-cx instructions should be unchanged

        qc = QuantumCircuit(2)
        qc.h(0)
        qc.t(1)

        cx_mat = self.get_cx_mat(qc)
        aligned_cx_mat = align_cx_matrix(cx_mat)
        assert aligned_cx_mat == [[], []]

    def test_already_aligned_cx(self):
        # Two rows, one cx0 brick already at col 1 (top=0 even, col=1 odd ->
        # parity mismatch). The brick is shifted to col 2 to fix parity.
        # Use the tagged endpoint names produced by `instructions_to_matrix_dag`
        # (`cx0c` for control, `cx0t` for target).
        mat = [
            [[], [DummyInstr("cx0c")]],  # row 0 control, top=0
            [[], [DummyInstr("cx0t")]],  # row 1 target
        ]
        out = align_cx_matrix(mat)

        assert len(out[0]) == 3
        assert out[0][1] == []
        self.assertEqual(out[0][2][0].name, "cx0c")
        self.assertEqual(out[1][2][0].name, "cx0t")

    def test_shift_cx_into_next_column(self):
        # top row index=1 (odd), col=0 (even) -> parity mismatch, shift to 1.
        mat = [
            [[]],
            [[DummyInstr("cx1c")]],  # control on row 1
            [[DummyInstr("cx1t")]],  # target on row 2
        ]
        result = align_cx_matrix(mat)
        self.assertEqual(len(result[0]), 2)
        self.assertEqual(result[0], [[], []], "Row 0 should be untouched")
        self.assertEqual(result[1][0], [])
        self.assertEqual(result[1][1][0].name, "cx1c")
        self.assertEqual(result[2][1][0].name, "cx1t")

    def test_aligned_and_unaligned_bricks(self):
        # cx2 on rows 0&1 at col 0 (top=0 even, col=0 even -> aligned)
        # cx3 on rows 1&2 at col 0 (top=1 odd, col=0 even -> unaligned, shifts)
        mat = [
            [[DummyInstr("cx2c")], []],
            [[DummyInstr("cx2t"), DummyInstr("cx3c")], []],
            [[DummyInstr("cx3t")], []],
        ]
        result = align_cx_matrix(mat)

        # cx2 remains at col 0
        self.assertEqual(result[0][0][0].name, "cx2c")
        self.assertEqual(result[1][0][0].name, "cx2t")
        # cx3 moves to col 1 (parity-corrected odd column for top=1 odd)
        names_at_1_1 = [i.name for i in result[1][1]]
        names_at_2_1 = [i.name for i in result[2][1]]
        self.assertIn("cx3c", names_at_1_1)
        self.assertIn("cx3t", names_at_2_1)
        # cx3 should not have leaked into col 0
        self.assertNotIn("cx3c", [i.name for i in result[1][0]])
        self.assertNotIn("cx3t", [i.name for i in result[2][0]])


from qiskit.circuit import Instruction


def names(matrix):
    """Helper to extract .name from Instruction matrix."""
    return [[ [instr.name for instr in cell] for cell in row] for row in matrix]

def legacy_pipeline(qc):
    """Decompose and schedule `qc`, then align with the gap-preserving aligner.

    Returns the routed circuit, the aligned CX matrix and the original matrix.
    """
    decomposed_qc = decomposer.decompose_qc_to_bricks_qiskit(qc, opt=3, with_ancillas=False)
    qc_mat, cx_mat = decomposer.instructions_to_matrix_dag(decomposed_qc)
    return decomposed_qc, align_cx_matrix(cx_mat), qc_mat


def get_aligned_and_original_from_circ(qc):
    return legacy_pipeline(qc)[1:]


class TestInsertRotations(unittest.TestCase):

    def test_empty_matrices(self):
        aligned = []
        original = []
        result = insert_rotations_adjacent_to_cx(aligned, original)
        self.assertEqual(result, [])

    def test_no_rotations(self):
        qc = QuantumCircuit(4)
        qc.cx(1, 0)
        qc.cx(2, 3)

        aligned, original = get_aligned_and_original_from_circ(qc)
        result = insert_rotations_adjacent_to_cx(aligned, original)

        self.assertEqual(names(result), names(aligned))

    def test_default_insert_to_column_zero(self):
        aligned = [[ [Instruction('cx1', 0, 0, [])] ]]
        original = [[ [Instruction('rz', 0, 0, [])] ]]
        result = insert_rotations_adjacent_to_cx(aligned, original)
        expected = [[ ['cx1', 'rz'] ]]
        self.assertEqual(names(result), expected)

    def test_left_neighbor_insertion(self):
        # An rz on the control, then the CX. Qiskit 2.4 keeps the rz before the
        # CX, Qiskit 2.6 commutes it to after; either way it must land in the
        # column next to the CX, and nothing may be reordered on its wire.
        qc = QuantumCircuit(2)
        qc.rz(np.pi / 3, 0)
        qc.cx(0, 1)

        decomposed, aligned, original = legacy_pipeline(qc)
        result = insert_rotations_adjacent_to_cx(aligned, original)

        check_aligned_matrix(result, decomposed)
        (column,) = cx_columns(result, 0)
        self.assertEqual(cx_columns(result, 1), [column])
        self.assertEqual(column % 2, 0)
        self.assertEqual([abs(c - column) for c in rotation_columns(result, 0)], [1])
        self.assertEqual(rotation_columns(result, 1), [])

    def test_right_neighbor_insertion(self):

        qc = QuantumCircuit(2)
        qc.cx(0, 1)
        qc.rz(np.pi/3, 0)

        aligned, original = get_aligned_and_original_from_circ(qc)
        result = insert_rotations_adjacent_to_cx(aligned, original)
        # visualiser.print_matrix(result)

        expected = [[['cx0c'], ['rz']], [['cx0t'], []]]
        self.assertEqual(names(result), expected)

    # def test_multiple_mixed_rotations_preserve_order(self):
    #     qc = QuantumCircuit(2)
    #     qc.rz(np.pi/3, 1)
    #     qc.rx(np.pi/4, 1)
    #     qc.rz(np.pi/5, 1)
    #
    #     qc.cx(0, 1)
    #     qc.rz(np.pi/3, 0)
    #     qc.rx(np.pi/4, 0)
    #     qc.rz(np.pi/5, 0)
    #
    #     aligned, original = get_aligned_and_original_from_circ(qc)
    #     result = insert_rotations_adjacent_to_cx(aligned, original)
    #     # visualiser.print_matrix(result)
    #
    #     expected = [[[], ['rx'], ['cx0c'], ['rz', 'rx', 'rz']],
    #             [[], ['rz', 'rx', 'rz'], ['cx0t'], ['rz', 'rx']]]
    #
    #     self.assertEqual(names(result), expected)

    def test_duplication_bug(self):
        qc = QuantumCircuit(5)
        qc.cx(0, 1)
        qc.h(2)
        # qc.cx(1, 2)
        qc.cx(4, 3)

        aligned, original = get_aligned_and_original_from_circ(qc)
        result = insert_rotations_adjacent_to_cx(aligned, original)

        expected = [[['cx0c'], []],
                    [['cx0t'], []],
                    [['rz', 'rx', 'rz'], []],
                    [[], ['cx1t']],
                    [[], ['cx1c']]]
        self.assertEqual(names(result), expected)


    def test_duplication_bug_reversed(self):
        qc = QuantumCircuit(6)
        qc.cx(1, 2)
        qc.h(3)
        # qc.cx(1, 2)
        qc.cx(5, 4)

        aligned, original = get_aligned_and_original_from_circ(qc)
        result = insert_rotations_adjacent_to_cx(aligned, original)
        # visualiser.print_matrix(result)

        expected = [[[], []],
                     [[], ['cx0c']],
                     [[], ['cx0t']],
                     [['rz', 'rx', 'rz'], []],
                     [['cx1t'], []],
                     [['cx1c'], []]]
        self.assertEqual(names(result), expected)

    def test_shift_chain_upper(self):
        qc_bugged = QuantumCircuit(3)

        qc_bugged.cx(1, 2)
        qc_bugged.h(1)
        qc_bugged.cx(0, 1)

        aligned, original = get_aligned_and_original_from_circ(qc_bugged)
        result = insert_rotations_adjacent_to_cx(aligned, original)
        # visualiser.print_matrix(original)
        # visualiser.print_matrix(result)

        expected = [[[], [], [], [], ['cx1c']],
                     [[], ['cx0c'], ['rz', 'rx', 'rz'], [], ['cx1t']],
                     [[], ['cx0t'], [], [], []]]
        self.assertEqual(names(result), expected)

    def test_double_shift_chain_upper(self):
        qc_bugged = QuantumCircuit(3)

        qc_bugged.cx(1, 2)
        qc_bugged.h(1)
        qc_bugged.cx(0, 1)

        qc_bugged.cx(1, 2)
        qc_bugged.h(1)
        qc_bugged.cx(0, 1)

        aligned, original = get_aligned_and_original_from_circ(qc_bugged)
        result = insert_rotations_adjacent_to_cx(aligned, original)

        expected = [[[], [], [], [], ['cx1c'], [], [], [], ['cx3c']],
                     [[],
                      ['cx0c'],
                      ['rz', 'rx', 'rz'],
                      [],
                      ['cx1t'],
                      ['cx2c'],
                      ['rz', 'rx', 'rz'],
                      [],
                      ['cx3t']],
                     [[], ['cx0t'], [], [], [], ['cx2t'], [], [], []]]
        self.assertEqual(names(result), expected)

    def test_triple_shift_chain_upper(self):
        qc_bugged = QuantumCircuit(3)

        qc_bugged.cx(1, 2)
        qc_bugged.h(1)
        qc_bugged.cx(0, 1)

        qc_bugged.cx(1, 2)
        qc_bugged.h(1)
        qc_bugged.cx(0, 1)

        qc_bugged.cx(1, 2)
        qc_bugged.h(1)
        qc_bugged.cx(0, 1)

        aligned, original = get_aligned_and_original_from_circ(qc_bugged)
        result = insert_rotations_adjacent_to_cx(aligned, original)

        expected = [[[], [], [], [], ['cx1c'], [], [], [], ['cx3c'], [], [], [], ['cx5c']],
                     [[],
                      ['cx0c'],
                      ['rz', 'rx', 'rz'],
                      [],
                      ['cx1t'],
                      ['cx2c'],
                      ['rz', 'rx', 'rz'],
                      [],
                      ['cx3t'],
                      ['cx4c'],
                      ['rz', 'rx', 'rz'],
                      [],
                      ['cx5t']],
                     [[], ['cx0t'], [], [], [], ['cx2t'], [], [], [], ['cx4t'], [], [], []]]
        self.assertEqual(names(result), expected)

    def test_mixed_double_shift_chain_upper(self):
        qc_bugged = QuantumCircuit(3)

        qc_bugged.cx(1, 2)
        qc_bugged.h(1)
        qc_bugged.cx(0, 1)

        qc_bugged.cx(1, 2)
        qc_bugged.h(1)
        qc_bugged.cx(0, 1)

        qc_bugged.h(0)
        qc_bugged.cx(1, 0)
        qc_bugged.h(1)
        qc_bugged.cx(2, 1)

        qc_bugged.h(0)
        qc_bugged.cx(1, 0)
        qc_bugged.h(1)
        qc_bugged.cx(2, 1)

        decomposed, aligned, original = legacy_pipeline(qc_bugged)
        result = insert_rotations_adjacent_to_cx(aligned, original)

        # Qiskit 2.4 and 2.6 emit different Euler forms for this circuit, so the
        # exact layout is not pinned. The invariants are: every CX pair shares a
        # column on adjacent rows at the parity its top row demands, no
        # instruction moves on its wire, and the matrix implements the routed
        # circuit on random input states.
        check_aligned_matrix(result, decomposed)
        self.assertEqual(len(result), qc_bugged.num_qubits)


    def test_many_shifts(self):
        qc_bugged = QuantumCircuit(5)

        input_vec = Statevector.from_label('+++++')

        qc_bugged.h(0)
        qc_bugged.cx(1, 0)

        qc_bugged.h(1)
        qc_bugged.cx(2, 1)
        qc_bugged.rz(np.pi / 2, 2)

        qc_bugged.rx(np.pi / 3, 2)
        qc_bugged.rz(np.pi / 4, 3)

        qc_bugged.cx(3, 4)
        qc_bugged.rz(np.pi / 4, 3)
        qc_bugged.h(4)

        qc_bugged.cx(1, 0)

        qc_bugged.h(1)
        qc_bugged.cx(1, 2)
        qc_bugged.rz(np.pi / 2, 2)

        qc_bugged.rx(np.pi / 3, 2)
        qc_bugged.rz(np.pi / 4, 3)

        qc_bugged.cx(3, 4)
        qc_bugged.rz(np.pi / 4, 3)
        qc_bugged.h(4)

        qc_bugged.cx(1, 0)

        qc_bugged.h(1)
        qc_bugged.cx(1, 2)
        qc_bugged.rz(np.pi / 2, 2)

        qc_bugged.rx(np.pi / 3, 2)
        qc_bugged.rz(np.pi / 4, 3)

        qc_bugged.cx(3, 4)
        qc_bugged.rz(np.pi / 4, 3)
        qc_bugged.h(4)

        decomposed, aligned, original = legacy_pipeline(qc_bugged)
        result = insert_rotations_adjacent_to_cx(aligned, original)

        # Qiskit 2.4 and 2.6 emit different Euler forms for this circuit, so the
        # exact layout is not pinned. The invariants are: every CX pair shares a
        # column on adjacent rows at the parity its top row demands, no
        # instruction moves on its wire, and the matrix implements the routed
        # circuit on random input states.
        check_aligned_matrix(result, decomposed)
        self.assertEqual(len(result), qc_bugged.num_qubits)



class TestLineariseMultiCtrl(unittest.TestCase):

    def _count_type(self, qc, gate_type):
        return sum(1 for instruction in qc.data if isinstance(instruction.operation, gate_type))

    def _names(self, qc):
        return [instruction.operation.name for instruction in qc.data]

    # ---------- MCX: ancilla handling ----------

    @pytest.mark.skipif(MCXRecursive is None, reason="MCXRecursive unavailable in this Qiskit")
    def test_mcx_ge5_controls_uses_phase_anc_and_allocates_if_missing(self):
        q = QuantumRegister(6, "q")  # 5 ctrls + 1 target
        qc = QuantumCircuit(q)
        qc.append(MCXGate(5), q[:5] + [q[5]])  # k = 5

        out = linearise_multi_ctrl(qc, multi_control_strategy="legacy-recursive")

        # Legacy recursive MCX with five controls needs one clean ancilla.
        anc_sizes = [len(r) for r in out.qregs if r.name.startswith("anc")]
        self.assertEqual(sum(anc_sizes), 1)

        # First instruction is replaced by MCXRecursive and includes a clean ancilla.
        instruction = out.data[0]
        inst = instruction.operation
        qubits = instruction.qubits
        self.assertIsInstance(inst, MCXRecursive)
        # Qiskit order is k controls + target + ancilla.
        self.assertEqual(len(qubits), 5 + 2)
        self.assertEqual(qubits[-2], q[5])
        self.assertNotIn(qubits[-1], list(q))

    @pytest.mark.skipif(MCXRecursive is None, reason="MCXRecursive unavailable in this Qiskit")
    def test_mcx_3_controls_no_extra_qubits(self):
        q = QuantumRegister(4, "q")  # 3 ctrls + 1 target
        qc = QuantumCircuit(q)
        qc.append(MCXGate(3), q[:3] + [q[3]])  # k = 3

        out = linearise_multi_ctrl(qc, multi_control_strategy="legacy-recursive")

        instruction = out.data[0]
        inst = instruction.operation
        qubits = instruction.qubits
        self.assertIsInstance(inst, MCXRecursive)
        # No ancilla used for k=3 → k + 1 qubits
        self.assertEqual(len(qubits), 3 + 1)

    # ---------- MCU1 / MCPhase: linearisation sequence ----------

    @pytest.mark.skipif(MCXRecursive is None, reason="MCXRecursive unavailable in this Qiskit")
    def test_mcu1_k4_sequence_compute_phase_uncompute(self):
        q = QuantumRegister(5, "q")  # 4 ctrls + 1 target
        qc = QuantumCircuit(q)
        theta = 0.123
        qc.append(PhaseGate(theta).control(4), q[:4] + [q[4]])

        out = linearise_multi_ctrl(qc, multi_control_strategy="legacy-recursive")

        # Expect: MCXRecursive (compute), 1-controlled Phase, MCXRecursive (uncompute)
        self.assertEqual(self._count_type(out, MCXRecursive), 2)
        # Middle name is cp/cphase depending on version
        names = self._names(out)
        self.assertIn(names[1], ("cp", "cphase"))

        # For k=4 (<5): compute/uncompute use only phase_anc → k + 1 qubits
        instruction1 = out.data[0]
        instruction3 = out.data[2]
        inst1 = instruction1.operation
        qubits1 = instruction1.qubits
        inst3 = instruction3.operation
        qubits3 = instruction3.qubits
        self.assertEqual(len(qubits1), 4 + 1)
        self.assertEqual(len(qubits3), 4 + 1)

    @pytest.mark.skipif(MCXRecursive is None, reason="MCXRecursive unavailable in this Qiskit")
    def test_mcu1_k5_sequence_uses_scratch_and_phase_anc(self):
        q = QuantumRegister(6, "q")  # 5 ctrls + 1 target
        qc = QuantumCircuit(q)
        theta = pi / 7
        qc.append(PhaseGate(theta).control(5), q[:5] + [q[5]])

        out = linearise_multi_ctrl(qc, multi_control_strategy="legacy-recursive")

        # Ensure at least two ancillas exist (phase + scratch)
        anc_sizes = [len(r) for r in out.qregs if r.name.startswith("anc")]
        self.assertTrue(any(sz >= 2 for sz in anc_sizes))

        # Expect compute → cp → uncompute with scratch+phase ancillas included
        self.assertEqual(self._count_type(out, MCXRecursive), 2)
        names = self._names(out)
        self.assertIn(names[1], ("cp", "cphase"))

        # For k=5: compute/uncompute target phase_anc and use scratch_anc as
        # MCXRecursive's explicit clean ancilla. This order is semantically
        # important: controls + phase target + scratch ancilla.
        instruction1 = out.data[0]
        instruction3 = out.data[2]
        inst1 = instruction1.operation
        qubits1 = instruction1.qubits
        inst3 = instruction3.operation
        qubits3 = instruction3.qubits
        self.assertEqual(len(qubits1), 5 + 2)
        self.assertEqual(len(qubits3), 5 + 2)
        self.assertNotIn(qubits1[-2], list(q))
        self.assertNotIn(qubits1[-1], list(q))
        self.assertEqual(qubits1[-2], qubits3[-2])
        self.assertEqual(qubits1[-1], qubits3[-1])

        # Controlled-phase should act on exactly [phase_anc, target] → 2 qubits total
        instruction2 = out.data[1]
        inst2 = instruction2.operation
        qubits2 = instruction2.qubits
        self.assertEqual(len(qubits2), 2)
        self.assertEqual(qubits2[0], qubits1[-2])
        self.assertEqual(qubits2[1], q[5])

    def test_hls_strategy_does_not_attach_explicit_recursive_ancilla(self):
        q = QuantumRegister(6, "q")  # 5 ctrls + 1 target
        qc = QuantumCircuit(q)
        qc.append(MCXGate(5), q[:5] + [q[5]])

        out = linearise_multi_ctrl(qc, multi_control_strategy="hls")

        instruction = out.data[0]
        inst = instruction.operation
        qubits = instruction.qubits
        self.assertIsInstance(inst, MCXGate)
        if MCXRecursive is not None:
            self.assertNotIsInstance(inst, MCXRecursive)
        self.assertEqual(len(qubits), 5 + 1)
        self.assertFalse(any(r.name.startswith("anc") for r in out.qregs))

    def test_hls_multi_control_phase_adds_only_phase_ancilla(self):
        q = QuantumRegister(6, "q")
        qc = QuantumCircuit(q)
        qc.append(PhaseGate(pi / 7).control(5), q[:5] + [q[5]])

        out = linearise_multi_ctrl(qc, multi_control_strategy="hls")

        ancillas = [
            qubit
            for register in out.qregs
            if register.name.startswith("anc")
            for qubit in register
        ]
        self.assertEqual(len(ancillas), 1)
        self.assertEqual(self._names(out), ["mcx", "cp", "mcx"])
        self.assertEqual(list(out.data[0].qubits)[-1], ancillas[0])
        self.assertEqual(list(out.data[1].qubits), [ancillas[0], q[5]])

    def test_linearise_multi_ctrl_does_not_mutate_input_circuit(self):
        q = QuantumRegister(6, "q")
        qc = QuantumCircuit(q)
        qc.append(PhaseGate(pi / 7).control(5), q[:5] + [q[5]])

        _ = linearise_multi_ctrl(qc, multi_control_strategy="hls")

        self.assertEqual(qc.num_qubits, 6)
        self.assertFalse(any(r.name.startswith("anc") for r in qc.qregs))

    # ---------- Pass-through behavior ----------

    def test_other_gates_pass_through(self):
        q = QuantumRegister(2, "q")
        c = ClassicalRegister(1, "c")
        qc = QuantumCircuit(q, c)
        qc.x(0)
        qc.measure(0, 0)

        out = linearise_multi_ctrl(qc)

        self.assertEqual([n for n in self._names(out)], ["x", "measure"])
        self.assertEqual(list(out.data[0].qubits), [q[0]])  # X on same qubit
        self.assertFalse(any(r.name.startswith("anc") for r in out.qregs))


class TestCxLinearity(unittest.TestCase):

    def _cx_endpoint_count(self, matrix):
        return sum(
            1
            for row in matrix
            for cell in row
            for instruction in cell
            if instruction.name.startswith("cx")
        )

    def test_brick_alignment_width_is_linear_in_cx_count(self):
        for cx_count in range(1, 12):
            qc = QuantumCircuit(2)
            for _ in range(cx_count):
                qc.cx(0, 1)

            original, cx_matrix = instructions_to_matrix_dag(qc)
            aligned = align_bricks(cx_matrix, original)

            width = max((len(row) for row in aligned), default=0)
            self.assertLessEqual(width, 2 * cx_count + 1)
            self.assertEqual(self._cx_endpoint_count(aligned), 2 * cx_count)

    def test_brick_alignment_keeps_one_brick_per_cx_group(self):
        qc = QuantumCircuit(4)
        for _ in range(5):
            qc.cx(0, 1)
            qc.cx(2, 3)

        original, cx_matrix = instructions_to_matrix_dag(qc)
        aligned = align_bricks(cx_matrix, original)
        group_locations = defaultdict(set)
        for row_index, row in enumerate(aligned):
            for col_index, cell in enumerate(row):
                for instruction in cell:
                    if instruction.name.startswith("cx"):
                        group_locations[instruction.name[2:-1]].add((row_index, col_index))

        self.assertEqual(len(group_locations), 10)
        for locations in group_locations.values():
            columns = {col for _, col in locations}
            self.assertEqual(len(columns), 1)
            self.assertEqual(len(locations), 2)
