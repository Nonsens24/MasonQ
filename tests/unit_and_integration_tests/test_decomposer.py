import numpy as np
import pytest
import unittest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from src.brickwork_transpiler import (visualiser, decomposer, brickwork_transpiler)
from src.brickwork_transpiler.decomposer import instructions_to_matrix_dag, align_cx_matrix, \
    insert_rotations_adjecant_to_cx, linearise_multi_ctrl


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

def get_matrices(qc):
    # Decompose to CX, rzrxrz, id
    decomposed_qc = decomposer.decompose_qc_to_bricks_qiskit(qc, opt=3, with_ancillas=False)

    # Optiise instruction matrix with dependency graph
    qc_mat, cx_mat = decomposer.instructions_to_matrix_dag(decomposed_qc)
    qc_mat_aligned = decomposer.align_bricks(cx_mat, qc_mat)

    return qc_mat, cx_mat, qc_mat_aligned

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
        # Two columns: rotations only, then mixed CX and rotations
        cols = [
            [['rz'], ['rx'], ['rz'], []],
            [['cx'], ['cx'], [], ['rz']],
        ]
        qc = QuantumCircuit(4)
        qc.rz(np.pi / 3, 0)
        qc.rx(np.pi / 4, 1)
        qc.rz(np.pi / 5, 2)
        qc.cx(1, 0)
        qc.rz(np.pi / 3, 3)

        qc_mat, cx_mat, qc_mat_aligned = get_matrices(qc)

        #Before shift
        cols_qc = list(zip(*qc_mat))

        assert len(cols_qc) == 2

        instr00 = cols_qc[0][0][0]
        instr01 = cols_qc[0][1][0]
        instr02 = cols_qc[0][2][0]
        instr03 = cols_qc[0][3][0]

        instr10 = cols_qc[1][0][0]
        instr11 = cols_qc[1][1][0]

        assert instr00.name == 'rz'
        assert instr01.name == 'rx'
        assert instr02.name == 'rz'
        assert instr03.name == 'rz'

        assert instr10.name == 'cx0t'
        assert instr11.name == 'cx0c'

        # After shift
        cols = list(zip(*qc_mat_aligned))

        assert len(cols) == 3

        instr00 = cols[0][0]
        instr01 = cols[0][1]
        instr02 = cols[0][2][0]
        instr03 = cols[0][3][0]

        instr20 = cols[2][0][0]
        instr21 = cols[2][1][0]

        assert instr00 == []
        assert instr01 == []
        assert instr02.name == 'rz'
        assert instr03.name == 'rz'

        assert instr20.name == 'cx0t'
        assert instr21.name == 'cx0c'



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
        # two rows, one cx0 brick already at col 1 (parity matches)
        cx0 = DummyInstr("cx0_")
        mat = [
            [[], [cx0]],  # row 0, col 1: top=0, col=1, 0%2==1%2? False → would shift
            [[], [cx0]],  # row 1
        ]
        # Actually since 0%2 != 1%2, it *should* shift right to col 2
        out = align_cx_matrix(mat)

        # visualiser.print_matrix(out)
        # expect a new column appended and both bricks moved
        assert len(out[0]) == 3
        assert out[0][1] == []
        self.assertEqual(out[0][2][0].name, cx0.name)
        self.assertEqual(out[1][2][0].name, cx0.name)

    def test_shift_cx_into_next_column(self):
        # top row index=1, col=0 → shift
        cx1 = DummyInstr("cx1_")
        mat = [
            [[]],
            [[cx1]],
            [[cx1]],
        ]
        result = align_cx_matrix(mat)
        # new width is 2
        self.assertEqual(len(result[0]), 2)
        # row 0 unchanged
        self.assertEqual(result[0], [[], []], "Row 0 should be untouched")
        # rows 1&2 moved to col 1
        self.assertEqual(result[1][0], [])
        self.assertEqual(result[1][1][0].name, cx1.name)
        self.assertEqual(result[2][1][0].name, cx1.name)

    def test_aligned_and_unaligned_bricks(self):
        # cx2 on rows 0&1 at col 0 (aligned), cx3 on rows 1&2 at col 0 (unaligned)
        cx2 = DummyInstr("cx2_")
        cx3 = DummyInstr("cx3_")
        mat = [
            [[cx2]],
            [[cx2, cx3]],
            [[cx3]],
        ]
        result = align_cx_matrix(mat)

        # visualiser.print_matrix(result)
        # cx2 remains at col 0
        self.assertEqual(cx2.name, result[0][0][0].name)
        self.assertIn(cx2.name, result[1][0][0].name)
        # cx3 moves to col 1
        self.assertNotIn(cx3.name, result[1][0][0].name)
        self.assertIn(cx3.name, result[1][1][0].name)
        self.assertIn(cx3.name, result[2][1][0].name)


from qiskit.circuit import Instruction


def names(matrix):
    """Helper to extract .name from Instruction matrix."""
    return [[ [instr.name for instr in cell] for cell in row] for row in matrix]

def get_aligned_and_original_from_circ(qc):
    # Decompose to CX, rzrxrz, id
    decomposed_qc = decomposer.decompose_qc_to_bricks_qiskit(qc, opt=3,
                                                             with_ancillas=False)

    # Optiise instruction matrix with dependency graph
    qc_mat, cx_mat = decomposer.instructions_to_matrix_dag(decomposed_qc)
    cx_mat_aligned = align_cx_matrix(cx_mat)

    return cx_mat_aligned, qc_mat


class TestInsertRotations(unittest.TestCase):

    def test_empty_matrices(self):
        aligned = []
        original = []
        result = insert_rotations_adjecant_to_cx(aligned, original)
        self.assertEqual(result, [])

    def test_no_rotations(self):
        qc = QuantumCircuit(4)
        qc.cx(1, 0)
        qc.cx(2, 3)

        aligned, original = get_aligned_and_original_from_circ(qc)
        result = insert_rotations_adjecant_to_cx(aligned, original)

        self.assertEqual(names(result), names(aligned))

    def test_default_insert_to_column_zero(self):
        aligned = [[ [Instruction('cx1', 0, 0, [])] ]]
        original = [[ [Instruction('rz', 0, 0, [])] ]]
        result = insert_rotations_adjecant_to_cx(aligned, original)
        expected = [[ ['cx1', 'rz'] ]]
        self.assertEqual(names(result), expected)

    def test_left_neighbor_insertion(self):
        qc = QuantumCircuit(2)
        qc.rz(np.pi / 3, 0)
        qc.cx(0, 1)

        aligned, original = get_aligned_and_original_from_circ(qc)
        result = insert_rotations_adjecant_to_cx(aligned, original)

        expected = [[[], ['rz'], ['cx0c']], [[], [], ['cx0t']]]
        self.assertEqual(names(result), expected)

    def test_right_neighbor_insertion(self):

        qc = QuantumCircuit(2)
        qc.cx(0, 1)
        qc.rz(np.pi/3, 0)

        aligned, original = get_aligned_and_original_from_circ(qc)
        result = insert_rotations_adjecant_to_cx(aligned, original)
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
    #     result = insert_rotations_adjecant_to_cx(aligned, original)
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
        result = insert_rotations_adjecant_to_cx(aligned, original)

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
        result = insert_rotations_adjecant_to_cx(aligned, original)
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
        result = insert_rotations_adjecant_to_cx(aligned, original)
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
        result = insert_rotations_adjecant_to_cx(aligned, original)

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
        result = insert_rotations_adjecant_to_cx(aligned, original)

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

        aligned, original = get_aligned_and_original_from_circ(qc_bugged)
        result = insert_rotations_adjecant_to_cx(aligned, original)

        expected = [[[],
                  [],
                  [],
                  [],
                  ['cx1c'],
                  [],
                  [],
                  [],
                  ['cx3c'],
                  ['rz'],
                  [],
                  [],
                  ['cx5t'],
                  [],
                  [],
                  []],
                 [[],
                  ['cx0c'],
                  ['rz', 'rx', 'rz'],
                  [],
                  ['cx1t'],
                  ['cx2c'],
                  ['rz'],
                  [],
                  ['cx3t'],
                  ['rz'],
                  [],
                  ['cx4t'],
                  ['cx5c'],
                  ['rz', 'rx', 'rz'],
                  [],
                  ['cx6t']],
                 [[],
                  ['cx0t'],
                  [],
                  [],
                  [],
                  ['cx2t'],
                  [],
                  [],
                  [],
                  [],
                  [],
                  ['cx4c'],
                  [],
                  [],
                  [],
                  ['cx6c']]]

        self.assertEqual(names(result), expected)


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

        aligned, original = get_aligned_and_original_from_circ(qc_bugged)
        result = insert_rotations_adjecant_to_cx(aligned, original)

        expected =  [[[],
              ['rz', 'rx', 'rz'],
              ['cx0t'],
              [],
              [],
              [],
              ['cx3t'],
              [],
              [],
              [],
              ['cx5t'],
              [],
              [],
              [],
              []],
             [[],
              [],
              ['cx0c'],
              ['rz', 'rx', 'rz'],
              [],
              ['cx2t'],
              ['cx3c'],
              ['rz', 'rx'],
              [],
              ['cx4c'],
              ['cx5c'],
              ['rx', 'rz'],
              [],
              ['cx6c'],
              []],
             [[],
              [],
              [],
              [],
              [],
              ['cx2c'],
              ['rz', 'rx'],
              [],
              [],
              ['cx4t'],
              ['rz', 'rx'],
              [],
              [],
              ['cx6t'],
              ['rz', 'rx']],
             [['rx'],
              ['cx1c'],
              ['rz', 'rx'],
              [],
              [],
              [],
              [],
              [],
              [],
              [],
              [],
              [],
              [],
              [],
              []],
             [['rz', 'rx', 'rz'],
              ['cx1t'],
              ['rx'],
              [],
              [],
              [],
              [],
              [],
              [],
              [],
              [],
              [],
              [],
              [],
              []]]

        self.assertEqual(names(result), expected)

import unittest
from math import pi

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit import AncillaRegister
from qiskit.circuit.library import MCXGate, MCU1Gate, PhaseGate, MCXRecursive

from src.brickwork_transpiler.decomposer import linearise_multi_ctrl  # ← replace with your import


class TestLineariseMultiCtrl(unittest.TestCase):

    def _count_type(self, qc, gate_type):
        return sum(1 for inst, _, _ in qc.data if isinstance(inst, gate_type))

    def _names(self, qc):
        return [inst.name for inst, _, _ in qc.data]

    # ---------- MCX: ancilla handling ----------

    def test_mcx_ge5_controls_uses_phase_anc_and_allocates_if_missing(self):
        q = QuantumRegister(6, "q")  # 5 ctrls + 1 target
        qc = QuantumCircuit(q)
        qc.append(MCXGate(5), q[:5] + [q[5]])  # k = 5

        out = linearise_multi_ctrl(qc)

        # At least one ancilla register of size ≥ 2 must exist
        anc_sizes = [len(r) for r in out.qregs if r.name.startswith("anc")]
        self.assertTrue(any(sz >= 2 for sz in anc_sizes))

        # First instruction replaced by MCXRecursive and includes phase ancilla
        inst, qubits, _ = out.data[0]
        self.assertIsInstance(inst, MCXRecursive)
        # k ctrls + phase_anc + target → k + 2 qubits
        self.assertEqual(len(qubits), 5 + 2)

    def test_mcx_3_controls_no_extra_qubits(self):
        q = QuantumRegister(4, "q")  # 3 ctrls + 1 target
        qc = QuantumCircuit(q)
        qc.append(MCXGate(3), q[:3] + [q[3]])  # k = 3

        out = linearise_multi_ctrl(qc)

        inst, qubits, _ = out.data[0]
        self.assertIsInstance(inst, MCXRecursive)
        # No ancilla used for k=3 → k + 1 qubits
        self.assertEqual(len(qubits), 3 + 1)

    # ---------- MCU1 / MCPhase: linearisation sequence ----------

    def test_mcu1_k4_sequence_compute_phase_uncompute(self):
        q = QuantumRegister(5, "q")  # 4 ctrls + 1 target
        qc = QuantumCircuit(q)
        theta = 0.123
        qc.append(MCU1Gate(theta, 4), q[:4] + [q[4]])

        out = linearise_multi_ctrl(qc)

        # Expect: MCXRecursive (compute), 1-controlled Phase, MCXRecursive (uncompute)
        self.assertEqual(self._count_type(out, MCXRecursive), 2)
        # Middle name is cp/cphase depending on version
        names = self._names(out)
        self.assertIn(names[1], ("cp", "cphase"))

        # For k=4 (<5): compute/uncompute use only phase_anc → k + 1 qubits
        inst1, qubits1, _ = out.data[0]
        inst3, qubits3, _ = out.data[2]
        self.assertEqual(len(qubits1), 4 + 1)
        self.assertEqual(len(qubits3), 4 + 1)

    def test_mcu1_k5_sequence_uses_scratch_and_phase_anc(self):
        q = QuantumRegister(6, "q")  # 5 ctrls + 1 target
        qc = QuantumCircuit(q)
        theta = pi / 7
        qc.append(MCU1Gate(theta, 5), q[:5] + [q[5]])

        out = linearise_multi_ctrl(qc)

        # Ensure at least two ancillas exist (phase + scratch)
        anc_sizes = [len(r) for r in out.qregs if r.name.startswith("anc")]
        self.assertTrue(any(sz >= 2 for sz in anc_sizes))

        # Expect compute → cp → uncompute with scratch+phase ancillas included
        self.assertEqual(self._count_type(out, MCXRecursive), 2)
        names = self._names(out)
        self.assertIn(names[1], ("cp", "cphase"))

        # For k=5 (≥5): compute/uncompute use scratch_anc + phase_anc → k + 2 qubits
        inst1, qubits1, _ = out.data[0]
        inst3, qubits3, _ = out.data[2]
        self.assertEqual(len(qubits1), 5 + 2)
        self.assertEqual(len(qubits3), 5 + 2)

        # Controlled-phase should act on exactly [phase_anc, target] → 2 qubits total
        inst2, qubits2, _ = out.data[1]
        self.assertEqual(len(qubits2), 2)

    # ---------- Pass-through behavior ----------

    def test_other_gates_pass_through(self):
        q = QuantumRegister(2, "q")
        c = ClassicalRegister(1, "c")
        qc = QuantumCircuit(q, c)
        qc.x(0)
        qc.measure(0, 0)

        out = linearise_multi_ctrl(qc)

        self.assertEqual([n for n in self._names(out)], ["x", "measure"])
        self.assertEqual(out.data[0][1], [q[0]])  # X on same qubit
