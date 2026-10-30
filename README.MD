<p align="center">
  <img src="images/masonQ_final_logo.png" alt="MasonQ logo" width="180">
</p>

# MasonQ: Reproducible Results

[![Paper](https://img.shields.io/badge/arXiv-2610.17145-b31b1b.svg)](https://arxiv.org/abs/2610.17145)
[![Branch](https://img.shields.io/badge/branch-reproducible--results-blue.svg)](https://github.com/Nonsens24/MasonQ/tree/reproducible-results)
[![Figures](https://img.shields.io/badge/figures-byte--identical_to_submission-brightgreen.svg)](experiments/reproducible_results/README.md#figures-of-the-paper)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![Qiskit](https://img.shields.io/badge/qiskit-0.46.3-6929c4.svg)](https://www.ibm.com/quantum/qiskit)
[![Graphix](https://img.shields.io/badge/graphix-0.3.1-blue.svg)](https://github.com/TeamGraphix/graphix)
[![Checksums](https://img.shields.io/badge/SHA256SUMS-97_files-lightgrey.svg)](experiments/reproducible_results/SHA256SUMS)


This branch reproduces the numerical results of *On the Computational
Complexity of Blind Quantum Machine Learning* (Rex Fleur, Tzula B. Propp,
Sebastian Feld, [arXiv:2610.17145](https://arxiv.org/abs/2610.17145)).

It is the MasonQ code as it was when those results were computed, frozen at
commit `cc3bdca` of 27 April 2026, with the experiment scripts, the algorithm
circuits, all experiment outputs and the lock file of the environment still in
place. On top of that, `experiments/reproducible_results/` holds the data behind
every figure, the script that redraws the figures byte for byte, the fixed-clock
HHL pipeline, the minimal B-QRS instance of Section 3.3, every figure file of
the arXiv submission, a verification record and checksums.

The current MasonQ package, with today's API and documentation, lives on the
[`master`](https://github.com/Nonsens24/MasonQ) branch. Nothing here is needed
to use MasonQ; everything here is needed to check the paper.

## What You Can Reproduce

| Result in the paper | How | Outcome |
|---|---|---|
| Figs. 5, 6, F12, F13, F14 | `make_scaling_figures.py` on the data | seven PNGs, byte-identical to the submission |
| Fig. 5b data, fixed-clock HHL | build circuits in the 2025 environment, transpile with the current MasonQ | gate counts and fidelities identical; brick depths within 1.5 % |
| Section 3.3, minimal B-QRS instance | `minimal_qrs_instance.py` with the archived code | 16 brick columns, 390 qubits, 384 measurements, 464 CZ; verified against Qiskit |
| The 2025 experiments behind Figs. 5a, 6, F12 to F14 | `run_archived_experiments.py` with the archived code | gate counts and Grover iteration counts identical; depths within a few per cent (unseeded SABRE) |
| File integrity | `shasum -a 256 -c SHA256SUMS` | 97 files |

## Where Things Are

```text
experiments/reproducible_results/
  README.md                       the detailed record: figure-to-data map, columns, provenance,
                                  verification, limitations
  data/                           17 experiment CSVs; the minimal B-QRS instance (numbers,
                                  pattern, routed circuit as QASM)
  figures/                        the results figures, regenerated; the minimal B-QRS circuits
                                  and brickwork graphs
  figures/manuscript/             every figure file of the arXiv submission of 12 Oct 2026
  scripts/                        requirements-2025.txt, make_scaling_figures.py,
                                  minimal_qrs_instance.py, run_archived_experiments.py,
                                  hhl_fixed_clock/
  verification/                   re-runs of 30 Oct 2026 and pip freezes of the environments
  SHA256SUMS

src/brickwork_transpiler/         the transpiler as used for the 2025 experiments
  experiments/                    the experiment scripts, as run
  experiments/data/output_data/   all 25 experiment outputs, including runs not in the paper
  algorithms/                     QRS variants and HHL helpers
requirements-lock.txt             full freeze of the 2025 environment
images/                           figures and drawings of the development period
```

## Installation

Two environments cover everything. The 2025 environment runs the archived code
of this branch; the current MasonQ runs one step, the transpilation of the
fixed-clock HHL circuits for Fig. 5b.

### The 2025 environment

Python 3.11, in a fresh virtual environment.
`experiments/reproducible_results/scripts/requirements-2025.txt` pins the
versions of the original run: Qiskit 0.46.3, Graphix 0.3.1, NumPy 2.2.6,
numba 0.61.2. `requirements-lock.txt` at the root is the full freeze it was
trimmed from.

```bash
git clone git@github.com:Nonsens24/MasonQ.git && cd MasonQ && git switch reproducible-results
```

```bash
python3.11 -m venv .venv-2025 && source .venv-2025/bin/activate && python -m pip install --upgrade pip
```

```bash
python -m pip install -r experiments/reproducible_results/scripts/requirements-2025.txt && python -m pip install --no-deps quantum_linear_solvers==0.1.1 && python -m pip install -e .
```

`quantum_linear_solvers` is Qiskit's HHL reference implementation. It goes in
without its dependencies because it declares an IBM provider package that pins
NumPy below 1.24 and is not needed for building circuits. The last command
installs this branch's package, `brickwork-transpiler` 0.1.0, as a library.

These steps were run from scratch on 30 October 2026 on an Intel Mac; the
archived library imported, the drivers ran, and the HHL builder produced the
original gate counts.

### Using the archived library

The API is the one the 2025 experiments used, which differs from today's
`masonq`: `transpile` returns the Graphix pattern, the node colour map and the
routed circuit.

```python
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
from brickwork_transpiler import brickwork_transpiler

qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)
pattern, colour_map, routed = brickwork_transpiler.transpile(
    qc, Statevector.from_label("++"), routing_method="sabre", layout_method="sabre", with_ancillas=False)
nodes, edges = pattern.get_graph()            # 26 nodes, 28 CZ edges for this circuit
state = pattern.simulate_pattern(backend="tensornetwork", graph_prep="parallel").to_statevector()
```

The archived experiment scripts are not entry points of the package: they
import `src.brickwork_transpiler` from the repository root and write to a
relative path. The drivers in `experiments/reproducible_results/scripts/`
reproduce those conditions and take the repository root and a scratch directory
as arguments, so nothing inside the repository is written to.

### The current MasonQ

Needed only for the Fig. 5b transpilation step. In a second environment, follow
the installation section of the `master` README, or install it straight from
the repository:

```bash
python -m pip install "masonq @ git+ssh://git@github.com/Nonsens24/MasonQ.git@master"
```

## Reproducing

All commands run from the repository root in the 2025 environment unless said
otherwise.

**The figures.** Any Python with NumPy and matplotlib will do; the submitted
PNGs were made with matplotlib 3.10.9.

```bash
cd experiments/reproducible_results/scripts && python make_scaling_figures.py
```

Seven PNGs appear in `experiments/reproducible_results/figures/`, byte-identical
to the submitted files, for example:

```bash
cd experiments/reproducible_results && cmp figures/bqrs_inference_final.png figures/manuscript/figures/bqrs_inference_final.png && echo identical
```

**The minimal B-QRS instance.** About a minute.

```bash
MPLBACKEND=Agg python experiments/reproducible_results/scripts/minimal_qrs_instance.py . /tmp/masonq-minimal 12
```

`/tmp/masonq-minimal/minimal_qrs_instance.txt` lists 16 brick columns, 390
nodes, 384 measurements, 464 CZ and overlap 1.000000000000 with the Qiskit
reference state, as in `data/minimal_qrs_instance.txt`. SABRE is unseeded: a run
gives 16 in about half to three quarters of its attempts and 21 otherwise, and
the script keeps the smallest.

**The archived 2025 experiments.** Small sizes, a few minutes:

```bash
python experiments/reproducible_results/scripts/run_archived_experiments.py . /tmp/masonq-rerun qft full nodb hhl
```

The CSVs land under `/tmp/masonq-rerun/src/ubqc_brickwork_transpiler/experiments/data/output_data/`.
Against `data/`, input gate counts and Grover iteration counts match exactly and
brick depths agree within a few per cent. Full-size re-runs take hours: QRS up
to L = 128, QFT up to 29 qubits, the HHL families up to N = 32.

**Fig. 5b from scratch.** About 15 minutes. The first command runs in the 2025
environment, the second in the current MasonQ environment.

```bash
cd experiments/reproducible_results/scripts/hhl_fixed_clock && python build_circuits.py 5 12 6
```

```bash
cd experiments/reproducible_results/scripts/hhl_fixed_clock && python transpile_circuits.py nl5 1 12 fixed_clock_rerun.csv && PYTHONPATH=. python semantic_check.py nl5 1 2 3
```

Gate counts and fidelities match `data/experiment_hhl_toeplitz_fixed_clock.csv`
exactly; brick depths agree within 1.5 % under Qiskit 2.4 and within 9 % under
Qiskit 2.6.

**The files.**

```bash
cd experiments/reproducible_results && shasum -a 256 -c SHA256SUMS
```

## Figures of the Paper

| Figure | Data | Produced by | Image |
|---|---|---|---|
| 5a, blind QFT | `experiments_qft.csv` | `qft_transpilation.py`, August 2025 | `qrs_thesis_qft_log3_bound_fancy_best.png` |
| 5b, blind HHL, fixed clock | `experiment_hhl_toeplitz_fixed_clock.csv` | `scripts/hhl_fixed_clock/`, October 2026 | `hhl_HHL_logN_sq_newplot_fancy_best.png` |
| 6a, B-QRS inference | `experiments_qrs_no_db_one_match.csv` | `qrs_no_db_transpilation.py`, August 2025 | `qrs_QRS_inference_scaling_fb_SINGLE.png` |
| 6b, B-QRS inference and training | `experiments_qrs_full_one_match.csv` | `qrs_full_transpilation.py`, August 2025 | `qrs_QRS_WITH_db_scaling_fb_SINGLE.png` |
| F12, HHL matrix families | four `experiment_hhl_*.csv` files | `hhl_transpilation.py`, October 2025 | `hhl_thesis_hhl_final_plots_unopt_dense.png` |
| F13, QRS with database, four cases | four `*qrs_full*.csv` files | `qrs_full_transpilation.py` | `qrs_qrs_with_db_L_no_decomp.png` |
| F14, QRS inference, four cases | four `*qrs_no_db*.csv` files | `qrs_no_db_transpilation.py` | `qrs_qrs_no_db_no_decomp.png` |
| 7, Section 3.3, minimal B-QRS | `minimal_qrs_instance.txt`, `minimal_qrs_pattern.txt`, `minimal_qrs_circuit_decomposed.qasm` | `scripts/minimal_qrs_instance.py` | `minimal_qrs_circuit*.png`, `minimal_qrs_brickwork_graph*.png` |

Data files are in `experiments/reproducible_results/data/`, images in
`experiments/reproducible_results/figures/`. The illustrations of the paper
(Figs. 1 to 4, A1, B2, B3, C4 to C9, D10, D11) are kept as submitted under
`figures/manuscript/`; the
[detailed README](experiments/reproducible_results/README.md#figures-of-the-paper)
lists every file with its origin, the data columns, and the provenance of each
run, commit by commit.

## Minimal B-QRS Instance

The six-qubit recommendation circuit of Section 3.3, transpiled with SABRE
layout and routing at Qiskit optimisation level 1:

| Quantity | Value |
|---|---|
| brick columns | 16 |
| graph depth | 65 |
| logical qubits | 6 |
| remotely prepared qubits | 390 |
| single-qubit measurements | 384 |
| CZ edges | 464 |
| qubits held at once | 12 |
| overlap with the Qiskit reference state | 1.000000000000 |

The archived experiment script used trivial layout, which gives 32 brick
columns; the submitted Fig. 7b and the hosted graph images show that larger
instance, while the manuscript text gives the numbers above. The matching
drawing is `experiments/reproducible_results/figures/minimal_qrs_circuit_decomposed.png`.

## Verification

Checks made on 30 October 2026, with outputs in
`experiments/reproducible_results/verification/`:

- The 15 original CSVs are byte-identical to the files at this branch's base
  and at the commits that added them in 2025.
- All seven results figures regenerate byte-identically to the submission.
- Fig. 5b re-run end to end with the current MasonQ: gate counts and fidelities
  identical for all twelve sizes, depths within 1.5 %, semantic check overlap 1.
- The archived code reproduces the QFT, QRS and HHL rows at small sizes with
  identical gate and iteration counts and depths within a few per cent; the HHL
  rows reproduce exactly at their own commit.
- The minimal instance verifies against Qiskit; the settings that make it small
  are recorded in a scan over layout, routing and optimisation level.

Depth differences of a few per cent are expected: SABRE layout and routing are
unseeded, and Qiskit's gate synthesis changed between versions 0.46, 2.4
and 2.6. The [detailed README](experiments/reproducible_results/README.md#verification)
has the numbers per check and the known limitations.

## Relevant Papers

- Rex Fleur, Tzula B. Propp, Sebastian Feld, *On the Computational Complexity
  of Blind Quantum Machine Learning*, arXiv:2610.17145 (2026):
  https://arxiv.org/abs/2610.17145
- Jiawei Cai, Rex Fleur, Benedikt Tissot, Wolfgang Löffler, Tzula B. Propp,
  *High-Fidelity Remote Graph State Preparation for Blind Quantum Computation*,
  arXiv:2610.06247 (2026): https://arxiv.org/abs/2610.06247

Background: [Universal Blind Quantum Computation](https://arxiv.org/abs/0807.4154),
[The Measurement Calculus](https://arxiv.org/abs/0704.1263),
[Graphix](https://github.com/TeamGraphix/graphix),
[Qiskit](https://www.ibm.com/quantum/qiskit).

## License

Proprietary.
