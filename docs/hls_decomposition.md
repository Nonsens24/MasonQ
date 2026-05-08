# HLS Decomposition

This page explains MasonQ's current Qiskit high-level synthesis policy for
multi-controlled gates.

## Short Version

MasonQ defaults to:

```python
transpile(qc, multi_control_strategy="hls")
```

In this mode MasonQ keeps multi-controlled X operations as semantic
`MCXGate` operations and lets Qiskit's high-level synthesis choose how to lower
them during Qiskit transpilation. This is the current Qiskit-compatible path and
the one new studies should use first.

Use:

```python
transpile(qc, multi_control_strategy="legacy-recursive")
```

only when reproducing older MasonQ experiments that depended on Qiskit's
recursive MCX class.

## Why HLS Is The Default

Qiskit no longer treats the number of MCX ancillas as something that should be
fixed at gate-construction time. The recommended model is:

1. put an `MCXGate(k)` in the circuit;
2. pass the circuit to Qiskit's transpiler;
3. let `HighLevelSynthesis` choose an implementation based on the available
   target, coupling map, and ancilla information.

This is why MasonQ's HLS path does not manually attach scratch ancillas to
plain MCX operations.

References:

- IBM Quantum `MCXGate` API: https://qiskit.qotlabs.org/docs/api/qiskit/qiskit.circuit.library.MCXGate
- IBM Quantum `HLSConfig` API: https://qiskit.qotlabs.org/docs/api/qiskit/qiskit.transpiler.passes.HLSConfig
- IBM Quantum `MCXSynthesisDefault` plugin API: https://qiskit.qotlabs.org/docs/api/qiskit/qiskit.transpiler.passes.synthesis.hls_plugins.MCXSynthesisDefault

## What MasonQ Does Before Qiskit HLS

MasonQ does not blindly decompose everything itself. The pre-Qiskit stage does
only the minimum needed to keep the brickwork pipeline well-defined:

1. `selective_decompose` opens ordinary composite wrappers while preserving
   multi-controlled operations for explicit handling.
2. `linearise_multi_ctrl` rewrites only the multi-control cases that MasonQ
   needs to control before basis lowering.
3. `decompose_qc_to_bricks_qiskit` calls Qiskit's `transpile(...)` with basis
   gates `rz`, `rx`, `cx`, and `id`, a line coupling map, and an `HLSConfig`.

After that, MasonQ schedules the resulting `rz`/`rx`/`cx` circuit into the
brickwork instruction matrix.

## Implemented Ancilla Policy

The implemented policy is demand-driven:

- HLS MCX: no package-added ancilla operands.
- HLS multi-controlled phase rewrite: one package-added phase workspace qubit.
- Legacy recursive MCX with fewer than five controls: no package-added scratch
  ancilla.
- Legacy recursive MCX with five or more controls: one clean scratch ancilla.
- Legacy recursive multi-controlled phase with five or more controls: one phase
  workspace plus one clean scratch ancilla.

`linearise_multi_ctrl` returns a new circuit. It does not mutate the input
circuit by appending ancilla registers to it.

## Why Multi-Controlled Phase Still Uses A Workspace

MasonQ lowers multi-controlled phase operations through a
compute-phase-uncompute pattern:

1. compute the AND of the controls into a phase workspace;
2. apply a one-control phase from the workspace to the target;
3. uncompute the workspace.

That rewrite needs a phase workspace qubit even in HLS mode. The MCX operations
used inside this rewrite are still semantic `MCXGate` operations under HLS, so
Qiskit chooses their final synthesis.

## CX-Linearity Requirement

The HLS choice changes the Qiskit decomposition before brick scheduling, so the
relevant invariant for MasonQ is not exact Qiskit gate count. The invariant is:

- after Qiskit basis lowering, each `cx` group contributes exactly one
  two-endpoint brick;
- the brick alignment pass does not duplicate or drop CX endpoints;
- aligned brick width grows linearly with the number of CX groups.

This is covered by fast regression tests in:

```text
tests/unit_and_integration_tests/test_decomposer.py::TestCxLinearity
```

## Reproducibility Guidance

For a paper or benchmark, record:

- MasonQ version and `show_versions()` output;
- `multi_control_strategy`;
- Qiskit optimisation level and fallback level;
- decomposed `cx` count;
- decomposed Qiskit depth;
- brick rows and brick columns;
- graph node count;
- whether verification was structural only or included `result.verify()`.

Do not compare HLS and legacy-recursive results as if they were the same
decomposition. They should be treated as different decomposition policies.

## Common Pitfalls

### HLS does not mean MasonQ simulates automatically

`transpile(...)` constructs the pattern and validates structure. It does not
run Graphix simulation. Simulation happens only when you call:

```python
result.simulate_statevector()
result.verify()
```

### `decomposed_circuit` is not the MBQC result

`result.decomposed_circuit` is the Qiskit circuit after lowering into MasonQ's
brickwork-compatible basis. The MBQC object is `result.pattern`.

### Legacy recursive warnings are expected in legacy tests

Qiskit's recursive MCX class is deprecated. MasonQ keeps
`multi_control_strategy="legacy-recursive"` only to reproduce older results.
