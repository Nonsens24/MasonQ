import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from brickwork_transpiler import decomposer, graph_builder, visualiser


def aligned_matrix(qc):
    """Decompose, schedule and align `qc`."""
    decomposed_qc = decomposer.decompose_qc_to_bricks_qiskit(qc, opt=3, with_ancillas=False)
    qc_mat, cx_mat = decomposer.instructions_to_matrix_dag(decomposed_qc)
    return decomposer.align_bricks(cx_mat, qc_mat)


def gen_test_graph(qc, matrix=None):
    """Brickwork graph of `qc`, or of an already aligned `matrix` of it."""
    if matrix is None:
        matrix = aligned_matrix(qc)
    bw_graph_data = graph_builder.generate_brickwork_graph_from_instruction_matrix(matrix)
    return graph_builder.to_networkx_graph(bw_graph_data)

def test_bw_graph_size_group_size_two_even():

    qc= QuantumCircuit(5)
    qc.h(0)
    qc.h(3)
    qc.cx(2, 3)

    bw_nx_graph = gen_test_graph(qc)

    # Debug info
    # visualiser.print_matrix(qc_mat)
    # visualiser.plot_graph(bw_nx_graph)
    # print(qc.draw())

    assert bw_nx_graph.number_of_nodes() == (5 * (3 * 4)) + 5


def test_bw_graph_size_group_size_two_odd():
    # An odd number of qubits, Hadamards on a random subset and one CX(2, 1).
    # How many brick columns Qiskit's synthesis needs depends on its version (an
    # H on the CX control may be split around the CX), so the expected node
    # count is derived from the aligned matrix: rows * (4 * columns + 1).
    rng = np.random.default_rng(2026)
    num_qubits = int(rng.integers(3, 11))

    if num_qubits % 2 == 0:  # enforce odd
        num_qubits += 1

    qc = QuantumCircuit(num_qubits)

    random_gates = rng.choice(num_qubits, replace=False, size=int(rng.integers(1, num_qubits + 1)))
    for i in random_gates:
        qc.h(int(i))

    qc.cx(2, 1)

    matrix = aligned_matrix(qc)
    bw_nx_graph = gen_test_graph(qc, matrix)

    brick_columns = len(matrix[0])
    assert brick_columns >= 2  # the Hadamard bricks and the CX brick cannot share a column
    assert len(matrix) == num_qubits
    assert bw_nx_graph.number_of_nodes() == num_qubits * (4 * brick_columns + 1)


def test_shift_bug():
    input_vector = Statevector.from_label('+++++')
    qc_bugged = QuantumCircuit(5)

    qc_bugged.cx(1, 0)

    qc_bugged.h(1)
    qc_bugged.cx(1, 2)
    qc_bugged.rz(np.pi / 2, 2)

    qc_bugged.rx(np.pi / 3, 2)
    qc_bugged.rz(np.pi / 4, 3)

    qc_bugged.cx(3, 4)
    qc_bugged.rz(np.pi / 4, 3)
    qc_bugged.h(4)

    bw_nx_graph = gen_test_graph(qc_bugged)

    # input qubits * (brick depth * number of bricks) + output qubits
    assert bw_nx_graph.number_of_nodes() == 5 * (4 * 5) + 5

def test_cx_alignment_left():
    input_vector = Statevector.from_label('+++++')

    qc = QuantumCircuit(5)
    qc.cx(2, 3)
    qc.cx(1, 2)

    bw_nx_graph = gen_test_graph(qc)

    # input qubits * (brick depth * number of bricks) + output qubits
    assert bw_nx_graph.number_of_nodes() == 5 * (4 * 2) + 5

def test_cx_alignment_right():
    input_vector = Statevector.from_label('+++++')

    qc = QuantumCircuit(5)
    qc.cx(1, 2)
    qc.cx(2, 3)

    bw_nx_graph = gen_test_graph(qc)

    # input qubits * (brick depth * number of bricks) + output qubits
    assert bw_nx_graph.number_of_nodes() == 5 * (4 * 3) + 5

def test_cx_alignment_depth_right():
    input_vector = Statevector.from_label('++++++')

    qc = QuantumCircuit(6)
    qc.cx(1, 2)
    qc.cx(4, 5)

    bw_nx_graph = gen_test_graph(qc)

    # input qubits * (brick depth * number of bricks) + output qubits
    assert bw_nx_graph.number_of_nodes() == 6 * (4 * 2) + 6

def test_cx_alignment_depth_left():
    input_vector = Statevector.from_label('++++++')

    qc = QuantumCircuit(6)
    qc.cx(1, 2)
    qc.cx(4, 5)

    bw_nx_graph = gen_test_graph(qc)

    # input qubits * (brick depth * number of bricks) + output qubits
    assert bw_nx_graph.number_of_nodes() == 6 * (4 * 2) + 6


def test_cx_alignment_depth_left_double():
    input_vector = Statevector.from_label('++++++++')

    qc = QuantumCircuit(8)
    qc.cx(2, 1)
    qc.cx(4, 5)
    qc.cx(6, 7)

    bw_nx_graph = gen_test_graph(qc)

    # input qubits * (brick depth * number of bricks) + output qubits
    assert bw_nx_graph.number_of_nodes() == 8 * (4 * 2) + 8

def test_cx_alignment_depth_right_double():
    input_vector = Statevector.from_label('++++++++')

    qc = QuantumCircuit(8)
    qc.cx(1, 0)
    qc.cx(3, 4)
    qc.cx(5, 6)

    bw_nx_graph = gen_test_graph(qc)

    # input qubits * (brick depth * number of bricks) + output qubits
    assert bw_nx_graph.number_of_nodes() == 8 * (4 * 2) + 8

def test_cx_alignment_depth_middle_shift():
    input_vector = Statevector.from_label('++++++++')

    qc = QuantumCircuit(8)
    qc.cx(0, 1)
    qc.cx(3, 4)
    qc.cx(6, 7)

    bw_nx_graph = gen_test_graph(qc)
    # input qubits * (brick depth * number of bricks) + output qubits
    assert bw_nx_graph.number_of_nodes() == 8 * (4 * 2) + 8

def test_cx_alignment_depth_outer_shift():
    input_vector = Statevector.from_label('+++++++++')

    qc = QuantumCircuit(9)
    qc.cx(2, 1)
    qc.cx(5, 4)
    qc.cx(8, 7)

    bw_nx_graph = gen_test_graph(qc)

    # input qubits * (brick depth * number of bricks) + output qubits
    assert bw_nx_graph.number_of_nodes() == 9 * (4 * 2) + 9


def test_cx_alignment_depth_outer_shift_four_cx():
    input_vector = Statevector.from_label('+++++++++')

    qc = QuantumCircuit(10)
    qc.cx(0, 1)
    qc.cx(3, 4)
    qc.cx(6, 5)
    qc.cx(8, 9)

    bw_nx_graph = gen_test_graph(qc)

    # input qubits * (brick depth * number of bricks) + output qubits
    assert bw_nx_graph.number_of_nodes() == 10 * (4 * 2) + 10


def test_cx_alignment_zig_zag():
    input_vector = Statevector.from_label('+++++++++++')

    qc = QuantumCircuit(11)
    qc.cx(0, 1)
    qc.cx(3, 4)
    qc.cx(6, 7)
    qc.cx(9, 10)

    bw_nx_graph = gen_test_graph(qc)

    # input qubits * (brick depth * number of bricks) + output qubits
    assert bw_nx_graph.number_of_nodes() == 11 * (4 * 2) + 11


def test_cx_alignment_zag_zig():
    input_vector = Statevector.from_label('++++++++++++')

    qc = QuantumCircuit(12)
    qc.cx(2, 1)
    qc.cx(5, 4)
    qc.cx(8, 7)
    qc.cx(11, 10)

    bw_nx_graph = gen_test_graph(qc)

    # input qubits * (brick depth * number of bricks) + output qubits
    assert bw_nx_graph.number_of_nodes() == 12 * (4 * 2) + 12


def test_cx_shifting_rotations():
    qc = QuantumCircuit(3)
    qc.cx(2, 1)
    qc.h(0)

    bw_nx_graph = gen_test_graph(qc)

    visualiser.plot_graph(bw_nx_graph)

    # input qubits * (brick depth * number of bricks) + output qubits
    assert bw_nx_graph.number_of_nodes() == 3 * (4 * 2) + 3

def test_cx_shifting_rotations_duplication():
    qc = QuantumCircuit(5)
    qc.cx(0, 1)
    qc.h(2)
    qc.cx(1, 2)
    qc.cx(4, 3)

    bw_nx_graph = gen_test_graph(qc)

    visualiser.plot_graph(bw_nx_graph)

    # input qubits * (brick depth * number of bricks) + output qubits
    assert bw_nx_graph.number_of_nodes() == 5 * (4 * 2) + 5





