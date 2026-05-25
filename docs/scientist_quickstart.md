# Scientist And User Guide

This is the main practical guide for using MasonQ in notebooks, scripts, and
evaluation workflows.

## Installation

### Recommended repository workflow

```bash
conda env create -f environment.yml
conda activate masonq-qiskit24
python -m pip install -e ".[dev]"
```

If you are using your own Conda environment name, install the same project into
that environment and make sure your IDE points at the matching interpreter.

## Recommended Workflows

### Brickwork transpilation

```python
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from brickwork_transpiler import transpile

qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)

result = transpile(
    qc,
    Statevector.from_label("00"),
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

### Selective cloaking

```python
from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import sensitive, cloak_compile, simulate_cloaked

qc = QuantumCircuit(3)
qc.h([0, 1, 2])

with sensitive(qc, [0, 1, 2], label="oracle") as oracle:
    oracle.cx(0, 1)
    oracle.x(2)

qc.h([0, 1, 2])

state = simulate_cloaked(qc, seed=0)
job = cloak_compile(qc, rounds=3, seed=0)

print(job.metadata["blind_share"].format())
```

Use cloaking when the sensitive region is compact and the surrounding algorithm
can remain public.

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
  Used by verification and reference-state helpers.
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

### `CloakedJob`

`cloak_compile(...)` returns a job object that includes the public outer circuit,
the blinded subcircuits, RSP preparation plan, QOTP tracking metadata, boundary
classification, and blind-share reporting.

This is the right object to hand off to a delegated execution layer.

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
PYTHONPATH=src python examples/cloak/01_finance_qaoa.py
PYTHONPATH=src python examples/cloak/03_defence_logistics.py
```

More example navigation is collected in:

- [Cloak examples overview](../examples/cloak/README.md)
- [Application demos](../examples/cloak/applications/README.md)

## Next Reading

- [Limitations](limitations.md)
- [Sparse instruction matrix](sparse_matrix.md)
- [Architecture](architecture.md)
- [VEIL / cloak opportunity catalogue](veil_opportunities.md)
