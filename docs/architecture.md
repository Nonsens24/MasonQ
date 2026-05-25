# Architecture

MasonQ converts unitary Qiskit circuits into brickwork measurement patterns.
The package has three layers:

1. Circuit preparation
   - `decomposer.selective_decompose` opens composite gates while preserving
     multi-controlled operations for controlled handling.
   - `decomposer.linearise_multi_ctrl` optionally rewrites large multi-control
     operations before Qiskit's transpiler lowers the circuit.
   - `decomposer.decompose_qc_to_bricks_qiskit` asks Qiskit to emit the
     brickwork-compatible basis `rz`, `rx`, `cx`, and `id` on a line coupling
     map.

2. Brick scheduling
   - `decomposer.instructions_to_matrix_dag` groups DAG-ready operations into
     columns.
   - `decomposer.align_cx_matrix` places CX bricks on the parity-compatible
     brickwork columns. This pass must remain linear in the number of CX
     groups it places; every CX contributes one two-row brick, and tests assert
     that brick width grows linearly with CX count.
   - `decomposer.insert_rotations_adjacent_to_cx` places single-qubit
     rotations near their neighbouring CX bricks. The legacy alias
     `insert_rotations_adjecant_to_cx` (with the historical typo) remains
     supported for backwards compatibility.

3. Pattern generation
   - `graph_builder.generate_brickwork_graph_from_instruction_matrix` creates
     the brickwork graph.
   - `pattern_converter.to_pattern` injects measurement angles and calls
     Graphix to build the MBQC pattern.

## Qiskit Decomposition Policy

The public transpiler currently defaults to:

```python
brickwork_transpiler.transpile(..., multi_control_strategy="hls")
```

That follows Qiskit's current recommendation for multi-controlled gates:
construct the semantic `MCXGate` and let high-level synthesis choose the
implementation. The historical recursive path remains available for
reproducibility:

```python
brickwork_transpiler.transpile(..., multi_control_strategy="legacy-recursive")
```

Do not switch the default without comparing:

- output state equivalence,
- introduced ancilla count,
- routed `cx` count,
- final brickwork depth,
- failure/fallback rate at Qiskit optimisation levels 1 and 3.

The primary optimization target for MasonQ's own scheduler is **minimal graph
depth**. In this package, graph depth is the number of graph columns:

```text
graph_depth = 4 * brick_columns + 1
```

Qiskit is responsible for producing an equivalent decomposed circuit in the
`rz`/`rx`/`cx`/`id` basis. MasonQ should then schedule that decomposed circuit
into the shallowest brickwork graph it can without changing circuit semantics.
Gate count and Qiskit circuit depth are useful diagnostics, but they are not
the core objective.

Explicit ancillas are allocated only when the chosen decomposition needs them:
plain HLS multi-controlled X gates get no package-added ancilla operands,
multi-controlled phase rewrites get one phase workspace qubit, and the legacy
recursive path gets a second scratch qubit only for controls >= 5.

See [HLS decomposition](hls_decomposition.md) for the detailed multi-control
policy and Qiskit references.

## Simulation Policy

`transpile(...)` does not run Graphix simulation automatically. It constructs
the pattern, validates structural invariants, and returns a `TranspileResult`.
Simulation is explicit:

```python
state = result.simulate_statevector()
verification = result.verify()
```

This keeps large conversions usable without accidentally triggering
exponential statevector work.

Noisy simulation goes through `brickwork_transpiler.simulate_with_noise`,
which is hard-wired to Graphix's **density-matrix backend**. That backend
is the only one in Graphix with native `apply_noise` support;
`tensornetwork` and `statevector` raise `NoiseNotSupportedError` on noise
commands. `simulate_with_noise` also disables `standardize` and
`shift_signals` by default so qubits are traced out as soon as they are
measured, keeping peak DM dimension proportional to the pattern's local
interaction degree rather than to the full graph node count.

## Stage Returns

Scientists often need resource data without paying for Graphix pattern
materialization. Use `return_stage` to stop the pipeline early:

```python
decomposed_qc = transpile(qc, return_stage="decomposed_circuit")
matrix = transpile(qc, return_stage="matrix")
sparse_matrix = transpile(qc, return_stage="sparse_matrix")
resources = transpile(qc, return_stage="resources")
graph_data = transpile(qc, return_stage="graph_data")
nx_graph = transpile(qc, return_stage="networkx_graph")
```

`return_mat=True` remains as a compatibility alias for
`return_stage="matrix"`.

`return_stage="sparse_matrix"` returns `SparseInstructionMatrix`, which stores
only non-empty aligned brick cells while preserving the dense matrix shape. This
is the preferred inspection format for large, sparse circuits.

`resources.graph_depth` is the graph-depth objective. `resources.brick_columns`
is the same depth measured in brick columns before expansion to graph columns.

## Test Layers

Use `tests/unit_and_integration_tests` for normal development. The
`tests/system_tests` folder contains slow Graphix/Qiskit equivalence simulations
and is automatically marked as both `system` and `slow`.

Recommended local loop:

```bash
pytest tests/unit_and_integration_tests -m "not slow and not system"
```

Run system tests only before releases or when changing scheduling,
measurement-angle generation, or reference-state logic.
