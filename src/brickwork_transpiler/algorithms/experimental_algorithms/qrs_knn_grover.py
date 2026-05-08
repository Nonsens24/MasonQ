from matplotlib import pyplot as plt
from qiskit.circuit.library import XGate
import numpy as np
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator

from brickwork_transpiler import utils
from brickwork_transpiler.utils import feature_to_generator


# This follows the quantum recommendation system as presented by Sawerwain and Wroblewski (2019)
# Link: https://sciendo.com/article/10.2478/amcs-2019-0011


# | User/IceCream | Chocolate | Vanilla | Strawberry | Nuts | Vegan |
# | ------------- | --------- | ------- | ---------- | ---- | ----- |
# | Sebastian-I   | 1         | 0       | 1          | 0    | 1     |
# | Tzula-C       | 0         | 1       | 0          | 1    | 0     |
# | Rex-E         | 1         | 1       | 1          | 0    | 1     |
# | Scot-T        | 0         | 1       | 1          | 1    | 0     |

def qrs(n_items, feature_mat, user_vector, plot=False, grover_iterations=1):

    item_qubits = int(np.log2(n_items))

    qrs_init = initialise_database(n_items, feature_mat, user_vector)
    q = int(np.log2(n_items))
    l = len(feature_mat[0])
    # database features are qubits q..q+l-1
    feature_qubits = list(range(q, q + l))
    # user-vector bits were loaded into qubits q+l..q+2l-1
    user_qubits = list(range(q + l, q + 2 * l))

    item_qubits_list = list(range(0, item_qubits))

    qrs_knn = knn(qrs_init, feature_qubits, user_qubits)
    qrs_amplified = grover(qrs_knn, item_qubits, l, user_vector, iterations=grover_iterations)
    # qrs_amplified = grover_on_indices(qrs_knn, item_qubits_list, feature_qubits, user_vector, 1, grover_iterations)

    # qrs_knn = knn(qrs_init, feature_mat, user_vector)
    # qrs_amplified = grover(qrs_knn, item_qubits, len(feature_mat[0]), user_vector, iterations=grover_iterations)

    # Build and draw the circuit
    if plot:
        qrs_amplified.draw(output='mpl',
                           fold=40,
                           )
        plt.savefig(f"images/qrs/recommendation_circ{grover_iterations}.png", dpi=300, bbox_inches="tight")
        plt.show()

    return qrs_amplified





# # Creates the user ID, Encodes the features, and creates a new user vector
# # Upper bound: O(2l + N+(N-1)/2, from Li et al. (2013), link: https://arxiv.org/abs/1210.7366
# def initialise_database(n_items: int,
#                         feature_mat: list[list[int]],
#                         user_vector: str) -> QuantumCircuit:
#     """
#     Creates a circuit that loads a database of size n_items=2^q with l-bit feature_vecs,
#     plus appends a user_vector.  If feature_mat is a linear code, uses only CNOTs;
#     otherwise does a full lookup via multi-controlled Xs.
#     """
#     # --- 0) basic checks & sizes ---
#     if n_items & (n_items - 1) != 0:
#         raise ValueError("n_items must be a power of two")
#     q = int(np.log2(n_items))
#     l = len(feature_mat[0])
#     if any(len(row) != l for row in feature_mat):
#         raise ValueError("All rows of feature_mat must have length l")
#
#     # total qubits = q index + l feature + len(user_vector)
#     qc = QuantumCircuit(q + l + len(user_vector))
#
#     # --- 1) uniform superposition on index register ---
#     qc.h(range(q))
#
#     # --- 2) database load ---
#     # try:
#     #     # try the fast linear/CNOT-only path
#     #     G = feature_to_generator(feature_mat)
#     #     for j in range(l):
#     #         for k in range(q):
#     #             if G[j][k]:
#     #                 qc.cx(k, q + j)
#     #
#     # except ValueError:
#     # not linear → fallback to general reversible lookup
#     # print("Not linear")
#     # for i, bits in enumerate(feature_mat):
#     #     bitstr = format(i, f'0{q}b')
#     #     # prepare controls to be |i⟩
#     #     for k, b in enumerate(bitstr):
#     #         if b == '0':
#     #             qc.x(k)
#     #     # for each '1' in the feature row, MCX into feature qubit
#     #     for j, b in enumerate(bits):
#     #         if b:
#     #             qc.mcx(list(range(q)), q + j, None, mode='noancilla')
#     #     # uncompute the control flips
#     #     for k, b in enumerate(bitstr):
#     #         if b == '0':
#     #             qc.x(k)
#
#
#
#     feature_qubits = list(range(q + l, q + l * 2))
#
#     # --- 3) append the user vector as X-flips ---
#     for i, bit in enumerate(reversed(user_vector)):
#         if bit == '0':
#             qc.x(feature_qubits[i])
#
#     return qc



import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import MCXGate

def initialise_database(n_items: int,
                        feature_mat: list[list[int]],
                        user_vector: str) -> QuantumCircuit:
    """
    Creates a circuit that loads a database of size n_items=2^q with l-bit feature_vecs,
    plus appends a user_vector. Uses a full lookup via multi-controlled Xs (MCX).
    """
    # --- 0) basic checks & sizes ---
    if n_items & (n_items - 1) != 0:
        raise ValueError("n_items must be a power of two")
    q = int(np.log2(n_items))              # number of index qubits
    l = len(feature_mat[0])                # feature vector length
    if any(len(row) != l for row in feature_mat):
        raise ValueError("All rows of feature_mat must have length l")

    # total_qubits = q index + l database features + len(user_vector)
    total_qubits = q + l + len(user_vector)
    qc = QuantumCircuit(total_qubits)

    # define registers
    id_qubits         = list(range(q))               # index qubits (0..q-1)
    db_feature_qubits = list(range(q, q + l))        # feature qubits (q..q+l-1)
    user_qubits       = list(range(q + l, total_qubits))  # user bits (q+l..end)

    # --- 1) uniform superposition on index register ---
    for qb in id_qubits:
        qc.h(qb)

    # --- 2) database load via MCX (full lookup) ---
    for i, bits in enumerate(feature_mat):
        # Build the q-bit binary string for i, then reverse it so that
        # pattern[0] is the LSB, pattern[q-1] is the MSB.
        pattern = format(i, f"0{q}b")   # MSB..LSB
        pattern = pattern[::-1]         # LSB..MSB

        # Invert those id_qubits[k] where the k-th bit is '0',
        # so that after inversion, all index qubits are |1> exactly when the register is |i>
        for k, b in enumerate(pattern):
            if b == '0':
                qc.x(id_qubits[k])

        # For each feature bit = 1 in row i, flip that feature qubit
        # controlled on all q index qubits being |1> (i.e. MCX with q controls)
        for j, b in enumerate(bits):
            if b == 1:
                qc.append(MCXGate(q), id_qubits + [db_feature_qubits[j]])

        # Undo the inversion on id_qubits
        for k, b in enumerate(pattern):
            if b == '0':
                qc.x(id_qubits[k])

    # --- 3) append the user_vector bits ---
    # Map string bits to user_qubits (index 0 of user_qubits corresponds to user_vector[0])
    for idx, bit in enumerate(user_vector):
        if bit == '1':
            qc.x(user_qubits[idx])

    return qc


# def initialise_database(n_items: int,
#                         feature_mat: list[list[int]],
#                         user_vector: str) -> QuantumCircuit:
#     """
#     Creates a circuit that loads a database of size n_items=2^q with l-bit feature_vecs,
#     plus appends a user_vector.  If feature_mat is a linear code, uses only CNOTs;
#     otherwise does a full lookup via multi-controlled Xs.
#     """
#     # --- 0) basic checks & sizes ---
#     if n_items & (n_items - 1) != 0:
#         raise ValueError("n_items must be a power of two")
#     q = int(np.log2(n_items))              # number of index qubits
#     l = len(feature_mat[0])                # feature vector length
#     if any(len(row) != l for row in feature_mat):
#         raise ValueError("All rows of feature_mat must have length l")
#
#     # total_qubits = q index + l database features + len(user_vector)
#     total_qubits = q + l + len(user_vector)
#     qc = QuantumCircuit(total_qubits)
#
#     # define registers
#     id_qubits         = list(range(q))
#     db_feature_qubits = list(range(q, q + l))
#     user_qubits       = list(range(q + l, total_qubits))
#
#     # --- 1) uniform superposition on index register ---
#     for qb in id_qubits:
#         qc.h(qb)
#
#     # --- 2) database load ---
#     # Check if feature_mat is a linear map: feature_mat[i] = XOR of basis rows
#     G = [feature_mat[1 << j] for j in range(q)]
#     is_linear = True
#     for i in range(len(feature_mat)):
#         # XOR of G[j] where bit j of i == 1
#         pred = [0] * l
#         for j in range(q):
#             if (i >> j) & 1:
#                 pred = [(p ^ g) for p, g in zip(pred, G[j])]
#         if pred != feature_mat[i]:
#             is_linear = False
#             break
#     # always use MCX lookup
#     for i, bits in enumerate(feature_mat):
#         pattern = format(i, f"0{q}b")
#         # invert zero‐bits of index to prepare all‐ones control
#         for k, b in enumerate(pattern):
#             if b == '0':
#                 qc.x(id_qubits[k])
#         # for each bit in 'bits' that is 1, MCX with all index qubits as controls
#         for j, b in enumerate(bits):
#             if b:
#                 qc.append(MCXGate(q), id_qubits + [q + j])
#         # uncompute the inverted index qubits
#         for k, b in enumerate(pattern):
#             if b == '0':
#                 qc.x(id_qubits[k])
#
#     # if is_linear:
#     #     # linear encoding via CNOTs
#     #     for j in range(q):
#     #         for k in range(l):
#     #             if G[j][k]:
#     #                 qc.cx(id_qubits[j], db_feature_qubits[k])
#     # else:
#     #     # full lookup: encode each row i using exact controls
#     #     for i, bits in enumerate(feature_mat):
#     #         # determine which id qubits need inversion to set up all-ones control
#     #         pattern = format(i, f"0{q}b")
#     #         zeros = [j for j, b in enumerate(pattern) if b == '0']
#     #         # invert zero bits so |i> -> all-ones on id_qubits
#     #         for j in zeros:
#     #             qc.x(id_qubits[j])
#     #
#     #         # for each feature bit=1, apply multi-controlled X
#     #         for k, bit in enumerate(bits):
#     #             if bit:
#     #                 # use MCX with q controls
#     #                 qc.append(MCXGate(q), id_qubits + [db_feature_qubits[k]])
#     #
#     #         # undo inversions to restore superposition controls
#     #         for j in zeros:
#     #             qc.x(id_qubits[j])
#
#     # --- 3) append the user_vector bits ---
#     # map string bits to user_qubits (LSB->first qubit)
#     # for idx, bit in enumerate(reversed(user_vector)):
#     for idx, bit in enumerate(user_vector):
#         if bit == '1':
#             qc.x(user_qubits[idx])
#
#     return qc



# # Performs the QKNN algorithm by first calculating the hamming distance and then summing the distances
# # See Trugenberger (2002) link: https://link.springer.com/article/10.1023/A:1024022632303
# def knn(qrs: QuantumCircuit, feature_size: int, item_qubits: int, user_vector: str) -> QuantumCircuit:
#     # Add ancilla qubit for KNN
#     c0 = QuantumRegister(1, name='c0')
#     qrs.add_register(c0)            # TODO: Move this to the top of the circuit!
#
#     # Hamming distance calculations:
#     for q in range(feature_size + item_qubits, qrs.num_qubits - 1-1): # -c0
#         print(f"feature_size = {feature_size}, q = {q}, qrs.num - q = {qrs.num_qubits - q}, item_qubits: {item_qubits}")
#         qrs.cx(qrs.qubits[q], qrs.qubits[qrs.num_qubits - q-1]) # -c0 - 1 index
#
#     # print(qrs.draw(output='text'))
#
#     # Quantum summing of Hamming distances:
#     qrs.h(c0)
#
#     for q in range(feature_size + item_qubits - 1, item_qubits - 1, -1): #start -1 for indexing
#         print(f"item_qubits: {item_qubits}, q = {q}, feature_size = {feature_size}")
#         qrs.cp(-np.pi/feature_size, qrs.qubits[q], c0) # feature size = l from the paper P2
#         qrs.rz(np.pi/2*feature_size, qrs.qubits[q])     # P1
#
#     qrs.h(c0)
#
#     print(qrs.draw(output='text'))
#
#
#
#     return qrs


from qiskit import QuantumCircuit, QuantumRegister


from qiskit import QuantumRegister

def knn(
    qc: QuantumCircuit,
    feature_qubits: list[int],
    user_qubits:    list[int]
) -> QuantumCircuit:
    """
    In-place QkNN Hamming-distance & phase-sum:
      - feature_qubits[i] holds the i-th database feature bit
      - user_qubits[i]    holds the i-th user-vector bit
    After this, the ancilla 'c0' carries amplitudes ∝ cos(π/(2l)·d).
    """
    l = len(feature_qubits)
    if l != len(user_qubits):
        raise ValueError("feature_qubits and user_qubits must have the same length")

    # 1) Add single ancilla c0 for the phase-sum
    c0_reg = QuantumRegister(1, name="c0")
    qc.add_register(c0_reg)
    c0 = c0_reg[0]  # starts in |0>

    # 2) XOR: for each i, compute d_i = r_i ⊕ t_i onto feature_qubits[i]
    for i in range(l):
        qc.cx(user_qubits[i], feature_qubits[i])

    # 3) Phase-sum those l distance bits onto c0
    qc.h(c0)  # put c0 into |+> = (|0>+|1>)/√2
    for f in feature_qubits:
        # (a) P2: deposit a phase e^{+i π/l} on (f=1, c0=0)
        qc.x(c0)
        qc.cp(+np.pi / l, f, c0)
        qc.x(c0)

        # (b) P1: single-qubit phase e^{-i π/(2l)} on (f=1)
        qc.p(-np.pi / (2 * l), f)

    qc.h(c0)

    # 4) Uncompute: restore feature_qubits to original r_i
    for i in range(l):
        qc.cx(user_qubits[i], feature_qubits[i])

    return qc


# def knn(
#     qc: QuantumCircuit,
#     feature_qubits: list[int],
#     user_qubits:    list[int]
# ) -> QuantumCircuit:
#     """
#     In-place QKNN Hamming-distance & sum:
#       - feature_qubits: indices of the l database-feature wires
#       - user_qubits:    indices of the l user-vector wires
#     Assumes 'user_qubits' already hold the user bits (loaded by initialise_database).
#     """
#     l = len(feature_qubits)
#     if l != len(user_qubits):
#         raise ValueError("feature_qubits and user_qubits must have the same length")
#
#     # 1) Add single ancilla c0 for the phase-sum
#     c0_reg = QuantumRegister(1, name="c0")
#     qc.add_register(c0_reg)
#     c0 = c0_reg[0]
#
#     # 2) Hamming‐distance fan-out CNOTs
#     #    lowest user bit → highest feature bit, next → next, etc.
#     for i in range(l):
#         u = user_qubits[i]
#         f = feature_qubits[l - 1 - i]
#         qc.cx(u, f)
#
#     # 3) Phase‐sum those l XOR-bits (now sitting in feature_qubits) onto c0
#     qc.h(c0)
#     for f in feature_qubits:
#         qc.cp(-np.pi / l, f, c0)
#         qc.p( np.pi / (2 * l), f)
#     qc.h(c0)
#
#     # 4) Uncompute the XOR so your database bits are restored
#     for i in range(l):
#         u = user_qubits[i]
#         f = feature_qubits[l - 1 - i]
#         qc.cx(u, f)
#
#     return qc


# Amplifies amplitudes of recommendations of interest using grover's algorithm
# See Grover (1996) link: https://dl.acm.org/doi/10.1145/237814.237866
from qiskit import QuantumCircuit, QuantumRegister
#
def grover(
    qc: QuantumCircuit,
    q: int,
    l: int,
    user_vector: str,
    iterations: int = 1
) -> QuantumCircuit:
    """
    Append `iterations` Grover rounds that mark the basis state == user_vector
    on the l-qubit feature register [q, …, q+l-1], using one aux qubit |qA>.
    """
    # --- 1) allocate the Grover ancilla ---
    grov = QuantumRegister(1, name='qA')
    qc.add_register(grov)
    qA = grov[0]

    feature_qubits = list(range(q, q + l))


    # b) prepare ancilla in |–> for phase kickback
    qc.x(qA)
    qc.h(qA)

    # Initialise circuit:
    # qc.h(feature_qubits)

    for _ in range(iterations):

        # ───────────── Oracle ─────────────
        for i, bit in enumerate(user_vector):
            if bit == '1':
                qc.x(feature_qubits[i])

        # c) multi-controlled X from all feature_qubits → qA
        qc.mcx(feature_qubits, qA)

        # e) uncompute the feature-qubit bit-flips
        for i, bit in enumerate(user_vector):
            if bit == '1':
                qc.x(feature_qubits[i])

        # ────────── Diffusion (inversion-about-mean) ──────────


        qc.h(feature_qubits)
        qc.x(feature_qubits)

        # multi-controlled Z on feature register, via H–MCX–H on last feature qubit
        qc.h(feature_qubits[-1])
        qc.mcx(feature_qubits[:-1], feature_qubits[-1])
        qc.h(feature_qubits[-1])

        qc.x(feature_qubits)
        qc.h(feature_qubits)

    qc.h(qA)

    return qc

from qiskit import QuantumRegister, ClassicalRegister

def grover_on_indices(
    qc: QuantumCircuit,
    index_qubits:   list[int],  # these are the q index qubits
    feature_qubits: list[int],  # can be ignored once c0=0 is observed
    user_vector:     str,
    aux_qubit:       int,
    iterations:      int = 1
) -> QuantumCircuit:
    """
    Grover on the index register:
      - index_qubits: [0..q-1]
      - aux_qubit:    a single qubit used as oracle target (in |->)
      - user_vector:  the l-bit string to match exactly (we assume l <=  q, or else use a separate feature-to-index lookup)
    """

    # 1) Prepare aux_qubit = |−> = (|0> − |1>)/√2
    qc.x(aux_qubit)
    qc.h(aux_qubit)

    # For convenience, assume feature_qubits hold the SAME bits r_p that index p encodes.
    # If not, you must re-load the feature string for each index. We sketch the "feature lookup" here:

    for _ in range(iterations):
        # ─────────── Oracle ───────────
        # (a) If we want to mark “r_p == user_vector exactly,”
        #     we must test each bit of r_p.  Suppose feature_qubits[i] = r_{p,i}.
        #     Then we do: for each i where user_vector[i]=='0', flip that feature bit so that matching pattern becomes all-1’s.
        for i, bit in enumerate(user_vector):
            if bit == '0':
                qc.x(feature_qubits[i])

        # (b) Now apply an MCX from all feature_qubits onto aux_qubit.
        #     This flips aux_qubit if and only if (all feature_qubits[i] = 1), i.e. r_p == user_vector.
        qc.mcx(feature_qubits, aux_qubit)

        # (c) Undo the bit-flips on feature_qubits
        for i, bit in enumerate(user_vector):
            if bit == '0':
                qc.x(feature_qubits[i])

        # At this point, the overall global phase of |p> in the index register
        # has been flipped *if and only if* r_p == user_vector exactly.

        # ───────── Diffusion on index_qubits ─────────
        # (1) H on all index qubits
        qc.h(index_qubits)
        # (2) X on all index qubits
        qc.x(index_qubits)
        # (3) multi-control Z on all index qubits (flip phase of |00...0>):
        qc.h(index_qubits[-1])
        qc.mcx(index_qubits[:-1], index_qubits[-1])
        qc.h(index_qubits[-1])
        # (4) X on all index qubits
        qc.x(index_qubits)
        # (5) H on all index qubits
        qc.h(index_qubits)

    # Finally, restore aux_qubit to |0> or discard it
    qc.h(aux_qubit)
    # (Optionally measure aux_qubit or leave it in |0>.)

    return qc



