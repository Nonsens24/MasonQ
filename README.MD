## Brickwork graph transpiler




# 🧱 Brickwork Transpiler

[![Build](https://img.shields.io/github/actions/workflow/status/Nonsens24/brickwork_transpiler/ci.yml?branch=main)](https://github.com/Nonsens24/brickwork_transpiler/actions)
[![codecov](https://codecov.io/gh/Nonsens24/brickwork_transpiler/branch/main/graph/badge.svg)](https://app.codecov.io/gh/Nonsens24/brickwork_transpiler)
[![PyPI](https://img.shields.io/badge/pypi-not_released-lightgrey.svg)](#)
[![Python](https://img.shields.io/badge/python-%203.11-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://<org>.github.io/<repo>/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://black.readthedocs.io/)
[![mypy](https://img.shields.io/badge/mypy-checked-informational)](http://mypy-lang.org/)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen)](https://docs.pytest.org/)

A brickwork graph (https://arxiv.org/abs/0807.4154) transpiler that converts unitary **Qiskit circuits** into Graphix
**brickwork (MBQC)** patterns (https://github.com/TeamGraphix/graphix), with provable statevector
equivalence, circuit optimisations, routing swaps, and ancilla management. Includes utilities for layout extraction, ancilla padding, 
reference-state generation, and robust comparisons up to global phase.


---

## 📖 Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [Transpile](#transpile)
  - [Padding inputs when the register widens](#padding-inputs-when-the-register-widens)
  - [Extract and undo layout](#extract-and-undo-layout)
  - [Reference state (layout-aware)](#reference-state-layout-aware)
- [Testing](#testing)
- [Design Notes](#design-notes)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Citation](#citation)
- [License](#license)
- [Acknowledgements](#acknowledgements)

---

## 🚀 Features

- **Qiskit → Brickwork** translation that outputs an MBQC pattern plus an optional color map for visualization.
- **Ancilla handling:** automatic padding with `|+⟩` on higher indices to match widened registers after transpilation.
- **Reference evaluation:** computes layout-aware reference states using Qiskit and matches MBQC simulator output after reordering.
- **Robust tests:** .

---
## 📄 Relevant Papers

- Universal Blind Quantum Computation (https://doi.org/10.48550/arXiv.0807.4154)
- Quantum Algorithm for Linear Systems of Equations (https://doi.org/10.1103/PhysRevLett.103.150502)
- Recommendation Systems With the Quantum K–NN and Grover Algorithms for Data Processing (https://doi.org/10.2478/amcs-2019-0011)
- The Measurement Calculus (https://doi.org/10.48550/arXiv.0704.1263)
- Optimizing Gate Decomposition for High-Level Quantum Programming (https://doi.org/10.22331/q-2025-03-12-1659)
- Verification implemented (https://doi.org/10.48550/arXiv.1203.5217)


### Other sources
- ▶️ An introduction to measurement-based quantum computation by Robert Raussendorf: https://www.youtube.com/watch?v=zBjAoOW3xHk
---


## ⚙️ Installation

### From PyPI - Unavailable
```bash
pip install brickwork-transpiler
````

### From source

```bash
git https://github.com/Nonsens24/brickwork_transpiler.git
cd brickwork_transpiler
pip install -e .
```

### Optional (dev & docs)

```bash
pip install -e ".[dev,docs]"
```

**Requirements:** Python ≥ 3.9, NumPy, Qiskit (Terra). For MBQC simulation and plotting, install Graphix and (optionally) matplotlib.

---

## 🏃 Quick Start


```python 
from src.brickwork_transpiler import brickwork_transpiler, utils, visualiser, circuits

  # 1) Build a small circuit
  qc = QuantumCircuit(2)
  qc.h(0); qc.cx(0, 1)
  
  input_vector = Statevector.from_label('++')
  
  # OR use a premade circuit
  # qc, input_vector = circuits.minimal_qrs([0, 0])

  # 2) Transpile the circuit
  bw_pattern, col_map, transpiled_qc = brickwork_transpiler.transpile(
      qc, input_vector,
      routing_method="sabre",
      layout_method="trivial",
      with_ancillas=True
  )


  # 3) Visualise the brickwork graph
  visualiser.plot_brickwork_graph_from_pattern(bw_pattern,
                                               show_angles=True,
                                               node_colours=col_map,
                                               use_node_colours=True,
                                               title="Brickwork graph: quick start test",
                                               save_plot=True)

  # 4) Simulate the measurement pattern 
  # Preprocess data to standard form
  bw_pattern.standardize()
  bw_pattern.shift_signals()

  # Get the output state from Graphix simulation
  tn = bw_pattern.simulate_pattern(backend="tensornetwork", graph_prep="parallel")
  psi = tn.to_statevector()

  # Independently Calculate reference output and extend input vector with new ancillae qubits
  reference_output = utils.calculate_ref_state_from_qiskit_circuit(bw_pattern, qc, transpiled_qc, input_vector)

  # Compare output states up to global phase
  if utils.assert_equal_up_to_global_phase(reference_output, psi):
      print("Equivalent up to global phase!")
```

---

## 🧑‍💻 Usage

### Transpile

```python
bw_pattern, col_map, qc_tr = brickwork_transpiler.transpile(
    qc,                 # original circuit (QuantumCircuit)
    input_vector,       # Statevector for 'qc'
    routing_method="sabre",  # "sabre" | "basic" | "lookahead" | ...
    layout_method="trivial",   # "sabre" | "trivial" | ...
    with_ancillas=True,      # permit ancilla expansion for linear scaling
)
```

### Padding inputs when the register widens

If the transpiled circuit has `k` more qubits than the original, pad the input with `|+⟩^{⊗k}` on **higher indices** (incorporated in reference state calculation) :

```python
sv_pad = utils.pad_with_plus_for_transpiled(input_vector, qc, qc_tr)
# returns (|+>^{⊗k}) ⊗ |ψ_in>
```


### Reference state (layout-aware)

Produce a reference state on the **logical output subsystem** in the **Graphix output order** (tracing out ancillas and non-output logicals when necessary):

```python
  reference_output = utils.calculate_ref_state_from_qiskit_circuit(bw_pattern, 
                                                                   qc, 
                                                                   transpiled_qc, 
                                                                   input_vector)
```

---

## 🧪 Testing


Run tests:

```bash
pytest -q
```

Recommended dev workflow:

```bash
pip install -e ".[dev]"
pre-commit install
pre-commit run --all-files
pytest -q
```

---

## 📝 Design Notes

* **Ancilla policy.** New wires introduced by transpilation are treated as ancillas and placed **after** the logical block. Padding uses `( |+>^{⊗k} ) ⊗ |ψ⟩`.

---

## 🗺️ Roadmap

* [ ] Fix Sabre layout permutation on simulated state vector to compare with reference state vector
* [ ] Qiskit HLS exact linearisation of MCU gates (https://quantum-journal.org/papers/q-2025-03-12-1659/)
* [ ] Verification implemented (https://arxiv.org/abs/1203.5217)
* [ ] Merge steps converting dependency graph to aligned matrix
* [ ] Noise-aware fidelity comparison (Kraus channels)
* [ ] Benchmarks across hardware-native layouts and couplings

---


## 📚 Citation

If this package supports your research, please cite:

```bibtex
@software{brickwork_transpiler,
  author  = {R. Fleur},
  title   = {Brickwork Transpiler},
  year    = {2025},
  url     = {https://github.com/Nonsens24/brickwork_transpiler}
}
```

---

## 📜 License

This project is licensed under the **Apache License 2.0**. See [LICENSE](./LICENSE) for details.


---

## 💡 Acknowledgements

* The Qiskit team for the layout and transpiler infrastructure.
* The MBQC/Graphix community for pattern simulation and tooling.
* The Feld group (Quantum Machine Learning) at TU Delft
