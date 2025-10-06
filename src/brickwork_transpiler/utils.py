import math
import itertools
from qiskit import QuantumCircuit
import csv
import os
from qiskit.quantum_info import Statevector
from qiskit.circuit.library import PermutationGate
import numpy as np


def assert_equal_up_to_global_phase(state1, state2, tol=1e-6):
    """
    Assert that two quantum state vectors are equal up to global phase.
    I've got 99 problems but global phase aint one

    Parameters:
    - state1, state2: iterable of complex numbers (e.g., output of a simulator)
    - tol: numerical tolerance for isclose()

    Raises:
    - AssertionError with diagnostic info if the assertion fails.
    """
    state1 = np.array(state1, dtype=complex)
    state2 = np.array(state2, dtype=complex)

    # Normalize (just in case)
    norm1 = np.linalg.norm(state1)
    norm2 = np.linalg.norm(state2)

    if np.isclose(norm1, 0.0, atol=tol) or np.isclose(norm2, 0.0, atol=tol):
        raise AssertionError(f"One of the states' norms is zero (cannot compare)")

    state1 /= norm1
    state2 /= norm2

    inner_product = np.vdot(state1, state2)
    magnitude = np.abs(inner_product)

    if not np.isclose(magnitude, 1.0, atol=tol, rtol=0.0):  # added rtol for border checking
        raise AssertionError(
            f"States are not equal up to global phase.\n"
            f"Inner product: {inner_product}\n"
            f"Absolute value: {magnitude:.6f} (should be close to 1)"
        )

    else:
        return True


def permute_qubits(circ: QuantumCircuit, perm: list[int]) -> QuantumCircuit:
    n = circ.num_qubits
    if sorted(perm) != list(range(n)):
        raise ValueError("perm must be a rearrangement of 0..n-1")

    new_circ = QuantumCircuit(n, circ.num_clbits)
    old_to_new = {
        old: new_circ.qubits[perm[idx]]
        for idx, old in enumerate(circ.qubits)
    }
    clbit_map = {old: new for old, new in zip(circ.clbits, new_circ.clbits)}

    for instr, qargs, cargs in circ.data:
        new_qargs = [old_to_new[q] for q in qargs]
        new_cargs = [clbit_map[c] for c in cargs]
        new_circ.append(instr, new_qargs, new_cargs)

    return new_circ


def index_to_coordinates(index: int, num_cols: int) -> tuple[int, int]:
    """
    Maps a linear node index to (row, column) assuming row-major layout.

    Parameters:
    - index: int – Node index in flat list
    - num_cols: int – Number of columns (time steps)

    Returns:
    - (row, column): tuple[int, int]
    """
    row = index // num_cols
    column = index % num_cols
    return (row, column)


def map_indices_to_coordinates(indices: list[int], num_cols: int) -> dict[int, tuple[int, int]]:
    """
    Maps list of node indices to (row, column) tuples.

    Parameters:
    - indices: list[int] – Flat node indices
    - num_cols: int – Number of columns (time steps)

    Returns:
    - Dictionary of index → (row, column)
    """
    return {i: index_to_coordinates(i, num_cols) for i in indices}


# Returns a list with qubit entries to be permuted when compared with qiskit reference outputs
def get_qubit_entries(bw_pattern):
    if bw_pattern is None:
        raise AssertionError("bw_pattern is None")

    qubit_entries = [t[0] for t in bw_pattern.output_nodes]
    return qubit_entries


def get_qiskit_permutation(bw_pattern):
    if bw_pattern is None:
        raise AssertionError("bw_pattern is None")

    qubit_entries = [t[0] for t in bw_pattern.output_nodes]

    # reverse the Graphix list to go from big-endian → little-endian
    qubit_entries.reverse()
    # entries_le == [1, 4, 0, 3, 2]

    # invert it: for each Qiskit qubit j, find its position in list
    perm = [qubit_entries.index(j) for j in range(len(qubit_entries))]
    return perm


# def _final_p2v(qc_virtual, qc_transpiled):
#     layraw = getattr(qc_transpiled, "layout", None)
#     n = qc_virtual.num_qubits
#     if layraw is None:
#         return {p: p for p in range(n)}
#
#     # Prefer final_layout, else initial_layout; else TranspileLayout accessors
#     lay = None
#     if hasattr(layraw, "final_layout") and layraw.final_layout is not None:
#         lay = layraw.final_layout
#     elif hasattr(layraw, "initial_layout") and layraw.initial_layout is not None:
#         lay = layraw.initial_layout
#
#     if lay is not None:
#         p2v = {}
#         for v, q in enumerate(qc_virtual.qubits):
#             phys = lay[q]
#             p = getattr(phys, "index", int(phys))
#             p2v[p] = v
#         return p2v
#
#     if hasattr(layraw, "get_virtual_bits"):
#         vb = layraw.get_virtual_bits()  # {virtual Qubit -> PhysicalQubit}
#         p2v = {}
#         for v, q in enumerate(qc_virtual.qubits):
#             phys = vb[q]
#             p = getattr(phys, "index", int(phys))
#             p2v[p] = v
#         return p2v
#
#     return {p: p for p in range(n)}

# def _pos2wire_from_tn_or_pattern(tn, bw_pattern):
#     # Try simulator metadata first (names differ across libs)
#     for attr in ("output_wires", "out_labels", "outputs", "order", "out_wires"):
#         if hasattr(tn, attr):
#             seq = list(getattr(tn, attr))
#             try:
#                 return [int(x) for x in seq]
#             except Exception:
#                 return seq
#     # Fallback: brickwork pattern as-listed (no reversing here)
#     return [w for (w, _) in bw_pattern.output_nodes]

# def _swap_net_for_perm(n, perm):
#     # Build a SWAP-only circuit s.t. virtual qubit k -> axis position perm[k]
#     qc = QuantumCircuit(n)
#     cur = list(range(n))  # which virtual label sits at position i
#     for i in range(n):
#         target_label = next(k for k, p in enumerate(perm) if p == i)
#         j = cur.index(target_label)
#         if j != i:
#             qc.swap(i, j)
#             cur[i], cur[j] = cur[j], cur[i]
#     return qc
#
# def _overlap(a, b):
#     a = np.asarray(a, complex); b = np.asarray(b, complex)
#     a /= np.linalg.norm(a); b /= np.linalg.norm(b)
#     return np.vdot(a, b)

# def reference_state_auto(bw_pattern, qc_virtual, input_vec, qc_transpiled, tn,
#                          verbose=True, brute_threshold=0.999, brute_max_n=8):
#     n = qc_virtual.num_qubits
#
#     # (A) position->wire from simulator (preferred) or pattern
#     pos2wire = _pos2wire_from_tn_or_pattern(tn, bw_pattern)
#
#     # (B) physical->virtual from *final* layout
#     p2v = _final_p2v(qc_virtual, qc_transpiled)
#
#     # Candidate lists of wires (axis positions 0..n-1 → physical wire)
#     cand_pos2wire = []
#     def add_cand(tag, order):
#         cand_pos2wire.append((tag, order))
#
#     add_cand("tn", pos2wire)
#     add_cand("tn_rev", list(reversed(pos2wire)))
#     # Try pattern-derived variants too (some backends ignore pattern ordering)
#     pat_wires = [w for (w, _) in bw_pattern.output_nodes]
#     add_cand("pat_raw", pat_wires)
#     add_cand("pat_rev", list(reversed(pat_wires)))
#     add_cand("pat_sorted", sorted(pat_wires))
#
#     # Deduplicate
#     seen = set(); uniq = []
#     for tag, o in cand_pos2wire:
#         t = tuple(o)
#         if t not in seen:
#             uniq.append((tag, list(o))); seen.add(t)
#
#     if verbose:
#         print("\n[REFAUTO] pos2wire candidates:")
#         for tag, o in uniq:
#             print(f"  {tag:>10}: {o}")
#         print("[REFAUTO] p2v(final):", p2v)
#
#     # Evaluate candidates; choose the best
#     base = input_vec.evolve(qc_virtual).data
#     best = ("<none>", None, -1.0, 0j)  # (tag, perm, |ip|, ip)
#     for tag, pos2w in uniq:
#         virt_order = [p2v.get(w, w) for w in pos2w]  # axis pos -> virtual idx
#         # perm[k] = axis position of virtual qubit k
#         perm = [virt_order.index(k) for k in range(n)]
#         swap_net = _swap_net_for_perm(n, perm)
#         ref = input_vec.evolve(qc_virtual).evolve(swap_net).data
#         ip = _overlap(tn.to_statevector(), ref)
#         mag = abs(ip)
#         if verbose:
#             print(f"[REFAUTO] overlap {tag:>10}: {ip}  |.|={mag:.6f}  perm={perm}")
#         if mag > best[2]:
#             best = (tag, perm, mag, ip)
#
#     # If not good enough, brute-force for small n
#     if best[2] < brute_threshold and n <= brute_max_n:
#         if verbose:
#             print(f"[REFAUTO] brute-forcing (n={n}) ...")
#         best_ip = None; best_perm = None; best_mag = -1.0
#         for perm in itertools.permutations(range(n)):
#             swap_net = _swap_net_for_perm(n, list(perm))
#             ref = input_vec.evolve(qc_virtual).evolve(swap_net).data
#             ip = _overlap(tn.to_statevector(), ref)
#             mag = abs(ip)
#             if mag > best_mag:
#                 best_mag, best_perm, best_ip = mag, list(perm), ip
#         if verbose:
#             print(f"[REFAUTO] brute best: perm={best_perm}  ip={best_ip}  |.|={best_mag:.6f}")
#         if best_mag > best[2]:
#             best = ("brute", best_perm, best_mag, best_ip)
#
#     # Build final reference with the chosen permutation
#     chosen_perm = best[1]
#     swap_net = _swap_net_for_perm(n, chosen_perm)
#     ref = input_vec.evolve(qc_virtual).evolve(swap_net)
#
#     if verbose:
#         print(f"[REFAUTO] chosen tag={best[0]}, perm={chosen_perm}, |ip|={best[2]:.6f}, ip={best[3]}")
#     return ref



def calculate_ref_state_from_qiskit_circuit(bw_pattern, qc, transpiled_qc,
                                            input_vector):
    if bw_pattern is None:
        raise AssertionError("bw_pattern is None")

    # Extend input vector based on ancillae
    extended_input_vector = pad_with_plus_for_transpiled(input_vector=input_vector, qc=qc, transpiled_qc=transpiled_qc)

    print("EVEQWEVQWEQWE: ", extended_input_vector.dim)

    qubit_entries = [t[0] for t in bw_pattern.output_nodes]

    # reverse the Graphix list to go from big-endian → little-endian
    qubit_entries.reverse()
    # entries_le == [1, 4, 0, 3, 2]

    # invert it: for each Qiskit qubit j, find its position in list
    perm = [qubit_entries.index(j) for j in range(len(qubit_entries))]

    qc_perm = permute_qubits(transpiled_qc, perm=perm)
    return extended_input_vector.evolve(qc_perm)



def pad_with_plus_for_transpiled(input_vector, qc, transpiled_qc):
    """
    Args:
        input_vector: Statevector for qc (e.g., Statevector.from_label('++'))
        qc: original circuit
        transpiled_qc: transpiled circuit

    Returns: Input vector that matches the new circuit width with ancillae

    """
    n_in = qc.num_qubits
    n_tr = transpiled_qc.num_qubits
    if n_tr < n_in:
        raise ValueError(f"Transpiled circuit has fewer qubits ({n_tr}) than original ({n_in}).")
    k = n_tr - n_in
    if k == 0:
        return input_vector  # already matches
    anc = Statevector.from_label('+' * k)
    # Place ancillas on higher indices to match usual transpiler behavior.
    return anc.expand(input_vector)  # == (|+>^{⊗k}) ⊗ input_vector



def feature_to_generator(feature_mat):
    """
    Given feature_mat: list of N rows (each a list of l bits),
    returns an l x q generator matrix G (as a list of l lists of length q)
    satisfying f(i) = G @ i mod 2 for all i in 0..N-1,
    or raises ValueError if feature_mat is not a linear code.
    """
    # 1) Dimensions
    N = len(feature_mat)
    if N == 0:
        raise ValueError("feature_mat must have at least one row")
    l = len(feature_mat[0])
    if any(len(row) != l for row in feature_mat):
        raise ValueError("All rows of feature_mat must have the same length l")

    # 2) Check N = 2^q
    if N & (N - 1) != 0:
        raise ValueError(f"N = {N} is not a power of 2")
    q = N.bit_length() - 1

    # 3) Build G by sampling f(e_k) for k=0..q-1
    #    e_k has index = (1 << k)
    basis_indices = [1 << k for k in range(q)]
    # G[j][k] = j-th bit of f(2^k)
    G = [[feature_mat[i][j] for i in basis_indices] for j in range(l)]

    # 4) Verify that f(i) == G @ i mod 2 for all i
    for i in range(N):
        # get binary expansion of i: bits[k]
        bits = [(i >> k) & 1 for k in range(q)]
        # compute G·bits mod2
        f_lin = [sum(G[j][k] * bits[k] for k in range(q)) & 1
                 for j in range(l)]
        if f_lin != feature_mat[i]:
            raise ValueError(f"feature_mat is not linear: "
                             f"mismatch at i={i}: "
                             f"expected {feature_mat[i]}, got {f_lin}")

    return G


class BufferedCSVWriter:
    def __init__(self, filename, headers):
        self.filename = filename
        self.headers = headers
        self.row = {}  # Current row buffer
        # Write header if file doesn't exist
        if not os.path.exists(filename):
            with open(filename, mode='w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()

    def set(self, key, value):
        self.row[key] = value

    def flush(self):
        # Write current row (can be partial), then clear buffer
        with open(self.filename, mode='a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.headers, restval="")
            writer.writerow(self.row)
        self.row = {}




# def calculate_ref_state_from_qiskit_circuit2424(
#     bw_pattern,
#     qc_in,
#     transpiled_qc,
#     input_vector,
#     *,
#     align_graphix_to_qiskit: bool = True,
#     ancilla_init: str = "0",   # if transpiled has extra qubits, append |0>... by default
# ):
#     """
#     Build a reference state that matches the ordering of your Graphix pipeline
#     *after* you undo SABRE on the Graphix state (i.e., **pre-route physical** order).
#
#     Steps:
#       (i)  Optionally realign Graphix big-endian qubit labels to Qiskit logical indices.
#       (ii) Apply qc_in to the provided input_vector (same input as Graphix uses).
#       (iii) Permute logical j -> pre-route physical p0 using initial_layout via a PermutationGate.
#
#     Returns
#     -------
#     Statevector
#         Qiskit Statevector ordered by **pre-route physical wires** p0 = 0..N-1.
#     """
#
#     if bw_pattern is None:
#         raise AssertionError("bw_pattern is None")
#
#     # ---------------- (i) Graphix → Qiskit logical alignment ----------------
#     qc_used = qc_in
#     if align_graphix_to_qiskit:
#         # Graphix gives output_nodes in big-endian. Reverse to little-endian.
#         qubit_entries = [t[0] for t in bw_pattern.output_nodes]
#         qubit_entries.reverse()  # Graphix big-endian → little-endian
#
#         # Build a permutation 'perm' so that for each Qiskit qubit j,
#         # perm[j] = its position in Graphix's little-endian list.
#         # Example: entries_le = [1,4,0,3,2] -> perm = [2,0,4,3,1]
#         perm = [qubit_entries.index(j) for j in range(len(qubit_entries))]
#
#         # Your helper that reindexes the circuit's qubits:
#         qc_used = permute_qubits(qc_in, perm=perm)
#
#     # ---------------- (ii) Evolve the input state through the *original* circuit ----------------
#     # (input_vector is your |+++++>, |000..>, or any state you choose)
#     ref_state_logical = input_vector.evolve(qc_used)
#
#     # ---------------- (optional) pad with ancillas if transpiled has more qubits ---------------
#     L = qc_used.num_qubits
#     N = transpiled_qc.num_qubits
#     if N < L:
#         raise ValueError(f"Transpiled circuit has {N} qubits, but qc_in has {L}.")
#     if N > L:
#         # Append |ancilla_init>^(N-L) on the *most significant* qubits (Qiskit convention)
#         anc = Statevector.from_label(ancilla_init * (N - L))
#         ref_state_logical = anc.tensor(ref_state_logical)  # ancillas on the left (higher wires)
#
#     # ---------------- (iii) logical → pre-route physical with initial_layout -------------------
#     layout = getattr(transpiled_qc, "layout", None)
#     if layout is None or getattr(layout, "initial_layout", None) is None:
#         # No layout info: nothing to reorder beyond logical
#         return ref_state_logical
#
#     init = layout.initial_layout  # virtual (logical qubit object) -> pre-route physical index p0
#
#     # Build pre[j] = p0 for each logical j in qc_used order.
#     # We rely on the qubit *objects* to access initial_layout robustly.
#     try:
#         pre = [init[q] for q in qc_used.qubits]  # p0 for each logical j
#     except Exception as ex:
#         raise RuntimeError("Unable to read initial_layout consistently.") from ex
#
#     # PermutationGate expects "perm[i] = j means move qubit i to position j".
#     # We want logical j → pre-route physical p0.
#     perm_j_to_p0 = list(range(N))
#     for j, p0 in enumerate(pre):
#         perm_j_to_p0[j] = p0
#
#     # For any extra (ancilla) logical positions j>=L (if any), fill remaining slots bijectively
#     if N > L:
#         used = set(pre)
#         remaining_positions = [p for p in range(N) if p not in used]
#         for offset, j in enumerate(range(L, N)):
#             perm_j_to_p0[j] = remaining_positions[offset]
#
#     # Sanity: must be a permutation of 0..N-1
#     if sorted(perm_j_to_p0) != list(range(N)):
#         raise ValueError(f"Invalid logical→pre-route mapping: {perm_j_to_p0}")
#
#     # Apply the permutation in *qubit index* space; PermutationGate handles little-endian internally.
#     ref_state_preroute_physical = ref_state_logical.evolve(PermutationGate(perm_j_to_p0))
#     return ref_state_preroute_physical

#
# # 1) Logical (qc_in order)  →  FINAL physical indices (after SABRE)
# def logical_to_final_physical(qc_in, transpiled_qc):
#     """
#     Returns L2P such that L2P[j] = FINAL physical index where logical qubit j ended up.
#     Uses: layout.input_qubit_mapping + layout.routing_permutation (if any).
#     """
#     layout = getattr(transpiled_qc, "layout", None)
#     if layout is None:
#         raise ValueError("transpiled_qc.layout is None")
#
#     # input_qubit_mapping: {Qubit_in -> int(initial_physical)}
#     if not hasattr(layout, "input_qubit_mapping") or layout.input_qubit_mapping is None:
#         raise ValueError("layout.input_qubit_mapping is missing")
#
#     # initial physical for each logical (in qc_in.qubits order)
#     pre = [layout.input_qubit_mapping[q] for q in qc_in.qubits]
#
#     # compose with routing permutation (initial_phys -> final_phys), if present
#     route = None
#     if hasattr(layout, "routing_permutation"):
#         try:
#             route = layout.routing_permutation()
#         except Exception:
#             route = None
#     if route:
#         route = list(route)
#         return [route[p] for p in pre]
#     return pre


# # 2) TN output axes  →  physical indices (no color maps needed)
# def axes_phys_from_tn_outputs(tn, bw_pattern=None):
#     """
#     Returns axes_phys such that axes_phys[k] = physical index represented by axis k
#     of tn.to_statevector().
#     Works with node labels that are ints or tuple-like (col, row, ...), or objects with .col/.column/.x.
#     """
#     seq = None
#     for obj, name in (
#         (tn, "default_output_nodes"),
#         (tn, "output_nodes"),
#         (tn, "output_indices"),
#         (tn, "output_qubits"),
#         (bw_pattern, "output_nodes"),
#     ):
#         if obj is not None and hasattr(obj, name):
#             try:
#                 s = list(getattr(obj, name))
#                 if s:
#                     seq = s
#                     break
#             except Exception:
#                 pass
#     if seq is None:
#         raise ValueError("Cannot find TN/pattern output nodes (default_output_nodes/output_nodes/...).")
#
#     def _col(node):
#         # attribute-based
#         for attr in ("col", "column", "x"):
#             if hasattr(node, attr):
#                 v = getattr(node, attr)
#                 if isinstance(v, (int, np.integer)):
#                     return int(v)
#         # tuple/list-based
#         if isinstance(node, (tuple, list)) and node and isinstance(node[0], (int, np.integer)):
#             return int(node[0])
#         # plain int
#         if isinstance(node, (int, np.integer)):
#             return int(node)
#         return None
#
#     cols = [_col(x) for x in seq]
#     if any(c is None for c in cols):
#         bad = next((x for x, c in zip(seq, cols) if c is None), None)
#         raise TypeError(f"Cannot interpret TN output node label {bad!r} → physical column index.")
#     return cols


# # 3) Permute the TN state from PHYSICAL → LOGICAL (only over the surviving outputs)
# def undo_sabre_on_tn_state(psi, L2P, axes_phys):
#     """
#     psi: 1D array or Statevector over N outputs (from tn.to_statevector()).
#     L2P[j] = final physical index of logical j (for the qubits that survive to outputs)
#     axes_phys[k] = physical index represented by axis k of psi
#
#     Returns Statevector whose axes are [logical-0, logical-1, ..., logical-(N-1)].
#     """
#     sv = psi if isinstance(psi, Statevector) else Statevector(np.asarray(psi, complex).ravel())
#     N = sv.num_qubits
#     if not (len(axes_phys) == N):
#         raise ValueError(f"axes_phys length {len(axes_phys)} != state qubits {N}.")
#
#     # If your pattern measured away some inputs, restrict L2P to the qubits that actually survive.
#     phys_set = set(axes_phys)
#     L2P_restricted = [p for p in L2P if p in phys_set]
#     if len(L2P_restricted) != N:
#         raise ValueError(
#             "Mismatch between TN outputs and logical qubits:\n"
#             f"- TN axes_phys (phys indices): {axes_phys}\n"
#             f"- Logical→Physical (all inputs): {L2P}\n"
#             "The pattern likely measured some inputs; build L2P only for surviving outputs."
#         )
#
#     # phys → logical
#     phys_to_log = {p: j for j, p in enumerate(L2P_restricted)}
#     # source axis k (phys p) → destination logical j
#     perm_axes_to_logical = [phys_to_log[p] for p in axes_phys]
#     return sv.evolve(PermutationGate(perm_axes_to_logical))



# def extract_logical_to_physical24(qc_in, qc_out):
#     """
#     Return l2p[j] = p1, where:
#       - j is the logical index (position of qc_in.qubits[j]),
#       - p1 is the *final* physical wire index in qc_out after routing.
#
#     This composes:
#         logical j --(initial_layout)--> pre-route physical p0
#         p0 --(routing_permutation)--> final physical p1
#     """
#     layout = getattr(qc_out, "layout", None)
#     if layout is None or getattr(layout, "initial_layout", None) is None:
#         # No layout -> identity on the common size
#         n = min(qc_in.num_qubits, qc_out.num_qubits)
#         return list(range(n))
#
#     init = layout.initial_layout  # virtual -> pre-route physical (accessible as init[q])
#     pre = [init[q] for q in qc_in.qubits]  # p0 for each logical j
#
#     try:
#         route = list(layout.routing_permutation())  # p0 -> p1
#     except Exception:
#         route = list(range(qc_out.num_qubits))
#
#     # logical j -> final physical p1
#     return [route[p0] for p0 in pre]



# def _invert_perm(pi):
#     """Return inverse permutation inv with inv[pi[i]] = i."""
#     inv = [None] * len(pi)
#     for i, j in enumerate(pi):
#         if j is None:
#             raise ValueError("Permutation contains None; cannot invert.")
#         inv[j] = i
#     if sorted(inv) != list(range(len(pi))):
#         raise ValueError(f"Invalid permutation to invert: {pi}")
#     return inv

# def undo_sabre_to_preroute_physical24(state, logical_to_physical, qc_in, qc_out, total_qubits=None):
#     """
#     Given `state` in the *final physical* wire order (i.e., from the transpiled circuit),
#     undo SABRE's routing permutation to obtain the state in the **pre-route physical**
#     order (the order given by `initial_layout`). This does NOT reorder to logical order.
#
#     Inputs:
#       - logical_to_physical: l2p[j] = p1 (final physical), as returned by extract_logical_to_physical.
#       - qc_in, qc_out: the original and transpiled circuits (for initial_layout and routing info).
#
#     Effect:
#       If r: p0 -> p1 is layout.routing_permutation(), this applies r^{-1},
#       i.e., PermutationGate with perm[p1] = p0.
#     """
#     # Normalize to Statevector
#     if isinstance(state, Statevector):
#         sv = state
#         N = sv.num_qubits
#     else:
#         arr = np.asarray(state, dtype=complex)
#         N = total_qubits if total_qubits is not None else int(round(math.log2(arr.size)))
#         sv = Statevector(arr, dims=[2]*N)
#
#     layout = getattr(qc_out, "layout", None)
#     if layout is None or getattr(layout, "initial_layout", None) is None:
#         # Nothing to undo
#         return sv
#
#     # 1) Pre-route physical indices for each logical j
#     init = layout.initial_layout
#     pre = [init[q] for q in qc_in.qubits]  # p0 for each logical j
#
#     # 2) If we can, take the full routing permutation from the layout.
#     #    This is robust (covers ancillas too).
#     try:
#         route = list(layout.routing_permutation())  # p0 -> p1
#         if len(route) != N:
#             # Defensive: if simulator/circuit has different width, trim/pad
#             route = route[:N] + list(range(len(route), N))
#     except Exception:
#         # 3) Reconstruct r from l2p and pre (works when no ancillas or all are unaffected)
#         if len(logical_to_physical) != N:
#             raise ValueError("Cannot reconstruct routing without full l2p and no routing_permutation available.")
#         route = [None] * N
#         for j, p1 in enumerate(logical_to_physical):
#             p0 = pre[j]
#             route[p0] = p1
#         # Fill any remaining holes by identity (best-effort, affects only unused wires)
#         for i in range(N):
#             if route[i] is None:
#                 route[i] = i
#
#     # 4) Undo SABRE: apply inverse routing r^{-1} with PermutationGate semantics perm[i]=j (“move i→j”)
#     route_inv = _invert_perm(route)  # route_inv[p1] = p0
#     perm = route_inv                # exactly the source->dest map we need
#
#     # Sanity
#     if sorted(perm) != list(range(N)):
#         raise ValueError(f"Invalid undo permutation {perm}")
#
#     return sv.evolve(PermutationGate(perm))



# def extract_physical_to_logical(qc_in, qc_out):
#     """
#     Returns a list `p2l` of length N = qc_out.num_qubits such that:
#       p2l[p] = j  means: physical output wire p holds logical qubit j (from qc_in).
#       p2l[p] = None if wire p does not correspond to a logical qubit from qc_in.
#     """
#     layout = getattr(qc_out, "layout", None)
#     if layout is None or getattr(layout, "initial_layout", None) is None:
#         # Identity fallback
#         N = qc_out.num_qubits
#         return list(range(min(qc_in.num_qubits, N))) + [None] * (N - qc_in.num_qubits)
#
#     init = layout.initial_layout  # virtual -> pre-route physical (typically)
#     # logical j -> pre-route physical p0
#     pre = [init[q] for q in qc_in.qubits]
#
#     # pre-route physical -> final physical
#     try:
#         route = list(layout.routing_permutation())
#     except Exception:
#         route = list(range(qc_out.num_qubits))
#
#     # logical j -> final physical p
#     l2p = [route[p0] for p0 in pre]
#
#     # Build full p2l of length N
#     N = qc_out.num_qubits
#     p2l = [None] * N
#     for j, p in enumerate(l2p):
#         p2l[p] = j
#     return p2l

# 2) Undo the layout on a statevector using the physical->logical map
def undo_layout_on_state(state, physical_to_logical, total_qubits=None):
    """
    Given a state in the transpiled circuit's *wire order* (physical ordering),
    return a Statevector re-ordered so that the original logical qubits
    (0,1,2,...) come first. `physical_to_logical[p] = j` says:
    "wire p carries logical j". We then set PermutationGate perm[p] = j.

    Any wires with physical_to_logical[p] is None are treated as ancillas and
    moved to positions L, L+1, ... after the logical block.
    """
    # Normalize input to a Statevector
    if isinstance(state, Statevector):
        sv = state
        N = sv.num_qubits
    else:
        arr = np.asarray(state, dtype=complex)
        N = total_qubits if total_qubits is not None else int(round(math.log2(arr.size)))
        sv = Statevector(arr, dims=[2] * N)

    if len(physical_to_logical) != N:
        raise ValueError(f"physical_to_logical has length {len(physical_to_logical)}, "
                         f"but state has {N} qubits. Provide a full-length map.")

    # Logical count L = number of non-None entries
    logical_positions = [(p, j) for p, j in enumerate(physical_to_logical) if j is not None]
    L = len(logical_positions)

    # Build source->dest permutation for PermutationGate
    perm = [None] * N
    for p, j in logical_positions:
        perm[p] = j
    anc_phys = [p for p, j in enumerate(physical_to_logical) if j is None]
    for k, p in enumerate(anc_phys):
        perm[p] = L + k

    # Validate permutation
    if sorted(perm) != list(range(N)):
        raise ValueError(f"Invalid permutation {perm} (must be a permutation of 0..{N-1}).")

    return sv.evolve(PermutationGate(perm))





# --- 1) Save the mapping (call this once, right after transpile) -----------------
def extract_logical_to_physical(qc_in, qc_out):
    """
    Returns a list `physical_to_logical` such that physical_to_logical[p]
    is the logical qubit index j that ended up on output wire p of qc_out.
    (I.e., index = physical, value = logical.)
    """
    def invert_permutation(pi):
        """Given pi[j] = p (logical->physical), return inv[p] = j (physical->logical)."""
        inv = [None] * len(pi)
        for j, p in enumerate(pi):
            inv[p] = j
        return inv

    layout = getattr(qc_out, "layout", None)
    print("layout", layout)

    if layout is not None and getattr(layout, "initial_layout", None) is not None:
        print("initial_layout", layout.initial_layout)
        init = layout.initial_layout  # bijection between virtual qubits and pre-route physical indices

        # Compute logical -> pre-route physical
        try:
            pre = [init[q] for q in qc_in.qubits]  # typical: init[virtual] -> physical
        except Exception:
            # Version-agnostic fallback: build logical->physical from whatever orientation init exposes
            # Try to get a dict {phys:int -> virt:Qubit}
            ptov = getattr(init, "get_virtual_bits", lambda: None)()
            if ptov is not None:
                logical_to_physical = [None] * qc_out.num_qubits
                for phys, virt in ptov.items():
                    logical_to_physical[virt.index] = phys
            else:
                # Final fallback: inspect items() and detect orientation by key type
                logical_to_physical = [None] * qc_out.num_qubits
                for k, v in init.items():
                    if isinstance(k, int):       # phys -> virt
                        phys, virt = k, v
                    else:                        # virt -> phys
                        phys, virt = v, k
                    logical_to_physical[virt.index] = phys
                # Invert at the end of the function
                return invert_permutation(logical_to_physical)

        # Apply routing permutation if present: pre-physical -> final-physical
        try:
            route = list(layout.routing_permutation())
        except Exception:
            route = list(range(qc_out.num_qubits))

        logical_to_physical = [route[p] for p in pre]

        # You want physical -> logical, so invert:
        physical_to_logical = invert_permutation(logical_to_physical)
        return physical_to_logical

    # Last resort: assume identity
    n = min(qc_in.num_qubits, qc_out.num_qubits)
    return list(range(n))
#


# def reorder_via_transpose(psi: np.ndarray) -> np.ndarray:
#     """
#     Swap MSB <-> LSB conventions in an n-qubit statevector.
#     Given a flat array `psi` of length 2**n, returns the same amplitudes
#     but with all indices bit-reversed.
#
#     This is equivalent to reshaping to (2,)*n, transposing axes [n-1,...,0],
#     then flattening, but uses an explicit, vectorized index mapping.
#     """
#     # 1) ensure a C-contiguous 1D array
#     psi = np.asarray(psi, order='C')
#     dim = psi.size
#
#     # 2) infer n and sanity-check
#     n = int(np.log2(dim))
#     if 2 ** n != dim:
#         raise ValueError(f"Length {dim} is not a power of 2; cannot infer n")
#
#     # 3) build an array of all indices [0,1,...,2**n-1]
#     idx = np.arange(dim, dtype=int)
#
#     # 4) bit-reverse each index in a vectorized way
#     rev = np.zeros_like(idx)
#     for bit in range(n):
#         rev = (rev << 1) | ((idx >> bit) & 1)
#
#     # 5) apply the permutation
#     return psi[rev]


# def reorder_via_transpose_n(psi: np.ndarray) -> np.ndarray:
#     """
#     Flip MSB↔LSB in an n-qubit statevector of length 2**n.
#     Works for n = 1,2,3,4,… as long as psi.size == 2**n.
#     """
#     psi = np.ascontiguousarray(psi)
#     dim = psi.size
#     n = int(np.log2(dim))
#     if 2 ** n != dim:
#         raise ValueError(f"Length {dim} is not a power of 2")
#
#     # view as an n-way tensor, each dim=2
#     psi_tensor = psi.reshape((2,) * n)
#     # reverse the axes
#     psi_t = psi_tensor.transpose(list(reversed(range(n))))
#     # flatten back
#     return psi_t.reshape(dim)
