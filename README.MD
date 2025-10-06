## Brickwork graph transpiler

Takes a unitary circuit and transpiles it into a brickwork graph state. The program builds the brickwork
graph by combining bicks (i.e., arbitrary single qubit rotations and CX gates). Graphix (https://github.com/TeamGraphix/graphix)
graph generator is mainly used to calculate the Z/X correction dependencies.

The generated brickwork graph will be used for simulating UBQC (https://arxiv.org/abs/0807.4154).


# 🧱 Brickwork Transpiler

[![Build](https://img.shields.io/github/actions/workflow/status/Nonsens24/brickwork_transpiler/ci.yml?branch=main)](https://github.com/Nonsens24/brickwork_transpiler/actions)
[![codecov](https://codecov.io/gh/Nonsens24/brickwork_transpiler/branch/main/graph/badge.svg)](https://app.codecov.io/gh/Nonsens24/brickwork_transpiler)
[![PyPI](https://img.shields.io/badge/pypi-not_released-lightgrey.svg)](#)

[![Python](https://img.shields.io/badge/python-3.9%20|%203.10%20|%203.11-blue.svg)](https://www.python.org/)

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://<org>.github.io/<repo>/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://black.readthedocs.io/)
[![mypy](https://img.shields.io/badge/mypy-checked-informational)](http://mypy-lang.org/)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen)](https://docs.pytest.org/)

A layout-aware transpiler that converts **Qiskit circuits** into **brickwork (MBQC)** patterns and back, with provable statevector equivalence even under **SABRE** layouts, routing swaps, and ancilla management. Includes utilities for layout extraction, ancilla padding, reference-state generation, and robust comparisons up to global phase.

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

- **Qiskit → Brickwork** translation that emits an MBQC pattern plus an optional color map for visualization.
- **Layout awareness:** uses `final_index_layout()` when available, or reconstructs from `initial_layout` and `routing_permutation()` (e.g., SABRE).
- **Ancilla handling:** automatic padding with `|+⟩` on higher indices to match widened registers after transpilation.
- **Reference evaluation:** computes layout-aware reference states and matches MBQC simulator output after reordering and partial trace.
- **Permutation utilities:** safe construction of `PermutationGate` patterns using the `perm[src]=dest` convention.
- **Robust tests:** helpers for global-phase equivalence, mixed-state detection, and layout synchronization.

---
## 📄 Papers

---


## ⚙️ Installation

### From PyPI
```bash
pip install brickwork-transpiler
````

### From source

```bash
git clone https://github.com/<org>/<repo>.git
cd <repo>
pip install -e .
```

### Optional (dev & docs)

```bash
pip install -e ".[dev,docs]"
```

**Requirements:** Python ≥ 3.9, NumPy, Qiskit (Terra). For MBQC simulation and plotting, install Graphix and (optionally) tensornetwork and matplotlib.

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
                                               title="Brickwork graph: sel_decomp_test",
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

If the transpiled circuit has `k` more qubits than the original, pad the input with `|+⟩^{⊗k}` on **higher indices**:

```python
sv_pad = utils.pad_with_plus_for_transpiled(input_vector, qc, qc_tr)
# returns (|+>^{⊗k}) ⊗ |ψ_in>
```

### Extract and undo layout

Extract a **full physical→logical** map (length = `qc_tr.num_qubits`; ancillas as `None`), then undo the layout on any state prepared in physical wire order:


### Reference state (layout-aware)

Produce a reference state on the **logical output subsystem** in the **Graphix output order** (tracing out ancillas and non-output logicals when necessary):

```python
ref = utils.calculate_ref_state_from_qiskit_circuit_layout_aware(
    bw_pattern=bw_pattern,
    qc_original=qc,
    qc_transpiled=qc_tr,
    padded_input_vector=sv_pad,
    return_density_if_mixed=False,  # True → return DensityMatrix if the subsystem is mixed
)
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

* **Permutation convention.** We adopt Qiskit’s `PermutationGate` convention `perm[src] = dest`. Human “order lists” (what appears at positions 0..N−1) are the **inverse** permutation.
* **Ancilla policy.** New wires introduced by transpilation are treated as ancillas and placed **after** the logical block. Padding uses `( |+>^{⊗k} ) ⊗ |ψ⟩`.
* **Layout composition.** Prefer `final_index_layout()` when available; otherwise reconstruct with `initial_layout` ∘ `routing_permutation()` to capture both SABRE’s initial placement and swap routing.

---

## 🗺️ Roadmap

* [ ] Clifford-only fast path for reference evaluation
* [ ] Noise-aware fidelity comparison (Kraus channels)
* [ ] Export of brickwork patterns to standard MBQC formats
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
* All contributors who helped refine layout-aware reference evaluation and testing.
