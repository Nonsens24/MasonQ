# Transpiler File Guide

This document explains how the MasonQ transpiler works after the cleanup pass
and what each source file is responsible for.

## Current Pipeline

The public entry point is:

```python
from brickwork_transpiler import transpile

result = transpile(qc, input_vector, return_result=True)
pattern = result.pattern
decomposed_qc = result.decomposed_circuit
resources = result.resources
```

The default tuple return remains available for older scripts:

```python
pattern, colour_map, decomposed_qc = transpile(qc, input_vector)
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
   per-qubit/per-column instruction matrix.
6. `decomposer.align_cx_matrix` places each CX group onto a parity-compatible
   brickwork column.
7. `decomposer.insert_rotations_adjacent_to_cx` places local rotations next to
   their neighbouring CX bricks without commuting them through CX gates.
8. `validation.validate_instruction_matrix` checks structural invariants.
9. `graph_builder.generate_brickwork_graph_from_instruction_matrix` builds the
   brickwork graph data.
10. `graph_builder.to_networkx_graph` converts graph data into NetworkX.
11. `pattern_converter.to_pattern` computes measurement angles, injects graph
    metadata, and creates the Graphix pattern.
12. `validation.validate_pattern_outputs` checks Graphix output ordering and
    dimensions.
13. `TranspileResult` packages the pattern, colour map, decomposed Qiskit
    circuit, instruction matrix, resources, and verification helpers.

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
`MCXRecursive`.

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
`tests/unit_and_integration_tests/test_decomposer.py::TestCxLinearity`.

## Optimization Objective

The package objective is minimal graph depth, not minimum Qiskit gate count:

```text
graph_depth = 4 * brick_columns + 1
```

Qiskit is trusted to decompose the input circuit into an equivalent circuit in
the supported basis. MasonQ's job starts after that: schedule the decomposed
operations into a brickwork graph with as little graph depth as possible while
preserving the decomposed circuit semantics.

When discussing future sparse representations, "sparse IR" means storing only
real scheduled operations and CX brick groups instead of storing a full
`rows x columns` matrix containing many empty cells. MasonQ now exposes a first
step in that direction with `SparseInstructionMatrix` and
`return_stage="sparse_matrix"`. The dense matrix remains the internal default
for pattern generation, debugging, and plotting.

## Public Source Files

### `src/brickwork_transpiler/__init__.py`

Defines the public package surface. It exports `transpile`, `TranspileResult`,
`VerificationResult`, resource helpers, timing helpers, custom exceptions, and
`show_versions`.

### `src/brickwork_transpiler/_versions.py`

Provides `show_versions()`, a small reproducibility helper that prints and
returns versions for Python, Qiskit, Graphix, Quimb, NumPy, NetworkX, and the
package itself.

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

### `src/brickwork_transpiler/graph_builder.py`

Converts the aligned instruction matrix into brickwork graph data and then into
a NetworkX graph. It is responsible for preserving row/column geometry and
node-level metadata used later by Graphix and the visualiser.

### `src/brickwork_transpiler/pattern_converter.py`

Converts the brickwork graph plus instruction matrix into a Graphix pattern.
It computes measurement angles, handles Graphix API compatibility, and ensures
CX gadgets are injected once from their top-row endpoint.

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

### `src/brickwork_transpiler/validation.py`

Contains structural validation checks for instruction matrices, graph data, and
pattern outputs. These checks catch malformed matrices, output ordering errors,
and invalid graph dimensions early.

### `src/brickwork_transpiler/exceptions.py`

Defines package-specific exceptions, including validation errors. Public errors
should come from here instead of raw generic exceptions when possible.

### `src/brickwork_transpiler/profiling.py`

Small timing utilities for recording elapsed time around expensive stages.

### `src/brickwork_transpiler/utils.py`

Shared numerical and layout utilities. Important responsibilities include
statevector comparison, qubit permutation, reference-state calculation, input
state padding for ancillas, Graphix output-order permutation, and layout mapping
helpers.

### `src/brickwork_transpiler/visualiser.py`

Plotting and graph visualisation support. It handles Graphix pattern graph
extraction, node labels, measurement angles, and safe plot saving/showing for
notebooks and IDEs.

### `src/brickwork_transpiler/main.py`

Small executable demo used by the `masonq-demo` console script. It should stay
lightweight and should not contain core algorithmic logic.

### `src/brickwork_transpiler/circuits.py`

Example and helper circuits used by demos, experiments, and tests.

### `src/brickwork_transpiler/bricks.py`

Legacy or supporting brick definitions. Keep this separate from the production
pipeline unless a brick abstraction is formally adopted.

### `src/brickwork_transpiler/bfk_encoder.py`

Support code for BFK-style encoding workflows. It records Alice's pi/4-grid
`|+_theta>` qubit preparations and Bob-facing blinded measurement angles
`delta = phi' + theta + r (mod 2)`. The core transpiler does not call this
automatically; experiments should call `encode_pattern(..., return_metadata=True)`
on an already-built brickwork pattern.

### `src/brickwork_transpiler/gx_angle_extractor.py`

Angle extraction helper code related to Graphix patterns. Use cautiously; the
main production angle path is in `pattern_converter.py`.

### `src/brickwork_transpiler/noise.py`

Noise-related helper code. This is not part of the core conversion path.

### `src/brickwork_transpiler/QRS_variations.py`

Research helper code for QRS variations. Treat as experimental/support code,
not as stable package API.

### `src/brickwork_transpiler/py.typed`

Marker file telling type checkers that the package ships type information.

## Algorithm Files

### `src/brickwork_transpiler/algorithms/__init__.py`

Marks the algorithms directory as a package.

### `src/brickwork_transpiler/algorithms/hhl.py`

HHL example/helper circuit code. This is useful for experiments but is not part
of the core transpiler contract.

### `src/brickwork_transpiler/algorithms/qrs_knn_grover.py`

QRS/Grover k-nearest-neighbour research helper code.

### `src/brickwork_transpiler/algorithms/experimental_algorithms/__init__.py`

Marks the experimental algorithms directory as a package.

### `src/brickwork_transpiler/algorithms/experimental_algorithms/qrs_hamming_threshold.py`

Experimental QRS variant using a Hamming-threshold style construction.

### `src/brickwork_transpiler/algorithms/experimental_algorithms/qrs_hybrid.py`

Experimental hybrid QRS construction.

### `src/brickwork_transpiler/algorithms/experimental_algorithms/qrs_knn_grover.py`

Experimental QRS/Grover implementation.

### `src/brickwork_transpiler/algorithms/experimental_algorithms/qrs_knn_grover_adapted.py`

Adapted experimental QRS/Grover implementation.

## Experiment Files

The experiment files are research scripts and benchmark drivers. They should
not define package-level behaviour.

### `src/brickwork_transpiler/experiments/hhl_transpilation.py`

HHL transpilation experiment script.

### `src/brickwork_transpiler/experiments/minimal_qrs_transpilation_simulation.py`

Minimal QRS transpilation/simulation experiment script.

### `src/brickwork_transpiler/experiments/plot_qrs_data.py`

Plotting script for QRS experiment data.

### `src/brickwork_transpiler/experiments/qft_transpilation.py`

QFT transpilation experiment script.

### `src/brickwork_transpiler/experiments/qrs_full_transpilation.py`

Full QRS transpilation experiment script.

### `src/brickwork_transpiler/experiments/qrs_no_amp_transpilation.py`

QRS experiment variant without amplitude-amplification components.

### `src/brickwork_transpiler/experiments/qrs_no_db_transpilation.py`

QRS experiment variant without database components.

### `src/brickwork_transpiler/experiments/data/lab_angles.csv`

Input data used by experiment scripts.

## Files That Should Not Matter To The Package

Generated caches and outputs should not be committed or relied on:

- `__pycache__/`
- `.pytest_cache/`
- `htmlcov/`
- `coverage.xml`
- `outputs/`
- `*.egg-info/`
- generated plot images under `images/graphs/`

The authoritative package configuration is `pyproject.toml`; the recommended
local conda environment is `environment.yml`.
