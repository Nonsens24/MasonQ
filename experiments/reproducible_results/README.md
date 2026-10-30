# Reproducible results: "On the Computational Complexity of Blind Quantum Machine Learning"

Rex Fleur, Tzula B. Propp, Sebastian Feld, arXiv:2610.17145.

This folder holds the numerical data behind every scaling figure of the paper, the script
that draws those figures from the data, the scripts of the fixed-clock HHL run, a record of
the verification runs made before submission, and checksums. It lives on the
`reproducible-results` branch of the MasonQ repository, whose base commit is the state of the
code with which the 2025 experiments were run, with the original experiment scripts and their
outputs in place under `src/brickwork_transpiler/experiments/`.

Nothing in `data/` was edited by hand. Fifteen of the seventeen files are byte-identical copies
of the experiment outputs committed in 2025 (checked with `cmp`, see section 5); the two
remaining files are the fixed-clock HHL run of October 2026, which has no earlier counterpart.

## 1. Contents

```text
experiments/reproducible_results/
  README.md                       this file
  SHA256SUMS                      checksums of every file below (verify: shasum -a 256 -c SHA256SUMS)
  data/                           17 CSV files, one per experiment (section 2), and the minimal
                                  B-QRS instance: its resource numbers and its pattern (section 3.4)
  figures/                        the 7 figure images, regenerated from data/ (section 4), and the
                                  brickwork graph of the minimal B-QRS instance, plain and encrypted
  figures/manuscript/             every figure file of the arXiv submission of 12 Oct 2026, under
                                  the paths the manuscript source uses (section 2.1)
  scripts/
    make_scaling_figures.py       draws Figs. 5, 6, F12, F13 and F14 from data/
    minimal_qrs_instance.py       reproduces the minimal B-QRS instance of Section 3.3 (section 3.4)
    run_archived_experiments.py   runs the archived 2025 experiment code for small sizes
    hhl_fixed_clock/              build_circuits.py, transpile_circuits.py, semantic_check.py:
                                  the Fig. 5b pipeline (section 3.2)
  verification/                   outputs and comparisons of the re-runs of 30 Oct 2026, and
                                  pip freezes of the three environments (section 5)
```

The branch itself provides, outside this folder:

| What | Where |
|---|---|
| Transpiler as used for the 2025 experiments | `src/brickwork_transpiler/` (base commit `cc3bdca`, 27 Apr 2026; transpiler core last changed 3 Oct 2025) |
| Experiment scripts, as run | `src/brickwork_transpiler/experiments/` |
| Algorithm circuits (QRS variants, HHL helpers) | `src/brickwork_transpiler/algorithms/` |
| All 25 experiment outputs, including runs not used in the paper | `src/brickwork_transpiler/experiments/data/output_data/` |
| Software environment of the 2025 runs | `requirements-lock.txt` (repository root) |
| Minimal QRS circuit drawings and histograms (Figs. 7, D10, D11) | `images/Circuits/`, `images/plots/` |

## 2. Figure to data to code

| Figure | Data file in `data/` | Produced by | Data committed |
|---|---|---|---|
| 5a, blind QFT | `experiments_qft.csv` | `qft_transpilation.py`, the loop quoted in `run_archived_experiments.py` | `6603b68`, 8 Aug 2025 |
| 5b, blind HHL, fixed clock | `experiment_hhl_toeplitz_fixed_clock.csv` | `scripts/hhl_fixed_clock/` (section 3.2) | 7 Oct 2026 |
| 6a, B-QRS inference | `experiments_qrs_no_db_one_match.csv` | `qrs_no_db_transpilation.py` (section 3.1, note on the database call) | `d9dc034`, 5 Aug 2025 |
| 6b, B-QRS inference and training | `experiments_qrs_full_one_match.csv` | `qrs_full_transpilation.py` | `6603b68`, 8 Aug 2025 |
| F12a, Toeplitz, default clock | `experiment_hhl_toeplitz_d_avf_opt0.csv` | `hhl_transpilation.py` (section 3.1, note on matrix families) | `a1146f7`, 3 Oct 2025 |
| F12b, normalised Laplacian | `experiment_hhl_laplacian_opt0_d_avg.csv` | `hhl_transpilation.py`, the live loop | `a1146f7`, 3 Oct 2025 |
| F12c, low-density Hermitian | `experiment_hhl_sparse_opt0_d_avg.csv` | `hhl_transpilation.py` | `a1146f7`, 3 Oct 2025 |
| F12d, low-density Hermitian, second sample | `experiment_hhl_sparse_one_over_m.csv` | `hhl_transpilation.py` | `a1146f7`, 3 Oct 2025 |
| F13, QRS with database, four cases | `experiments_qrs_full_one_match.csv`, `experiment_qrs_full_no_matching_element.csv`, `experiment_qrs_full_subset_grover.csv`, `experiment_qrs_full_one_match_duplicates.csv` | `qrs_full_transpilation.py`, one function per case | `6603b68`, 8 Aug 2025 |
| F14, QRS inference, four cases | `experiments_qrs_no_db_one_match.csv`, `experiment_qrs_no_db_no_matching_element.csv`, `experiment_qrs_no_db_subset_grover.csv`, `experiment_qrs_no_db_one_match_duplicates.csv` | `qrs_no_db_transpilation.py`, one function per case | `d9dc034`, 5 Aug 2025 |
| Table 1 | none, analytic | | |
| Section 3.3, minimal B-QRS; Fig. 7 | `minimal_qrs_instance.txt` (resource numbers), `minimal_qrs_pattern.txt` (the pattern), `minimal_qrs_circuit_decomposed.qasm` (the routed circuit); images in `figures/`: `minimal_qrs_circuit.png` (Fig. 7a), `minimal_qrs_circuit_decomposed.png` (Fig. 7b), `minimal_qrs_brickwork_graph.png`/`.pdf` (gate colours), `minimal_qrs_brickwork_graph_encrypted.png`/`.pdf` (BFK-randomised angles, no colours) | `scripts/minimal_qrs_instance.py` with the archived code (section 3.4) | 30 Oct 2026 |
| D10, D11, output counts | none, images only | `minimal_qrs_transpilation_simulation.py::run_and_plot_minimal_qrs_only_db` | images in `images/plots/` |

### 2.1 The manuscript's figure files

`figures/manuscript/` holds, byte for byte and under the paths the LaTeX source uses, every
figure file included by the arXiv submission of 12 October 2026 (`BQML_Paper_Arxiv_clean_v2`).
The table says, for each, whether this folder regenerates it from `data/` (checked byte for
byte on 30 October 2026), whether it is an image tracked in this repository, or whether it
exists only as submitted.

| Figure | File under `figures/manuscript/figures/` | Status |
|---|---|---|
| 1 | `graphs/bw_single_rotation.png` | illustration, as submitted |
| 2a, 2b | `graphs/bw_cx_top_cropped.png`, `graphs/bw_cx_bot_cropped.png` | illustration, as submitted |
| 3a, 3b, 3c | `graphs/cx_single_swap/thesis_cx_swap_cropped.png`, `..._decomposed_cropped.png`, `thesis_bw_cx_swap_cropped.png` | illustration, as submitted |
| 4 | `masonq-pipeline-page_fbdone.png` | drawn diagram, as submitted |
| 5a | `newRerun/qrs_thesis_qft_log3_bound_fancy_best.png` | regenerated, identical: `figures/qrs_thesis_qft_log3_bound_fancy_best.png` |
| 5b | `newRerun/hhl_HHL_logN_sq_newplot_fancy_best.png` | regenerated, identical: `figures/hhl_HHL_logN_sq_newplot_fancy_best.png` |
| 6a | `bqrs_inference_final.png` | regenerated, identical: `figures/qrs_QRS_inference_scaling_fb_SINGLE.png` |
| 6b | `bqrs_all_final.png` | regenerated, identical: `figures/qrs_QRS_WITH_db_scaling_fb_SINGLE.png` |
| 7a | `experiment/minimal_recommendation_circuit.png` | repository image `images/Circuits/minimal_recommendation_circuit.png`; same circuit as `figures/minimal_qrs_circuit.png` |
| 7b | `experiment/Decomposed_minimal_recommendation_circuit.png` | repository image `images/Circuits/Decomposed_minimal_recommendation_circuit.png`: the trivial-layout decomposition of the 32-column instance, see the note below |
| A1 | `bw_impr_shift_proof.png` | hand sketch, as submitted |
| B2a to B2d | `decomp_opt_example/thesis_cx4_circ.png`, `Brickworkgraph_sabre_onlyqq_and_initial.png`, `Brickworkgraph_sabre_onlyqq.png`, `Brickworkgraph_nooptimisations.png` | illustration, as submitted |
| B3 | `id_brick_cropped.png` | illustration, as submitted |
| C4 | `DAG_example/bw_dag.png` | illustration, as submitted |
| C5, C6 | `DAG_example/circuit_dag_ex.png`, `circuit_dag_ex_decomposed.png` | repository images `images/thesis_cx_swap.png`, `images/qft3_example_poster_after_decomposition.png` |
| C7 | `DAG_example/bw_dag_example.png` | illustration, as submitted |
| C8 | `encoded/UBQCstructure_enc.png` | illustration, as submitted |
| C9 | `noise/noise_graph.png` | illustration, as submitted |
| D10a to D10d | `experiment/minimal_qrs_plot_0,0.png` … `1,1.png` | simulated output counts, as submitted (not in the repository) |
| D11a to D11d | `min_qrs_exp/minimal_qrs_statevector_evolution_plot_0,0.png` … `1,1.png` | repository images `images/plots/minimal_qrs_statevector_evolution_plot_[x, y].png` |
| F12 | `newRerun/hhl_thesis_hhl_final_plots_unopt_dense.png` | regenerated, identical: `figures/hhl_thesis_hhl_final_plots_unopt_dense.png` |
| F13 | `new/qrs_qrs_with_db_L_no_decomp.png` | regenerated, identical: `figures/qrs_qrs_with_db_L_no_decomp.png` |
| F14 | `new/qrs_qrs_no_db_no_decomp.png` | regenerated, identical: `figures/qrs_qrs_no_db_no_decomp.png` |

The illustrations were drawn with MasonQ's visualiser from small example circuits at various
times between September 2025 and October 2026 and cropped by hand; they carry no numerical
result and are not regenerated here. Note on Fig. 7b: the submitted drawing is the
trivial-layout decomposition behind the 32-column instance of the archived experiment script,
while the manuscript text gives the numbers of the 16-column instance of section 3.4; the
drawing that belongs to those numbers is `figures/minimal_qrs_circuit_decomposed.png`.

Three files in `data/` are not drawn in the submitted figures and are kept for transparency:

- `experiment_hhl_toeplize_trotter2_no_opt.csv`: the Toeplitz run with Qiskit's default clock
  register that an earlier draft used for Fig. 5b. It was replaced because that register grows
  with N, so the circuit is not polylogarithmic in N (section 5, item on the x axis).
- `experiment_hhl_toeplitz_default_clock_rerun.csv`: the same default-clock circuits rebuilt
  and transpiled with the October 2026 code, for comparison with the fixed-clock run.
- `experiments_hhl.csv`: an earlier low-density Hermitian run.

The figure files are named as in the manuscript source:

| Figure | File in `figures/` |
|---|---|
| 5a | `qrs_thesis_qft_log3_bound_fancy_best.png` |
| 5b | `hhl_HHL_logN_sq_newplot_fancy_best.png` |
| 6a | `qrs_QRS_inference_scaling_fb_SINGLE.png` |
| 6b | `qrs_QRS_WITH_db_scaling_fb_SINGLE.png` |
| F12 | `hhl_thesis_hhl_final_plots_unopt_dense.png` |
| F13 | `qrs_qrs_with_db_L_no_decomp.png` |
| F14 | `qrs_qrs_no_db_no_decomp.png` |

### Columns

All experiments record the same quantity: `transpiled_depth` is the brickwork depth D(B) of the
paper, the number of brick columns of MasonQ's aligned instruction matrix
(`len(instr_mat[0])` in the scripts). The graph depth of the paper is 4 D(B) + 1.

| Column | Meaning |
|---|---|
| `transpiled_depth` | brick columns of the aligned instruction matrix, D(B) |
| `decomposed_depth` | depth of the circuit after Qiskit's decomposition and routing to the rz, rx, cx basis |
| `original_depth` | depth of the input circuit |
| `num_gates_original` | gate count of the input circuit as recorded by the code at the time (see the QRS note below) |
| `num_gates_transpiled` | gate count after decomposition to the rz, rx, cx basis |
| `N` | matrix dimension 2^n (HHL files); in `experiments_qft.csv` there is no size column: row k is the (k + 3)-qubit QFT, n = 3 to 29, N = 2^n |
| `kappa`, `s_sparsity`, `d_avg` | condition number, sparsity, and average CX distance of the decomposed circuit (HHL files; `d_avg` was added in October 2025) |
| `L`, `g`, `num_iterations` | database size 2^q, number of good elements, Grover iterations ⌊π/4 √(L/g)⌋ (QRS files) |
| fixed-clock files: `n`, `nl`, `width`, `fidelity`, `seconds` | system qubits, clock qubits, circuit width, post-selected solution fidelity for N ≤ 64, transpilation time |

QRS note: the figures use only `transpiled_depth`, `L` and `num_iterations` of the QRS files.
The `num_gates_original` column of the inference-only QRS files reproduces exactly at their
data commit; the same column of the with-database QRS files could not be reproduced from the
archived code (re-runs give different values while depths and iteration counts agree), so for
those files it should not be used. It is left as recorded.

## 3. How the data were produced

### 3.1 The 2025 experiments (Figs. 5a, 6, F12, F13, F14)

Environment: `requirements-lock.txt` at the repository root, Python 3.11 with Qiskit 0.46.3,
Graphix 0.3.1, NumPy 2.2.6, numba 0.61.2, networkx 3.5, scipy 1.15.3, matplotlib 3.10.5. The
authors' conda environment `B-QML` still matches this file package for package
(`verification/environments/envB_original_2025_qiskit0.46_pip-freeze.txt`); HHL additionally
needs Qiskit's `linear_solvers` package.

Transpiler settings: SABRE layout and SABRE routing for every experiment; Qiskit optimisation
level 3 (the default of `transpile` at this commit) for QFT and QRS, level 1 with ancillas for
HHL. The measured quantity is the brick depth after MasonQ's alignment; nothing is simulated.

The scripts are research code and have no command-line entry points: the functions were
called from an IDE, the repository root was on `sys.path` (imports read
`src.brickwork_transpiler`), and the CSVs were written to a path relative to the working
directory. `scripts/run_archived_experiments.py` reproduces these conditions from a scratch
directory. Four facts about the archived scripts matter for anyone re-running them:

- The QFT loop in `qft_transpilation.py` is commented out in the archived file (only the
  plotting call remains). The loop is reproduced verbatim in `run_archived_experiments.py`.
- The inference-only QRS data (Figs. 6a, F14) were taken on 5 August 2025 with the call to
  `initialise_database` inside `qrs_knn_grover.qrs` commented out (commit `d9dc034`). The call
  was re-enabled a week later (commit `233c2d1`), and the archived `qrs_no_db_transpilation.py`
  therefore builds the circuit with database encoding when run unchanged. The driver disables
  that call for the `nodb` step, which is what was run in 2025.
- The four HHL matrix families of Fig. F12 were produced by editing the matrix block of
  `experiment_hhl_transpilation` in `hhl_transpilation.py` between runs. The archived file has
  the normalised-Laplacian block live and the others commented. The file `*_one_over_m.csv` is
  a second random draw of the sparse Hermitian matrix: ε does not enter these circuits.
- The transpiler core changed between the August runs and the branch base (cleanup commits
  of 3 October 2025). Section 5 reports how closely each data set is reproduced by the code at
  its own commit and by the code at the branch base.

### 3.2 The fixed-clock HHL run (Fig. 5b)

Done in October 2026, in three steps, with the scripts in `scripts/hhl_fixed_clock/`:

1. `build_circuits.py 5 12 6`, in the 2025 environment (Qiskit 0.46.3 with `linear_solvers`):
   builds Qiskit's HHL circuit for the tridiagonal Toeplitz matrix A_N(1, −1/6), exact
   reciprocal, ε = 10⁻², |b⟩ = H^⊗n|0⟩, with the clock register fixed at nl = 5 qubits for every
   N = 2 … 4096 (Qiskit's default is nl = n + 2). It expands composite gates, keeps
   multi-controlled gates whole, writes one JSON file per n, and for N ≤ 64 computes the
   post-selected solution fidelity by state-vector simulation.
2. `transpile_circuits.py nl5 1 12 experiment_hhl_toeplitz_fixed_clock.csv`, with the current
   MasonQ (branch `master`, Qiskit 2.x): transpiles each circuit with SABRE layout and routing,
   optimisation level 1 and ancillas, and records the brick depth. The CSV in `data/` was
   produced on 7 October 2026 with the development version that became commit `bec2298`
   (27 October 2026) of `master`, under Qiskit 2.4.1 and Graphix 0.3.5.
3. `semantic_check.py nl5 1 2 3`: for N = 2, 4, 8, rebuilds a circuit from the aligned brick
   matrix and compares it with the routed circuit on random input states.

`transpile_circuits.py` uses the current public API (`return_stage="matrix"`), so it runs
against `master`, not against the code of this branch's base.

### 3.3 The figures

`scripts/make_scaling_figures.py` reads `data/`, writes `figures/`, and asserts for every
drawn reference curve that it stays on the stated side of the data. It needs only NumPy and
matplotlib. The reference curves are upper bounds with constants chosen by hand; only their
shape is claimed (see the paper).

### 3.4 The minimal B-QRS instance (Section 3.3 of the paper)

`scripts/minimal_qrs_instance.py` builds the six-qubit minimal recommendation circuit
(`circuits.minimal_qrs([0, 1])`: database {(0,0), (0,1)}, user feature (0, 1)), transpiles it
with the archived code using SABRE layout and SABRE routing, Qiskit optimisation level 1 and no
ancillas, repeats this (SABRE is randomised) and keeps the smallest brickwork graph, simulates
that pattern with Graphix and compares it with the Qiskit reference state, and writes the
pattern, the resource numbers, the input circuit and the decomposed and routed circuit (drawn,
and the latter also as QASM), and two graph images: the coloured brickwork graph and its
BFK-encrypted version (randomised angles, no gate colours). All committed files come from one
run of 30 October 2026, which gave 16 brick columns in 6 of 12 runs and 21 in the others; the
kept instance is:

| Quantity | Value |
|---|---|
| brick columns D(B) | 16 |
| graph columns, 4D + 1 | 65 |
| rows (logical qubits) | 6 |
| graph nodes, i.e. remotely prepared qubits | 390 |
| single-qubit measurements | 384 |
| CZ edges | 464 |
| qubits held at once (two graph columns, cylindrical register) | 12 |
| overlap of the simulated pattern with the Qiskit reference state | 1.000000000000 |

The archived experiment script `minimal_qrs_transpilation_simulation.py` used trivial layout
with SABRE routing, which gives 32 brick columns (774 qubits, 928 CZ) deterministically; the
settings scan in `verification/minimal_qrs_settings_scan_2026-10-30.txt` compares the layout,
routing and optimisation-level choices for both the archived code and the current `master`,
which gives the same 16-column instance with SABRE layout.

## 4. How to regenerate

Figures, from any Python with NumPy and matplotlib (the submitted PNGs were made with
matplotlib 3.10.9):

```bash
cd experiments/reproducible_results/scripts && python make_scaling_figures.py
```

Fig. 5b from scratch (about 15 minutes; `<2025 env>` is a Python from `requirements-lock.txt`
plus `linear_solvers`, `<master env>` a Python with the current MasonQ installed):

```bash
cd experiments/reproducible_results/scripts/hhl_fixed_clock
<2025 env> build_circuits.py 5 12 6
<master env> transpile_circuits.py nl5 1 12 fixed_clock_rerun.csv
PYTHONPATH=. <master env> semantic_check.py nl5 1 2 3
```

The minimal B-QRS instance (about a minute):

```bash
MPLBACKEND=Agg <2025 env> experiments/reproducible_results/scripts/minimal_qrs_instance.py <repository root> /tmp/masonq-minimal 12
```

The archived 2025 experiments, small sizes, from a scratch directory so that nothing in the
repository is written to:

```bash
<2025 env> experiments/reproducible_results/scripts/run_archived_experiments.py <repository root> /tmp/masonq-rerun qft full nodb hhl
```

Full-size re-runs take much longer: the QRS experiments go up to L = 128 and the QFT to 29
qubits; the HHL families to N = 32 (hours).

## 5. Verification record

### 5.1 Checks of 30 October 2026

| Check | Result |
|---|---|
| Data integrity | the 15 original CSVs in `data/` are byte-identical to `src/brickwork_transpiler/experiments/data/output_data/` at the base commit and to the commits listed in section 2 |
| Figures | all seven PNGs regenerated from `data/` are byte-identical to the figure files of the arXiv submission of 12 Oct 2026 (section 2.1); for Fig. 6 this required restoring the legend order of the submitted version in `make_scaling_figures.py` on 30 Oct (`verification/figures_regenerated_2026-10-30.txt`) |
| Fig. 5b, full pipeline re-run, `master` commit `6dd57b0` in the Qiskit 2.4.1 environment | gate counts and fidelities identical for all 12 sizes; brick depths within 1.5 % (`verification/fig5b_rerun_2026-10-30_master_qiskit24.txt`) |
| Fig. 5b, the same under Qiskit 2.6.1 and Graphix 0.4.1 | gate counts and fidelities identical; depths within 8.7 %; semantic check overlap 1.000000000000 for N = 2, 4, 8 (`verification/fig5b_rerun_2026-10-30_master_qiskit26.txt`) |
| Archived code at the branch base, 2025 environment: QFT n = 3 … 10 | gate counts identical; depths within 5.8 % |
| same: QRS with database, L = 4, 8, 16 | iteration counts identical; depths within 0.7 % |
| same: HHL normalised Laplacian, N = 4, 8 | gate counts identical; depths within 9.6 % |
| Archived code at the data commits: QFT at `6603b68` | gate counts identical; depths within 9.7 % |
| same: QRS with database at `6603b68` | iteration counts identical; depths within 2.4 % |
| same: HHL Laplacian at `a1146f7` | gate counts and depths identical (0.0 %) |
| QRS inference only (Fig. 6a), archived code at `d9dc034`, L = 4, 8, 16 | gate counts and iteration counts identical; depths within 2.3 % |
| same, archived code at the branch base with the database call disabled as in 2025 | iteration counts identical; depths within 5.7 % (run unpatched, the base code builds the with-database circuit instead: `verification/archived_code_main_envB/`) |
| Minimal B-QRS, section 3.3 | the committed instance (16 brick columns, 390 qubits, 464 CZ; section 3.4) simulates to the Qiskit reference state with overlap 1. The archived script's own configuration (trivial layout) gives 32 brick columns (774 qubits, 928 CZ) deterministically; an earlier manuscript draft stated 31 (750 qubits, 900 CZ), which no setting reproduces. With SABRE layout at optimisation level 2 the archived code reaches 12 brick columns (294 qubits, 348 CZ) in part of the runs. See `verification/minimal_qrs_2026-10-30.txt` and `verification/minimal_qrs_settings_scan_2026-10-30.txt` |

Depth differences of a few per cent between re-runs are expected: SABRE layout and routing are
randomised and not seeded in these experiments, and Qiskit's gate synthesis changed between
versions 0.46, 2.4 and 2.6. Gate counts of the input circuits and Grover iteration counts are
deterministic and reproduce exactly.

### 5.2 Independent check of 7 October 2026

Before the figures were finalised, every numerical claim of the scaling analysis was recomputed
from the CSVs, the archived code and Qiskit's `linear_solvers` source. The outcomes that bear on
the data:

- The CSV column `N` of the HHL files already holds the matrix dimension 2^n. Earlier drafts of
  Fig. 5b and F12 plotted 2^N instead; the x axis of the submitted figures is the corrected one.
  With the correct axis, the default-clock Toeplitz data of the earlier draft are not
  polylogarithmic over the measured range, which is why Fig. 5b was re-done with a fixed clock.
- Rebuilding Qiskit's HHL circuits reproduces the gate counts of every HHL row exactly, for
  both the default clock (N = 2 … 128) and the fixed clock (N = 2 … 4096).
- Row k of `experiments_qft.csv` is the (k + 3)-qubit QFT: `num_gates_original` equals
  n + 5 n(n − 1)/2 + 3 ⌊n/2⌋ for every row.
- In the QRS files, `L` is the database size and `num_iterations` = ⌊π/4 √(L/g)⌋.
- Fig. F12(d) differs from F12(c) only by the random matrix drawn at N = 8, not by ε, and is
  labelled as a second sample.
- The semantic check of the fixed-clock pipeline compares the brick matrix with MasonQ's routed
  circuit, not with the original circuit; it shows that the alignment preserves the routed
  circuit.

## 6. Known limitations

- The exact commit used for each 2025 run was not recorded. The data commits listed in
  section 2 are the commits in which the CSVs were added or last changed; the code at those
  commits and at the branch base reproduces the data as reported in section 5, up to routing
  randomness.
- The `num_gates_original` column of the with-database QRS files is not reproducible
  (section 2).
- The minimal B-QRS instance depends on SABRE's randomised layout and routing: the committed
  16-column instance is obtained in about half to three quarters of the runs, the others give
  21 columns, and optimisation level 2 occasionally gives 12. The numbers in the paper are
  those of the committed instance in `data/minimal_qrs_instance.txt`; the submitted Fig. 7b and
  the hosted graph images still show the earlier 32-column instance (section 2.1).
- Solution fidelity of the fixed-clock HHL circuits is checked only for N ≤ 64, with a uniform
  |b⟩.
- The output-count histograms of Figs. D10 and D11 were not re-run.
- SABRE layout and routing are not seeded, so brick depths vary by a few per cent between runs.

## 7. Checksums

`SHA256SUMS` lists every file in `data/`, `figures/`, `scripts/` and `verification/`. Verify from
this folder with:

```bash
shasum -a 256 -c SHA256SUMS
```
