"""Demo entry point for local manual runs.

Prefer installed/module execution:

    python -m brickwork_transpiler.main

This file also supports direct execution from `src/brickwork_transpiler/main.py`
because some IDEs run files that way. In that mode, Python puts the package
directory itself on `sys.path`, which would make `import brickwork_transpiler`
resolve to the sibling `brickwork_transpiler.py` module instead of the package.
The bootstrap below replaces that path with the `src` directory.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import numpy as np

if __package__ in {None, ""}:
    package_dir = Path(__file__).resolve().parent
    src_dir = package_dir.parent
    sys.path = [p for p in sys.path if Path(p or ".").resolve() != package_dir]
    sys.path.insert(0, str(src_dir))

os.environ.setdefault(
    "NUMBA_CACHE_DIR",
    str(Path(tempfile.gettempdir()) / "masonq_numba_cache"),
)
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "masonq_mpl_cache"),
)
os.environ.setdefault(
    "XDG_CACHE_HOME",
    str(Path(tempfile.gettempdir()) / "masonq_cache"),
)

from brickwork_transpiler import brickwork_transpiler, circuits, utils


def main():
    from brickwork_transpiler import visualiser

    qc, input_vector = circuits.qft(3)

    from brickwork_transpiler import transpile

    result = transpile(
        qc,
        input_vector,
        routing_method="sabre",
        layout_method="trivial",
        with_ancillas=True,
        fallback_opt=1,
        return_result=True,
    )

    pattern = result.pattern
    decomposed_qc = result.decomposed_circuit
    resources = result.resources

    result.plot(show=True)



    print("pattern: ", pattern)
    print("decomposed_qc: ", decomposed_qc)
    print("resources: ", resources)

    return 0

    # qc, input_vector = circuits.h_and_cx_circ()
    # qc, input_vector = circuits.minimal_qrs([0, 0])
    # qc, input_vector = circuits.big_shifter_both_up_low_rotation_brick_shifted()
    qc, input_vector = circuits.qft(3)

    iv2 = input_vector.copy()

    qc.draw(output='mpl',
                        fold=40,
                        style="iqp"
                        )



    bw_pattern, col_map, decomposed_qc = brickwork_transpiler.transpile(
        qc, input_vector,
        routing_method="sabre",
        layout_method="trivial",
        with_ancillas=False
    )


    # Plot informative graph
    visualiser.plot_brickwork_graph_from_pattern(bw_pattern,
                                                 show_angles=True,
                                                 node_colours=col_map,
                                                 use_node_colours=True,
                                                 title="Brickwork graph: sel_decomp_test",
                                                 save_plot=True,
                                                 show=True)

    print("Simulating circuit...")

    # Preprocess data to standard form
    bw_pattern.standardize()
    bw_pattern.shift_signals()

    # Get the output state from Graphix simulation
    tn = bw_pattern.simulate_pattern(
        backend="tensornetwork",
        graph_prep="parallel",
        rng=np.random.default_rng(0),
    )
    psi = tn.to_statevector()

    # Extend input vector with new ancillae qubits
    reference_output = utils.calculate_ref_state_from_qiskit_circuit(bw_pattern, qc, decomposed_qc, input_vector)

    # Now compare against the MBQC simulator output `psi`
    if utils.assert_equal_up_to_global_phase(reference_output, psi):
        print("Equivalent up to global phase!")

    print(f"Qiskit ref_state: {reference_output}")
    print(f"Simulated output state: {psi}")
    # Compare output state upto global phase
    if utils.assert_equal_up_to_global_phase(reference_output, psi):
        print("Equivalent up to global phase!")


    # hhl_transpilation.experiment_hhl_transpilation(7)
    # hhl_transpilation.plot_single_hhl_dataset("HHL_logN_sq")
    # hhl_transpilation.plot_hhl_from_multiple_files("thesis_hhl_final_plots_unopt_dense_d_avg")
    # qft_transpilation.plot_single_qft_dataset("thesis_qft_log3_bound")
    # plot_qrs_data.plot_qrs_with_db_scaling_from_files("qrs_with_db_L_no_decomp")
    # hhl_transpilation.plot_depth_per_gate_vs_m_logfit("vs_m_plot")
    # hhl_transpilation.plot_scaling_with_m_as_width("d_or_m_overlay_hhl_exp_toeplitz_raw_no_log")
    # hhl_transpilation.plot_hhl_davg_three()

    return 0


if __name__ == "__main__":
    main()
