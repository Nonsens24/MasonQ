"""Reproduce the minimal B-QRS instance of the paper's Section 3.3 with the archived code.

The circuit is circuits.minimal_qrs([0, 1]) (database {(0,0), (0,1)}, user feature (0, 1); six
qubits). It is transpiled with SABRE layout and SABRE routing, Qiskit optimisation level 1 and
no ancillas. SABRE is randomised, so the transpilation is repeated and the smallest brickwork
graph is kept; it is then simulated with Graphix and compared with the Qiskit reference state,
exactly as the archived system tests do.

Environment: the one in requirements-lock.txt at the repository root (Qiskit 0.46.3, Graphix
0.3.1). Run from any directory; nothing is written inside the repository except what you name
as the output directory.

usage:
    MPLBACKEND=Agg python minimal_qrs_instance.py <repository root> <output dir> [runs]

Writes to <output dir>:
    minimal_qrs_instance.txt                   settings, resource numbers, verification, run statistics
    minimal_qrs_pattern.txt                    the Graphix pattern, one command per line
    minimal_qrs_brickwork_graph.png            the brickwork graph drawn by MasonQ's visualiser (+ .pdf)
    minimal_qrs_brickwork_graph_encrypted.png  the same graph after BFK angle randomisation, drawn
                                               without gate colours (+ .pdf)
    minimal_qrs_circuit.png                    the input circuit (paper Fig. 7a)
    minimal_qrs_circuit_decomposed.png         the circuit after Qiskit's decomposition, SABRE
                                               layout and routing, as given to the brickwork
                                               alignment (paper Fig. 7b); also as .qasm
"""
import contextlib
import copy
import datetime
import io
import os
import platform
import shutil
import sys
from collections import Counter

import numpy as np


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    root, out_dir = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    runs = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    sys.path.insert(0, root)
    os.makedirs(os.path.join(out_dir, "images", "graphs"), exist_ok=True)
    os.chdir(out_dir)  # the archived visualiser saves under images/graphs/ of the cwd

    from importlib.metadata import version as pkg_version

    from src.brickwork_transpiler import brickwork_transpiler, circuits, utils, visualiser

    settings = dict(routing_method="sabre", layout_method="sabre", with_ancillas=False, opt=1)
    best = None
    depths = []
    for _ in range(runs):
        qc, input_vec = circuits.minimal_qrs([0, 1])
        with contextlib.redirect_stdout(io.StringIO()):
            pattern, col_map, transpiled_qc = brickwork_transpiler.transpile(
                qc, input_vec, plot_decomposed=False, **settings)
        nodes, edges = pattern.get_graph()
        graph_columns = max(c for _, c in nodes) + 1
        bricks = (graph_columns - 1) // 4
        depths.append(bricks)
        if best is None or bricks < best["bricks"]:
            best = dict(bricks=bricks, graph_columns=graph_columns, nodes=len(nodes), cz=len(edges),
                        rows=len({r for r, _ in nodes}), pattern=pattern, col_map=col_map,
                        qc=qc, transpiled_qc=transpiled_qc, input_vec=input_vec)

    # verification on a copy: standardize/shift_signals rewrite the command list
    check = copy.deepcopy(best["pattern"])
    check.standardize()
    check.shift_signals()
    psi = np.asarray(check.simulate_pattern(backend="tensornetwork", graph_prep="parallel").to_statevector()).ravel()
    ref = utils.calculate_ref_state_from_qiskit_circuit(check, best["qc"], best["transpiled_qc"], best["input_vec"])
    ref = np.asarray(ref.data if hasattr(ref, "data") else ref).ravel()
    overlap = abs(np.vdot(ref / np.linalg.norm(ref), psi / np.linalg.norm(psi))) ** 2

    # pattern, one command per line
    with open("minimal_qrs_pattern.txt", "w", encoding="utf-8") as fh:
        fh.write(f"# Minimal B-QRS brickwork pattern, {best['rows']} rows x {best['graph_columns']} graph columns "
                 f"({best['bricks']} brick columns); output nodes {list(best['pattern'].output_nodes)}\n")
        for cmd in best["pattern"]:
            fh.write(repr(cmd) + "\n")

    # graph image via the archived visualiser (saves images/graphs/<title>.png and .pdf under cwd)
    title = "Brickwork graph: Minimal QRS"
    with contextlib.redirect_stdout(io.StringIO()):
        visualiser.plot_brickwork_graph_from_pattern(
            best["pattern"], show_angles=True, node_colours=best["col_map"], use_node_colours=True,
            title=title, save_plot=True)
    for ext in ("png", "pdf"):
        shutil.move(os.path.join("images", "graphs", f"{title}.{ext}"), f"minimal_qrs_brickwork_graph.{ext}")

    # the input circuit and the decomposed, laid-out and routed circuit behind the pattern
    import matplotlib.pyplot as plt
    for name, circ in (("minimal_qrs_circuit", best["qc"]), ("minimal_qrs_circuit_decomposed", best["transpiled_qc"])):
        fig = circ.draw(output="mpl", fold=30, style="iqp")
        fig.savefig(f"{name}.png", dpi=300, bbox_inches="tight")
        plt.close(fig)
    try:
        from qiskit import qasm2
        qasm_text = qasm2.dumps(best["transpiled_qc"])
    except Exception:
        qasm_text = best["transpiled_qc"].qasm()
    with open("minimal_qrs_circuit_decomposed.qasm", "w", encoding="utf-8") as fh:
        fh.write(qasm_text)

    # encrypted version: BFK angle randomisation, drawn without gate colours
    from src.brickwork_transpiler.bfk_encoder import encode_pattern
    encoded, _log_alice = encode_pattern(copy.deepcopy(best["pattern"]))
    with contextlib.redirect_stdout(io.StringIO()):
        visualiser.plot_brickwork_graph_encrypted(encoded, use_locks=False, show_angles=True, title=title)
    for ext in ("png", "pdf"):
        shutil.move(os.path.join("images", "graphs", f"{title}_enc.{ext}"),
                    f"minimal_qrs_brickwork_graph_encrypted.{ext}")
    shutil.rmtree("images")

    counts = dict(sorted(Counter(depths).items()))
    lines = [
        f"Minimal B-QRS instance (paper Section 3.3), generated {datetime.date.today().isoformat()}",
        f"code: MasonQ at {root}",
        f"environment: Python {platform.python_version()}, qiskit {pkg_version('qiskit')}, "
        f"graphix {pkg_version('graphix')}",
        "circuit: circuits.minimal_qrs([0, 1]); database {(0,0), (0,1)}, user feature (0, 1); "
        f"{best['qc'].num_qubits} qubits, {len(best['qc'].data)} gates",
        f"decomposed and routed circuit: {best['transpiled_qc'].num_qubits} qubits, "
        f"{len(best['transpiled_qc'].data)} gates, depth {best['transpiled_qc'].depth()}, "
        f"ops {dict(best['transpiled_qc'].count_ops())}",
        f"transpile settings: {settings}",
        f"runs: {runs}; brick columns per run: {counts}; smallest kept",
        "",
        f"brick columns (D)        {best['bricks']}",
        f"graph columns (4D + 1)   {best['graph_columns']}",
        f"rows (logical qubits)    {best['rows']}",
        f"graph nodes (RSP qubits) {best['nodes']}",
        f"measurements             {best['nodes'] - best['rows']}",
        f"CZ edges                 {best['cz']}",
        f"qubits held at once      {2 * best['rows']} (two graph columns of {best['rows']}, cylindrical register)",
        "",
        f"verification: Graphix tensor-network simulation vs Qiskit reference state, overlap {overlap:.12f}",
    ]
    with open("minimal_qrs_instance.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
