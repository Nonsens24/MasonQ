import numpy as np
from matplotlib import pyplot as plt

from brickwork_transpiler import brickwork_transpiler, circuits
from brickwork_transpiler.algorithms import qrs_knn_grover

import brickwork_transpiler.utils as bw_utils




# --- DATA ---
def get_data():

    #2^2
    feature_mat1 = [
        [0, 1, 0, 0, 0, 1],  # Sebastian-I
        [1, 0, 0, 1, 1, 1],  # Tzula-C
        [1, 1, 1, 0, 1, 0],  # Rex-E
        [0, 0, 0, 0, 0, 1],
    ]

    # 2^3
    feature_mat2 = [
        [0, 0, 0, 1, 1, 0],  # Sebastian-I
        [0, 1, 0, 1, 0, 0],  # Tzula-C
        [1, 1, 1, 0, 1, 0],  # Rex-E
        [0, 1, 1, 1, 1, 0],  # Scott-T
        [0, 1, 0, 0, 0, 1],  # Sebastian-I
        [0, 1, 0, 1, 0, 0],  # Tzula-C
        [1, 0, 0, 1, 1, 0],
        [0, 0, 0, 0, 0, 1],
    ]

    # 2^4
    feature_mat3 = [
        [0, 0, 0, 0, 0, 0],  # 0000 → 000000
        [0, 0, 0, 1, 1, 0],  # 0001 → 000110
        [0, 0, 1, 0, 0, 1],  # 0010 → 001001
        [0, 0, 1, 1, 1, 1],  # 0011 → 001111
        [0, 0, 0, 1, 0, 0],  # 0100 → 000100
        [0, 0, 0, 0, 1, 0],  # 0101 → 000010
        [0, 0, 1, 1, 0, 1],  # 0110 → 001101
        [0, 0, 1, 0, 1, 1],  # 0111 → 001011
        [0, 1, 0, 0, 0, 1],  # 1000 → 100000
        [1, 0, 0, 1, 1, 0],  # 1001 → 100110
        [0, 0, 0, 0, 0, 1],
        [1, 0, 1, 1, 1, 1],  # 1011 → 101111
        [1, 0, 0, 1, 0, 0],  # 1100 → 100100
        [1, 0, 0, 0, 1, 0],  # 1101 → 100010
        [1, 0, 1, 1, 0, 1],  # 1110 → 101101
        [1, 0, 1, 0, 1, 1],  # 1111 → 101011
    ]

    # 2^5
    feature_mat4 = [
        [0, 0, 0, 0, 0, 0],  # 0000 → 000000
        [0, 0, 0, 1, 1, 0],  # 0001 → 000110
        [0, 0, 1, 0, 0, 1],  # 0010 → 001001
        [0, 0, 1, 1, 1, 1],  # 0011 → 001111
        [0, 0, 0, 1, 0, 0],  # 0100 → 000100
        [0, 1, 0, 0, 0, 1],  # 0101 → 000010
        [0, 0, 1, 1, 0, 1],  # 0110 → 001101
        [0, 0, 1, 0, 1, 1],  # 0111 → 001011
        [1, 0, 0, 0, 0, 0],  # 1000 → 100000
        [1, 0, 0, 1, 1, 0],  # 1001 → 100110
        [0, 0, 0, 0, 0, 1],
        [1, 0, 1, 1, 1, 1],  # 1011 → 101111
        [1, 0, 0, 1, 0, 0],  # 1100 → 100100
        [1, 0, 0, 0, 1, 0],  # 1101 → 100010
        [1, 0, 1, 1, 0, 1],  # 1110 → 101101
        [1, 0, 1, 0, 1, 1],  # 1111 → 101011
        [0, 0, 0, 0, 0, 0],  # 0000 → 000000
        [0, 0, 0, 1, 1, 0],  # 0001 → 000110
        [0, 0, 1, 0, 0, 1],  # 0010 → 001001
        [0, 0, 1, 1, 1, 1],  # 0011 → 001111
        [0, 0, 0, 1, 0, 0],  # 0100 → 000100
        [0, 0, 0, 0, 1, 0],  # 0101 → 000010
        [0, 0, 1, 1, 0, 1],  # 0110 → 001101
        [0, 0, 1, 0, 1, 1],  # 0111 → 001011
        [1, 0, 0, 0, 0, 0],  # 1000 → 100000
        [1, 0, 0, 1, 1, 0],  # 1001 → 100110
        [1, 0, 1, 0, 0, 1],  # 1010 → 101001
        [1, 0, 1, 1, 1, 1],  # 1011 → 101111
        [1, 0, 0, 1, 0, 0],  # 1100 → 100100
        [1, 0, 0, 0, 1, 0],  # 1101 → 100010
        [1, 0, 1, 1, 0, 1],  # 1110 → 101101
        [1, 0, 1, 0, 1, 1],  # 1111 → 101011
    ]

    # 2^6
    feature_mat5 = [
        [0, 0, 0, 0, 0, 0],  # 0000 → 000000
        [0, 0, 0, 1, 1, 0],  # 0001 → 000110
        [0, 0, 1, 0, 0, 1],  # 0010 → 001001
        [0, 0, 1, 1, 1, 1],  # 0011 → 001111
        [0, 0, 0, 1, 0, 0],  # 0100 → 000100
        [0, 0, 0, 0, 1, 0],  # 0101 → 000010
        [0, 0, 1, 1, 0, 1],  # 0110 → 001101
        [0, 0, 1, 0, 1, 1],  # 0111 → 001011
        [1, 0, 0, 0, 0, 0],  # 1000 → 100000
        [1, 0, 0, 1, 1, 0],  # 1001 → 100110
        [1, 0, 1, 0, 0, 1],  # 1010 → 101001
        [1, 0, 1, 1, 1, 1],  # 1011 → 101111
        [1, 0, 0, 1, 0, 0],  # 1100 → 100100
        [1, 0, 0, 0, 1, 0],  # 1101 → 100010
        [1, 0, 1, 1, 0, 1],  # 1110 → 101101
        [1, 0, 1, 0, 1, 1],  # 1111 → 101011
        [0, 0, 0, 0, 0, 0],  # 0000 → 000000
        [0, 0, 0, 1, 1, 0],  # 0001 → 000110
        [0, 0, 1, 0, 0, 1],  # 0010 → 001001
        [0, 0, 1, 1, 1, 1],  # 0011 → 001111
        [0, 0, 0, 1, 0, 0],  # 0100 → 000100
        [0, 0, 0, 0, 1, 0],  # 0101 → 000010
        [0, 0, 1, 1, 0, 1],  # 0110 → 001101
        [0, 0, 1, 0, 1, 1],  # 0111 → 001011
        [1, 0, 0, 0, 0, 0],  # 1000 → 100000
        [1, 0, 0, 1, 1, 0],  # 1001 → 100110
        [1, 0, 1, 0, 0, 1],  # 1010 → 101001
        [1, 0, 1, 1, 1, 1],  # 1011 → 101111
        [1, 0, 0, 1, 0, 0],  # 1100 → 100100
        [1, 0, 0, 0, 1, 0],  # 1101 → 100010
        [1, 0, 1, 1, 0, 1],  # 1110 → 101101
        [1, 0, 1, 0, 1, 1],  # 1111 → 101011
        [0, 0, 0, 0, 0, 0],  # 0000 → 000000
        [0, 0, 0, 1, 1, 0],  # 0001 → 000110
        [0, 0, 1, 0, 0, 1],  # 0010 → 001001
        [0, 0, 1, 1, 1, 1],  # 0011 → 001111
        [0, 0, 0, 1, 0, 0],  # 0100 → 000100
        [0, 0, 0, 0, 1, 0],  # 0101 → 000010
        [0, 0, 1, 1, 0, 1],  # 0110 → 001101
        [0, 0, 1, 0, 1, 1],  # 0111 → 001011
        [1, 0, 0, 0, 0, 0],  # 1000 → 100000
        [0, 1, 0, 0, 0, 1],  # 1001 → 100110
        [1, 0, 1, 0, 0, 1],  # 1010 → 101001
        [0, 0, 0, 0, 0, 1],
        [1, 0, 0, 1, 0, 0],  # 1100 → 100100
        [1, 0, 0, 0, 1, 0],  # 1101 → 100010
        [1, 0, 1, 1, 0, 1],  # 1110 → 101101
        [1, 0, 1, 0, 1, 1],  # 1111 → 101011
        [0, 0, 0, 0, 0, 0],  # 0000 → 000000
        [0, 0, 0, 1, 1, 0],  # 0001 → 000110
        [0, 0, 1, 0, 0, 1],  # 0010 → 001001
        [0, 0, 1, 1, 1, 1],  # 0011 → 001111
        [0, 0, 0, 1, 0, 0],  # 0100 → 000100
        [0, 0, 0, 0, 1, 0],  # 0101 → 000010
        [0, 0, 1, 1, 0, 1],  # 0110 → 001101
        [0, 0, 1, 0, 1, 1],  # 0111 → 001011
        [1, 0, 0, 0, 0, 0],  # 1000 → 100000
        [1, 0, 0, 1, 1, 0],  # 1001 → 100110
        [1, 0, 1, 0, 0, 1],  # 1010 → 101001
        [1, 0, 1, 1, 1, 1],  # 1011 → 101111
        [1, 0, 0, 1, 0, 0],  # 1100 → 100100
        [1, 0, 0, 0, 1, 0],  # 1101 → 100010
        [1, 0, 1, 1, 0, 1],  # 1110 → 101101
        [1, 0, 1, 0, 1, 1],  # 1111 → 101011
    ]

    # 2^7
    feature_mat6 = [
        [0, 0, 0, 0, 0, 0],  # 0000 → 000000
        [0, 0, 0, 1, 1, 0],  # 0001 → 000110
        [0, 0, 1, 0, 0, 1],  # 0010 → 001001
        [0, 0, 1, 1, 1, 1],  # 0011 → 001111
        [0, 0, 0, 1, 0, 0],  # 0100 → 000100
        [0, 0, 0, 0, 1, 0],  # 0101 → 000010
        [0, 0, 1, 1, 0, 1],  # 0110 → 001101
        [0, 0, 1, 0, 1, 1],  # 0111 → 001011
        [1, 0, 0, 0, 0, 0],  # 1000 → 100000
        [1, 0, 0, 1, 1, 0],  # 1001 → 100110
        [1, 0, 1, 0, 0, 1],  # 1010 → 101001
        [1, 0, 1, 1, 1, 1],  # 1011 → 101111
        [1, 0, 0, 1, 0, 0],  # 1100 → 100100
        [1, 0, 0, 0, 1, 0],  # 1101 → 100010
        [1, 0, 1, 1, 0, 1],  # 1110 → 101101
        [1, 0, 1, 0, 1, 1],  # 1111 → 101011
        [0, 0, 0, 0, 0, 0],  # 0000 → 000000
        [0, 0, 0, 1, 1, 0],  # 0001 → 000110
        [0, 0, 1, 0, 0, 1],  # 0010 → 001001
        [0, 0, 1, 1, 1, 1],  # 0011 → 001111
        [0, 0, 0, 1, 0, 0],  # 0100 → 000100
        [0, 0, 0, 0, 1, 0],  # 0101 → 000010
        [0, 0, 1, 1, 0, 1],  # 0110 → 001101
        [0, 0, 1, 0, 1, 1],  # 0111 → 001011
        [1, 0, 0, 0, 0, 0],  # 1000 → 100000
        [1, 0, 0, 1, 1, 0],  # 1001 → 100110
        [1, 0, 1, 0, 0, 1],  # 1010 → 101001
        [1, 0, 1, 1, 1, 1],  # 1011 → 101111
        [1, 0, 0, 1, 0, 0],  # 1100 → 100100
        [1, 0, 0, 0, 1, 0],  # 1101 → 100010
        [1, 0, 1, 1, 0, 1],  # 1110 → 101101
        [1, 0, 1, 0, 1, 1],  # 1111 → 101011
        [0, 0, 0, 0, 0, 0],  # 0000 → 000000
        [0, 0, 0, 1, 1, 0],  # 0001 → 000110
        [0, 0, 1, 0, 0, 1],  # 0010 → 001001
        [0, 0, 1, 1, 1, 1],  # 0011 → 001111
        [0, 0, 0, 1, 0, 0],  # 0100 → 000100
        [0, 0, 0, 0, 1, 0],  # 0101 → 000010
        [0, 0, 1, 1, 0, 1],  # 0110 → 001101
        [0, 0, 1, 0, 1, 1],  # 0111 → 001011
        [1, 0, 0, 0, 0, 0],  # 1000 → 100000
        [1, 0, 0, 1, 1, 0],  # 1001 → 100110
        [1, 0, 1, 0, 0, 1],  # 1010 → 101001
        [1, 0, 1, 1, 1, 1],  # 1011 → 101111
        [1, 0, 0, 1, 0, 0],  # 1100 → 100100
        [1, 0, 0, 0, 1, 0],  # 1101 → 100010
        [1, 0, 1, 1, 0, 1],  # 1110 → 101101
        [1, 0, 1, 0, 1, 1],  # 1111 → 101011
        [0, 0, 0, 0, 0, 0],  # 0000 → 000000
        [0, 0, 0, 1, 1, 0],  # 0001 → 000110
        [0, 0, 1, 0, 0, 1],  # 0010 → 001001
        [0, 0, 1, 1, 1, 1],  # 0011 → 001111
        [0, 0, 0, 1, 0, 0],  # 0100 → 000100
        [0, 0, 0, 0, 1, 0],  # 0101 → 000010
        [0, 0, 1, 1, 0, 1],  # 0110 → 001101
        [0, 0, 1, 0, 1, 1],  # 0111 → 001011
        [1, 0, 0, 0, 0, 0],  # 1000 → 100000
        [1, 0, 0, 1, 1, 0],  # 1001 → 100110
        [1, 0, 1, 0, 0, 1],  # 1010 → 101001
        [1, 0, 1, 1, 1, 1],  # 1011 → 101111
        [1, 0, 0, 1, 0, 0],  # 1100 → 100100
        [1, 0, 0, 0, 1, 0],  # 1101 → 100010
        [1, 0, 1, 1, 0, 1],  # 1110 → 101101
        [1, 0, 1, 0, 1, 1],  # 1111 → 101011
        [0, 1, 0, 0, 0, 1],  # 0000 → 000000
        [0, 0, 0, 1, 1, 0],  # 0001 → 000110
        [0, 0, 1, 0, 0, 1],  # 0010 → 001001
        [0, 0, 1, 1, 1, 1],  # 0011 → 001111
        [0, 0, 0, 1, 0, 0],  # 0100 → 000100
        [0, 0, 0, 0, 1, 0],  # 0101 → 000010
        [0, 0, 1, 1, 0, 1],  # 0110 → 001101
        [0, 0, 1, 0, 1, 1],  # 0111 → 001011
        [1, 0, 0, 0, 0, 0],  # 1000 → 100000
        [1, 0, 0, 1, 1, 0],  # 1001 → 100110
        [1, 0, 1, 0, 0, 1],  # 1010 → 101001
        [1, 0, 1, 1, 1, 1],  # 1011 → 101111
        [1, 0, 0, 1, 0, 0],  # 1100 → 100100
        [1, 0, 0, 0, 1, 0],  # 1101 → 100010
        [1, 0, 1, 1, 0, 1],  # 1110 → 101101
        [1, 0, 1, 0, 1, 1],  # 1111 → 101011
        [0, 0, 0, 0, 0, 0],  # 0000 → 000000
        [0, 0, 0, 1, 1, 0],  # 0001 → 000110
        [0, 0, 1, 0, 0, 1],  # 0010 → 001001
        [0, 0, 1, 1, 1, 1],  # 0011 → 001111
        [0, 0, 0, 1, 0, 0],  # 0100 → 000100
        [0, 0, 0, 0, 1, 0],  # 0101 → 000010
        [0, 0, 1, 1, 0, 1],  # 0110 → 001101
        [0, 0, 1, 0, 1, 1],  # 0111 → 001011
        [1, 0, 0, 0, 0, 0],  # 1000 → 100000
        [1, 0, 0, 1, 1, 0],  # 1001 → 100110
        [1, 0, 1, 0, 0, 1],  # 1010 → 101001
        [1, 0, 1, 1, 1, 1],  # 1011 → 101111
        [1, 0, 0, 1, 0, 0],  # 1100 → 100100
        [1, 0, 0, 0, 1, 0],  # 1101 → 100010
        [1, 0, 1, 1, 0, 1],  # 1110 → 101101
        [1, 0, 1, 0, 1, 1],  # 1111 → 101011
        [0, 0, 0, 0, 0, 0],  # 0000 → 000000
        [0, 0, 0, 1, 1, 0],  # 0001 → 000110
        [0, 0, 1, 0, 0, 1],  # 0010 → 001001
        [0, 0, 1, 1, 1, 1],  # 0011 → 001111
        [0, 0, 0, 1, 0, 0],  # 0100 → 000100
        [0, 0, 0, 0, 1, 0],  # 0101 → 000010
        [0, 0, 1, 1, 0, 1],  # 0110 → 001101
        [0, 0, 1, 0, 1, 1],  # 0111 → 001011
        [1, 0, 0, 0, 0, 0],  # 1000 → 100000
        [1, 0, 0, 1, 1, 0],  # 1001 → 100110
        [1, 0, 1, 0, 0, 1],  # 1010 → 101001
        [1, 0, 1, 1, 1, 1],  # 1011 → 101111
        [1, 0, 0, 1, 0, 0],  # 1100 → 100100
        [1, 0, 0, 0, 1, 0],  # 1101 → 100010
        [1, 0, 1, 1, 0, 1],  # 1110 → 101101
        [1, 0, 1, 0, 1, 1],  # 1111 → 101011
        [0, 0, 0, 0, 0, 0],  # 0000 → 000000
        [0, 0, 0, 1, 1, 0],  # 0001 → 000110
        [0, 0, 1, 0, 0, 1],  # 0010 → 001001
        [0, 0, 1, 1, 1, 1],  # 0011 → 001111
        [0, 0, 0, 1, 0, 0],  # 0100 → 000100
        [0, 0, 0, 0, 1, 0],  # 0101 → 000010
        [0, 0, 1, 1, 0, 1],  # 0110 → 001101
        [0, 0, 1, 0, 1, 1],  # 0111 → 001011
        [1, 0, 0, 0, 0, 0],  # 1000 → 100000
        [1, 0, 0, 1, 1, 0],  # 1001 → 100110
        [1, 0, 1, 0, 0, 1],  # 1010 → 101001
        [1, 0, 1, 1, 1, 1],  # 1011 → 101111
        [1, 0, 0, 1, 0, 0],  # 1100 → 100100
        [0, 0, 0, 0, 0, 1],
        [1, 0, 1, 1, 0, 1],  # 1110 → 101101
        [1, 0, 1, 0, 1, 1],  # 1111 → 101011
    ]

    return feature_mat1, feature_mat2, feature_mat3, feature_mat4, feature_mat5, feature_mat6

def get_writer(file_name: str, file_path: str="src/ubqc_brickwork_transpiler/experiments/data/output_data/"):


    header = ["num_iterations", "decomposed_depth", "transpiled_depth", "original_depth", "num_gates_original",
              "num_gates_transpiled", "L", "g"]

    return bw_utils.BufferedCSVWriter(file_path + file_name, header)


def experiment_qrs_no_db_one_matching_element():

    filename = "experiments_qrs_no_db_one_match.csv"
    writer = get_writer(filename)

    user_feature = [0, 1, 0, 0, 0, 1]
    feature_subset = [[0, 1, 0, 0, 0, 1]]
    grover_iterations = None  # None for optimal, or set a specific int
    g = 1


    feature_mats = get_data()

    for id_fm, feature_mat in enumerate(feature_mats):
        n_items = len(feature_mat)
        num_id_qubits = int(np.log2(n_items))
        num_db_feature_qubits = len(feature_mat[0])
        feature_qubits = list(range(num_id_qubits, num_id_qubits + num_db_feature_qubits))

        # # --- BUILD CIRCUIT ---
        qrs_circ = qrs_knn_grover.qrs(
            n_items=n_items,
            feature_mat=feature_mat,
            user_vector=user_feature,
            feature_subset=feature_subset,
            g=g,
            plot_circ=False,
            plot_histogram=False,
            grover_iterations=grover_iterations,  # None lets Qiskit calculate the optimal amount
            file_writer = writer
        )
        # qrs_circ = circuits.mcu1_circuit()
        print(f"gate count: {qrs_circ.decompose(reps=4).count_ops()}")

        print("Transpiling...")
        instr_mat = brickwork_transpiler.transpile(qrs_circ, routing_method='sabre', layout_method='sabre',
                                                   return_mat=True, file_writer=writer)

        writer.set("transpiled_depth", len(instr_mat[0]))
        writer.set("original_depth", qrs_circ.depth())
        writer.flush()


def experiment_qrs_no_db_no_matching_element():

    filename = "experiment_qrs_no_db_no_matching_element.csv"
    writer = get_writer(filename)

    user_feature = [0, 1, 0, 0, 0, 1]
    feature_subset = [[0, 'X', 0, 'X', 0, 1]] # Matches: [0, 1, 0, 0, 0, 1], [0, 0, 0, 0, 0, 1],
    grover_iterations = None  # None for optimal, or set a specific int
    g = None # No matches

    feature_mats = get_data()

    for id_fm, feature_mat in enumerate(feature_mats):
        n_items = len(feature_mat)
        num_id_qubits = int(np.log2(n_items))
        num_db_feature_qubits = len(feature_mat[0])
        feature_qubits = list(range(num_id_qubits, num_id_qubits + num_db_feature_qubits))

        # --- BUILD CIRCUIT ---
        qrs_circ = qrs_knn_grover.qrs(
            n_items=n_items,
            feature_mat=feature_mat,
            user_vector=user_feature,
            feature_subset=feature_subset,
            g=g,
            plot_circ=False,
            plot_histogram=False,
            grover_iterations=grover_iterations,  # None lets Qiskit calculate the optimal amount
            file_writer = writer
        )

        # print("Transpiling...")
        instr_mat = brickwork_transpiler.transpile(qrs_circ, routing_method='sabre', layout_method='sabre',
                                                   return_mat=True, file_writer=writer)

        writer.set("transpiled_depth", len(instr_mat[0]))
        writer.set("original_depth", qrs_circ.depth())
        writer.flush()


def experiment_qrs_no_db_subset_grover():

    filename = "experiment_qrs_no_db_subset_grover.csv"
    writer = get_writer(filename)

    user_feature = [0, 1, 0, 0, 0, 1] # not in the database
    feature_subset = [[0, 'X', 0, 'X', 0, 1]] # Matches: [0, 1, 0, 0, 0, 1], [0, 0, 0, 0, 0, 1],
    grover_iterations = None  # None for optimal, or set a specific int
    g = 2

    feature_mats = get_data()

    for id_fm, feature_mat in enumerate(feature_mats):
        n_items = len(feature_mat)
        num_id_qubits = int(np.log2(n_items))
        num_db_feature_qubits = len(feature_mat[0])
        feature_qubits = list(range(num_id_qubits, num_id_qubits + num_db_feature_qubits))

        # --- BUILD CIRCUIT ---
        qrs_circ = qrs_knn_grover.qrs(
            n_items=n_items,
            feature_mat=feature_mat,
            user_vector=user_feature,
            feature_subset=feature_subset,
            g=g,
            plot_circ=False,
            plot_histogram=False,
            grover_iterations=grover_iterations,  # None lets Qiskit calculate the optimal amount
            file_writer = writer
        )

        # print("Transpiling...")
        instr_mat = brickwork_transpiler.transpile(qrs_circ, routing_method='sabre', layout_method='sabre',
                                                   return_mat=True, file_writer=writer)

        writer.set("transpiled_depth", len(instr_mat[0]))
        writer.set("original_depth", qrs_circ.depth())
        writer.flush()


def experiment_qrs_no_db_one_match_duplicates():
    filename = "experiment_qrs_no_db_one_match_duplicates.csv"
    writer = get_writer(filename)

    user_feature = [0, 1, 0, 0, 0, 1]  # not in the database
    feature_subset =  [[1, 0, 0, 1, 1, 0]]
    grover_iterations = None  # None for optimal, or set a specific int
    g = 3 #placeholder

    feature_mats = get_data()

    for id_fm, feature_mat in enumerate(feature_mats):
        n_items = len(feature_mat)
        num_id_qubits = int(np.log2(n_items))
        num_db_feature_qubits = len(feature_mat[0])
        feature_qubits = list(range(num_id_qubits, num_id_qubits + num_db_feature_qubits))

        # --- BUILD CIRCUIT ---
        qrs_circ = qrs_knn_grover.qrs(
            n_items=n_items,
            feature_mat=feature_mat,
            user_vector=user_feature,
            feature_subset=feature_subset,
            g=g,
            plot_circ=False,
            plot_histogram=False,
            grover_iterations=grover_iterations,  # None lets Qiskit calculate the optimal amount
            file_writer=writer
        )

        # print("Transpiling...")
        instr_mat = brickwork_transpiler.transpile(qrs_circ, routing_method='sabre', layout_method='sabre',
                                                   return_mat=True, file_writer=writer)

        writer.set("transpiled_depth", len(instr_mat[0]))
        writer.set("original_depth", qrs_circ.depth())
        writer.flush()
