import os, csv, math, numpy as np

from numpy.f2py.capi_maps import c2capi_map
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator
from scipy.sparse import diags
import scipy as sp

import brickwork_transpiler.utils as bw_utils
from brickwork_transpiler import brickwork_transpiler, circuits


def _make_hhl_solver():
    """Create the optional HHL solver without importing removed Qiskit APIs."""
    try:
        from linear_solvers import HHL
    except ImportError as exc:
        raise ImportError(
            "HHL experiments require the optional external "
            "`quantum_linear_solvers` package."
        ) from exc

    try:
        return HHL()
    except TypeError as exc:
        raise RuntimeError(
            "The installed `quantum_linear_solvers` package expects legacy "
            "Qiskit QuantumInstance APIs. Use a version compatible with "
            "Qiskit 2.x or keep this experiment on a separate legacy env."
        ) from exc


# ---------------------------------------------------------------------------
# CSV helper – identical header to your QFT experiment
# ---------------------------------------------------------------------------
def get_writer(file_name: str,
               file_path: str = "src/ubqc_brickwork_transpiler/experiments/data/output_data/"):

    header = ["decomposed_depth", "transpiled_depth", "original_depth",
              "num_gates_original", "num_gates_transpiled", "N", "kappa", "s_sparsity", "d_avg"]
    full_path = os.path.join(file_path, file_name)

    os.makedirs(file_path, exist_ok=True)
    if not os.path.isfile(full_path):
        with open(full_path, "w", newline="") as fh:
            csv.writer(fh).writerow(header)

    return bw_utils.BufferedCSVWriter(full_path, header)

# # ---------------------------------------------------------------------------
# # Utility: build a small-κ, Hermitian, 2^n × 2^n matrix
# # ---------------------------------------------------------------------------
# def make_well_conditioned_matrix(num_qubits: int, kappa_target: float = 1.5):
#     """
#     Returns A_n = U D U^† with spectrum in [1, kappa_target]
#     so that κ(A_n) ≈ kappa_target and dimension = 2**num_qubits.
#     """
#     dim = 1 << num_qubits                         # 2**num_qubits
#     # Diagonal spectrum between 1 and kappa_target
#     evals = np.linspace(1.0, kappa_target, dim)
#     D = np.diag(evals)
#
#     # Random unitary via QR of a complex Ginibre matrix
#     X = (np.random.randn(dim, dim) +
#          1j * np.random.randn(dim, dim)) / math.sqrt(2.0)
#     Q, _ = np.linalg.qr(X)                        # unitary Q
#     A = Q @ D @ Q.conj().T
#     # Ensure exactly Hermitian (numerical precision)
#     A = (A + A.conj().T) / 2.0
#     return A, evals

import numpy as np
import math
from typing import Tuple

# ---------------------------------------------------------------------------
# Simplest HHL-friendly matrix:
#   - A0 = tridiagonal Laplacian on a path (open chain): s = 3
#   - Positive definite (no zero mode), Hermitian
#   - Rescaled so spec(A) ⊂ [1, kappa_target]
#   - Returns (A_dense, evals) to match your current interface
# ---------------------------------------------------------------------------
def make_well_conditioned_matrix(num_qubits: int,
                                 kappa_target: float = 1.5) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build an s=3 sparse Hermitian A of size N=2**num_qubits, with spectrum in [1, kappa_target].

    We use the path-graph Laplacian with open boundaries (tridiagonal Toeplitz):
        A0 = 2 I - T - T^T
    whose eigenvalues are known in closed form:
        λ_j(A0) = 2 - 2 cos(π j / (N+1)),   j = 1..N  (all > 0)

    We then map [λ_min, λ_max] -> [1, kappa_target] via A = a*A0 + b*I.
    """
    N = 1 << num_qubits  # matrix dimension = 2**num_qubits

    # --- build tridiagonal A0 (dense for simplicity; keep s=3 structure) ---
    A0 = np.zeros((N, N), dtype=float)
    np.fill_diagonal(A0, 2.0)
    i = np.arange(N - 1)
    A0[i, i + 1] = -1.0
    A0[i + 1, i] = -1.0
    # (Open chain: no wrap-around; ensures positive definiteness.)

    # --- closed-form eigen-extrema for A0 on a path graph ---
    # λ_min = 2 - 2 cos(π/(N+1))
    # λ_max = 2 - 2 cos(π N/(N+1)) = 2 + 2 cos(π/(N+1))
    theta = math.pi / (N + 1.0)
    lam_min = 2.0 - 2.0 * math.cos(theta)
    lam_max = 2.0 + 2.0 * math.cos(theta)

    # --- affine rescaling A = a*A0 + b*I so that spec(A) ⊂ [1, kappa_target] ---
    if abs(lam_max - lam_min) < 1e-15:
        # Degenerate (won't happen here), just return identity
        A = np.eye(N, dtype=float)
        evals = np.ones(N, dtype=float)
        return A, evals

    a = (kappa_target - 1.0) / (lam_max - lam_min)
    b = 1.0 - a * lam_min

    A = a * A0 + b * np.eye(N, dtype=float)

    # (Optional) eigenvalues if you want to log them quickly without eig():
    j = np.arange(1, N + 1, dtype=float)
    evals0 = 2.0 - 2.0 * np.cos(math.pi * j / (N + 1.0))
    evals = a * evals0 + b

    return A, evals


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------
def experiment_hhl_transpilation(max_qubits: int = 5):
    """
    Builds and transpiles HHL circuits for 1 … max_qubits system qubits.
    Results saved to experiments_hhl.csv in the same format as QFT data.
    """
    filename = "experiments_hhl.csv"
    writer   = get_writer(filename)

    for n in range(2, max_qubits + 1):

        from linear_solvers.matrices import TridiagonalToeplitz
        # ---- 1) Well-conditioned tridiagonal Toeplitz (κ constant in n) ----
        # Choose a > 2|b|, e.g., a=1, b=-1/6 -> κ = (a+2|b|)/(a-2|b|) = 2
        # A_circuit = TridiagonalToeplitz(
        #     num_state_qubits=n,
        #     main_diag=1.0,
        #     off_diag=-1.0 / 6.0,
        #     trotter_steps=2,  # increase if you need tighter simulation accuracy
        #     # evolution_time=1.0,   # default okay; lower for a smaller Trotter error
        #     name=f"tridi_{n}"
        # )

        # ---- 2) Efficient |b> state-prep: O(n) gates, not O(N) data loading ----
        # Option A: uniform superposition |b> = H^{⊗ n} |0...0>
        # b_prep = QuantumCircuit(n, name=f"b_uniform_{n}")
        # b_prep.h(range(n))

        import numpy as np

        # def make_hpd_with_condition(N: int, kappa: float = 10.0, seed: int | None = 0) -> np.ndarray:
        #     """
        #     Build a dense Hermitian Positive Definite A with spectrum in [1/kappa, 1].
        #     This avoids kappa=inf in HHL and preserves non-1D connectivity.
        #     """
        #     rng = np.random.default_rng(seed)
        #     # Random orthonormal basis Q via QR
        #     M = rng.normal(size=(N, N))
        #     Q, _ = np.linalg.qr(M)
        #     # Choose eigenvalues in [1/kappa, 1]
        #     eigs = rng.uniform(low=1.0 / kappa, high=1.0, size=N)
        #     D = np.diag(eigs)
        #     A = Q @ D @ Q.T
        #     # Symmetrize to kill numeric drift
        #     A = 0.5 * (A + A.T)
        #     return A

        import scipy.sparse as sp


        def log_band_hpd(
                N: int,
                kappa: float = 10.0,
                seed: int | None = 0,
                max_offset: int | None = None,
                off_diag_scale: float = 0.1,
        ) -> np.ndarray:
            """
            Generate an N x N Hermitian Positive Definite matrix with log-bandwidth sparsity.

            Structure:
                - Each row has nonzeros on the diagonal and at offsets up to log(N).
                - This keeps sparsity ~ O(log N).
                - The nonzeros at distance O(log N) cause non-adjacent CX gates when transpiled
                  on 1D/brickwork layouts, leading to ~ (log N)^2 depth scaling.

            Args:
                N: dimension of the matrix (must match 2^n for HHL).
                kappa: target condition number scale (approximate).
                seed: RNG seed.
                max_offset: if not None, cap the off-diagonal distance.
                off_diag_scale: magnitude scale for off-diagonal entries.

            Returns:
                A: (N,N) numpy.ndarray, dense Hermitian PD matrix.
            """
            rng = np.random.default_rng(seed)
            L = int(np.log2(N)) if max_offset is None else min(int(np.log2(N)), max_offset)

            A = np.zeros((N, N), dtype=float)

            # Fill symmetric off-diagonals up to distance L
            for k in range(1, L + 1):
                vals = off_diag_scale * rng.uniform(-1.0, 1.0, size=N - k)
                A[np.arange(N - k), np.arange(k, N)] = vals
                A[np.arange(k, N), np.arange(N - k)] = vals

            # Strict diagonal dominance to ensure positive definiteness
            row_sums = np.sum(np.abs(A), axis=1)
            diag = rng.uniform(low=1.0 / kappa, high=1.0, size=N)
            A[np.arange(N), np.arange(N)] = diag + row_sums + 1e-3

            # Normalize spectrum so max eigenvalue ~ 1
            lam_max = np.linalg.norm(A, 2)
            A /= lam_max

            return A

        # ----------------- EXAMPLE USAGE WITH HHL -----------------
        N = 1 << n  # dimension
        kappa_target = 8.0  # well-conditioned to keep HHL happy
        print("N: ", N)

        # print("crating matrix")
        # A = make_hpd_withn(N, kappa=kappa_target, seed=42)
        # A = log_band_matrix(N, kappa_target)
        # print("done")
        # A_circuit = log_band_hpd(N, kappa=kappa_target, seed=42)
        #s
        # # Prepare a normalized |b> (structured or random)
        # # b_prep = np.random.rand(N)
        # # b_prep = b_prep / np.linalg.norm(b_prep)
        # b_prep = QuantumCircuit(n, name=f"b_uniform_{n}")
        # b_prep.h(range(n))
        #
        # # If your HHL requires real input, A is already real-symmetric.
        # # If it needs Hermitian complex, you can cast to complex: A = A.astype(complex)
        #
        # # Qiskit-style call (adjust import/instance names to your environment):
        # # from qiskit.algorithms.linear_solvers.hhl import HHL
        # # hhl = HHL(quantum_instance=qinstance)
        # # circ = hhl.construct_circuit(A, b_prep)
        #
        # # ---- 3) Build HHL circuit using circuit-based rhs preparation ----
        # hhl = HHL(quantum_instance=qinstance)
        # print("making circ")
        # circ = hhl.construct_circuit(A, b_prep)
        # print("circ made")

        # Efficient |b> prep (uniform superposition)
        # b_circ = QuantumCircuit(n)
        # b_circ.h(range(n))

        # Build log-bandwidth HPD matrix
        # A = log_band_hpd(N, kappa=8.0, seed=42) # NOT LOG

        # build a tridiagonal Laplacian matrix (s=3 sparse)
        # diag = 2 * np.ones(N)
        # off = -1 * np.ones(N - 1)
        # A = diags([off, diag, off], [-1, 0, 1], format="csr").toarray().astype(np.complex128) NOT LOG

        # convert to dense (for Operator)
        # A = A_sparse.toarray()x

        # wrap as a Qiskit Operator

        # Construct HHL circuit
        # hhl = HHL(quantum_instance=qinstance)
        # circ = hhl.construct_circuit(A, b_circ)

        # # 1) Generate well-conditioned matrix A_n and normalised |b>
        # # A, evals = make_well_conditioned_matrix(n)
        # b    = np.random.rand(1 << n)
        # b    = b / np.linalg.norm(b)
        #
        # # 2) Build HHL circuit
        # from linear_solvers.matrices import TridiagonalToeplitz
        #
        # # n = number of system qubits
        # A_circuit = TridiagonalToeplitz(n, main_diag=2.0, off_diag=1.0, trotter_steps=2)  # s=3, structured NOT LOG
        # A_circuit = TridiagonalToeplitz(
        #     num_state_qubits=n,
        #     main_diag=1.0,
        #     off_diag=-1.0 / 6.0,
        #     trotter_steps=2
        # )
        #
        # pip install networkx scipy   LAATSTE
        import networkx as nx, scipy.sparse as sp
        d, alpha =  2, 1.0  # N=2^n, degree d; ensure d*(2^n) is even
        A_circuit = sp.eye(N, format="csr") + alpha * nx.normalized_laplacian_matrix(
            nx.random_regular_graph(d, N, seed=0))

        A_circuit = A_circuit.toarray()

        # A_circuit = (lambda B: (B.T @ B + 1e-9 * sp.eye(N)).tocsr())(sp.random(N, N, density=0.05, format="csr"))

        # A_circuit = A_circuit.toarray()
        print("matrix made")

        b_prep = QuantumCircuit(n, name=f"b_uniform_{n}")
        b_prep.h(range(n))
        # #
        # from scipy import sparse
        # A = sparse.random(N, N, density=0.05, format='csr')
        # A = (A + A.T) / 2 + sp.eye(N, N) # Hermitian, non-1D
        # A = A.toarray()

        # print(A)
        # sp.csr_matrix(density=0.05)

        # hhl   = HHL(quantum_instance=qinstance)
        # circ  = hhl.construct_circuit(A_circuit, b_circ)
        #
        #
        # print(circ.count_ops())

        from qiskit import transpile

        # 1) Build your circuit
        hhl = _make_hhl_solver() # 1/m for testing width cost
        circ = hhl.construct_circuit(A_circuit, b_prep)

        # circ = circuits.QPE(N)

        # circ.draw(output='mpl',
        #                    fold=40,
        #                    style="iqp"
        #                    )
        print("circ made")

        # 2) Expand all algorithmic boxes (QPE, etc.)
        # circ_expanded = circ.decompose(reps=10)  # reps high enough to fully open nested boxes

        # 3) Transpile to a basis that preserves the gates you want to count
        #    - single-qubit: rz, sx, x (the standard U = Rz-Sx-Rz set)
        #    - two-qubit: cx
        #    - keep higher-level: cp, mcx  (so they don't get lowered to many CXs)
        # tcirc = transpile(
        #     circ,
        #     basis_gates=['rz', 'rx', 'sx', 'x', 'H', 'cx', 'cp', 'mcx', 'mcu'],
        #     optimization_level=0
        # )
        #
        # tcirc.draw(output='mpl',
        #                 fold=40,
        #                 style="iqp")
        #
        # # 4) Count and clean
        # counts = tcirc.count_ops()
        # for k in ('measure', 'barrier', 'reset', 'delay', 'global_phase'):
        #     counts.pop(k, None)
        #
        # print("Gate counts (current basis):")
        # print(sum(counts.values()))


        # continue
        # # 3) Brickwork transpilation

        instr_mat = brickwork_transpiler.transpile(
            circ,
            routing_method="sabre",
            layout_method="sabre",
            return_mat=True,
            file_writer=writer,
            with_ancillas=True,
            plot_decomposed=False,
            opt=1
        )

        # 4) Collect metrics
        writer.set("original_depth",      circ.depth())
        writer.set("transpiled_depth",    len(instr_mat[0]))
        writer.set("N",    2**n)
        # kappa = float(np.max(evals) / np.min(evals))
        # writer.set("kappa", kappa)
        writer.set("s_sparsity", 3)
        writer.flush()

    plot_single_hhl_dataset("hhl_transpilation_cost_experiment_plot_with_ancillae")


import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D



def plot_single_hhl_dataset(name_of_plot: str = "hhl_default_laplacian.png"):
    """
    Visualise brickwork–transpilation cost for the HHL circuits stored in
    experiments_hhl.csv.

    Required CSV columns:
        decomposed_depth, transpiled_depth, N

    Three curves are shown:
        • decomposed circuit depth
        • brickwork-transpiled depth
        • c·log²(n)                      ← NEW
    plus the original reference c·log³(n).

    The x-axis is n = 2^N (powers of two displayed as clean 10^k ticks).
    """


    # --------------------------------------------------------------------
    # Load data
    # --------------------------------------------------------------------
    base_dir = "src/ubqc_brickwork_transpiler/experiments/data/output_data/"
    filename = "experiments_hhl.csv"


    df = pd.read_csv(os.path.join(base_dir, filename))
    df = df[df["N"] > 0]

    # --- inputs already loaded above this block ---
    # df with columns: decomposed_depth, transpiled_depth, N
    # -----------------------------------------------------

    # Interpret CSV's N as exponent n; avoid forming huge integers
    n = df["N"].to_numpy(dtype=float)  # e.g. [2,4,8,16,...]
    N = np.power(2, n)
    logN = np.log(N)  # log(2**n)
    Nsize = np.exp(logN)  # equals 2**n, in float

    decomposed_depth = df["num_gates_original"].to_numpy(dtype=float)
    transpiled_depth = df["transpiled_depth"].to_numpy(dtype=float)

    # Reference curves: choose constants, match names to powers
    c_log2, c_log3 = 15000.0, 10000.0 #10k to
    ref_log2 = c_log2 * (logN)
    ref_log3 = c_log3 * (logN**3)

    # --------------------------------------------------------------------
    # Styling
    # --------------------------------------------------------------------
    colours = {"decomposed_depth": "orange",
               "transpiled_depth": "green",
               "ref_log2": "red",
               "ref_log3": "blue"}
    markers = {"decomposed_depth": "s",
               "transpiled_depth": "^"}
    labels = {"decomposed_depth": "Decomposed depth",
              "transpiled_depth": "Brickwork depth",
              "ref_log2": r"$c_{1}\,\cdot\log N$",
              "ref_log3": r"$c_{2}\,\cdot\log^{2} N$"}

    mark_every = max(1, len(Nsize) // 8)

    # Robust bounds for log-scale: finite & positive only
    y_all = np.r_[decomposed_depth, transpiled_depth, ref_log2, ref_log3].astype(float)
    y_all = y_all[np.isfinite(y_all) & (y_all > 0)]
    if y_all.size == 0:
        raise ValueError("No positive finite y-values for log-scale.")
    y_min = max(1.0, y_all.min())
    y_max = y_all.max() * 1.3
    if y_min == y_max:  # degenerate case padding
        pad = 0.05 * y_min
        y_min, y_max = y_min - pad, y_max + pad

    # --------------------------------------------------------------------
    # Figure
    # --------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8, 6))

    for key in ("decomposed_depth", "transpiled_depth"):
        ax.plot(Nsize, locals()[key],
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

    # Reference curves (no markers)
    ax.plot(Nsize, ref_log3,
            label=labels["ref_log3"],
            color=colours["ref_log3"],
            linestyle="--",
            linewidth=2.4,
            alpha=0.9)
    ax.plot(Nsize, ref_log2,
            label=labels["ref_log2"],
            color=colours["ref_log2"],
            linestyle="-.",
            linewidth=2.4,
            alpha=0.9)

    print("y_min=", y_min, "y_max=", y_max)
    print("finite?", np.isfinite([y_min, y_max]))
    print("positive?", (y_min > 0, y_max > 0))

    # --------------------------------------------------------------------
    # Axes and legend
    # --------------------------------------------------------------------
    ax.set_title("HHL Transpilation Cost", fontsize=15, fontweight="bold")
    ax.set_xlabel(r"Problem size $N = 2^{n}$", fontsize=13)
    ax.set_ylabel("Depth (log scale)", fontsize=13)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_ylim(y_min, y_max)

    # Clean powers-of-10 ticks on N=2^n (x-axis)
    ax.xaxis.set_major_locator(mticker.LogLocator(base=10.0))
    ax.xaxis.set_major_formatter(mticker.LogFormatterMathtext(base=10.0))
    ax.xaxis.set_minor_locator(mticker.NullLocator())

    ax.tick_params(axis="both", which="major", labelsize=12)
    ax.grid(axis="y", which="both", linestyle=":", alpha=0.35)

    legend_handles = [
        Line2D([0], [0], color=colours["decomposed_depth"],
               marker=markers["decomposed_depth"], linestyle="-",
               markersize=8, label=labels["decomposed_depth"],
               markeredgecolor="white", markeredgewidth=1.7),
        Line2D([0], [0], color=colours["transpiled_depth"],
               marker=markers["transpiled_depth"], linestyle="-",
               markersize=8, label=labels["transpiled_depth"],
               markeredgecolor="white", markeredgewidth=1.7),
        Line2D([0], [0], color=colours["ref_log2"], linestyle="-.",
               linewidth=3, label=labels["ref_log2"]),
        Line2D([0], [0], color=colours["ref_log3"], linestyle="--",
               linewidth=3, label=labels["ref_log3"]),
    ]
    ax.legend(handles=legend_handles, fontsize=13, frameon=False, loc="best")

    plt.tight_layout()
    plt.savefig(f"images/plots/hhl_{name_of_plot}", dpi=300, bbox_inches="tight")
    plt.show()
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def plot_scaling_with_m_as_width(
    name_prefix="hhl_scaling_m_is_width",
    base_dir="src/ubqc_brickwork_transpiler/experiments/data/output_data/",
    filename="experiment_hhl_toeplitz_d_avf_opt0.csv",
    depth_key="transpiled_depth",
    gates_key="num_gates_original",  # or "num_gates_transpiled"
    d_avg_key="d_avg"
):
    """
    Assumptions:
      - width := m := log2(N), stored as column N (we set m = float(N))
      - bricks proxy B := depth * m (no fill-factor modeling)
      - primary, width-invariant metric: yD = depth / gates
      - bricks-normalized ratio yB = B/(m*gates) == yD (by construction)
    """
    path = os.path.join(base_dir, filename)
    df = pd.read_csv(path)

    need = ["N", depth_key, gates_key, d_avg_key]
    miss = [c for c in need if c not in df.columns]
    if miss:
        raise ValueError(f"CSV missing columns: {miss}")

    # Filter valid rows
    df = df[(df["N"] > 0) & (df[gates_key] > 0) & (df[d_avg_key] > 0)].copy()
    if df.empty:
        raise ValueError("No valid rows after filtering (need N>0, gates>0, d_avg>0).")

    # Define m as width
    df["m"] = df["N"].astype(float)          # width = m = log2(N) as per your convention
    df.sort_values("m", inplace=True)

    # Extract arrays
    D     = df[depth_key].astype(float).to_numpy()
    G     = df[gates_key].astype(float).to_numpy()
    m     = df["m"].to_numpy()
    davg  = df[d_avg_key].astype(float).to_numpy()

    # Metrics
    yD = D / G                 # depth per gate (primary, width-invariant)
    B  = D * m                 # bricks proxy using width=m
    yB = B / (m * G)           # equals yD by construction; kept for clarity

    # --- Plots
    os.makedirs("images/plots", exist_ok=True)

    # 1) yD vs m
    plt.figure(figsize=(7,4))
    plt.plot(m, yD, "s-", lw=2)
    plt.xlabel(r"$m=\log_2 N$ (width)")
    plt.ylabel(r"Depth / gate")
    plt.title("Depth per gate vs width m")
    plt.grid(True, linestyle=":", alpha=0.35)
    plt.tight_layout()
    out1 = f"images/plots/{name_prefix}_yD_vs_m.png"
    plt.savefig(out1, dpi=300, bbox_inches="tight"); plt.show()

    # 2) yD vs d_avg
    order = np.argsort(davg)
    plt.figure(figsize=(7,4))
    plt.plot(davg[order], yD[order], "o-", lw=2)
    plt.xlabel(r"$d_{\mathrm{avg}}$")
    plt.ylabel(r"Depth / gate")
    plt.title(r"Depth per gate vs $d_{\mathrm{avg}}$")
    plt.grid(True, linestyle=":", alpha=0.35)
    plt.tight_layout()
    out2 = f"images/plots/{name_prefix}_yD_vs_davg.png"
    plt.savefig(out2, dpi=300, bbox_inches="tight"); plt.show()

    # 3) d_avg vs m (to show d_avg grows slower than m)
    plt.figure(figsize=(7,4))
    plt.plot(m, davg, "o-", lw=2)
    plt.xlabel(r"$m$")
    plt.ylabel(r"$d_{\mathrm{avg}}$")
    plt.title(r"$d_{\mathrm{avg}}$ vs $m$")
    plt.grid(True, linestyle=":", alpha=0.35)
    plt.tight_layout()
    out3 = f"images/plots/{name_prefix}_davg_vs_m.png"
    plt.savefig(out3, dpi=300, bbox_inches="tight"); plt.show()

    # Optional: sublinearity check ratio
    plt.figure(figsize=(7,4))
    plt.plot(m, davg / m, "^-", lw=2)
    plt.xlabel(r"$m$")
    plt.ylabel(r"$d_{\mathrm{avg}}/m$")
    plt.title(r"Sublinearity check: $d_{\mathrm{avg}}/m$ vs $m$")
    plt.grid(True, linestyle=":", alpha=0.35)
    plt.tight_layout()
    out4 = f"images/plots/{name_prefix}_davg_over_m.png"
    plt.savefig(out4, dpi=300, bbox_inches="tight"); plt.show()

    # --- Quick correlations (no fits)
    def corr(x, z):
        sx, sz = np.std(x), np.std(z)
        return np.nan if sx==0 or sz==0 else np.corrcoef(x, z)[0, 1]

    print("Saved:")
    for p in [out1, out2, out3, out4]:
        print("  ", p)
    print(f"corr(yD, m)       = {corr(yD, m):.3f}")
    print(f"corr(yD, d_avg)   = {corr(yD, davg):.3f}")

    # 1) Spearman (monotonicity)
    def spearman(x, y):
        xr = pd.Series(x).rank(method="average").to_numpy()
        yr = pd.Series(y).rank(method="average").to_numpy()
        sx, sy = np.std(xr), np.std(yr)
        return np.nan if sx == 0 or sy == 0 else np.corrcoef(xr, yr)[0, 1]

    rho_m = spearman(m, yD)
    rho_dav = spearman(davg, yD)
    print(f"Spearman(yD, m)     = {rho_m:.3f}")
    print(f"Spearman(yD, d_avg) = {rho_dav:.3f}")

    # 2) Partial correlations (residualize)
    def partial_corr(x, y, z):
        # corr(x,y | z): regress out z linearly (minimal assumption)
        z1 = np.c_[np.ones_like(z), z]
        beta_x = np.linalg.lstsq(z1, x, rcond=None)[0]
        beta_y = np.linalg.lstsq(z1, y, rcond=None)[0]
        rx = x - z1 @ beta_x
        ry = y - z1 @ beta_y
        sx, sy = np.std(rx), np.std(ry)
        return np.nan if sx == 0 or sy == 0 else np.corrcoef(rx, ry)[0, 1]

    pcorr_yD_dav_given_m = partial_corr(davg, yD, m)  # does d_avg explain yD beyond m?
    pcorr_yD_m_given_dav = partial_corr(m, yD, davg)  # does m explain yD beyond d_avg?
    print(f"Partial corr(yD, d_avg | m) = {pcorr_yD_dav_given_m:.3f}")
    print(f"Partial corr(yD, m | d_avg) = {pcorr_yD_m_given_dav:.3f}")

    # 3) Simple permutation test for corr significance
    rng = np.random.default_rng(0)
    def perm_test_corr(x, y, iters=10000):
        obs = np.corrcoef(x, y)[0, 1]
        cnt = 0
        for _ in range(iters):
            y_perm = rng.permutation(y)
            if abs(np.corrcoef(x, y_perm)[0, 1]) >= abs(obs):
                cnt += 1
        return (cnt + 1) / (iters + 1)

    p_m = perm_test_corr(m, yD, iters=5000)
    p_dav = perm_test_corr(davg, yD, iters=5000)
    print(f"Permutation p-value corr(yD, m):     {p_m:.4g}")
    print(f"Permutation p-value corr(yD, d_avg): {p_dav:.4g}")

    # --- add/replace this whole "Model comparison" block at the end of your function ---

    # =========================
    # Model comparison
    # =========================
    # Baselines to test:
    #   1) Constant-only (original complexity O(1)): yD ~ a
    #   2) Linear in m:  yD ~ a + b*m
    #   3) Linear in d_avg: yD ~ a + b*d_avg
    # Optional:
    #   4) Linear in ln(d_avg): yD ~ a + b*ln(d_avg)  (distance-driven logarithmic overhead)

    def fit_constant_and_scores(y):
        # Intercept-only OLS: y ~ a
        n = len(y)
        X1 = np.ones((n, 1))
        beta, _, _, _ = np.linalg.lstsq(X1, y, rcond=None)  # beta = [a]
        yhat = X1 @ beta
        resid = y - yhat
        ss_res = np.sum(resid ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
        k = 1  # intercept only
        n_eff = n
        adj_r2 = 1 - (1 - r2) * (n_eff - 1) / (n_eff - k) if n_eff > k else np.nan
        sigma2 = ss_res / n_eff
        aic = n_eff * np.log(sigma2) + 2 * k
        bic = n_eff * np.log(sigma2) + k * np.log(n_eff)
        # LOOCV for intercept-only is just MSE with a leverage correction (here leverage = 1/n)
        h = 1.0 / n_eff
        loocv_resid = resid / (1 - h)
        loocv_rmse = np.sqrt(np.mean(loocv_resid ** 2))
        return {"beta": beta, "r2": r2, "adj_r2": adj_r2, "aic": aic, "bic": bic, "loocv_rmse": loocv_rmse}

    def fit_linear_and_scores(X, y):
        # X: (n,) or (n,1). Adds intercept internally.
        X = np.asarray(X).reshape(-1, 1)
        n = X.shape[0]
        X1 = np.c_[np.ones(n), X]
        beta, _, _, _ = np.linalg.lstsq(X1, y, rcond=None)
        yhat = X1 @ beta
        resid = y - yhat
        ss_res = np.sum(resid ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
        k = X1.shape[1]  # parameters incl. intercept
        n_eff = n
        adj_r2 = 1 - (1 - r2) * (n_eff - 1) / (n_eff - k) if n_eff > k else np.nan
        sigma2 = ss_res / n_eff
        aic = n_eff * np.log(sigma2) + 2 * k
        bic = n_eff * np.log(sigma2) + k * np.log(n_eff)
        # LOOCV RMSE via hat matrix
        XtX_inv = np.linalg.inv(X1.T @ X1)
        H = (X1 @ XtX_inv) @ X1.T
        h = np.clip(np.diag(H), 1e-12, 1 - 1e-12)
        loocv_resid = resid / (1 - h)
        loocv_rmse = np.sqrt(np.mean(loocv_resid ** 2))
        return {"beta": beta, "r2": r2, "adj_r2": adj_r2, "aic": aic, "bic": bic, "loocv_rmse": loocv_rmse}

    model_const = fit_constant_and_scores(yD)  # yD ~ a
    model_m = fit_linear_and_scores(m, yD)  # yD ~ a + b*m
    model_dav = fit_linear_and_scores(davg, yD)  # yD ~ a + b*d_avg

    # Optional logarithmic predictor (enable if meaningful for your theory)
    with np.errstate(divide="ignore"):
        log_davg = np.log(davg)
    # Filter out -inf if present (shouldn't occur after your positive filtering, but be safe)
    mask_log = np.isfinite(log_davg)
    model_ln_dav = fit_linear_and_scores(log_davg[mask_log], yD[mask_log]) if mask_log.all() else None

    print("\n=== Model comparison ===")

    def _fmt(tag, s):
        return (f"{tag:18s} | "
                f"R^2={s['r2']:.3f}, adjR^2={s['adj_r2']:.3f}, "
                f"AIC={s['aic']:.2f}, BIC={s['bic']:.2f}, LOOCV-RMSE={s['loocv_rmse']:.4g}")

    print(_fmt("Constant (O(1))", model_const))
    print(_fmt("Linear in m", model_m))
    print(_fmt("Linear in d_avg", model_dav))
    if model_ln_dav is not None:
        print(_fmt("Linear in ln d_avg", model_ln_dav))

    # Simple verdicts based on adj-R^2 (higher is better) and LOOCV-RMSE (lower is better)
    candidates = {
        "Constant (O(1))": model_const,
        "Linear in m": model_m,
        "Linear in d_avg": model_dav,
    }
    if model_ln_dav is not None:
        candidates["Linear in ln d_avg"] = model_ln_dav

    # Rank by adj-R^2 then LOOCV-RMSE
    best = min(
        candidates.items(),
        key=lambda kv: (-np.nan_to_num(kv[1]["adj_r2"], nan=-np.inf),
                        np.nan_to_num(kv[1]["loocv_rmse"], nan=np.inf))
    )
    print(f"Verdict: {best[0]} provides the best baseline by adj-R^2/LOOCV-RMSE.")

    # Optional: nested F-test constant vs. linear (useful if you want a significance test)
    def nested_F_test(y, X):
        # Tests whether slope adds explanatory power over constant-only.
        n = len(y)
        X1 = np.c_[np.ones(n), X.reshape(-1, 1)]
        beta1, _, _, _ = np.linalg.lstsq(X1, y, rcond=None)
        yhat1 = X1 @ beta1
        ss_res1 = np.sum((y - yhat1) ** 2)
        # constant-only
        ybar = np.mean(y)
        ss_res0 = np.sum((y - ybar) ** 2)  # since constant-only fitted mean
        df_num = 1
        df_den = n - 2
        if df_den <= 0: return np.nan, np.nan
        F = ((ss_res0 - ss_res1) / df_num) / (ss_res1 / df_den)
        # p-value from F(1, n-2); we avoid SciPy, so no exact p here
        return F, df_den

    F_m, df_m = nested_F_test(yD, m)
    F_d, df_d = nested_F_test(yD, davg)
    print(f"Nested F (const vs linear in m):     F={F_m:.3f}, df_den={df_m}")
    print(f"Nested F (const vs linear in d_avg): F={F_d:.3f}, df_den={df_d}")

    # === Interpretation helpers for log model ===
    if model_ln_dav is not None:
        b_log = model_ln_dav["beta"][1]
        delta_per_doubling = b_log * np.log(2.0)  # change in yD when d_avg doubles
        print(f"\nEffect size: ΔyD per doubling of d_avg ≈ {delta_per_doubling:.4g}")

    # === Multi-predictor model: yD ~ 1 + ln(d_avg) + m ===
    def fit_multi_and_infer(Xcols, y):
        # Xcols: list of 1D arrays (same length), no intercept; we add it here.
        X = np.column_stack(Xcols)
        n, p = X.shape
        X1 = np.c_[np.ones(n), X]
        # OLS
        beta, _, _, _ = np.linalg.lstsq(X1, y, rcond=None)
        yhat = X1 @ beta
        resid = y - yhat
        ss_res = float(np.dot(resid, resid))
        ss_tot = float(np.dot(y - y.mean(), y - y.mean()))
        r2 = 1.0 - ss_res/ss_tot if ss_tot > 0 else np.nan
        k = p + 1  # parameters incl. intercept
        df = n - k
        adj_r2 = 1 - (1 - r2) * (n - 1) / (n - k) if n > k else np.nan
        sigma2 = ss_res / max(df, 1)
        # Covariance, SEs, t-stats
        XtX_inv = np.linalg.inv(X1.T @ X1)
        cov = sigma2 * XtX_inv
        se = np.sqrt(np.diag(cov))
        tvals = beta / np.where(se>0, se, np.nan)
        # Normal-approx two-sided p-values (OK for moderate/large df)
        from math import erfc, sqrt
        pvals_norm = erfc(np.abs(tvals)/sqrt(2.0))  # ≈ 2*(1-Φ(|t|))
        # IC + LOOCV
        aic = n * np.log(ss_res / n) + 2 * k
        bic = n * np.log(ss_res / n) + k * np.log(n)
        H = (X1 @ XtX_inv) @ X1.T
        h = np.clip(np.diag(H), 1e-12, 1 - 1e-12)
        loocv_resid = resid / (1 - h)
        loocv_rmse = np.sqrt(np.mean(loocv_resid**2))
        return {
            "beta": beta, "se": se, "t": tvals, "p_norm": pvals_norm,
            "r2": r2, "adj_r2": adj_r2, "aic": aic, "bic": bic, "loocv_rmse": loocv_rmse, "df": df
        }

    if model_ln_dav is not None:
        with np.errstate(divide="ignore"):
            log_davg = np.log(davg)
        mask = np.isfinite(log_davg)
        multi = fit_multi_and_infer([log_davg[mask], m[mask]], yD[mask])

        print("\n=== Joint model: yD ~ a + b1*ln(d_avg) + b2*m ===")
        b0, b1, b2 = multi["beta"]
        se0, se1, se2 = multi["se"]
        t0, t1, t2 = multi["t"]
        p0, p1, p2 = multi["p_norm"]
        def _fmt_beta(b, se, t, p):
            return f"{b:.6g}  (SE {se:.3g}, t {t:.3g}, p≈{p:.3g})"
        print(f"Intercept: { _fmt_beta(b0, se0, t0, p0) }")
        print(f"b1 [ln d]: { _fmt_beta(b1, se1, t1, p1) }")
        print(f"b2 [m]   : { _fmt_beta(b2, se2, t2, p2) }")
        print(f"R^2={multi['r2']:.3f}, adjR^2={multi['adj_r2']:.3f}, AIC={multi['aic']:.2f}, "
              f"BIC={multi['bic']:.2f}, LOOCV-RMSE={multi['loocv_rmse']:.4g}, df={multi['df']}")
        # Quick verdict on residual width effect:
        if abs(t2) < 2:
            print("Interpretation: conditional on ln(d_avg), residual dependence on m is weak (|t|<~2).")
        else:
            print("Interpretation: m still contributes beyond ln(d_avg) (|t|>=~2).")



def plot_depth_per_gate_vs_m_logfit(
    name_of_plot: str = "hhl_depth_per_gate_vs_m.png",
    base_dir: str = "src/ubqc_brickwork_transpiler/experiments/data/output_data/",
    filename: str = "experiments_hhl.csv",
    depth_key: str = "transpiled_depth",
    gates_key: str = "num_gates_original",   # set to "num_gates_transpiled" if you prefer
    log_base: float = np.e                   # use np.e (natural log) or 2 for log2
):
    """
    Plot (depth / #gates) vs m and fit a logarithm:
        y = depth/gates  ~  a * log(m) + b

    CSV must contain columns:
        - N                  (stores m = log2 problem size)
        - depth_key          (e.g., 'transpiled_depth')
        - gates_key          (e.g., 'num_gates_original' or 'num_gates_transpiled')
    """
    path = os.path.join(base_dir, filename)
    df = pd.read_csv(path)

    # Basic checks and cleanup
    need = {"N", depth_key, gates_key}
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing columns: {missing}")

    df = df[df["N"] > 0].copy()
    df["m"] = df["N"].astype(float)

    # Filter rows with valid gate counts to avoid divide-by-zero
    df = df[df[gates_key].astype(float) > 0].copy()
    if df.empty:
        raise ValueError("No rows with positive gate counts to plot.")

    m = df["m"].to_numpy(dtype=float)
    depth = df[depth_key].to_numpy(dtype=float)
    gates = df[gates_key].to_numpy(dtype=float)

    y = depth / gates                      # depth per gate
    if np.any(~np.isfinite(y)):
        mask = np.isfinite(y)
        m, y = m[mask], y[mask]

    # Logarithmic regressor: z = log_base(m)
    if log_base == 2:
        z = np.log2(m)
    else:
        z = np.log(m)

    # Fit y ≈ a * log(m) + b
    a, b = np.polyfit(z, y, 1)
    y_fit = a * z + b

    # Compute R^2 on the log-fit
    ss_res = np.sum((y - y_fit)**2)
    ss_tot = np.sum((y - y.mean())**2)
    r2 = 1.0 - ss_res/ss_tot if ss_tot > 0 else np.nan

    # Plot
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(m, y, marker="s", linestyle="-", linewidth=2.2, markersize=7,
            label=f"{depth_key}/{gates_key}")
    # Smooth fit curve over m (use same x-scale)
    m_smooth = np.linspace(m.min(), m.max(), 200)
    z_smooth = np.log2(m_smooth) if log_base == 2 else np.log(m_smooth)
    ax.plot(m_smooth, a * z_smooth + b, linestyle="--", linewidth=2.0,
            label=f"Log fit: a·log(m)+b  (a={a:.3g}, b={b:.3g}, R²={r2:.3f})")

    ax.set_title("Depth per gate vs width m with logarithmic fit", fontsize=15, fontweight="bold")
    ax.set_xlabel(r"Width $m=\log_2 N$", fontsize=13)
    ax.set_ylabel(r"Depth / gate", fontsize=13)
    ax.grid(True, linestyle=":", alpha=0.35)
    ax.legend(frameon=False, fontsize=12)
    plt.tight_layout()

    out_path = f"images/plots/{name_of_plot}"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.show()

    base_txt = "ln" if log_base == np.e else f"log{int(log_base)}"
    print(f"Saved {out_path}. Fit: depth/gate ≈ {a:.4g}·{base_txt}(m) + {b:.4g}  (R²={r2:.4f})")

# def plot_hhl_from_multiple_files(name_of_plot="default.png"):
#     """
#     Plot HHL transpilation results from multiple experiment files,
#     showing decomposed depth, transpiled depth, and logN/log²N reference curves.
#
#     Each file is plotted in a separate subplot (two side by side).
#     """
#
#     base_dir = "src/ubqc_brickwork_transpiler/experiments/data/output_data/"
#     file_map = {
#         "HHL experiment: Tridiagonal Toeplitz": "experiment_hhl_toeplize_trotter2_no_opt.csv",
#         "HHL experiment: Normalised Laplacian": "experiment_hhl_d2_laplacian.csv",
#         "HHL experiment: low density matrix": "experiment_hhl_log_sq.csv",
#         r"HHL experiment: inefficient $|b\rangle$": "experiment_hhl_no_eff_b.csv",
#
#     }
#
#     plot_exps = list(file_map.keys())
#
#     data = {}
#     for exp in plot_exps:
#         fname = os.path.join(base_dir, file_map[exp])
#         df = pd.read_csv(fname)
#         df = df[df["N"] > 0]
#
#         n = df["N"].to_numpy(dtype=float)  # exponent values
#         N = np.power(2, n)  # problem size
#         logN = np.log(N)
#
#         data[exp] = {
#             "N": N,
#             "logN": logN,
#             "decomposed_depth": df["num_gates_original"].to_numpy(dtype=float),
#             "transpiled_depth": df["transpiled_depth"].to_numpy(dtype=float),
#         }
#
#     # Styling
#     colours = {
#         "decomposed_depth": "orange",
#         "transpiled_depth": "green",
#         "logN": "red",
#         "log2": "blue",
#     }
#     markers = {
#         "decomposed_depth": "s",
#         "transpiled_depth": "^",
#     }
#     labels = {
#         "decomposed_depth": "Decomposed depth",
#         "transpiled_depth": "Brickwork depth",
#         "logN": r"$c_{1}\,\cdot\log N$",
#         "log2": r"$c_{2}\,\cdot\log^{2} N$",
#     }
#
#     # Scaling constants
#     c1, c2 = 15000.0, 10000.0
#
#     # Global y-axis range
#     all_yvals = []
#     for exp, exp_data in data.items():
#         N = exp_data["N"]
#         logN = exp_data["logN"]
#         all_yvals.extend(exp_data["decomposed_depth"])
#         all_yvals.extend(exp_data["transpiled_depth"])
#         all_yvals.extend(c1 * logN)
#         all_yvals.extend(c2 * logN**2)
#
#     ymin = max(1.0, min(all_yvals))
#     ymax = max(all_yvals) * 1.3
#
#     # Two subplots side by side
#     fig, axs = plt.subplots(1, 2, figsize=(16, 6), sharey=True, constrained_layout=True)
#
#     for idx, exp in enumerate(plot_exps):
#         ax = axs[idx]
#         exp_data = data[exp]
#         N = exp_data["N"]
#         logN = exp_data["logN"]
#
#         # Depth curves
#         for key in ["decomposed_depth", "transpiled_depth"]:
#             ax.plot(
#                 N, exp_data[key],
#                 label=labels[key],
#                 marker=markers[key],
#                 linestyle="-",
#                 color=colours[key],
#                 linewidth=2.7,
#                 markersize=10,
#                 alpha=0.97,
#                 markeredgecolor="white",
#                 markeredgewidth=1.7,
#             )
#
#         # Reference curves
#         ax.plot(N, c1 * logN,
#                 label=labels["logN"],
#                 color=colours["logN"],
#                 linestyle="--", linewidth=2.4, alpha=0.9)
#         ax.plot(N, c2 * (logN**2),
#                 label=labels["log2"],
#                 color=colours["log2"],
#                 linestyle="-.", linewidth=2.4, alpha=0.9)
#
#         # Axis formatting
#         ax.set_title(exp, fontsize=15, fontweight="bold")
#         ax.set_xlabel(r"Problem size $N = 2^{n}$", fontsize=13)
#         ax.set_xscale("log")
#         ax.set_yscale("log")
#         ax.set_ylim(ymin, ymax)
#         ax.xaxis.set_major_locator(mticker.LogLocator(base=10.0))
#         ax.xaxis.set_major_formatter(mticker.LogFormatterMathtext(base=10.0))
#         ax.xaxis.set_minor_locator(mticker.NullLocator())
#         ax.tick_params(axis="both", which="major", labelsize=12)
#         ax.grid(axis="y", which="both", linestyle=":", alpha=0.35)
#
#     axs[0].set_ylabel("Circuit depth (log scale)", fontsize=13)
#
#     # Shared legend
#     legend_elements = [
#         Line2D([0], [0], color=colours["decomposed_depth"], marker=markers["decomposed_depth"],
#                linestyle="-", markersize=10, label=labels["decomposed_depth"],
#                markeredgecolor="white", markeredgewidth=1.7),
#         Line2D([0], [0], color=colours["transpiled_depth"], marker=markers["transpiled_depth"],
#                linestyle="-", markersize=10, label=labels["transpiled_depth"],
#                markeredgecolor="white", markeredgewidth=1.7),
#         Line2D([0], [0], color=colours["logN"], linestyle="--", linewidth=3, label=labels["logN"]),
#         Line2D([0], [0], color=colours["log2"], linestyle="-.", linewidth=3, label=labels["log2"]),
#     ]
#     fig.legend(handles=legend_elements,
#                loc="lower center", ncol=4, fontsize=13, frameon=False,
#                bbox_to_anchor=(0.52, -0.08))
#
#     plt.savefig(f"images/plots/hhl_{name_of_plot}", dpi=300, bbox_inches="tight")
#     plt.show()


def plot_hhl_from_multiple_files(name_of_plot="default_4_thesis.png"):
    """
    Plot HHL transpilation results from multiple experiment files,
    showing decomposed depth, transpiled depth, and logN/log²N/log³N reference curves.

    Each file is plotted in a separate subplot.
    """

    base_dir = "src/ubqc_brickwork_transpiler/experiments/data/output_data/"
    # file_map = {
    #     "HHL experiment: Tridiagonal Toeplitz": "experiment_hhl_toeplize_trotter2_no_opt.csv",
    #     "HHL experiment: Normalised Laplacian": "experiment_hhl_d2_laplacian.csv",
    #     "HHL experiment: Low-Density Hermitian": "experiments_hhl.csv",
    #     r"HHL experiment: Low-Density Hermitian (opt)": "experiment_hhl_dense_unoptimised.csv",
    #
    # }

    file_map = {
        "HHL experiment: Tridiagonal Toeplitz no opt": "experiment_hhl_toeplitz_d_avf_opt0.csv",
        "HHL experiment: Normalised Laplacian no opt": "experiment_hhl_laplacian_opt0_d_avg.csv",
        "HHL experiment: Low-Density Hermitian no opt": "experiment_hhl_sparse_opt0_d_avg.csv",
        r"HHL experiment: Low-Density Hermitian error = 1/m": "experiment_hhl_sparse_one_over_m.csv",

    }

    # Choose which to plot
    plot_exps = list(file_map.keys())

    data = {}
    for exp in plot_exps:
        fname = os.path.join(base_dir, file_map[exp])
        df = pd.read_csv(fname)
        df = df[df["N"] > 0]

        n = df["N"].to_numpy(dtype=float)  # exponent values
        N = np.power(2, n)  # problem size
        logN = np.log(N)

        data[exp] = {
            "N": N,
            "logN": logN,
            "num_gates_original": df["num_gates_original"].to_numpy(dtype=float),
            "transpiled_depth": df["transpiled_depth"].to_numpy(dtype=float),
        }

    # Styling
    colours = {
        "num_gates_original": "orange",
        "transpiled_depth": "green",
        "logN": "red",
        "log2": "blue",
        "log3": "purple",
        "log4": "black",
    }
    markers = {
        "num_gates_original": "s",
        "transpiled_depth": "^",
    }
    labels = {
        "num_gates_original": "Number gates original",
        "transpiled_depth": "Brickwork depth",
        "logN": r"$c_{1}\,\cdot\log N$",
        "log2": r"$c_{2}\,\cdot\log^{2} N$",
        "log3": r"$c_{3}\,\cdot\log^{3} N$",
        "log4": r"$c_{4}\,\cdot\log^{4} N$",
    }

    # Scaling constants for reference curves
    c1, c2, c3 = 15000.0, 8000.0, 3000.0

    # Determine global y-axis limits
    all_yvals = []
    for exp, exp_data in data.items():
        N = exp_data["N"]
        logN = exp_data["logN"]
        all_yvals.extend(exp_data["num_gates_original"])
        all_yvals.extend(exp_data["transpiled_depth"])
        all_yvals.extend(c1 * logN)
        all_yvals.extend(c2 * logN ** 2)
        all_yvals.extend(c3 * logN ** 3)

    ymin = max(1.0, min(all_yvals))
    ymax = max(all_yvals) * 1.3

    # Create subplot grid
    fig, axs = plt.subplots(2, 2, figsize=(16, 13), sharey=True, constrained_layout=True)
    axs = axs.flatten()

    for idx, exp in enumerate(plot_exps):
        ax = axs[idx]
        exp_data = data[exp]
        N = exp_data["N"]
        logN = exp_data["logN"]

        # Main curves
        for key in ["num_gates_original", "transpiled_depth"]:
            ax.plot(
                N, exp_data[key],
                label=labels[key],
                marker=markers[key],
                linestyle="-",
                color=colours[key],
                linewidth=2.7,
                markersize=10,
                alpha=0.97,
                markeredgecolor="white",
                markeredgewidth=1.7,
            )

        # Reference curves
        ax.plot(N, c1 * logN,
                label=labels["logN"],
                color=colours["logN"],
                linestyle="--", linewidth=2.4, alpha=0.9)
        ax.plot(N, c2 * (logN ** 2),
                label=labels["log2"],
                color=colours["log2"],
                linestyle="-.", linewidth=2.4, alpha=0.9)
        ax.plot(N, c3 * (logN ** 3),
                label=labels["log3"],
                color=colours["log3"],
                linestyle=":", linewidth=2.4, alpha=0.9)
        ax.plot(N, c3 * (logN ** 4),
                label=labels["log4"],
                color=colours["log4"],
                linestyle=":", linewidth=2.4, alpha=0.9)

        # Axis formatting
        ax.set_title(exp, fontsize=15, fontweight="bold")
        ax.set_xlabel(r"Problem size $N = 2^{n}$", fontsize=13)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_ylim(ymin, ymax)
        ax.xaxis.set_major_locator(mticker.LogLocator(base=10.0))
        ax.xaxis.set_major_formatter(mticker.LogFormatterMathtext(base=10.0))
        ax.xaxis.set_minor_locator(mticker.NullLocator())
        ax.tick_params(axis="both", which="major", labelsize=12)
        ax.grid(axis="y", which="both", linestyle=":", alpha=0.35)

    axs[0].set_ylabel("Circuit depth (log scale)", fontsize=13)
    axs[2].set_ylabel("Circuit depth (log scale)", fontsize=13)

    # Shared legend
    legend_elements = [
        Line2D([0], [0], color=colours["num_gates_original"], marker=markers["num_gates_original"],
               linestyle="-", markersize=10, label=labels["num_gates_original"],
               markeredgecolor="white", markeredgewidth=1.7),
        Line2D([0], [0], color=colours["transpiled_depth"], marker=markers["transpiled_depth"],
               linestyle="-", markersize=10, label=labels["transpiled_depth"],
               markeredgecolor="white", markeredgewidth=1.7),
        Line2D([0], [0], color=colours["logN"], linestyle="--", linewidth=3, label=labels["logN"]),
        Line2D([0], [0], color=colours["log2"], linestyle="-.", linewidth=3, label=labels["log2"]),
        Line2D([0], [0], color=colours["log3"], linestyle=":", linewidth=3, label=labels["log3"]),
        Line2D([0], [0], color=colours["log4"], linestyle=":", linewidth=3, label=labels["log4"]),
    ]
    fig.legend(handles=legend_elements,
               loc="lower center", ncol=6, fontsize=13, frameon=False,
               bbox_to_anchor=(0.52, -0.03))

    plt.savefig(f"images/plots/hhl_{name_of_plot}", dpi=300, bbox_inches="tight")
    plt.show()

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def plot_hhl_davg_three(files=None, name_of_plot="hhl_davg_3curves.png"):
    """
    Load three experiment CSV files, extract N and d_avg, and
    plot the three d_avg curves on a single log-log figure.
    """
    base_dir = "src/ubqc_brickwork_transpiler/experiments/data/output_data/"

    # Default three files (adjust names as needed)
    if files is None:
        files = {
            "Toeplitz (no opt)": "experiment_hhl_toeplitz_d_avf_opt0.csv",
            "Laplacian (no opt)": "experiment_hhl_laplacian_opt0_d_avg.csv",
            "Sparse Hermitian (no opt)": "experiment_hhl_sparse_opt0_d_avg.csv",
        }

    plt.figure(figsize=(8.5, 6.0))
    for label, fname in files.items():
        df = pd.read_csv(os.path.join(base_dir, fname))

        # Keep only valid rows
        df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=["d_avg"])
        # Accept either 'N' directly or an exponent column 'n'
        if "N" in df.columns:
            N = df["N"].astype(float).to_numpy()
        elif "n" in df.columns:
            N = np.power(2.0, df["n"].astype(float).to_numpy())
        else:
            raise ValueError(f"{fname}: expected 'N' or 'n' column.")

        y = df["d_avg"].astype(float).to_numpy()

        # Sort by N to avoid jagged lines if file order differs
        order = np.argsort(N)
        N, y = N[order], y[order]

        plt.plot(N, y, marker="o", linewidth=2.0, markersize=6, linestyle="--", alpha=0.95, label=label)

    # plt.xscale("log")
    # plt.yscale("log")
    plt.xlabel(r"Matrix dimension 2^n")
    plt.ylabel(r"$d_{\mathrm{avg}}$ (depth)")
    plt.grid(True, which="both", axis="both", linestyle=":", alpha=0.35)
    plt.legend(frameon=False)
    os.makedirs("images/plots", exist_ok=True)
    plt.savefig("images/plots/" + name_of_plot, dpi=300, bbox_inches="tight")
    plt.show()

    #
    # # Interpret the CSV's N as the exponent n
    # n = df["N"].to_numpy(dtype=float)  # e.g., [2, 4, 8, 16, ...]
    # logN = n * np.log(2.0)  # log(2**n) = n*log(2)
    #
    # decomposed_depth = df["decomposed_depth"].to_numpy(dtype=float)
    # transpiled_depth = df["transpiled_depth"].to_numpy(dtype=float)
    #
    # # Reference curves: choose constants for the intended powers of log(N)
    # c_log2 = 300.0
    # # c_log3 = 1000.0
    # ref_log2 = c_log2 * (logN ** 2)  # c · (log N)^2
    # ref_log3 = c_log3 * (logN ** 3)  # c · (log N)^3
    #
    # # c1 = 1000
    # c2 = 100
    #
    # N = np.power(df["N"].to_numpy(dtype=float), 2.0)
    # # N = np.power(2.0, n)  # float64, no overflow here
    # # or better, avoid huge N entirely:
    # logN = np.log(N)  # since log(2**n) = n*log(2)
    # ref_log2 = c1 * (logN ** 2)
    # ref_log3 = c2 * (logN ** 3)

    # # --------------------------------------------------------------------
    # # Styling
    # # --------------------------------------------------------------------
    # colours = {"decomposed_depth": "orange",
    #            "transpiled_depth": "green",
    #            "ref_log2":         "red",
    #            "ref_log3":         "blue"}
    # markers = {"decomposed_depth": "s",
    #            "transpiled_depth": "^"}
    # labels  = {"decomposed_depth": "Decomposed depth",
    #            "transpiled_depth": "Brickwork depth",
    #            "ref_log2":         r"$c_1 \cdot \log N$",
    #            "ref_log3":         r"$c_2 \cdot \log^{2} N$"}
    #
    # mark_every = max(1, len(N) // 8)
    #
    # y_min = max(1, np.min([*decomposed_depth, *transpiled_depth,
    #                        *ref_log2, *ref_log3]))
    # y_max = np.max([*decomposed_depth, *transpiled_depth,
    #                 *ref_log2, *ref_log3]) * 1.3
    #
    # # --------------------------------------------------------------------
    # # Figure
    # # --------------------------------------------------------------------
    # fig, ax = plt.subplots(figsize=(8, 6))
    #
    # for key in ("decomposed_depth", "transpiled_depth"):
    #     ax.plot(N, locals()[key],
    #             label=labels[key],
    #             marker=markers[key],
    #             markevery=mark_every,
    #             linestyle="-",
    #             color=colours[key],
    #             linewidth=2.7,
    #             markersize=8,
    #             alpha=0.97,
    #             markeredgecolor="white",
    #             markeredgewidth=1.7)
    #
    # # Reference curves (no markers)
    # ax.plot(N, ref_log3,
    #         label=labels["ref_log3"],
    #         color=colours["ref_log3"],
    #         linestyle="--",
    #         linewidth=2.4,
    #         alpha=0.9)
    # ax.plot(N, ref_log2,
    #         label=labels["ref_log2"],
    #         color=colours["ref_log2"],
    #         linestyle="-.",
    #         linewidth=2.4,
    #         alpha=0.9)
    #
    # print("y_min=", y_min, "y_max=", y_max)
    # print("finite?", np.isfinite([y_min, y_max]))
    # print("positive?", (y_min > 0, y_max > 0))
    #
    # # --------------------------------------------------------------------
    # # Axes and legend
    # # --------------------------------------------------------------------
    # ax.set_title("HHL Transpilation Cost", fontsize=15, fontweight="bold")
    # ax.set_xlabel(r"Problem size $N = 2^{n}$", fontsize=13)
    # ax.set_ylabel("Depth (log scale)", fontsize=13)
    # ax.set_xscale("log")
    # ax.set_yscale("log")
    # ax.set_ylim(y_min, y_max)
    #
    # # — clean powers-of-10 ticks only —
    # ax.xaxis.set_major_locator(mticker.LogLocator(base=10.0))
    # ax.xaxis.set_major_formatter(mticker.LogFormatterMathtext(base=10.0))
    # ax.xaxis.set_minor_locator(mticker.NullLocator())
    #
    # ax.tick_params(axis="both", which="major", labelsize=12)
    # ax.grid(axis="y", which="both", linestyle=":", alpha=0.35)
    #
    # # Legend (matching markers/linestyles)
    # legend_handles = [
    #     Line2D([0], [0], color=colours["decomposed_depth"],
    #            marker=markers["decomposed_depth"], linestyle="-",
    #            markersize=8, label=labels["decomposed_depth"],
    #            markeredgecolor="white", markeredgewidth=1.7),
    #     Line2D([0], [0], color=colours["transpiled_depth"],
    #            marker=markers["transpiled_depth"], linestyle="-",
    #            markersize=8, label=labels["transpiled_depth"],
    #            markeredgecolor="white", markeredgewidth=1.7),
    #     Line2D([0], [0], color=colours["ref_log2"], linestyle="-.",
    #            linewidth=3, label=labels["ref_log2"]),
    #     Line2D([0], [0], color=colours["ref_log3"], linestyle="--",
    #            linewidth=3, label=labels["ref_log3"]),
    # ]
    # ax.legend(handles=legend_handles, fontsize=13, frameon=False, loc="best")
    #
    # plt.tight_layout()
    # plt.savefig(f"images/qrs/qrs_{name_of_plot}", dpi=300, bbox_inches="tight")
    # plt.show()
