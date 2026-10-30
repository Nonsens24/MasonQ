"""Regenerate the brickwork-depth scaling figures (Fig. 5, Fig. 6, Figs. F12-F14).

Data are the CSVs written by MasonQ's experiment scripts
(experiments/data/output_data), copied unchanged into ./data, plus the
fixed-clock HHL rerun produced by ./hhl_fixed_clock. Figures are written to
./results under the file names used in the manuscript.

Axis conventions, checked by assertions below:
  QFT  row k of experiments_qft.csv is the (k + 3)-qubit QFT, so N = 2^n.
  HHL  the CSV column `N` already stores the matrix dimension 2^n.
  QRS  the CSV column `L` stores the database size 2^n (n = 2..7).

HHL data sets (tridiagonal Toeplitz A_N(1, -1/6): kappa = 2, s = 3; Qiskit's
linear_solvers HHL with exact reciprocal, epsilon = 1e-2):
  Fig. 5b  experiment_hhl_toeplitz_fixed_clock.csv: clock register fixed at
           5 qubits for every N (N = 2..4096), transpiled with the current
           MasonQ. Solution fidelity >= 0.998 for N <= 64. Gate count
           ~ 1437 n^2, so the circuit is polylogarithmic in N; Theorem 4
           then predicts D = O(omega n_gates) = O(log^3 N).
  F12a     Qiskit's default clock of n + 2 qubits, which grows with N.
           U^(2^j) uses ceil(sqrt(2^j) k) Trotter steps and the exact
           reciprocal acts on 2^(n+1) clock values, so this circuit carries
           a sqrt(N) factor and, for large N, a term linear in N.
  F12b-d   explicit matrices (normalised Laplacian, two sparse Hermitian
           samples), also with the default clock. The matrix is compiled as a
           dense unitary and repeated 2^j times for clock qubit j, so these
           circuits grow roughly as N^3. epsilon does not enter them at all.
F12 compares the brickwork depth with the circuit gate count and with the
Theorem 4 bound O(omega n_gates).

Reference curves use the natural logarithm; the base only rescales c.

Run:  python make_scaling_figures.py
"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
OUT = HERE.parent / "figures"

GREEN, GREEN_FACE = "#2E7D4F", "#90EE90"
BLUE = "#4C72B0"
RED, RED_FACE = "#C44E52", "#E8817F"
ORANGE, ORANGE_FACE = "#D1694A", "#F4A582"
EDGE = "#222222"

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["DejaVu Serif"],
        "mathtext.fontset": "dejavusans",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titlesize": 15,
        "axes.titleweight": "bold",
        "axes.labelsize": 13,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "legend.fontsize": 11,
        "savefig.dpi": 300,
    }
)

QRS_XLABEL = r"Database size, $L = 2^n$"


def read_csv(name):
    with open(DATA / name, newline="") as fh:
        rows = list(csv.DictReader(fh))
    return {key: np.array([float(r[key]) if r[key] else np.nan for r in rows]) for key in rows[0]}


def style_axes(ax, title, xlabel, ylabel="Depth"):
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_axisbelow(True)
    ax.grid(axis="y", which="major", color="#d9d9d9", linewidth=0.8)
    ax.grid(axis="y", which="minor", color="#f0f0f0", linewidth=0.5)


def new_axes(title, xlabel):
    fig, ax = plt.subplots(figsize=(7.4, 5.2))
    style_axes(ax, title, xlabel)
    return fig, ax


def power_of_two_ticks(ax, exponents, minor_exponents=()):
    ax.xaxis.set_major_locator(mticker.FixedLocator([2.0**e for e in exponents]))
    ax.xaxis.set_major_formatter(mticker.FixedFormatter([rf"$2^{{{e}}}$" for e in exponents]))
    ax.xaxis.set_minor_locator(mticker.FixedLocator([2.0**e for e in minor_exponents]))
    ax.xaxis.set_minor_formatter(mticker.NullFormatter())


def data_line(ax, x, y, label, colour, face, marker):
    ax.plot(x, y, color=colour, linewidth=2.2, marker=marker, markersize=8,
            markerfacecolor=face, markeredgecolor=EDGE, markeredgewidth=0.9,
            label=label, zorder=3)


def reference_line(ax, x, y, label, colour, dashes=(0, (6, 3))):
    ax.plot(x, y, color=colour, linewidth=2.0, linestyle=dashes, label=label, zorder=2)


def finish(fig, ax, name, legend_loc, reverse_legend=False):
    # The submitted single-panel QRS figures (Fig. 6) list the legend entries in reverse
    # plot order: reference curve, brickwork graph, database size.
    handles, labels = ax.get_legend_handles_labels()
    if reverse_legend:
        handles, labels = handles[::-1], labels[::-1]
    ax.legend(handles, labels, loc=legend_loc, frameon=True, framealpha=0.95, edgecolor="#cccccc")
    fig.tight_layout()
    fig.savefig(OUT / name, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote results/{name}")


def finish_grid(fig, axes, name):
    """Save a panel figure with one legend above all panels."""
    handles, labels = {}, {}
    for ax in np.ravel(axes):
        for h, lab in zip(*ax.get_legend_handles_labels()):
            handles.setdefault(lab, h)
    labels = list(handles)
    fig.legend([handles[lab] for lab in labels], labels, loc="upper center",
               ncol=min(len(labels), 3), frameon=False, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(OUT / name, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote results/{name}")


def report(tag, data, ref, side):
    ratio = data / ref
    extreme = ratio.max() if side == "above" else ratio.min()
    ok = np.all(ref > data) if side == "above" else np.all(ref < data)
    print(f"  {tag}: reference {side} every point: {ok} (tightest data/ref = {extreme:.3g})")
    assert ok, f"{tag} reference does not stay {side} the data"


def dimension_exponents(N, column):
    n = np.round(np.log2(N)).astype(int)
    assert np.array_equal(N, 2.0**n), f"column {column} is not a power of two"
    return n


# --------------------------------------------------------------------------
# Fig. 5a  Blind QFT
# --------------------------------------------------------------------------
def figure_qft():
    d = read_csv("experiments_qft.csv")
    n = np.arange(3, 3 + len(d["transpiled_depth"]))
    # Row-to-n check: the selectively decomposed n-qubit QFT has n H gates,
    # n(n-1)/2 controlled phases of 5 gates each, and floor(n/2) SWAPs of 3 CX.
    expected_gates = n + 5 * n * (n - 1) // 2 + 3 * (n // 2)
    assert np.array_equal(d["num_gates_original"], expected_gates), "QFT row/qubit mismatch"

    N = 2.0**n
    lnN = n * np.log(2.0)
    depth = d["transpiled_depth"]
    # Upper bound only: depth / log^2 N keeps falling (6.0 -> 1.9), so a
    # log^2 N curve under the data would suggest a lower bound that is false.
    log3 = 7.0 * lnN**3
    report("QFT c log^3 N", depth, log3, "above")

    fig, ax = new_axes("Blind Quantum Fourier Transform", r"Problem size, $N = 2^n$")
    reference_line(ax, N, log3, r"$c \cdot \log^3 N$", BLUE)
    data_line(ax, N, depth, "Brickwork graph", GREEN, GREEN_FACE, "s")
    power_of_two_ticks(ax, range(4, 29, 4), n)
    finish(fig, ax, "qrs_thesis_qft_log3_bound_fancy_best.png", "upper left")


# --------------------------------------------------------------------------
# Fig. 5b  Blind HHL
# --------------------------------------------------------------------------
def figure_hhl():
    d = read_csv("experiment_hhl_toeplitz_fixed_clock.csv")
    N = d["N"]
    n = dimension_exponents(N, "N")
    assert np.all(d["nl"] == 5), "Fig. 5b uses a fixed 5-qubit clock register"
    depth = d["transpiled_depth"]
    circuit = d["num_gates_original"]
    # Theorem 4 with omega = O(log N) and n_gates = O(log^2 N) gives O(log^3 N).
    log3 = 5.0e3 * np.log(N) ** 3
    report("HHL c log^3 N", depth, log3, "above")
    slope = np.diff(np.log(depth)) / np.diff(np.log(N))
    print(f"  HHL local slope d log D / d log N = {np.round(slope, 2)}")
    print(f"  HHL gates / n^2 = {np.round(circuit / n**2).astype(int)}")

    fig, ax = new_axes("Blind Harrow–Hassidim–Lloyd", r"Problem size, $N = 2^n$")
    reference_line(ax, N, log3, r"$c \cdot \log^3 N$", BLUE)
    data_line(ax, N, depth, "Brickwork graph", GREEN, GREEN_FACE, "s")
    data_line(ax, N, circuit, "Circuit (gate count)", ORANGE, ORANGE_FACE, "o")
    power_of_two_ticks(ax, range(2, 13, 2), n)
    finish(fig, ax, "hhl_HHL_logN_sq_newplot_fancy_best.png", "upper left")


# --------------------------------------------------------------------------
# Fig. F12  Blind HHL across matrix families
# --------------------------------------------------------------------------
def hhl_width(n, family):
    """Logical width omega of the Qiskit HHL circuit for an n-qubit system.

    omega = n_b + n_l + n_a + 1 (system, clock, ancillas, flag), where the
    clock has n_l = n + 2 qubits (n + 1 eigenvalue bits plus one sign bit,
    valid while kappa <= 2^(n+1) - 1). TridiagonalToeplitz adds n - 1
    ancillas for n > 1; an explicit matrix (NumPyMatrix) adds none. Checked
    against constructed circuits: Toeplitz N = 2, 4, 8 -> 5, 8, 11 and
    explicit N = 4, 8 -> 7, 9.
    """
    ancillas = np.where(n > 1, n - 1, 0) if family == "toeplitz" else 0
    return n + (n + 2) + ancillas + 1


HHL_PANELS = [
    ("Tridiagonal Toeplitz, no optimisation", "experiment_hhl_toeplitz_d_avf_opt0.csv", "toeplitz"),
    ("Normalised Laplacian, no optimisation", "experiment_hhl_laplacian_opt0_d_avg.csv", "matrix"),
    ("Low-density Hermitian, no optimisation", "experiment_hhl_sparse_opt0_d_avg.csv", "matrix"),
    # A second random draw of the sparse matrix. The file name says epsilon = 1/m, but epsilon
    # does not enter the explicit-matrix circuits (dense unitary, exact reciprocal); the only
    # difference from panel (c) is the N = 8 sample, which synthesises to fewer gates.
    ("Low-density Hermitian, second sample", "experiment_hhl_sparse_one_over_m.csv", "matrix"),
]
THEOREM4_C = 0.3  # one constant for all four matrix families


def figure_hhl_families():
    fig, axes = plt.subplots(2, 2, figsize=(12.4, 9.6))
    for k, (ax, (title, csv_name, family)) in enumerate(zip(axes.flat, HHL_PANELS)):
        d = read_csv(csv_name)
        N = d["N"]
        n = dimension_exponents(N, f"N in {csv_name}")
        depth = d["transpiled_depth"]
        gates = d["num_gates_original"]
        bound = THEOREM4_C * hhl_width(n, family) * gates
        report(f"F12 {title}: Theorem 4", depth, bound, "above")

        style_axes(ax, title, r"Problem size, $N = 2^n$", "Depth" if k % 2 == 0 else None)
        data_line(ax, N, gates, "Circuit (gate count)", ORANGE, ORANGE_FACE, "o")
        data_line(ax, N, depth, "Brickwork graph", GREEN, GREEN_FACE, "s")
        reference_line(ax, N, bound, r"$c \cdot \omega\, n_{\mathrm{gates}}$ (Theorem 4)", BLUE)
        slope = np.diff(np.log(depth)) / np.diff(np.log(N))
        print(f"    local slope d log D / d log N = {np.round(slope, 2)}")
        ax.set_xlim(2**0.7, 2**5.3)
        power_of_two_ticks(ax, range(1, 6))
    finish_grid(fig, axes, "hhl_thesis_hhl_final_plots_unopt_dense.png")


# --------------------------------------------------------------------------
# Fig. 6a/6b, F13, F14  Blind QRS
# --------------------------------------------------------------------------
def draw_qrs_panel(ax, csv_name, ref, ref_label, tag):
    d = read_csv(csv_name)
    L = d["L"]
    n = dimension_exponents(L, f"L in {csv_name}")
    depth = d["transpiled_depth"]
    curve = ref(L)
    report(tag, depth, curve, "above")
    data_line(ax, L, L, r"Database size ($L$)", RED, RED_FACE, "^")
    data_line(ax, L, depth, "Brickwork graph", GREEN, GREEN_FACE, "s")
    reference_line(ax, L, curve, ref_label, BLUE)
    for x, y, k in zip(L, depth, d["num_iterations"].astype(int)):
        ax.annotate(str(k), (x, y), textcoords="offset points", xytext=(0, 11),
                    ha="center", fontsize=11, color="#333333")
    power_of_two_ticks(ax, n)


def figure_qrs(csv_name, title, ref, ref_label, out_name, legend_loc):
    fig, ax = new_axes(title, QRS_XLABEL)
    draw_qrs_panel(ax, csv_name, ref, ref_label, title)
    finish(fig, ax, out_name, legend_loc, reverse_legend=True)


def figure_qrs_grid(panels, ref, ref_label, out_name):
    fig, axes = plt.subplots(2, 2, figsize=(12.4, 9.6), sharey=True)
    for k, (ax, (title, csv_name)) in enumerate(zip(axes.flat, panels)):
        style_axes(ax, title, QRS_XLABEL, "Depth" if k % 2 == 0 else None)
        draw_qrs_panel(ax, csv_name, ref, ref_label, f"{out_name} {title}")
    finish_grid(fig, axes, out_name)


def qrs_inference_ref(L):
    return 1.0e4 * np.sqrt(L) * np.log(L)


def qrs_training_ref(L):
    return 1.0e4 * L**2 * np.log(L)


def main():
    OUT.mkdir(exist_ok=True)
    figure_qft()
    figure_hhl()
    figure_hhl_families()
    # Constants unchanged from the published Fig. 6, F13 and F14.
    figure_qrs(
        "experiments_qrs_no_db_one_match.csv",
        "B-QRS: Blind Inference",
        qrs_inference_ref,
        r"$c_2 \cdot \sqrt{L}\,\log L$",
        "qrs_QRS_inference_scaling_fb_SINGLE.png",
        "center right",
    )
    figure_qrs(
        "experiments_qrs_full_one_match.csv",
        "B-QRS: Blind Inference + Blind Training",
        qrs_training_ref,
        r"$c_2 \cdot L^2\,\log L$",
        "qrs_QRS_WITH_db_scaling_fb_SINGLE.png",
        "upper left",
    )
    figure_qrs_grid(
        [
            ("With database, single match", "experiments_qrs_full_one_match.csv"),
            ("With database, no match", "experiment_qrs_full_no_matching_element.csv"),
            ("With database, subset matches", "experiment_qrs_full_subset_grover.csv"),
            ("With database, duplicate matches", "experiment_qrs_full_one_match_duplicates.csv"),
        ],
        qrs_training_ref,
        r"$c_2 \cdot L^2\,\log L$",
        "qrs_qrs_with_db_L_no_decomp.png",
    )
    figure_qrs_grid(
        [
            ("Inference, single match", "experiments_qrs_no_db_one_match.csv"),
            ("Inference, no match", "experiment_qrs_no_db_no_matching_element.csv"),
            ("Inference, subset matches", "experiment_qrs_no_db_subset_grover.csv"),
            ("Inference, duplicate matches", "experiment_qrs_no_db_one_match_duplicates.csv"),
        ],
        qrs_inference_ref,
        r"$c \cdot \sqrt{L}\,\log L$",
        "qrs_qrs_no_db_no_decomp.png",
    )


if __name__ == "__main__":
    main()
