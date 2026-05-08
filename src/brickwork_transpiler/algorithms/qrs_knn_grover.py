from matplotlib import pyplot as plt
from qiskit import QuantumCircuit, QuantumRegister
from qiskit.circuit.library import MCXGate
from qiskit_algorithms import AmplificationProblem, Grover
import numpy as np

# This implementation follows the quantum recommendation system as presented by Sawerwain and Wroblewski (2019)
# Link: https://sciendo.com/article/10.2478/amcs-2019-0011


def _make_sampler(shots: int):
    """Create the Qiskit 2.x/Aer SamplerV2 used by Grover."""
    try:
        from qiskit_aer.primitives import SamplerV2
    except ImportError as exc:
        raise ImportError(
            "QRS Grover simulation requires `qiskit-aer>=0.17`. Install the "
            'optional stack with `pip install -e ".[qrs]"`.'
        ) from exc
    return SamplerV2(default_shots=shots)


def qrs(n_items, feature_mat, user_vector, feature_subset, g, plot_circ=False, plot_histogram=False,
        grover_iterations=None, file_writer=None):

    num_id_qubits = int(np.log2(n_items))
    num_db_feature_qubits = len(feature_mat[0])
    num_user_qubits = len(user_vector)

    # --- 0) basic checks ---
    if n_items & (n_items - 1) != 0:
        raise ValueError("n_items must be a power of two")
    if any(len(row) != num_db_feature_qubits for row in feature_mat):
        raise ValueError("All rows of feature_mat must have length l")

    total_qubits = num_id_qubits + num_db_feature_qubits + num_user_qubits

    # define registers
    id_qubits         = list(range(num_id_qubits))               # index qubits (0..q-1)
    feature_qubits = list(range(num_id_qubits, num_id_qubits + num_db_feature_qubits))        # feature qubits (q..q+l-1)
    user_qubits       = list(range(num_id_qubits + num_db_feature_qubits, total_qubits))  # user bits (q+l..end)

    # total_qubits = q index + l database features + len(user_vector)
    qc = QuantumCircuit(total_qubits)
    # qc = QuantumCircuit(total_qubits, num_db_feature_qubits)

    # print("Running database initialisation...")
    qrs_init = initialise_database(qc, id_qubits, feature_qubits, user_qubits, user_vector, feature_mat)

    # print("Running Q-KNN...")
    qrs_knn = knn(qrs_init, feature_qubits, user_qubits)

    if grover_iterations != 0:

        qA = qc.qregs[-1][0] if qc.qregs and qc.qregs[-1].name == 'qA' else None
        if qA is None:
            grov = QuantumRegister(1, "qA")
            qc.add_register(grov)
            qA = grov[0]
        qc.x(qA); qc.h(qA)

        # print("Running Grover...")
        qrs_amplified = amplify_recommendations(qrs_knn, feature_qubits, user_qubits, user_vector, len(feature_mat), g,
                                                feature_subset, plot=plot_histogram, iterations=grover_iterations,
                                                file_writer=file_writer)

    else:
        print("No amplification")
        qrs_amplified = qrs_knn

    # Build and draw the circuit
    if plot_circ:
        print("Plotting circuit...")
        qrs_amplified.decompose(reps=3)
        qrs_amplified.draw(output='mpl',
                           fold=40,
                           style="iqp")
        plt.savefig(f"images/qrs/recommendation_circ_grover_iters{grover_iterations}.png", dpi=300, bbox_inches="tight")
        plt.show()

    return qrs_amplified


def initialise_database(qc: QuantumCircuit,
                        id_qubits: [],
                        feature_qubits: [],
                        user_qubits: [],
                        user_vector: [],
                        feature_mat: list[list[int]],) -> QuantumCircuit:
    """
    Creates a circuit that loads a database of size n_items=2^q with l-bit feature_vecs,
    plus appends a user_vector. Uses a full lookup via multi-controlled Xs (MCX).
    """


    # --- 1) uniform superposition on index register ---
    for qb in id_qubits:
        qc.h(qb)

    # --- 2) database load via MCX (full lookup) ---
    for i, bits in enumerate(feature_mat):
        # Build the q-bit binary string for i, then reverse it so that
        # pattern[0] is the LSB, pattern[q-1] is the MSB.
        pattern = format(i, f"0{len(id_qubits)}b")   # MSB..LSB
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
                qc.append(MCXGate(len(id_qubits)), id_qubits + [feature_qubits[j]])

        for k, b in enumerate(pattern):
            if b == '0':
                qc.x(id_qubits[k])

    # -- 3) Encode user vector
    for idx, bit in enumerate(user_vector):
        if bit == 1:
            qc.x(user_qubits[idx])


    return qc


# def knn(
#     qc: QuantumCircuit,
#     feature_qubits: list[int],
#     user_qubits:    list[int]
# ) -> QuantumCircuit:
#     """
#     In-place QkNN Hamming-distance & phase-sum:
#       - feature_qubits[i] holds the i-th database feature bit
#       - user_qubits[i]    holds the i-th user-vector bit
#     After this, the ancilla 'c0' carries amplitudes ∝ cos(π/(2l)·d).
#     """
#     l = len(feature_qubits)
#     if l != len(user_qubits):
#         raise ValueError("feature_qubits and user_qubits must have the same length")
#
#     # 1) Add single ancilla c0 for the phase-sum
#     c0 = QuantumRegister(1, name="c0")
#     qc.add_register(c0)
#
#     qc.h(c0)  # put c0 into |+> = (|0>+|1>)/√2
#
#
#     return qc


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
    c0 = QuantumRegister(1, name="c0")
    qc.add_register(c0)

    qc.h(c0)  # put c0 into |+> = (|0>+|1>)/√2

    for i in range(l):
        qc.cx(user_qubits[(l-1) - i], feature_qubits[i])

    # for u_q, f_q in zip(user_qubits, feature_qubits):
    #     qc.cx(u_q, f_q)

    # 3) Phase-sum those l distance bits onto c0

    for f in feature_qubits:
        # (a) P2: deposit a phase e^{+i π/l} on (f=1, c0=0)
        qc.cp(+np.pi / l, f, c0)

        # (b) P1: single-qubit phase e^{-i π/(2l)} on (f=1)
        qc.p(-np.pi / (2 * l), f)

    qc.h(c0)

    #  Uncompute QKNN -- for single pattern amp
    for i in range(l):
        qc.cx(user_qubits[(l - 1) - i], feature_qubits[i])

    return qc



def amplify_recommendations(qc: QuantumCircuit,
                            feature_qubits: list[int],
                            user_qubits: list[int],
                            user_feature: [],
                            L: int,
                            g,
                            feature_subset: [[]],
                            shots: int = 2048,
                            plot: bool = False,
                            plot_circ_grover: bool = False,
                            iterations=None,
                            file_writer=None,
                            circ_only: bool = False,
                            ) -> QuantumCircuit:


    # --- FLAG QUBIT: detection by register name ---
    flag_reg = [reg for reg in qc.qregs if reg.name == "c0"]
    assert len(flag_reg) == 1, "Flag register 'c0' not found or ambiguous!"
    flag_qubit = qc.find_bit(flag_reg[0][0]).index  # The only qubit in c0

    oracle_subset = multi_subset_oracle(feature_qubits, feature_subset, flag_qubit, qc.num_qubits)

    # Usage when defining your AmplificationProblem:
    problem = AmplificationProblem(
        oracle=oracle_subset,
        state_preparation=qc,
        is_good_state=create_is_good_state(feature_qubits, user_feature)
    )

    # Optimal iterations Grover Nielsen, Chuang (2010)
    # N = 2 ** len(feature_qubits)
    # M = 2 ** feature_subset[0].count('X')
    # optimal_iterations = int(np.floor(np.pi / 4 * np.sqrt(N / M)))

    # Guessing the optimal number g of iterations according to Sawerwain and Wroblewski (2019)
    # count_X = lambda pattern: sum(1 for x in pattern if x == 'X')
    # g = 2**count_X(feature_subset)

    optimal_iterations = iterations

    if g is None:
        optimal_iterations = 0
        iterations = None

    if iterations is None and optimal_iterations != 0:
        # g = 1 # Perfect example case
        optimal_iterations = int(np.floor(np.pi / 4 * np.sqrt(L / g)))

    # --- RUN GROVER ---
    sampler = _make_sampler(shots)
    grover = Grover(sampler=sampler, iterations=optimal_iterations)

    print("Simulating circuit...")
    result = grover.amplify(problem)
    iterations_used = result.iterations[0] # For set pre-calculated iterations the list has 1 item

    if len(result.iterations) > 1:
        raise ValueError("Iterations list contained more than one value")

    grover_opt = Grover(sampler=sampler, iterations=optimal_iterations)
    if file_writer:
        file_writer.set("L", L)
        file_writer.set("g", g)
        file_writer.set("num_iterations", optimal_iterations)
        print(f"num of iterations: {optimal_iterations}")

    circuit = grover_opt.construct_circuit(problem)#.decompose(reps=2) # for non-unitary rectangle amplification

    if circ_only:
        return circuit

    if plot_circ_grover:
        print("Plotting amplification circuit...")
        circuit.draw(output='mpl',
                           fold=40,
                           style="iqp")
        plt.savefig(f"images/qrs/amp_part_recommendation_circ_iters{iterations_used}.png", dpi=300, bbox_inches="tight")
        plt.show()

    # Get the raw list of histograms (one dict per executed circuit)
    raw_list = result.circuit_results

    # Turn it into a single plain dict of counts
    if not raw_list:
        raise ValueError("No circuit results found in GroverResult")
    elif len(raw_list) == 1 and isinstance(raw_list[0], dict):
        counts = raw_list[0]  # the one histogram you want
    else:
        # If there are multiple runs, merge their histograms
        counts = {}
        for entry in raw_list:
            if not isinstance(entry, dict):
                continue
            for bitstr, c in entry.items():
                counts[bitstr] = counts.get(bitstr, 0) + c


    filtered = {}
    for bitstring, shots in counts.items():
        # 1) pull out the flag qubit value:
        flag_bit = bitstring[-1 - flag_qubit]
        if flag_bit != '0':
            continue

        # 2) extract only the feature bits, in MSB→LSB order:
        feat_bits = ''.join(
            bitstring[-1 - q]
            for q in sorted(feature_qubits)
        )

        # 3) tally
        filtered[feat_bits] = filtered.get(feat_bits, 0) + shots

    # filtered now has just the post-selected counts.
    # --- PLOT ---
    if plot:
        if filtered:
            sorted_bits = sorted(filtered)
            sorted_counts = [filtered[b] for b in sorted_bits]
            total = sum(sorted_counts)
            user_bits = ''.join(map(str, user_feature))
            xticks = []
            for b in sorted_bits:
                hd = sum(c != u for c, u in zip(b, user_bits))
                xticks.append(f"{b} (HD={hd})")
            probs = [100 * v / total for v in sorted_counts]
            plt.figure(figsize=(10, 5))
            plt.bar(range(len(probs)), probs)
            plt.xticks(range(len(probs)), xticks, rotation=45, ha='right')
            plt.title(f"Grover x{iterations_used} | User: {user_feature}")
            plt.ylabel("Probability (%)")
            plt.tight_layout()
            plt.savefig(f"images/plots/qrs_single_match_iter{iterations_used}.png", dpi=300,
                        bbox_inches="tight")
            plt.show()
        else:
            print("No 'good' states detected in the results.")


    return circuit


# Wrapper to match the required signature of Grover's AmplificationProblem
def create_is_good_state(feature_qubits, user_feature):
    def is_good_state(bitstring):
        feat = ''.join(bitstring[-1 - q] for q in sorted(feature_qubits))
        for f_bit, u_bit in zip(feat, user_feature):
            if u_bit == 'X':
                continue
            if f_bit != str(u_bit):
                return False
        return True

    return is_good_state


def multi_subset_oracle(feature_qubits, subsets, flag_qubit, total_qubits):

    oracle = QuantumCircuit(total_qubits)
    for subset in subsets:
        sub_oracle = QuantumCircuit(total_qubits)
        active_controls = []
        for q, bit in zip(feature_qubits, subset):
            if bit == 'X':
                continue
            if bit == 0:
                sub_oracle.x(q)
            active_controls.append(q)

        # Pick the correct control gate
        if len(active_controls) == 0:
            # All 'X': just flip the flag_qubit
            sub_oracle.x(flag_qubit)
        elif len(active_controls) == 1:
            # Only one control: use cx
            sub_oracle.cx(active_controls[0], flag_qubit)
        else:
            # Standard: multiple controls
            sub_oracle.mcx(active_controls, flag_qubit)

        # Undo the Xs
        for q, bit in zip(feature_qubits, subset):
            if bit == 'X':
                continue
            if bit == 0:
                sub_oracle.x(q)
        oracle.compose(sub_oracle, inplace=True)

    return oracle
