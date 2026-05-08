
[//]: # (![Logo]&#40;images/masonQ_nobg.png&#41;)
![](images/masonQ_dark.png)

MasonQ is a layout-aware transpiler from unitary Qiskit circuits to brickwork
measurement-based quantum computation patterns. It lowers circuits to a
brickwork-compatible `rz`/`rx`/`cx` basis, schedules them onto a brickwork
instruction matrix, builds the corresponding graph, and emits a Graphix pattern
with measurement angles.

The project is research-grade and currently alpha quality: the core pipeline is
covered by unit and integration tests, while slower end-to-end Graphix/Qiskit
statevector checks live in `tests/system_tests`.

## Installation

From source:

```bash
git clone https://github.com/Nonsens24/brickwork_transpiler.git
cd brickwork_transpiler
python -m pip install -e ".[dev,viz,qrs]"
```

For IBM Quantum Runtime access:

```bash
python -m pip install -e ".[ibm]"
```

Use `qiskit-ibm-runtime` for IBM access. Do not install the deprecated
`qiskit-ibm-provider` or `qiskit-ibmq-provider` packages in new environments.

For library use only:

```bash
python -m pip install -e .
```

## Quick Start

```python
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from brickwork_transpiler import transpile

qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)

input_state = Statevector.from_label("++")

result = transpile(
    qc,
    input_state,
    routing_method="sabre",
    layout_method="trivial",
    with_ancillas=True,
    return_result=True,
)

result.plot(save_path="images/graphs/quickstart.pdf", show=False)
verification = result.verify()
print(result.resources)
print(verification.equivalent, verification.fidelity)
```

`transpile(...)` does not simulate automatically. It constructs and validates
the brickwork pattern. Simulation happens only when you explicitly call
`result.simulate_statevector()` or `result.verify()`.

## Simulation And Reference Checks

The actual brickwork/MBQC object is the Graphix pattern:

```python
pattern = result.pattern
```

To simulate the brickwork pattern with Graphix:

```python
brickwork_state = result.simulate_statevector(
    backend="tensornetwork",
    graph_prep="parallel",
    seed=0,
)
```

To compare that Graphix result against a layout-aware Qiskit statevector
reference:

```python
verification = result.verify(tolerance=1e-8)

print(verification.equivalent)
print(verification.fidelity)
```

For advanced debugging, the Qiskit reference can be computed directly from the
original circuit, the Graphix output ordering, and the decomposed Qiskit circuit:

```python
from brickwork_transpiler import utils

reference_state = utils.calculate_ref_state_from_qiskit_circuit(
    result.pattern,
    qc,
    result.decomposed_circuit,
    input_state,
)
```

Use `verify()` for normal correctness checks. It runs both sides consistently
and handles the output-order comparison used by the package.

If you want to inspect or reproduce the comparison yourself:

```python
brickwork_state = result.simulate_statevector()
qiskit_reference = result.qiskit_reference_statevector()
permutation = result.output_permutation()

print(permutation)
```

`output_permutation()` is the qubit permutation that maps the decomposed Qiskit
circuit output order into Graphix's output statevector order. This is the
important piece when `layout_method` is not trivial.

## Layout Methods And Verification

MasonQ supports Qiskit layout/routing choices through the normal Qiskit
arguments:

```python
result = transpile(
    qc,
    input_state,
    routing_method="sabre",
    layout_method="sabre",
    return_result=True,
)
```

The recommended choices are:

- `layout_method="trivial"` for debugging and deterministic logical-to-row
  interpretation;
- `layout_method="sabre"` for realistic line-layout routing experiments;
- `routing_method="sabre"` for nontrivial circuits on the line coupling map.

For verification, MasonQ compares the Graphix simulation with the decomposed
Qiskit circuit after Qiskit's layout and routing have already been applied.
It then permutes the Qiskit reference into Graphix output order. This means
`result.verify()` can be used with nontrivial layout methods for supported
circuits:

```python
verification = result.verify(tolerance=1e-8)
assert verification.equivalent
```

For manual checks, compare `result.simulate_statevector()` with
`result.qiskit_reference_statevector()`. Both are returned in Graphix output
order.

## Public Pipeline

```python
bw_pattern, col_map, decomposed_qc = brickwork_transpiler.transpile(
    qc,
    input_vector=None,
    routing_method="sabre",
    layout_method="trivial",
    with_ancillas=True,
    opt=3,
    fallback_opt=1,
    multi_control_strategy="hls",
)
```

For new code, prefer `return_result=True`. `TranspileResult` exposes:

- `result.pattern`
- `result.decomposed_circuit`
- `result.resources`
- `result.plot(...)`
- `result.simulate_statevector(...)`
- `result.verify(...)`
- `result.save_pattern_text(...)`

`multi_control_strategy="hls"` uses Qiskit's current high-level synthesis path
for multi-controlled gates. For reproducing older experiments, use
`multi_control_strategy="legacy-recursive"` and record equivalence, ancilla
count, CX count, and brickwork depth in your run notes.

The decomposition adds explicit ancillas only when required: no package-added
ancilla for plain HLS MCX, one phase workspace for multi-controlled phase
rewrites, and one extra scratch qubit only for legacy recursive controls >= 5.
The CX brick scheduler is regression-tested so aligned brick width grows
linearly with the number of CX groups.

## Development

Fast development loop:

```bash
pytest tests/unit_and_integration_tests -m "not slow and not system"
```

Full end-to-end checks:

```bash
pytest tests/system_tests
```

## Reproducibility

Print dependency versions in notebooks or benchmark logs:

```python
import brickwork_transpiler as bwt

bwt.show_versions()
```

Known scope and caveats are documented in [docs/limitations.md](docs/limitations.md).

The system tests are intentionally slow because they simulate complete
Graphix/Qiskit equivalence cases.

## Package Layout

- `brickwork_transpiler.brickwork_transpiler`: public orchestration API.
- `brickwork_transpiler.decomposer`: Qiskit decomposition, DAG grouping, and
  brick matrix alignment.
- `brickwork_transpiler.graph_builder`: brickwork graph construction.
- `brickwork_transpiler.pattern_converter`: measurement-angle injection and
  Graphix pattern generation.
- `brickwork_transpiler.utils`: statevector comparison, layout/reference-state
  helpers, and small data utilities.
- `brickwork_transpiler.algorithms`: example/research circuits, including QRS
  and HHL-related work.
- `brickwork_transpiler.experiments`: research scripts and plotting utilities.

See [docs/architecture.md](docs/architecture.md) for the decomposition policy
and algorithmic invariants.

## Documentation

- [Documentation index](docs/README.md)
- [Architecture and decomposition policy](docs/architecture.md)
- [HLS decomposition and ancilla policy](docs/hls_decomposition.md)
- [Transpiler file guide](docs/transpiler_file_guide.md)
- [Scientist quickstart](docs/scientist_quickstart.md)
- [Dependency migration](docs/dependency_migration.md)
- [Limitations](docs/limitations.md)

## License

Proprietary. See [LICENSE](LICENSE).

## References

- Universal Blind Quantum Computation: https://arxiv.org/abs/0807.4154
- The Measurement Calculus: https://arxiv.org/abs/0704.1263
- Graphix: https://github.com/TeamGraphix/graphix
- Qiskit: https://www.ibm.com/quantum/qiskit
