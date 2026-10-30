# MasonQ: Reproducible Results

[![Paper](https://img.shields.io/badge/arXiv-2610.17145-b31b1b.svg)](https://arxiv.org/abs/2610.17145)
[![Branch](https://img.shields.io/badge/branch-reproducible--results-blue.svg)](https://github.com/Nonsens24/MasonQ/tree/reproducible-results/experiments/reproducible_results)
[![Figures](https://img.shields.io/badge/figures-byte--identical_to_submission-brightgreen.svg)](#figures-of-the-paper)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![Qiskit](https://img.shields.io/badge/qiskit-0.46.3-6929c4.svg)](https://www.ibm.com/quantum/qiskit)
[![Graphix](https://img.shields.io/badge/graphix-0.3.1-blue.svg)](https://github.com/TeamGraphix/graphix)
[![Checksums](https://img.shields.io/badge/SHA256SUMS-96_files-lightgrey.svg)](SHA256SUMS)

Data, figures and scripts behind *On the Computational Complexity of Blind
Quantum Machine Learning* (Rex Fleur, Tzula B. Propp, Sebastian Feld,
[arXiv:2610.17145](https://arxiv.org/abs/2610.17145)).

This folder lives on the `reproducible-results` branch, whose base commit
`cc3bdca` (27 April 2026) is the state of MasonQ with which the 2025 experiments
were run: the experiment scripts, the algorithm circuits, all 25 experiment
outputs and the lock file of their environment are in place under
`src/brickwork_transpiler/`. Every CSV in `data/` is an unedited copy of those
outputs, except the two fixed-clock HHL files, which were produced in October
2026 and have no earlier counterpart. Every figure file of the arXiv submission
of 12 October 2026 is in `figures/manuscript/`, and the seven results figures
regenerate from `data/` byte for byte.

## Quick Start

Verify the files, then redraw the results figures. Only NumPy and matplotlib are
needed for this; the submitted PNGs were made with matplotlib 3.10.9.

```bash
shasum -a 256 -c SHA256SUMS
```

```bash
cd scripts && python make_scaling_figures.py
```

The script asserts that every reference curve stays on the stated side of the
data and writes Figs. 5, 6, F12, F13 and F14 to `figures/`.

## What Is Here

```text
experiments/reproducible_results/
  README.md
  SHA256SUMS                      checksums of every file below
  data/                           17 experiment CSVs; the minimal B-QRS instance (numbers,
                                  pattern, routed circuit as QASM)
  figures/                        the 7 results figures, regenerated from data/; the minimal
                                  B-QRS circuit drawings and brickwork graphs
  figures/manuscript/             every figure file of the arXiv submission, under the paths
                                  the LaTeX source uses
  scripts/
    make_scaling_figures.py       draws Figs. 5, 6, F12, F13 and F14 from data/
    minimal_qrs_instance.py       reproduces the minimal B-QRS instance of Section 3.3
    run_archived_experiments.py   runs the archived 2025 experiment code for small sizes
    hhl_fixed_clock/              build_circuits.py, transpile_circuits.py, semantic_check.py:
                                  the Fig. 5b pipeline
  verification/                   outputs and comparisons of the re-runs of 30 Oct 2026;
                                  pip freezes of the three environments
```

Elsewhere on the branch:

| What | Where |
|---|---|
| Transpiler as used for the 2025 experiments (core last changed 3 Oct 2025) | `src/brickwork_transpiler/` |
| Experiment scripts, as run | `src/brickwork_transpiler/experiments/` |
| Algorithm circuits (QRS variants, HHL helpers) | `src/brickwork_transpiler/algorithms/` |
| All 25 experiment outputs, including runs not used in the paper | `src/brickwork_transpiler/experiments/data/output_data/` |
| Environment of the 2025 runs (Qiskit 0.46.3, Graphix 0.3.1, NumPy 2.2.6, Python 3.11) | `requirements-lock.txt` |

## Figures of the Paper

Results figures: the data file, the code that produced the data, and the commit
in which the data were added to the repository. Each regenerated image is
byte-identical to the corresponding file of the submission.

| Figure | Data in `data/` | Produced by | Data committed | Image in `figures/` |
|---|---|---|---|---|
| 5a, blind QFT | `experiments_qft.csv` | `qft_transpilation.py` (the loop, see below) | `6603b68`, 8 Aug 2025 | `qrs_thesis_qft_log3_bound_fancy_best.png` |
| 5b, blind HHL, fixed clock | `experiment_hhl_toeplitz_fixed_clock.csv` | `scripts/hhl_fixed_clock/` | 7 Oct 2026 | `hhl_HHL_logN_sq_newplot_fancy_best.png` |
| 6a, B-QRS inference | `experiments_qrs_no_db_one_match.csv` | `qrs_no_db_transpilation.py` (database call disabled, see below) | `d9dc034`, 5 Aug 2025 | `qrs_QRS_inference_scaling_fb_SINGLE.png` |
| 6b, B-QRS inference and training | `experiments_qrs_full_one_match.csv` | `qrs_full_transpilation.py` | `6603b68`, 8 Aug 2025 | `qrs_QRS_WITH_db_scaling_fb_SINGLE.png` |
| F12a to F12d, HHL families | `experiment_hhl_toeplitz_d_avf_opt0.csv`, `experiment_hhl_laplacian_opt0_d_avg.csv`, `experiment_hhl_sparse_opt0_d_avg.csv`, `experiment_hhl_sparse_one_over_m.csv` | `hhl_transpilation.py` (matrix block edited per family) | `a1146f7`, 3 Oct 2025 | `hhl_thesis_hhl_final_plots_unopt_dense.png` |
| F13, QRS with database, four cases | `experiments_qrs_full_one_match.csv`, `experiment_qrs_full_no_matching_element.csv`, `experiment_qrs_full_subset_grover.csv`, `experiment_qrs_full_one_match_duplicates.csv` | `qrs_full_transpilation.py`, one function per case | `6603b68` | `qrs_qrs_with_db_L_no_decomp.png` |
| F14, QRS inference, four cases | `experiments_qrs_no_db_one_match.csv`, `experiment_qrs_no_db_no_matching_element.csv`, `experiment_qrs_no_db_subset_grover.csv`, `experiment_qrs_no_db_one_match_duplicates.csv` | `qrs_no_db_transpilation.py`, one function per case | `d9dc034` | `qrs_qrs_no_db_no_decomp.png` |
| 7, Section 3.3, minimal B-QRS | `minimal_qrs_instance.txt`, `minimal_qrs_pattern.txt`, `minimal_qrs_circuit_decomposed.qasm` | `scripts/minimal_qrs_instance.py` | 30 Oct 2026 | `minimal_qrs_circuit.png`, `minimal_qrs_circuit_decomposed.png`, `minimal_qrs_brickwork_graph.png`/`.pdf`, `minimal_qrs_brickwork_graph_encrypted.png`/`.pdf` |

All other figures of the submission, as submitted, under `figures/manuscript/figures/`:

| Figure | File | Origin |
|---|---|---|
| 1, 2, 3, B2, B3, C4, C7, C8, C9 | `graphs/bw_single_rotation.png`; `graphs/bw_cx_top_cropped.png`, `graphs/bw_cx_bot_cropped.png`; `graphs/cx_single_swap/*`; `decomp_opt_example/*`; `id_brick_cropped.png`; `DAG_example/bw_dag.png`; `DAG_example/bw_dag_example.png`; `encoded/UBQCstructure_enc.png`; `noise/noise_graph.png` | illustrations drawn with MasonQ's visualiser from small example circuits between September 2025 and October 2026, cropped by hand; no numerical result |
| 4 | `masonq-pipeline-page_fbdone.png` | drawn diagram |
| A1 | `bw_impr_shift_proof.png` | hand sketch |
| 7a, 7b | `experiment/minimal_recommendation_circuit.png`, `experiment/Decomposed_minimal_recommendation_circuit.png` | repository images `images/Circuits/`; 7b is the trivial-layout decomposition of the 32-column instance, see [Minimal B-QRS Instance](#minimal-b-qrs-instance) |
| C5, C6 | `DAG_example/circuit_dag_ex.png`, `DAG_example/circuit_dag_ex_decomposed.png` | repository images `images/thesis_cx_swap.png`, `images/qft3_example_poster_after_decomposition.png` |
| D10a to D10d | `experiment/minimal_qrs_plot_0,0.png` to `1,1.png` | simulated output counts, 4096 shots; not in the repository |
| D11a to D11d | `min_qrs_exp/minimal_qrs_statevector_evolution_plot_0,0.png` to `1,1.png` | repository images `images/plots/minimal_qrs_statevector_evolution_plot_[x, y].png` |
| 5a, 5b, 6a, 6b, F12, F13, F14 | `newRerun/*`, `bqrs_inference_final.png`, `bqrs_all_final.png`, `new/*` | the submitted copies of the results figures above |

Three files in `data/` are not drawn in the paper and are kept for transparency:
`experiment_hhl_toeplize_trotter2_no_opt.csv` (the default-clock Toeplitz run an
earlier draft used for Fig. 5b; replaced because Qiskit's clock register grows
with N), `experiment_hhl_toeplitz_default_clock_rerun.csv` (those circuits
re-transpiled with the October 2026 code) and `experiments_hhl.csv` (an earlier
low-density Hermitian run).

## Data Columns

`transpiled_depth` is the brickwork depth D(B) of the paper: the number of brick
columns of MasonQ's aligned instruction matrix. The graph depth is 4 D(B) + 1.

| Column | Meaning |
|---|---|
| `transpiled_depth` | brick columns of the aligned instruction matrix, D(B) |
| `decomposed_depth` | depth of the circuit after Qiskit's decomposition and routing to the rz, rx, cx basis |
| `original_depth` | depth of the input circuit |
| `num_gates_original` | gate count of the input circuit as recorded at the time (see the note below) |
| `num_gates_transpiled` | gate count after decomposition to the rz, rx, cx basis |
| `N` | matrix dimension 2^n (HHL files). `experiments_qft.csv` has no size column: row k is the (k + 3)-qubit QFT, n = 3 to 29 |
| `kappa`, `s_sparsity`, `d_avg` | condition number, sparsity, average CX distance of the decomposed circuit (HHL files; `d_avg` added October 2025) |
| `L`, `g`, `num_iterations` | database size 2^q, number of good elements, Grover iterations ⌊π/4 √(L/g)⌋ (QRS files) |
| `n`, `nl`, `width`, `fidelity`, `seconds` | fixed-clock files: system qubits, clock qubits, circuit width, post-selected solution fidelity for N ≤ 64, transpilation time |

The figures use only `transpiled_depth`, `L` and `num_iterations` of the QRS
files. The `num_gates_original` column of the with-database QRS files could not
be reproduced from the archived code and should not be used; the same column of
the inference-only files reproduces exactly.

## How the Data Were Produced

**The 2025 experiments (Figs. 5a, 6, F12, F13, F14).** Environment:
`requirements-lock.txt` at the repository root, Python 3.11 with Qiskit 0.46.3,
Graphix 0.3.1, NumPy 2.2.6, numba 0.61.2, networkx 3.5, scipy 1.15.3; HHL also
needs Qiskit's `linear_solvers`. Settings: SABRE layout and routing throughout,
Qiskit optimisation level 3 (the default then) for QFT and QRS, level 1 with
ancillas for HHL. The recorded quantity is the brick depth after alignment;
nothing is simulated. The scripts are research code without entry points: the
functions were called from an IDE with the repository root on `sys.path`, and
they write CSVs to a path relative to the working directory.
`scripts/run_archived_experiments.py` reproduces these conditions from a scratch
directory. Four details matter for a re-run:

- The QFT loop in `qft_transpilation.py` is commented out in the archived file;
  the driver contains that loop verbatim.
- The inference-only QRS data (Figs. 6a, F14) were taken with the call to
  `initialise_database` inside `qrs_knn_grover.qrs` commented out (commit
  `d9dc034`). A later commit re-enabled it, so the archived `qrs_no_db` script
  builds the with-database circuit unless that call is disabled; the driver does
  this for the `nodb` step.
- The four HHL families of Fig. F12 came from editing the matrix block of
  `experiment_hhl_transpilation` between runs; the archived file has the
  normalised-Laplacian block live. `*_one_over_m.csv` is a second random draw of
  the sparse Hermitian matrix; ε does not enter these circuits.
- The transpiler core changed between the August runs and the branch base
  (cleanup commits of 3 October 2025); see [Verification](#verification) for how
  closely each data set is reproduced at its own commit and at the base.

**The fixed-clock HHL run (Fig. 5b).** October 2026, with
`scripts/hhl_fixed_clock/`: `build_circuits.py 5 12 6` in the 2025 environment
builds Qiskit's HHL circuit for the tridiagonal Toeplitz matrix A_N(1, −1/6),
exact reciprocal, ε = 10⁻², |b⟩ = H^⊗n|0⟩, with the clock register fixed at
nl = 5 for every N = 2 to 4096 (Qiskit's default is n + 2), and computes the
post-selected solution fidelity for N ≤ 64. `transpile_circuits.py nl5 1 12
<csv>` then transpiles each circuit with the current MasonQ (branch `master`,
Qiskit 2.x; SABRE layout and routing, level 1, ancillas) and records the brick
depth; the committed CSV was made on 7 October 2026 with the development version
that became `master` commit `bec2298`, under Qiskit 2.4.1 and Graphix 0.3.5.
`semantic_check.py nl5 1 2 3` rebuilds circuits from the aligned brick matrix and
compares them with the routed circuits. This step uses the current API, so it
runs against `master`, not against this branch's base.

**The figures.** `scripts/make_scaling_figures.py` reads `data/` and writes
`figures/`. The reference curves are upper bounds with constants chosen by hand;
only their shape is claimed.

## Minimal B-QRS Instance

`scripts/minimal_qrs_instance.py` builds the six-qubit circuit
`circuits.minimal_qrs([0, 1])` (database {(0,0), (0,1)}, user feature (0, 1)),
transpiles it with the archived code using SABRE layout and routing, Qiskit
optimisation level 1 and no ancillas, repeats this because SABRE is randomised,
keeps the smallest brickwork graph, simulates that pattern with Graphix against
the Qiskit reference state, and writes the pattern, the numbers, the input and
routed circuits (drawn, the latter also as QASM) and the brickwork graph, plain
and BFK-encrypted. All committed files come from one run of 30 October 2026,
which gave 16 brick columns in 6 of 12 runs and 21 in the others:

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

The archived experiment script used trivial layout with SABRE routing, which
gives 32 brick columns (774 qubits, 928 CZ) deterministically; the submitted
Fig. 7b and the graph images it links show that instance, while the manuscript
text gives the numbers above. The matching drawing is
`figures/minimal_qrs_circuit_decomposed.png`.
`verification/minimal_qrs_settings_scan_2026-10-30.txt` compares layout, routing
and optimisation-level settings for the archived code and for `master`, which
gives the same 16-column instance with SABRE layout.

## Reproducing

`<2025 env>` is a Python from `requirements-lock.txt` plus `linear_solvers`;
`<master env>` one with the current MasonQ installed.

Fig. 5b from scratch, about 15 minutes:

```bash
cd scripts/hhl_fixed_clock && <2025 env> build_circuits.py 5 12 6 && <master env> transpile_circuits.py nl5 1 12 fixed_clock_rerun.csv && PYTHONPATH=. <master env> semantic_check.py nl5 1 2 3
```

The minimal B-QRS instance, about a minute:

```bash
MPLBACKEND=Agg <2025 env> scripts/minimal_qrs_instance.py <repository root> /tmp/masonq-minimal 12
```

The archived 2025 experiments for small sizes, from a scratch directory so that
nothing in the repository is written to:

```bash
<2025 env> scripts/run_archived_experiments.py <repository root> /tmp/masonq-rerun qft full nodb hhl
```

Full-size re-runs take hours: QRS up to L = 128, QFT up to 29 qubits, the HHL
families up to N = 32.

## Verification

Checks of 30 October 2026; outputs in `verification/`.

| Check | Result |
|---|---|
| Data integrity | the 15 original CSVs are byte-identical to the files at the base commit and at the data commits |
| Figures | all seven regenerated PNGs are byte-identical to the submission (`figures_regenerated_2026-10-30.txt`); for Fig. 6 the legend order of the submitted version was restored in the script |
| Fig. 5b re-run, `master` commit `6dd57b0`, Qiskit 2.4.1 | gate counts and fidelities identical for all 12 sizes; depths within 1.5 % |
| same, Qiskit 2.6.1 and Graphix 0.4.1 | gate counts and fidelities identical; depths within 8.7 %; semantic check overlap 1.000000000000 for N = 2, 4, 8 |
| Archived code at the base, 2025 environment: QFT n = 3 to 10; QRS with database L = 4, 8, 16; HHL Laplacian N = 4, 8 | gate and iteration counts identical; depths within 5.8 %, 0.7 % and 9.6 % |
| Archived code at the data commits: QFT (`6603b68`); QRS with database (`6603b68`); HHL Laplacian (`a1146f7`) | depths within 9.7 %, 2.4 % and 0.0 % |
| QRS inference only at `d9dc034`; at the base with the database call disabled | gate and iteration counts identical; depths within 2.3 % and 5.7 % |
| Minimal B-QRS | committed instance verified (overlap 1); the archived configuration gives 32 columns; an earlier draft's 31 columns (750 qubits, 900 CZ) is reproduced by no setting; level 2 reaches 12 columns in part of the runs |

Depth differences of a few per cent between re-runs are expected: SABRE layout
and routing are unseeded, and Qiskit's gate synthesis changed between versions
0.46, 2.4 and 2.6. Gate counts and Grover iteration counts reproduce exactly.

An independent check on 7 October 2026 recomputed every numerical claim of the
scaling analysis from the CSVs, the archived code and Qiskit's `linear_solvers`
source. Its findings that bear on the data: the HHL column `N` holds the matrix
dimension, and earlier drafts of Figs. 5b and F12 had plotted 2^N instead, which
is why Fig. 5b was redone with a fixed clock; rebuilding Qiskit's HHL circuits
reproduces every HHL gate count exactly; row k of the QFT file is the
(k + 3)-qubit QFT with n + 5n(n − 1)/2 + 3⌊n/2⌋ gates; `num_iterations` is
⌊π/4 √(L/g)⌋; Fig. F12(d) is a second random sample, not an ε variant; and the
semantic check compares the brick matrix with the routed circuit, not with the
original.

## Known Limitations

- The exact commit of each 2025 run was not recorded; the data commits above are
  where the CSVs were added or last changed, and the code there reproduces them
  up to routing randomness.
- `num_gates_original` in the with-database QRS files is not reproducible.
- The minimal B-QRS instance depends on unseeded SABRE: 16 columns in about half
  to three quarters of the runs, 21 otherwise; level 2 occasionally gives 12. The
  submitted Fig. 7b and hosted graph images still show the 32-column instance.
- Fixed-clock HHL fidelity is checked only for N ≤ 64 with a uniform |b⟩.
- Figs. D10 and D11 were not re-run.

## License

Proprietary, as the package.
