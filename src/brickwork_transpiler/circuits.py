"""Small fixture circuits used by the tests and examples.

Every function returns `(circuit, input_state)` with the input state |+>^n,
the state a brickwork pattern starts from.
"""

import numpy as np
from qiskit import QuantumCircuit, QuantumRegister
from qiskit.quantum_info import Statevector


def h_and_cx_circ():
    input_vector = Statevector.from_label("++")

    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)

    return qc, input_vector


def cx_and_h_circ():
    input_vector = Statevector.from_label("++")

    qc = QuantumCircuit(2)
    qc.cx(0, 1)
    qc.h(1)

    return qc, input_vector


def big_shifter_both_up_low_rotation_brick_shifted():
    input_vector = Statevector.from_label("+++++")

    qc_bugged = QuantumCircuit(5)

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

    return qc_bugged, input_vector


def qft(n):
    """
    Returns a QuantumCircuit implementing the n-qubit Quantum Fourier Transform.
    """
    input_vector = Statevector.from_label("+" * n)

    qc = QuantumCircuit(n, name="QFT")
    # Apply QFT
    for j in range(n):
        qc.h(j)
        for k in range(j + 1, n):
            lam = np.pi / float(2 ** (k - j))
            qc.cp(lam, k, j)
    # Swap qubits to reverse order
    for i in range(n // 2):
        qc.swap(i, n - i - 1)

    return qc, input_vector


def minimal_qrs(user_feature):
    qc = QuantumCircuit(5)
    c0 = QuantumRegister(1, name="c0")
    qc.add_register(c0)

    input_vector = Statevector.from_label("++++++")

    # Database:
    # 0 - 00
    # 1 - 10

    index_qubit = 0
    db_qubits = [1, 2]
    feature_qubits = [3, 4]
    # c0 = 5

    # 0 Initialize from +

    qc.h(db_qubits)
    qc.h(feature_qubits)

    # 1 Encode database
    # qc.h(0) Not necessary since is already in |+>
    qc.cx(index_qubit, db_qubits[1])

    # 2 Encode feature
    for i, bit in enumerate(reversed(user_feature)):
        if bit == 1:
            qc.x(feature_qubits[i])

    # 3 Hamming distance calculation
    qc.cx(feature_qubits[0], db_qubits[1])
    qc.cx(feature_qubits[1], db_qubits[0])

    # 4 Sum of distances
    l = 2
    # (a) P2: deposit a phase e^{+i π/l} on (f=1, c0=0)
    qc.cp(+np.pi / l, db_qubits[0], c0)
    qc.cp(+np.pi / l, db_qubits[1], c0)

    # (b) P1: single-qubit phase e^{-i π/(2l)} on (f=1)
    qc.p(-np.pi / (2 * l), db_qubits)

    # Uncompute encoding
    qc.cx(feature_qubits[0], db_qubits[1])
    qc.cx(feature_qubits[1], db_qubits[0])

    # Ancilla
    qc.h(c0)

    return qc, input_vector
