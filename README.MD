# MasonQ

[![Build](https://github.com/Nonsens24/MasonQ/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/Nonsens24/MasonQ/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Nonsens24/MasonQ/branch/master/graph/badge.svg)](https://app.codecov.io/gh/Nonsens24/MasonQ)
[![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](pyproject.toml)
[![PyPI](https://img.shields.io/badge/pypi-not_released-lightgrey.svg)](#)
[![Python](https://img.shields.io/badge/python-3.10--3.12-blue.svg)](https://www.python.org/)
[![Qiskit](https://img.shields.io/badge/qiskit-2.4--2.6-6929c4.svg)](https://www.ibm.com/quantum/qiskit)
[![Graphix](https://img.shields.io/badge/graphix-0.3.5--0.4-blue.svg)](https://github.com/TeamGraphix/graphix)
[![License](https://img.shields.io/badge/license-proprietary-lightgrey.svg)](#)
[![Docs](https://img.shields.io/badge/docs-local-blue.svg)](docs/README.md)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen)](https://docs.pytest.org/)

MasonQ converts unitary Qiskit circuits into brickwork measurement-based
quantum computation patterns. It lowers circuits to the `rz`/`rx`/`cx`/`id`
basis, schedules them into a brickwork instruction matrix, builds the graph,
and emits a Graphix pattern with measurement angles.

The package is aimed at scientific workflows where the brickwork graph,
resource estimates, and a reproducible verification path matter. The public API
is alpha, but the core pipeline has unit and integration coverage plus slower
Graphix/Qiskit equivalence checks in `tests/system_tests`.

## Installation

Use Python 3.11 or 3.12. From a local checkout, in a fresh virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -e .
```

That one command installs everything: the transpiler, the plotting libraries,
the test and formatting tools, and `qiskit-ibm-runtime` for scripts of your own
that talk to IBM Quantum. The transpiler, the Graphix simulation and the local
Qiskit reference checks use only the core group of `dependencies` in
`pyproject.toml`; for a smaller environment, delete the groups you do not need
there before installing.

On Linux, Windows and Apple Silicon Macs this resolves to Graphix 0.4 and
Qiskit 2.6. On Intel Macs pip takes Graphix 0.3.5 instead, because numba 0.63
and later ship no Intel macOS wheels (the code runs on both), and an older
`cryptography` for the same reason. To use Graphix 0.4 on an Intel Mac, take
numba and llvmlite from conda-forge:

```bash
conda env create -f environment-graphix04.yml
conda activate masonq-graphix04
python -m pip install --no-deps -e .
```

See [Dependency migration](docs/dependency_migration.md) if an old environment
tries to build `numba` or `llvmlite` from source.

## Using MasonQ From Another Project

MasonQ is not on PyPI. Install it into the other project's environment in one
of these ways; the import is the same afterwards. Pin the `master` branch, the
one with the current code.

From the GitHub repository, for anyone with access to it (use `git+https://`
instead of `git+ssh://` if you authenticate to GitHub over HTTPS):

```bash
python -m pip install "masonq @ git+ssh://git@github.com/Nonsens24/MasonQ.git@master"
```

From a local checkout or the unzipped folder. Without `-e` pip copies the
package into the environment and no longer looks at the source folder:

```bash
python -m pip install /path/to/MasonQ
```

As a dependency of the other project, in its `pyproject.toml`:

```toml
dependencies = [
  "masonq @ git+ssh://git@github.com/Nonsens24/MasonQ.git@master",
]
```

Then, in that project:

```python
from brickwork_transpiler import transpile
```

The platform bounds in `pyproject.toml` travel with the package, so these
installs resolve the same way as the local one, including on Intel Macs.

## Quick Start

```python
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from brickwork_transpiler import transpile

qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)

# Brickwork patterns start every qubit in |+>, so that is the reference input.
input_state = Statevector.from_label("++")

result = transpile(qc, input_state, return_result=True, progress=True)
print(result.resources)

verification = result.verify()
print(verification.equivalent, verification.fidelity)

# Visualize the output Brickwork graph
result.plot(save_path="outputs/brickwork_graph.png", title="H and CX")
```

`transpile(...)` does not simulate automatically. It constructs and validates
the brickwork representation. Simulation happens only when you call
`result.simulate_statevector()` or `result.verify()`.

Pass `progress=True` to long-running calls for concise timed status messages.

## Visualise the Graph

MasonQ draws the brickwork graph itself, with matplotlib, which is installed
with it:

```python
result.plot(save_path="outputs/brickwork_graph.png", title="H and CX")
```

That writes the figure to the given path (a `.pdf` path gives a vector file).
Each node is a graph qubit, placed by wire (rows) and position along the wire
(columns); its label is `(row, column)` and its measurement angle as a multiple
of pi, and the colour gives the brick type, as the legend says: identity, Euler
rotation, or one of the two CX bricks. Measurement runs from left to right, and
the unmeasured output qubits sit on the far right.

To open a window instead of a file, pass `show=True`. Without `save_path`,
`plot()` writes `images/graphs/<title>.pdf` and `.png` under the current
directory.

## Main Objects

- `result.pattern`: the Graphix brickwork pattern.
- `result.decomposed_circuit`: the Qiskit circuit after decomposition, layout,
  routing, and basis lowering.
- `result.resources`: rows, brick columns, graph depth, graph nodes, and
  decomposed-circuit metrics.
- `result.plot(...)`: plot or save the generated brickwork graph.
- `result.simulate_statevector(...)`: simulate the Graphix pattern.
- `result.qiskit_reference_statevector(...)`: Qiskit reference in Graphix
  output order.
- `result.output_permutation()`: Qiskit-output to Graphix-output qubit order.
- `result.verify(...)`: Graphix/Qiskit statevector equivalence check.

For large resource sweeps, stop early:

```python
resources = transpile(qc, return_stage="resources")
sparse_matrix = transpile(qc, return_stage="sparse_matrix")
```

The scheduler objective is minimal brickwork graph depth:

```text
graph_depth = 4 * brick_columns + 1
```

## Noisy Simulation

`brickwork_transpiler.simulate_with_noise` runs a pattern on Graphix's
density-matrix backend, the only backend that applies noise, and deliberately
skips `standardize()` so the density matrix stays small. The tensor-network
backend used by `verify()` does not support noise. Details are in the
[Scientist guide](docs/scientist_quickstart.md).

## Documentation

Start with the [Scientist guide](docs/scientist_quickstart.md) for the full
workflow: transpilation options, layout and routing choices, return types,
decomposition strategies, verification, and sparse matrices.

- [Documentation index](docs/README.md)
- [Architecture](docs/architecture.md)
- [HLS decomposition and ancilla policy](docs/hls_decomposition.md)
- [Sparse instruction matrix](docs/sparse_matrix.md)
- [Dependency migration](docs/dependency_migration.md)
- [Limitations](docs/limitations.md)
- [Transpiler file guide](docs/transpiler_file_guide.md)

## Development

Fast tests:

```bash
pytest tests/unit_and_integration_tests -m "not slow and not system"
```

Slow end-to-end checks:

```bash
pytest tests/system_tests
```

Print versions in notebooks or benchmark logs:

```python
import brickwork_transpiler as bwt

bwt.show_versions()
```

## License

Proprietary.

## References

- Universal Blind Quantum Computation: https://arxiv.org/abs/0807.4154
- The Measurement Calculus: https://arxiv.org/abs/0704.1263
- Graphix: https://github.com/TeamGraphix/graphix
- Qiskit: https://www.ibm.com/quantum/qiskit
