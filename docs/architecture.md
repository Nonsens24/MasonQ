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
   - `decomposer.insert_rotations_adjecant_to_cx` places single-qubit rotations
     near neighbouring CX bricks.

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

The important invariant is semantic equivalence, not exact gate count. Gate
count and brickwork depth should be treated as benchmarking outputs, not as
part of the package API.

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
