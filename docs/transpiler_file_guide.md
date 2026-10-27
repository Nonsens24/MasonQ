# Transpiler File Guide

This document explains how the MasonQ transpiler works and what each source
file is responsible for.

## Current Pipeline

The public entry point is:

```python
from brickwork_transpiler import transpile

result = transpile(qc, return_result=True)
pattern = result.pattern
decomposed_qc = result.decomposed_circuit
resources = result.resources
```

The default tuple return remains available for older scripts:

```python
pattern, colour_map, decomposed_qc = transpile(qc)
```

The returned Qiskit circuit is called `decomposed_circuit` because it is the
Qiskit-side circuit lowered into the package's brickwork basis. It is not the
final MBQC object. `result.transpiled_circuit` remains as a compatibility alias
only.

The pipeline is:

1. `brickwork_transpiler.transpile` receives a unitary Qiskit circuit.
2. `decomposer.selective_decompose` opens composite wrappers while preserving
   multi-controlled operations that need explicit handling.
3. `decomposer.linearise_multi_ctrl` optionally rewrites multi-controlled
   operations before Qiskit's basis decomposition.
4. `decomposer.decompose_qc_to_bricks_qiskit` asks Qiskit to emit the
   brickwork-compatible basis `rz`, `rx`, `cx`, and `id` on a line coupling map.
5. `decomposer.instructions_to_matrix_dag` schedules Qiskit operations into a
   per-qubit/per-column instruction matrix and tags every CX endpoint
   (`cx_tags.tag_cx`).
6. `decomposer.align_cx_matrix` places each CX group onto a parity-compatible
   brickwork column.
7. `decomposer.insert_rotations_adjacent_to_cx` places local rotations next to
   their neighbouring CX bricks without commuting them through CX gates.
8. `validation.validate_instruction_matrix` checks structural invariants.
9. `graph_builder.generate_brickwork_graph_from_instruction_matrix` builds the
   brickwork graph data.
10. `graph_builder.to_networkx_graph` converts graph data into NetworkX.
11. `pattern_converter.to_pattern` computes measurement angles and creates the
    Graphix pattern through `OpenGraph.to_pattern()`.
12. `validation.validate_pattern_outputs` checks Graphix output ordering and
    dimensions.
13. `TranspileResult` packages the pattern, colour map, decomposed Qiskit
    circuit, instruction matrix, resources, and verification helpers.

The pattern has no input nodes: every graph qubit starts in `|+>`, as in
universal blind quantum computation, so the pattern computes `U|+...+>` and
`verify()` compares against that reference.

## Decomposition Policy

The default multi-control strategy is:

```python
transpile(qc, multi_control_strategy="hls")
```

This follows current Qiskit practice: represent multi-controlled X operations
with semantic `MCXGate` objects and let Qiskit's high-level synthesis choose the
implementation during basis lowering.

The legacy path remains available:

```python
transpile(qc, multi_control_strategy="legacy-recursive")
```

Use it only when reproducing older experiments that depended on
`MCXRecursive`, which Qiskit deprecated in 2.1 and removes in 3.0.

For the detailed HLS/MCX policy, see
[HLS decomposition](hls_decomposition.md).

## Ancilla Policy

Ancillas are allocated only when the decomposition path actually needs them:

- Plain HLS `MCXGate` operations get no package-added ancilla operands.
- Multi-controlled phase rewrites get one phase workspace qubit.
- The legacy recursive strategy gets one scratch qubit only for controls `>= 5`.
- `linearise_multi_ctrl` does not mutate the input circuit. It returns a new
  circuit and adds any required ancilla registers there.

This is the implemented policy in `decomposer._required_explicit_ancillas` and
`decomposer._copy_with_required_ancillas`.

## CX Linearity Requirement

The brick scheduler must remain linear in the number of CX groups. The current
implementation keeps these invariants:

- each original CX group contributes one two-endpoint brick;
- no CX endpoint is duplicated or lost during alignment;
- aligned brick width grows linearly with the number of CX groups;
- rotations are inserted near neighbouring CX bricks without changing CX group
  count.

The fast test suite contains regression tests for these invariants in
`tests/unit_and_integration_tests/test_decomposer.py::TestCxLinearity` and the
`test_align_cx_*.py` files.

## Optimization Objective

The package objective is minimal graph depth, not minimum Qiskit gate count:

```text
graph_depth = 4 * brick_columns + 1
```

Qiskit is trusted to decompose the input circuit into an equivalent circuit in
the supported basis. MasonQ's job starts after that: schedule the decomposed
operations into a brickwork graph with as little graph depth as possible while
preserving the decomposed circuit semantics.

`SparseInstructionMatrix` and `return_stage="sparse_matrix"` store only the
non-empty cells of an aligned matrix. The dense matrix remains the internal
default for pattern generation, debugging, and plotting.

## Source Files

### `src/brickwork_transpiler/__init__.py`

Defines the public package surface: `transpile`, `TranspileResult`,
`VerificationResult`, the BFK encoder, the noise helpers, resource and timing
helpers, custom exceptions, and `show_versions`.

### `src/brickwork_transpiler/brickwork_transpiler.py`

Top-level orchestration for the conversion pipeline. It calls decomposition,
matrix scheduling, graph construction, pattern conversion, validation, and
finally returns either the legacy tuple or a `TranspileResult`.

### `src/brickwork_transpiler/decomposer.py`

Owns the Qiskit-side decomposition and brick scheduling logic:

- selective decomposition of composite gates;
- demand-driven multi-control handling;
- Qiskit basis lowering to `rz`/`rx`/`cx`/`id`;
- DAG-based operation grouping;
- CX endpoint tagging;
- parity-compatible CX brick alignment;
- rotation insertion around CX bricks.

This is the key file for correctness, performance, and CX-linearity.

### `src/brickwork_transpiler/cx_tags.py`

The `cx{id}c` / `cx{id}t` endpoint-name format and the only code that
produces or parses it.

### `src/brickwork_transpiler/validation.py`

Structural validation checks for instruction matrices, graph data, and
pattern outputs. These checks catch malformed matrices, output ordering errors,
and invalid graph dimensions early.

### `src/brickwork_transpiler/graph_builder.py`

Converts the aligned instruction matrix into brickwork graph data and then into
a NetworkX graph. It is responsible for preserving row/column geometry.

### `src/brickwork_transpiler/pattern_converter.py`

Converts the brickwork graph plus instruction matrix into a Graphix pattern.
It computes measurement angles, holds the CX brick angle tables, and injects
each CX gadget once from its top-row endpoint.

### `src/brickwork_transpiler/result.py`

Defines `TranspileResult` and `VerificationResult`. This is the scientist-facing
result API: resources, plotting, simulation, verification, pattern copying, and
text export live here. It also exposes `output_permutation()` and
`qiskit_reference_statevector()` for manual Graphix/Qiskit statevector checks.

### `src/brickwork_transpiler/resources.py`

Defines `ResourceEstimate` and `estimate_resources`. It reports decomposed
Qiskit qubits, depth, gate count, CX count, brick rows, brick columns, and graph
node count.

### `src/brickwork_transpiler/sparse.py`

Defines `SparseInstructionMatrix`, a space-efficient aligned brick matrix view
that stores only non-empty cells plus the original row/column dimensions. It is
returned by `transpile(..., return_stage="sparse_matrix")`.

### `src/brickwork_transpiler/utils.py`

Shared numerical and layout utilities: statevector comparison, qubit
permutation, reference-state calculation, input state padding for ancillas,
Graphix output-order permutation, and the layout mapping helpers used by the
system tests.

### `src/brickwork_transpiler/noise.py`

Noisy simulation through Graphix's density-matrix backend, plus
`density_matrix` and `state_fidelity` helpers. Not part of the conversion path.

### `src/brickwork_transpiler/bfk_encoder.py`

BFK Protocol-1 encoding of a whole pattern. It records Alice's pi/4-grid
`|+_theta>` qubit preparations and Bob-facing blinded measurement angles
`delta = phi' + theta + r (mod 2)`. The core transpiler does not call this
automatically; experiments should call `encode_pattern(..., return_metadata=True)`
on an already-built brickwork pattern.

### `src/brickwork_transpiler/visualiser.py`

Plotting and graph visualisation support: brickwork graph plots with
measurement angles, a plain grid plot, and a text dump of instruction
matrices, with safe plot saving/showing for notebooks and IDEs.

### `src/brickwork_transpiler/bricks.py`

Hand-built single bricks (Euler rotation, CX with either orientation) as
standalone Graphix patterns, used by the tests to check the angle tables.

### `src/brickwork_transpiler/circuits.py`

Small fixture circuits used by the tests and examples.

### `src/brickwork_transpiler/progress.py`, `profiling.py`, `exceptions.py`, `_versions.py`

Progress reporting for long runs, a small timing helper, the package
exceptions, and `show_versions()`.

### `src/brickwork_transpiler/main.py`

Small executable demo used by the `masonq-demo` console script. It should stay
lightweight and should not contain core algorithmic logic.

### `src/brickwork_transpiler/py.typed`

Marker file telling type checkers that the package ships type information.

## Files That Should Not Matter To The Package

Generated caches and outputs should not be committed or relied on:

- `__pycache__/`
- `.pytest_cache/`
- `htmlcov/`
- `coverage.xml`
- `outputs/`
- `*.egg-info/`
- generated plot images under `images/graphs/`

The authoritative package configuration is `pyproject.toml`;
`environment-graphix04.yml` is the conda-forge route to Graphix 0.4 on Intel
Macs.
