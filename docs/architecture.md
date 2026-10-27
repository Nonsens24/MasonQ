# Architecture

This page describes the implementation-level structure of MasonQ for maintainers
and reviewers.

## System Overview

MasonQ is a whole-circuit brickwork transpiler. It converts Qiskit circuits
into aligned brickwork structures and Graphix patterns; the pipeline below is
the entire package.

## Transpiler Pipeline

### 1. Circuit preparation

- `decomposer.selective_decompose`
  Opens composite gates while preserving multi-controlled operations for
  specialised handling.
- `decomposer.linearise_multi_ctrl`
  Optionally rewrites large multi-control operations before Qiskit lowering.
- `decomposer.decompose_qc_to_bricks_qiskit`
  Delegates basis-lowering to Qiskit and targets the brickwork-compatible
  `rz`/`rx`/`cx`/`id` basis on a line coupling map.

### 2. Brick scheduling

- `decomposer.instructions_to_matrix_dag`
  Groups decomposed operations into DAG-aware columns.
- `decomposer.align_cx_matrix`
  Places CX bricks on parity-compatible brickwork columns.
- `decomposer.insert_rotations_adjacent_to_cx`
  Moves single-qubit rotations next to neighbouring CX bricks.

The CX alignment pass must remain linear in the number of CX groups it places.

### 3. Pattern generation

- `graph_builder.generate_brickwork_graph_from_instruction_matrix`
  Builds the brickwork graph.
- `pattern_converter.to_pattern`
  Injects measurement angles and produces the Graphix pattern.

## Scheduling Objective

MasonQ's internal scheduling objective is minimal graph depth, not minimal
Qiskit gate depth.

```text
graph_depth = 4 * brick_columns + 1
```

Gate count and decomposed circuit depth remain useful diagnostics, but the
brickwork graph depth is the primary optimisation target.

## Decomposition Policy

The public transpiler defaults to:

```python
brickwork_transpiler.transpile(..., multi_control_strategy="hls")
```

This keeps multi-controlled operations semantic until Qiskit's high-level
synthesis chooses an implementation.

The historical path remains available for reproducibility:

```python
brickwork_transpiler.transpile(..., multi_control_strategy="legacy-recursive")
```

Do not change the default without comparing:

- output equivalence;
- ancilla count;
- routed CX count;
- brickwork depth;
- failure and fallback rates under supported Qiskit versions.

## Ancilla Policy

Package-added ancillas are demand-driven.

- HLS MCX operations receive no package-added ancilla operands.
- Multi-controlled phase rewrites use one phase workspace qubit.
- The legacy recursive path uses an extra scratch qubit only for controls
  greater than or equal to 5.

See [HLS decomposition](hls_decomposition.md) for the detailed policy.

## Simulation Policy

`transpile(...)` builds output objects and validates structure. It does not run
simulation automatically.

```python
state = result.simulate_statevector()
verification = result.verify()
```

This keeps large conversions usable without accidentally triggering expensive
statevector work.

Noisy simulation goes through `brickwork_transpiler.simulate_with_noise`, which
depends on Graphix's density-matrix backend.

## Stage Returns

Use `return_stage` when users need intermediate products without the full result
object:

```python
decomposed_qc = transpile(qc, return_stage="decomposed_circuit")
matrix = transpile(qc, return_stage="matrix")
sparse_matrix = transpile(qc, return_stage="sparse_matrix")
resources = transpile(qc, return_stage="resources")
```

`return_stage="sparse_matrix"` is the preferred inspection format for large,
sparse aligned matrices.

## Testing Layers

- `tests/unit_and_integration_tests`
  Default development loop.
- `tests/system_tests`
  Slow Graphix/Qiskit equivalence checks.

Recommended local loop:

```bash
pytest tests/unit_and_integration_tests -m "not slow and not system"
```

Run system tests before releases and after changes to scheduling,
measurement-angle generation, or reference-state logic.
