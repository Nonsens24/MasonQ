# Scientist And User Guide

This is the main practical guide for using MasonQ in notebooks, scripts, and
evaluation workflows.

## Installation

### Recommended repository workflow

Use Python 3.11 or 3.12 in a fresh virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

On Intel Macs this gives Graphix 0.3.5 rather than 0.4; the README describes
the conda-forge route (`environment-graphix04.yml`) if you need 0.4 there. If
you use an environment of your own, install the project into it and make sure
your IDE points at the matching interpreter.

## Recommended Workflows

### Brickwork transpilation

```python
from qiskit import QuantumCircuit

from brickwork_transpiler import transpile

qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)

result = transpile(
    qc,
    layout_method="trivial",
    routing_method="sabre",
    return_result=True,
)

print(result.resources)
pattern = result.pattern
```

Use `return_result=True` for normal work. The result object gives you the
pattern, decomposed circuit, resource estimates, simulation helpers, and
verification helpers in one place.

Brickwork patterns prepare every qubit in `|+>`, so the pattern computes
`U|+...+>`. `verify()` uses that input by default. To start from another
state, prepend the preparation gates to the circuit; passing a different
input state raises an error.

## Core API Surface

### Transpiler

The main entry point is:

```python
result = transpile(
    qc,
    input_vector=None,
    routing_method=None,
    layout_method=None,
    with_ancillas=True,
    opt=3,
    fallback_opt=1,
    multi_control_strategy="hls",
    validate=True,
    return_result=True,
)
```

Most important options:

- `input_vector`
  Optional. The reference input for verification is always `|+>^n`; pass it
  only to be explicit.
- `layout_method`
  Forwarded to Qiskit. Common choices are `None`, `"trivial"`, `"dense"`, and
  `"sabre"`.
- `routing_method`
  Forwarded to Qiskit. Common choices are `None`, `"basic"`, `"lookahead"`,
  `"stochastic"`, and `"sabre"`.
- `with_ancillas`
  Allows package-added ancillas only when the chosen decomposition needs them.
- `opt`
  Qiskit optimisation level.
- `fallback_opt`
  Retry optimisation level if the first pass fails.
- `multi_control_strategy`
  Use `"hls"` for current work and `"legacy-recursive"` only for historical
  reproduction.
- `validate`
  Runs structural checks on the generated output.

## Result Objects

### `TranspileResult`

Important attributes and helpers:

- `pattern`
- `decomposed_circuit`
- `instruction_matrix`
- `resources`
- `plot(...)`
- `simulate(...)`
- `simulate_statevector(...)`
- `qiskit_reference_statevector(...)`
- `output_permutation()`
- `verify(...)`
- `save_pattern_text(...)`

Use explicit simulation only when you need it:

```python
state = result.simulate_statevector(progress=True)
verification = result.verify(tolerance=1e-8, progress=True)
```

`transpile(...)` does not simulate automatically.

### Noisy simulation

`simulate_with_noise(pattern, noise_model)` runs the pattern on Graphix's
density-matrix backend, the only backend that applies noise. It deliberately
does not call `standardize()` first: a standardised pattern keeps every prepared
qubit alive until the end, so the density matrix grows with the graph size
instead of the row count. The tensor-network backend used by `simulate()` and
`verify()` does not support noise.

## Return Stages For Diagnostics

When you do not need the full result object, use `return_stage`:

```python
decomposed_qc = transpile(qc, return_stage="decomposed_circuit")
matrix = transpile(qc, return_stage="matrix")
sparse_matrix = transpile(qc, return_stage="sparse_matrix")
resources = transpile(qc, return_stage="resources")
graph_data = transpile(qc, return_stage="graph_data")
nx_graph = transpile(qc, return_stage="networkx_graph")
```

Use `return_stage="resources"` for large sweeps that only need estimates. Use
`return_stage="sparse_matrix"` when you want a compact view of aligned work.

## Layout And Routing Guidance

MasonQ delegates basis-lowering and routing to Qiskit before brickwork
scheduling. Layout and routing choices therefore affect CX count, brick columns,
graph depth, and output permutation.

Good defaults:

```python
debug_result = transpile(
    qc,
    input_vector,
    layout_method="trivial",
    routing_method="sabre",
    return_result=True,
)

study_result = transpile(
    qc,
    input_vector,
    layout_method="sabre",
    routing_method="sabre",
    return_result=True,
)
```

For nontrivial layout, compare against MasonQ's layout-aware reference helpers
rather than a naive Qiskit statevector.

## Progress And Long Runs

Library calls stay quiet by default. For notebook or terminal jobs, use:

```python
result = transpile(qc, return_result=True, progress=True)
```

You may also pass a callback such as `progress=messages.append`.

## Example Entry Points

From the repository root:

```bash
PYTHONPATH=src python examples/01_basic_transpile.py
PYTHONPATH=src python examples/02_plot_and_verify.py
```

The other examples are `03_resource_estimates.py` and `04_save_pattern.py`.

## Next Reading

- [Limitations](limitations.md)
- [Sparse instruction matrix](sparse_matrix.md)
- [Architecture](architecture.md)
