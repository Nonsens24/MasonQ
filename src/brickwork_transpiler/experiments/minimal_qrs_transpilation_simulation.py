from matplotlib import pyplot as plt

from brickwork_transpiler import brickwork_transpiler, circuits, utils, visualiser
from brickwork_transpiler.bfk_encoder import encode_pattern
# from src.ubqc_brickwork_transpiler.utils import extract_logical_to_physical, undo_layout_on_state


def build_graph():

    experiment, _ = circuits.minimal_qrs()

    experiment.draw(output='mpl',
                    fold=30,
                    style="iqp"
                    )
    plt.savefig(f"images/Circuits/minimal_recommendation_circuit.png", dpi=300, bbox_inches="tight")
    plt.show()

    bw_pattern, col_map = brickwork_transpiler.transpile(experiment, routing_method='sabre', layout_method='trivial',
                                                         with_ancillas=False, plot_decomposed=True)

    visualiser.plot_brickwork_graph_from_pattern(bw_pattern,
                                                 show_angles=True,
                                                 node_colours=col_map,
                                                 use_node_colours=True,
                                                 title="Brickwork graph: Minimal QRS")

    file_path = "src/ubqc_brickwork_transpiler/experiments/data/output_data/"

    pattern_writer = utils.BufferedCSVWriter(file_path + "minimal_qrs_experiment_pattern.txt", ["pattern"])
    log_writer = utils.BufferedCSVWriter(file_path + "minimal_qrs_experiment_log.txt", ["log"])

    encoded_pattern, log_alice = encode_pattern(bw_pattern, return_metadata=True)
    pattern_writer.set("pattern", encoded_pattern.print_pattern(lim=2 ** 32))
    log_writer.set("log", log_alice)

    pattern_writer.flush()
    log_writer.flush()

    visualiser.plot_brickwork_graph_encrypted(encoded_pattern, use_locks=False,
                                              title="Brickwork Graph: Minimal QRS Encoded",
                                              show_angles=True)

    # Minimal runner: execute from given input statevector and plot filtered histogram

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit.circuit.library import Initialize

from brickwork_transpiler import circuits


def _default_aer_backend():
    """Return the modern Aer simulator backend used by this optional experiment."""
    try:
        from qiskit_aer import AerSimulator
    except ImportError as exc:
        raise ImportError(
            "The minimal QRS simulation requires `qiskit-aer`. Install it with "
            '`pip install -e ".[qrs]"` or `pip install qiskit-aer`.'
        ) from exc
    return AerSimulator()


_BACKEND = _default_aer_backend()


def run_and_plot_minimal_qrs_only_db(*,
                                     shots: int = 4096,
                                     db_qubits: list[int] | None = None,
                                     plot: bool = True,
                                     flip_plot_labels: bool = False,
                                     ) -> dict[str, int]:
    """
    Run minimal_qrs from its provided input statevector, measure ONLY c0 and db_qubits,
    post-select on c0 == '0', and print/plot the histogram over db_qubits only.

    Returns
    -------
    filtered : dict[str,int]
        Histogram over DB bits (as a bitstring) after post-selection on c0=0.
        (Rightmost printed bit corresponds to the *lowest* db_qubit index mapped to c[1].)
    """
    user_feature = [0, 0]
    # Build circuit + input state
    qc, input_state = circuits.minimal_qrs(user_feature)

    # Default DB subset if not provided (matches minimal_qrs definition)
    if db_qubits is None:
        db_qubits = [1, 2]

    # Prepare from the given Statevector
    init = Initialize(input_state.data)
    qc = qc.copy()
    qc.compose(init, qubits=qc.qubits, front=True, inplace=True)

    # Classical register: c[0] holds c0 (for post-selection), c[1:] hold DB bits
    m = 1 + len(db_qubits)
    cr = ClassicalRegister(m, "c")
    qc.add_register(cr)

    # Map qubits to classical bits:
    # - c0 (last quantum wire) -> c[0]  (rightmost)
    c0_idx = qc.num_qubits - 1
    qc.measure(c0_idx, cr[0])

    # - db_qubits -> c[1], c[2], ...
    #   (We map in ascending physical index for determinism.)
    for j, q in enumerate(sorted(db_qubits)):
        qc.measure(q, cr[1 + j])

    # Execute
    compiled = transpile(qc, _BACKEND, optimization_level=1)
    job = _BACKEND.run(compiled, shots=shots)
    result = job.result()
    counts = result.get_counts(compiled)  # dict: bitstring -> shots

    # --- Post-select on c0 == '0' and keep ONLY DB bits ---
    # Bitstrings are MSB..LSB; rightmost char corresponds to c[0] (our c0)
    def _sanitize(s: str) -> str:
        return s.replace(" ", "")

    counts = {_sanitize(k): int(v) for k, v in counts.items()}

    filtered: dict[str, int] = {}
    for bitstring, shots_ in counts.items():
        # c0 at rightmost position (c[0])
        if bitstring[-1] != '0':
            continue

        # DB bits occupy c[1..m-1]; take them in the same order we measured:
        # c[1] is next-to-rightmost, c[2] after that, etc.
        # Build a compact DB string (rightmost char = c[1]).
        db_bits = ''.join(bitstring[-1 - k] for k in range(1, m))
        filtered[db_bits] = filtered.get(db_bits, 0) + shots_

    # Print a small summary
    total_good = sum(filtered.values())
    print(f"Post-selected on c0=0 | good shots = {total_good}/{sum(counts.values())}")
    for b in sorted(filtered):
        print(f"{b}: {filtered[b]}")

    # --- Plot (DB-only) ---
    if plot:
        if filtered:
            xs = sorted(filtered)                     # canonical keys (whatever order you computed)
            ys = [filtered[b] for b in xs]
            tot = sum(ys)
            probs = [100.0 * y / tot for y in ys]

            # DISPLAY-ONLY: flip label bit order if you want MSB↔LSB swapped
            labels = [b[::-1] for b in xs] if flip_plot_labels else xs

            plt.figure(figsize=(7, 3.6))
            plt.bar(range(len(xs)), probs)
            plt.xticks(range(len(xs)), labels)        # use display labels, not xs
            plt.ylabel("Probability (%)")
            plt.title(f"Minimal QRS Results (post-selected c0=0) | feature: {user_feature}")
            plt.tight_layout()
            plt.savefig(f"images/plots/minimal_qrs_plot_{user_feature}.png", dpi=300,
                        bbox_inches="tight")
            plt.show()
        else:
            print("No shots survived post-selection (c0=0).")

    return filtered


import os
import numpy as np
import matplotlib.pyplot as plt
from qiskit.quantum_info import Statevector

def plot_conditional_from_vector(
    qc,
    transpiled_qc,
    vector,                     # Statevector OR flat numpy array (MBQC ψ)
    targets_logical=(2, 1),     # report these logical qubits (left→right in labels)
    ancilla="c0",               # "c0" to use the c0[0] register; or an int logical index
    save_path="images/plots/minimal_qrs.png",
    show=True
):
    """
    Uses your mapping + undo_layout_on_state to bring `vector` to LOGICAL order,
    computes P(targets | ancilla=0), and saves a bar chart.
    Returns (cond_dict, kept_mass, save_path).
    """
    # 1) mapping for THIS run (don't reuse across runs!)
    mapping = extract_logical_to_physical(qc, transpiled_qc)
    n = transpiled_qc.num_qubits

    # 2) logical state via your helper
    try:
        sv_log = undo_layout_on_state(vector, mapping, total_qubits=n)
    except TypeError:
        sv_log = undo_layout_on_state(vector, mapping)
    sv_log = Statevector(getattr(sv_log, "data", sv_log), dims=(2,)*n)

    # 3) choose ancilla logical index
    if isinstance(ancilla, int):
        anc_idx = ancilla
    elif isinstance(ancilla, str) and ancilla == "c0":
        # find c0[0] in the *original logical circuit*
        try:
            anc_idx = next(qc.qubits.index(reg[0]) for reg in qc.qregs if reg.name == "c0")
        except StopIteration:
            raise ValueError("No register named 'c0' found in qc.")
    else:
        raise ValueError("ancilla must be 'c0' or an integer logical index.")

    # 4) exact probabilities (logical, little-endian)
    p = sv_log.probabilities()
    idx = np.arange(1 << n, dtype=np.uint64)

    # 5) post-select ancilla = 0
    keep = ((idx >> anc_idx) & 1) == 0
    mass = float(p[keep].sum())
    if mass == 0.0:
        raise ValueError("Pr[ancilla=0] = 0 (picked the wrong ancilla?).")

    # 6) conditional over targets (in the order you asked for)
    t0, t1 = targets_logical
    b0 = ((idx >> t0) & 1)[keep]
    b1 = ((idx >> t1) & 1)[keep]
    w  = p[keep]

    def _sum(bit0, bit1):
        sel = (b0 == bit0) & (b1 == bit1)
        return float(w[sel].sum()) / mass

    cond = {"00": _sum(0,0), "01": _sum(0,1), "10": _sum(1,0), "11": _sum(1,1)}

    # 7) plot + save
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    labels = ["00","01","10","11"]
    heights = [cond[l] for l in labels]
    fig, ax = plt.subplots()
    ax.bar(labels, heights)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Probability")
    ax.set_title(f"P{targets_logical} | ancilla(q={anc_idx})=0  kept={mass:.3f}")
    for x, h in enumerate(heights):
        ax.text(x, h + 0.02, f"{h:.3f}", ha="center", va="bottom")
    fig.savefig(save_path, dpi=200, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)

    return cond, mass, save_path

import os
import numpy as np
import matplotlib.pyplot as plt
from qiskit.quantum_info import Statevector

# --- core helpers --------------------------------------------------------------
def _undo_to_logical(vector, mapping, total_qubits):
    """Use your helper to return a LOGICAL-order Statevector (q0 = LSB)."""
    try:
        sv_log = undo_layout_on_state(vector, mapping, total_qubits=total_qubits)
    except TypeError:
        sv_log = undo_layout_on_state(vector, mapping)
    return Statevector(getattr(sv_log, "data", sv_log), dims=(2,)*total_qubits)

def _probabilities(sv_log):
    p = sv_log.probabilities()
    n = int(np.log2(p.size))
    idx = np.arange(1 << n, dtype=np.uint64)
    return p, n, idx

def _cond_targets_given_anc0(p, n, idx, targets, ancilla):
    keep = ((idx >> ancilla) & 1) == 0
    mass = float(p[keep].sum())
    if mass == 0.0:
        raise RuntimeError("Pr[ancilla=0] = 0 for the chosen ancilla.")
    t0, t1 = targets
    b0 = ((idx >> t0) & 1)[keep]
    b1 = ((idx >> t1) & 1)[keep]
    w  = p[keep]
    def s(bit0, bit1):
        sel = (b0 == bit0) & (b1 == bit1)
        return float(w[sel].sum()) / mass
    return {"00": s(0,0), "01": s(0,1), "10": s(1,0), "11": s(1,1)}, mass

def _plot_and_save(cond, title, save_path, show=True):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    labels = ["00","01","10","11"]
    heights = [cond.get(l, 0.0) for l in labels]
    fig, ax = plt.subplots()
    ax.bar(labels, heights)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Probability")
    ax.set_title(title)
    for x, h in enumerate(heights):
        ax.text(x, h + 0.02, f"{h:.3f}", ha="center", va="bottom")
    fig.savefig(save_path, dpi=200, bbox_inches="tight")
    if show: plt.show()
    plt.close(fig)


def simulate_and_plot_from_statevector(qc, transpiled_qc, vector, save_path,
                          expect=(2/3, 1/3, 0.0, 0.0), tol=0.15, show=True):
    """
    Auto-pick (ancilla, targets) that best matches expected pattern (~ 2/3, 1/3, 0, 0).
    Returns (cond, mass, ancilla, targets, save_path).
    """
    mapping = extract_logical_to_physical(qc, transpiled_qc)
    sv_log  = _undo_to_logical(vector, mapping, transpiled_qc.num_qubits)
    p, n, idx = _probabilities(sv_log)

    # candidates: qubits that are neither ~0 nor ~1 deterministically
    masses = [float(p[((idx>>a)&1)==0].sum()) for a in range(n)]
    cand_anc = [a for a, m in enumerate(masses) if 1e-6 < m < 1 - 1e-6]

    best = None
    target_qubits = list(range(n))
    for a in cand_anc:
        for t0 in target_qubits:
            if t0 == a: continue
            for t1 in target_qubits:
                if t1 == a or t1 == t0: continue
                cond, mass = _cond_targets_given_anc0(p, n, idx, (t0, t1), a)
                vec = (cond["00"], cond["01"], cond["10"], cond["11"])
                score = sum((vi - ei)**2 for vi, ei in zip(vec, expect))
                if best is None or score < best[0]:
                    best = (score, a, (t0, t1), cond, mass)

    if best is None:
        raise RuntimeError("No suitable ancilla candidates found (all masses ~0 or ~1).")

    score, a, targets, cond, mass = best
    ok = (abs(cond["00"]-expect[0]) <= tol and
          abs(cond["01"]-expect[1]) <= tol and
          cond["10"] <= tol and
          cond["11"] <= tol)

    print("Pr[ancilla=0] per logical qubit:", [f"{x:.3f}" for x in masses])
    print(f"Picked ancilla=q{a}, targets={targets}, score={score:.4g}, ok={ok}")

    title = f"P{targets} | q{a}=0  (kept={mass:.3f})"
    _plot_and_save(cond, title, save_path, show)
    return cond, mass, a, targets, save_path


# import os
# import numpy as np
# import matplotlib.pyplot as plt
# from qiskit.quantum_info import Statevector
#
# def analyze_vector_and_plot(
#     vector,                     # Statevector OR flat numpy array (MBQC ψ)
#     mapping,                    # logical -> physical from extract_logical_to_physical(qc, transpiled_qc)
#     total_qubits,               # transpiled_qc.num_qubits
#     targets_logical=(2, 1),     # qubits of interest (logical indices; left→right in labels)
#     ancilla_logical=0,          # logical ancilla to post-select on (keeps events with ancilla=0)
#     shots=None,                 # optional: sample counts via multinomial
#     save_path="images/plots/minimal_qrs.png",
#     show=True,
#     title=None
# ):
#     """
#     Undo layout to logical order, compute P(targets | ancilla=0), plot and save.
#     Returns (cond_probs_dict, kept_mass, counts_or_None, save_path).
#     """
#
#     # 1) Convert to LOGICAL state using your working helper
#     #    (try both signatures to support your two usage patterns)
#     try:
#         sv_log = undo_layout_on_state(vector, mapping, total_qubits=total_qubits)
#     except TypeError:
#         sv_log = undo_layout_on_state(vector, mapping)
#
#     # Ensure we have a Qiskit Statevector object
#     sv_log = Statevector(getattr(sv_log, "data", sv_log), dims=(2,)*total_qubits)
#
#     # 2) Exact probabilities in Qiskit (little-endian, q0 = LSB, indices are LOGICAL now)
#     p = sv_log.probabilities()
#     n = total_qubits
#     idx = np.arange(1 << n, dtype=np.uint64)
#
#     # 3) Post-select ancilla = 0
#     keep = ((idx >> ancilla_logical) & 1) == 0
#     mass = float(p[keep].sum())
#     if mass == 0.0:
#         raise ValueError("Post-selection event has zero probability (ancilla always 1).")
#
#     # 4) Conditional over the target pair (in the order you provided)
#     t0, t1 = targets_logical
#     b0 = ((idx >> t0) & 1)[keep]
#     b1 = ((idx >> t1) & 1)[keep]
#     w  = p[keep]
#
#     def _sum(bit0, bit1):
#         sel = (b0 == bit0) & (b1 == bit1)
#         return float(w[sel].sum()) / mass
#
#     cond = {"00": _sum(0,0), "01": _sum(0,1), "10": _sum(1,0), "11": _sum(1,1)}
#
#     # Optional: sample counts
#     counts = None
#     if shots:
#         labels = ["00","01","10","11"]
#         weights = np.array([cond[l] for l in labels], dtype=float)
#         counts = dict(zip(labels, np.random.default_rng().multinomial(int(shots), weights)))
#
#     # 5) Plot + save
#     labels  = ["00","01","10","11"]
#     heights = [cond[l] for l in labels]
#     fig, ax = plt.subplots()
#     ax.bar(labels, heights)
#     ax.set_ylim(0, 1)
#     ax.set_ylabel("Probability")
#     if title is None:
#         title = f"P{targets_logical} | q{ancilla_logical}=0 (kept={mass:.3f})"
#     ax.set_title(title)
#     for x, h in enumerate(heights):
#         ax.text(x, h + 0.02, f"{h:.3f}", ha="center", va="bottom")
#     os.makedirs(os.path.dirname(save_path), exist_ok=True)
#     fig.savefig(save_path, dpi=200, bbox_inches="tight")
#     if show:
#         plt.show()
#     plt.close(fig)
#
#     return cond, mass, counts, save_path


# --- example call --------------------------------------------------------------
# Expecting ~66% for '00' and ~33% for '01' with your analysis order (q2, q1):
# (If labels look bit-reversed, set input_is_qiskit_order=False.)
# cond, mass, mapping, path = simulate_qrs_plot(
#     user_feature=[0, 0],
#     targets_logical=(2, 1),
#     ancilla_logical=None,          # auto-detect c0[0]
#     mapping_is_l2p=True,
#     input_is_qiskit_order=True,
#     save_path="images/plots/minimal_qrs.png",
#     show=True
# )
# print(cond, mass, path)

#
# def run_minimal_qrs_and_plot(
#     user_vector,
#     targets_logical=(2, 1),      # which logical qubits to show, left→right in the labels
#     ancilla_logical=0,            # logical ancilla to post-select on (0 keeps ~75% in your example)
#     input_is_qiskit_order=True,   # set False if Graphix returns MSB-first bit order
#     mapping_is_l2p=True,          # set False if your extract_* returns physical->logical
#     save_path=None,               # e.g. "images/plots/minimal_qrs.png"
#     show=True
# ):
#     """
#     Simulate minimal QRS from user_vector, undo layout to LOGICAL order, post-select ancilla=0,
#     and save a bar chart of P(targets | ancilla=0).
#
#     Returns (cond_dict, kept_mass, mapping, save_path)
#     """
#     # --- build + transpile ---
#     qc, input_vec = circuits.minimal_qrs(user_vector)
#     bw_pattern, col_map, transpiled_qc = ubqc_brickwork_transpiler.transpile(
#         qc, input_vec, routing_method="sabre", layout_method="sabre", with_ancillas=False
#     )
#
#     # --- MBQC standardize + simulate ---
#     bw_pattern.standardize()
#     bw_pattern.shift_signals()
#     tn = bw_pattern.simulate_pattern(backend="tensornetwork", graph_prep="parallel")
#     graphix_vec = tn.to_statevector()  # flat complex amplitudes
#
#     # --- mapping used on THIS run (handles probabilistic placement) ---
#     mapping = extract_logical_to_physical(qc, transpiled_qc)  # logical -> physical (usually)
#
#     # --- helpers (kept local for concision) ---
#     def _invert_mapping(m, n):
#         if isinstance(m, dict):
#             return {v: k for k, v in m.items()}
#         inv = [None]*n
#         for log, phys in enumerate(m):
#             inv[phys] = log
#         return inv
#
#     def _to_logical_state(amps, n, *, mapping, mapping_is_l2p=True, input_is_qiskit_order=True):
#         data = np.asarray(getattr(amps, "data", amps), dtype=complex).reshape(-1)
#         assert data.size == (1 << n), "Length must be 2**n."
#         s = float((data.conj()*data).real.sum())
#         if not np.isclose(s, 1.0, atol=1e-12): data /= np.sqrt(s)
#
#         # Endianness: convert MSB-first -> little-endian if needed
#         if not input_is_qiskit_order:
#             idx = np.fromiter((int(f"{i:0{n}b}"[::-1], 2) for i in range(1<<n)),
#                               dtype=np.int64, count=(1<<n))
#             data = data[idx]
#
#         # Ensure logical->physical permutation list
#         l2p = mapping if mapping_is_l2p else _invert_mapping(mapping, n)
#         if isinstance(l2p, dict): l2p = [int(l2p[j]) for j in range(n)]
#
#         # Remap amplitudes: logical index x -> physical index y
#         out = np.empty_like(data)
#         for x in range(1 << n):
#             y = 0
#             for j in range(n):
#                 y |= ((x >> j) & 1) << l2p[j]
#             out[x] = data[y]
#         return out
#
#     def _conditional_targets_given_anc0(data_log, n, targets, ancilla):
#         p = (data_log.conj()*data_log).real
#         idx = np.arange(1<<n, dtype=np.uint64)
#         keep = ((idx>>ancilla)&1)==0
#         mass = float(p[keep].sum())
#         if mass == 0.0: raise ValueError("Pr[ancilla=0] = 0.")
#         bits = [((idx>>t)&1)[keep] for t in targets]
#         w = p[keep]
#         def s(b):
#             sel = np.ones_like(w, bool)
#             for arr, bit in zip(bits, b): sel &= (arr==bit)
#             return float(w[sel].sum())/mass
#         return {"00": s((0,0)), "01": s((0,1)), "10": s((1,0)), "11": s((1,1))}, mass
#
#     # --- undo layout to LOGICAL order and compute conditional ---
#     n = transpiled_qc.num_qubits
#     data_log = _to_logical_state(graphix_vec, n,
#                                  mapping=mapping,
#                                  mapping_is_l2p=mapping_is_l2p,
#                                  input_is_qiskit_order=input_is_qiskit_order)
#     cond, mass = _conditional_targets_given_anc0(data_log, n,
#                                                  targets=targets_logical,
#                                                  ancilla=ancilla_logical)
#
#     # --- plot + save ---
#     labels  = ["00", "01", "10", "11"]
#     heights = [cond.get(l, 0.0) for l in labels]
#     fig, ax = plt.subplots()
#     ax.bar(labels, heights)
#     ax.set_ylim(0, 1)
#     ax.set_ylabel("Probability")
#     title = f"P{targets_logical} | q{ancilla_logical}=0 (kept={mass:.3f})"
#     ax.set_title(title)
#     for x, h in enumerate(heights):
#         ax.text(x, h + 0.02, f"{h:.3f}", ha="center", va="bottom")
#
#     if save_path is None:
#         uv_tag = "".join(map(str, user_vector)) if hasattr(user_vector, "__iter__") else str(user_vector)
#         save_path = f"images/plots/minimal_qrs_uv_{uv_tag}.png"
#     os.makedirs(os.path.dirname(save_path), exist_ok=True)
#     fig.savefig(save_path, dpi=200, bbox_inches="tight")
#     if show:
#         plt.show()
#     plt.close(fig)
#
#     return cond, mass, mapping, save_path
#
