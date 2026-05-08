import numpy as np
import os
import csv

from qiskit.circuit.library import QFT

from brickwork_transpiler import brickwork_transpiler, circuits

import brickwork_transpiler.utils as bw_utils


def get_writer(file_name: str, file_path: str = "src/ubqc_brickwork_transpiler/experiments/data/output_data/"):

    header = ["decomposed_depth", "transpiled_depth", "original_depth", "num_gates_original",
              "num_gates_transpiled"]
    full_path = os.path.join(file_path, file_name)

    # Ensure the directory exists
    os.makedirs(file_path, exist_ok=True)

    # Create file with header if it doesn't exist
    if not os.path.isfile(full_path):
        with open(full_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)

    # Now return your custom writer
    return bw_utils.BufferedCSVWriter(full_path, header)


def experiment_qft_transpilation():

    filename = "experiments_qft.csv"
    writer = get_writer(filename)

    max_size = 30


    # for num_qubits in range(3, max_size):
    #
    #     # Build the canonical QFT from the library
    #     qft_circ = QFT(num_qubits=num_qubits,
    #                    approximation_degree=0,  # exact QFT
    #                    do_swaps=True,
    #                    inverse=False,
    #                    name=f"QFT_{num_qubits}")
    #
    #     # print("Transpiling...")
    #     instr_mat = ubqc_brickwork_transpiler.transpile(qft_circ, routing_method='sabre', layout_method='sabre',
    #                                                return_mat=True, file_writer=writer)
    #
    #     writer.set("transpiled_depth", len(instr_mat[0]))
    #     writer.set("original_depth", qft_circ.depth())
    #     writer.flush()

    plot_single_qft_dataset("Thesis_qft_transpilation_cost.png")

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D


def plot_single_qft_dataset(name_of_plot: str = "qft_default.png"):
    base_dir = "src/ubqc_brickwork_transpiler/experiments/data/output_data/"
    filename = "experiments_qft.csv"

    # -------------------------------------------------------
    # Load data   – drop n = 0 to avoid log(0)
    # -------------------------------------------------------
    df = pd.read_csv(os.path.join(base_dir, filename))
    df = df[df["num_gates_original"] > 0]

    n                = df["num_gates_original"].to_numpy()
    num_gates_orig = df["num_gates_original"].to_numpy()
    transpiled_depth = df["transpiled_depth"].to_numpy()

    n_qubits = np.arange(3, 3 + len(df))  # 3,4,5,...

    # Reference curve  c·√n·log²n
    c         = 50
    # nlogn_ref = c * np.sqrt(n_qubits) * np.log(n_qubits)**
    nlogn_ref = c * np.log(n_qubits)**3

    # -------------------------------------------------------
    # NEW: qubit-count reference  log²(n_qubits)
    #        first row = 3 qubits, then +1 per row
    # -------------------------------------------------------
    log2_ref   =  10 * np.log(n_qubits) ** 2          # no prefactor
    # -------------------------------------------------------

    # -------------------------------------------------------
    # Styling
    # -------------------------------------------------------
    colours = {"num_gates_orig": "orange",
               "transpiled_depth": "green",
               "nlogn_ref":        "blue",
               "log2_ref":         "red"}        # NEW colour
    markers = {#"num_gates_orig": "s",
               "transpiled_depth": "^"}
    labels  = {#"num_gates_orig": "Number of gates original circuit",
               "transpiled_depth": "Brickwork graph depth",
               "nlogn_ref":        r"$c_1 \cdot \log^3 N$",
               "log2_ref":         r"$c_2 \cdot \log^{2} N$"}

    # show at most ~8 markers per curve
    mark_every = max(1, len(n) // 8)

    y_min = max(1, np.min([*num_gates_orig,
                           *transpiled_depth,
                           *nlogn_ref,
                           *log2_ref]))
    y_max = np.max([*num_gates_orig,
                    *transpiled_depth,
                    *nlogn_ref,
                    *log2_ref]) * 1.3

    # -------------------------------------------------------
    # Figure
    # -------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8, 6))

    key = "transpiled_depth"
    ax.plot(n, locals()[key],
            label=labels[key],
            marker=markers[key],
            markevery=mark_every,
            linestyle="-",
            color=colours[key],
            linewidth=2.7,
            markersize=8,
            alpha=0.97,
            markeredgecolor="white",
            markeredgewidth=1.7)

    # Guide curves (no markers)
    ax.plot(n, nlogn_ref,
            label=labels["nlogn_ref"],
            color=colours["nlogn_ref"],
            linestyle="--",
            linewidth=2.4,
            alpha=0.9)

    ax.plot(n, log2_ref,
            label=labels["log2_ref"],
            color=colours["log2_ref"],
            linestyle="-.",
            linewidth=2.4,
            alpha=0.9)

    # -------------------------------------------------------
    # Axes and legend
    # -------------------------------------------------------
    ax.set_title("QFT Transpilation Cost", fontsize=15, fontweight="bold")
    ax.set_xlabel(r"Input circuit size (log scale)", fontsize=13)
    ax.set_ylabel(r"Depth (log scale)", fontsize=13)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_ylim(y_min, y_max)

    ax.xaxis.set_major_locator(mticker.LogLocator(base=10, numticks=10))
    ax.xaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f"{int(v):d}" if v >= 1 else "")
    )
    ax.xaxis.set_minor_locator(mticker.LogLocator(base=10,
                                                  subs=np.arange(1, 10) * 0.1,
                                                  numticks=100))
    ax.xaxis.set_minor_formatter(mticker.NullFormatter())

    ax.tick_params(axis="both", which="major", labelsize=12)
    ax.grid(axis="y", which="both", linestyle=":", alpha=0.35)

    legend_handles = [
        # Line2D([0], [0], color=colours["num_gates_orig"],
        #        marker=markers["num_gates_orig"], linestyle="-",
        #        markersize=8, label=labels["num_gates_orig"],
        #        markeredgecolor="white", markeredgewidth=1.7),
        Line2D([0], [0], color=colours["transpiled_depth"],
               marker=markers["transpiled_depth"], linestyle="-",
               markersize=8, label=labels["transpiled_depth"],
               markeredgecolor="white", markeredgewidth=1.7),
        Line2D([0], [0], color=colours["nlogn_ref"], linestyle="--",
               linewidth=3, label=labels["nlogn_ref"]),
        Line2D([0], [0], color=colours["log2_ref"], linestyle="-.",
               linewidth=3, label=labels["log2_ref"]),
    ]
    ax.legend(handles=legend_handles, fontsize=13, frameon=False, loc="best")

    plt.tight_layout()
    plt.savefig(f"images/qrs/qrs_{name_of_plot}", dpi=300, bbox_inches="tight")
    plt.show()
