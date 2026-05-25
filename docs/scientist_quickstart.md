# Scientist Guide

This guide is the practical reference for using MasonQ in notebooks, scripts,
and benchmark studies. The README gives the short public entry point; this page
collects the knobs scientists are most likely to vary.

## Install And Check Versions

```bash
pip install masonq
```

For local development from a checkout:

```bash
python -m pip install -e ".[dev]"
```

For optional IBM cloud/backend access in your own scripts:

```bash
python -m pip install "masonq[ibm]"
```

MasonQ itself does not use IBM Runtime for transpilation, Graphix simulation,
or local Qiskit reference checks.

Record versions in notebooks and benchmark logs:

```python
import brickwork_transpiler as bwt

bwt.show_versions()
```

## Recommended Workflow

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
    layout_method="trivial",
    routing_method="sabre",
    return_result=True,
    progress=True,
)

pattern = result.pattern
decomposed_qc = result.decomposed_circuit
resources = result.resources
```

The Graphix object is `result.pattern`. The Qiskit-side lowered circuit is
`result.decomposed_circuit`. The latter is useful for diagnostics, but it is
not the final MBQC object.

`transpile(...)` does not simulate automatically. Use simulation only when you
ask for it:

```python
state = result.simulate_statevector(progress=True)
verification = result.verify(tolerance=1e-8, progress=True)
```

Progress messages are off by default so library calls stay quiet in automated
workflows. Pass `progress=True` when running expensive notebook or terminal
jobs. You can also pass a callback, for example `progress=messages.append`, to
collect the same messages without printing them.

## Transpilation Options

The public function is:

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

Core options:

- `input_vector`: input state used later by `result.verify()` and
  `result.qiskit_reference_statevector()`.
- `layout_method`: passed to Qiskit's `transpile(...)`; common choices include
  `None`, `"trivial"`, `"dense"`, and `"sabre"`.
- `routing_method`: passed to Qiskit's `transpile(...)`; common choices include
  `None`, `"basic"`, `"lookahead"`, `"stochastic"`, and `"sabre"`.
- `with_ancillas`: allows MasonQ's pre-decomposition step to add explicit
  ancillas only when its selected decomposition requires them.
- `opt`: Qiskit optimization level, usually `3` for the best single-qubit
  merging or `1` for more robust large-circuit runs.
- `fallback_opt`: retry optimization level if the first Qiskit transpilation
  fails; set to `None` to fail immediately.
- `multi_control_strategy`: `"hls"` for the current default, or
  `"legacy-recursive"` for older experiment reproduction.
- `validate`: run structural validation of the matrix, graph, and pattern
  outputs.

Less common compatibility/debug options:

- `plot_decomposed=True`: draw the lowered Qiskit circuit.
- `verbose=True`: enable MasonQ logging.
- `file_writer`: legacy experiment hook for recording metrics.
- `return_mat=True`: legacy alias for `return_stage="matrix"`.
- `progress=True`: print concise timed progress messages for long-running
  stages, or pass a callback such as `progress=messages.append`.

## Layout And Routing

MasonQ asks Qiskit to lower the circuit to a line coupling map before brickwork
scheduling. Layout and routing choices therefore affect the decomposed circuit,
CX count, brick columns, graph depth, and output permutation.

Good starting points:

```python
# Deterministic debugging.
debug_result = transpile(
    qc,
    input_state,
    layout_method="trivial",
    routing_method="sabre",
    return_result=True,
)

# More realistic routing/layout study.
sabre_result = transpile(
    qc,
    input_state,
    layout_method="sabre",
    routing_method="sabre",
    return_result=True,
)

# Let Qiskit choose defaults for the given version.
default_result = transpile(qc, input_state, return_result=True)
```

Other Qiskit layout and routing plugin names may be accepted by your installed
Qiskit version. MasonQ forwards these strings to Qiskit rather than
reimplementing them.

For nontrivial layout, use MasonQ's layout-aware reference helpers:

```python
brickwork_state = result.simulate_statevector()
reference_state = result.qiskit_reference_statevector()
permutation = result.output_permutation()
```

Both `brickwork_state` and `reference_state` are returned in Graphix output
order. `output_permutation()` tells you how the decomposed Qiskit output order
was permuted to match Graphix.

## Decomposition Methods

The default is:

```python
transpile(qc, multi_control_strategy="hls")
```

This keeps multi-controlled X gates semantic and lets Qiskit's high-level
synthesis choose their implementation during basis lowering. Use this path for
new studies unless you have a specific reason not to.

For reproducing older runs:

```python
transpile(qc, multi_control_strategy="legacy-recursive")
```

The implemented ancilla policy is demand-driven:

- HLS MCX operations get no package-added ancilla operands.
- Multi-controlled phase rewrites get one phase workspace qubit.
- Legacy recursive MCX uses one clean scratch qubit only for controls `>= 5`.

See [HLS decomposition](hls_decomposition.md) for the detailed policy and
Qiskit references.

When comparing decomposition strategies, record at least:

- semantic equivalence on small circuits;
- number of qubits and package-added ancillas;
- decomposed `cx` count and Qiskit depth;
- `resources.brick_columns`, `resources.graph_depth`, and
  `resources.graph_nodes`;
- Qiskit `opt`, `fallback_opt`, layout, and routing methods.

MasonQ's scheduling objective is minimal graph depth:

```text
graph_depth = 4 * brick_columns + 1
```

The CX brick alignment pass is expected to scale linearly in the number of CX
groups after Qiskit decomposition.

## Return Types

Use `return_result=True` for normal work:

```python
result = transpile(qc, input_state, return_result=True)
```

`TranspileResult` exposes:

- `pattern`: Graphix brickwork pattern.
- `colour_map` / `color_map`: node-colour metadata for plotting.
- `decomposed_circuit`: lowered Qiskit circuit.
- `instruction_matrix`: dense aligned brick instruction matrix.
- `resources`: resource estimate computed from the matrix and circuit.
- `plot(...)`: safe plotting wrapper.
- `simulate(...)`: Graphix backend state object.
- `simulate_statevector(...)`: flat Graphix output statevector.
- `qiskit_reference_statevector(...)`: reference state in Graphix output order.
- `output_permutation()`: Qiskit-output to Graphix-output order.
- `verify(...)`: explicit Graphix/Qiskit comparison.
- `save_pattern_text(...)`: write Graphix's text pattern representation.

Use `return_stage` for sweeps and diagnostics:

```python
decomposed_qc = transpile(qc, return_stage="decomposed_circuit")
matrix = transpile(qc, return_stage="matrix")
sparse_matrix = transpile(qc, return_stage="sparse_matrix")
resources = transpile(qc, return_stage="resources")
graph_data = transpile(qc, return_stage="graph_data")
nx_graph = transpile(qc, return_stage="networkx_graph")
```

`return_stage="instruction_matrix"` is an alias for `"matrix"`.
`return_mat=True` is kept only for old notebooks and is equivalent to
`return_stage="matrix"`.

The historical tuple return still works:

```python
pattern, colour_map, decomposed_qc = transpile(qc, input_state)
```

New code should prefer `return_result=True`.

## Resource Sweeps

For large circuits, avoid building or simulating the full pattern unless you
need it:

```python
resources = transpile(qc, return_stage="resources")

print(resources.rows)
print(resources.brick_columns)
print(resources.graph_depth)
print(resources.graph_nodes)
print(resources.decomposed_depth)
print(resources.decomposed_cx_count)
```

Use the sparse matrix when the dense instruction matrix would mostly contain
empty cells:

```python
sparse = transpile(qc, return_stage="sparse_matrix")

print(sparse.shape)
print(sparse.non_empty_cells)
print(sparse.occupancy)

for row, column, instructions in sparse.iter_non_empty():
    print(row, column, [instruction.name for instruction in instructions])
```

Convert back only when a legacy tool expects the dense format:

```python
dense = sparse.to_dense()
```

See [Sparse instruction matrix](sparse_matrix.md) for the complete API.

## Correctness Checks

For small circuits:

```python
verification = result.verify(tolerance=1e-8, backend="tensornetwork")
verification.raise_for_failure()
```

`verify()` simulates the Graphix pattern, computes the Qiskit reference from
the source circuit and `result.decomposed_circuit`, then compares both states in
Graphix output order.

For manual checks:

```python
brickwork_state = result.simulate_statevector(seed=0)
qiskit_reference = result.qiskit_reference_statevector()
permutation = result.output_permutation()

print(permutation)
```

For larger circuits, full statevector simulation is usually the wrong default.
Use structural validation and resource estimates, then verify only small
representative cases.

## Plotting

For notebooks and IDEs, prefer saving large graphs:

```python
result.plot(save_path="images/graphs/my_circuit.pdf", show=False)
```

Use `show=True` for small interactive plots.

## Noisy Simulation

For incoherent-noise studies use `simulate_with_noise`:

```python
from brickwork_transpiler import (
    DepolarisingNoiseModel,
    simulate_with_noise,
    density_matrix,
    state_fidelity,
)

noise = DepolarisingNoiseModel(
    prepare_error_prob=0.01,
    entanglement_error_prob=0.02,
    measure_channel_prob=0.01,
)
state = simulate_with_noise(result.pattern, noise, seed=0)

rho = density_matrix(state)                          # numpy ndarray, trace 1
fidelity = state_fidelity(state, qiskit_reference)   # in [0, 1]
```

Graphix's `densitymatrix` backend is the **only** backend that implements
`apply_noise`; `tensornetwork` and `statevector` raise
`NoiseNotSupportedError`. `simulate_with_noise` therefore always uses the
density-matrix backend.

`standardize` and `shift_signals` default to `False` here (the opposite of
the noiseless path) so that measurements stay interleaved with
preparations. This keeps the density matrix small enough to simulate
moderate brickwork patterns in seconds rather than blowing up to
`2^(graph nodes)`.

## BFK Experiment Metadata

For blind-computation experiments:

```python
from brickwork_transpiler import encode_pattern

encoded_pattern, alice_log = encode_pattern(
    result.pattern,
    return_metadata=True,
)

preparations = alice_log["preparations"]
measurements = alice_log["measurements"]
```

The BFK encoder follows Protocol 1 of Broadbent-Fitzsimons-Kashefi: Alice
prepares graph qubits as `|+_theta>`, with `theta` sampled from the eight
pi/4 angles, and sends Bob blinded measurement angles
`delta = phi' + theta + r (mod 2)`.

Supplied `theta_lookup` values are validated against the pi/4 grid by default.
Set `quantum_outputs=True` for Protocol 3-style quantum-output experiments,
where output qubits are prepared as `|+>`.

## What To Report In A Paper

For reproducibility, report:

- MasonQ version and `show_versions()` output;
- source circuit construction and input state;
- `layout_method`, `routing_method`, `opt`, and `fallback_opt`;
- `multi_control_strategy` and whether `with_ancillas` was enabled;
- decomposed qubit count, `cx` count, and Qiskit depth;
- brick rows, brick columns, graph depth, and graph nodes;
- whether correctness was checked by `verify()` or by structural/resource
  validation only.
