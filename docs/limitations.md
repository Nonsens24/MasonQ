# Limitations

MasonQ is strongest as a transparent brickwork transpiler and a selective
cloaking layer for compact sensitive subcircuits. This page describes the main
practical boundaries.

## Stable Public Surface

The stable user-facing workflows are:

- `transpile(..., return_result=True)`
- `TranspileResult`
- `brickwork_transpiler.cloak`

Research helpers and algorithm-specific modules should be treated more
cautiously unless the docs explicitly present them as stable.

## Verification Cost

`TranspileResult.verify()` compares a Graphix simulation against a Qiskit
reference statevector. This is useful for small and medium circuits, but it is
still exponential in the number of output qubits.

For larger workloads, prefer resource inspection and structural validation.

## Supported Circuit Surface

The core path is designed for unitary circuits lowered by Qiskit into the
`rz`/`rx`/`cx` basis.

The following are not part of the current stable surface:

- dynamic circuits;
- mid-circuit measurement workflows;
- heavy reset-based logic;
- classical control integrated into the circuit definition.

## Selective Cloaking Economics

Cloak works best when the sensitive region is much smaller than the overall
workflow. If most of the circuit must remain private, the cost profile trends
toward full blind computation and the selective advantage drops.

Use blind-share reporting to confirm that the hidden patch remains compact.

## Multi-Controlled Gates

The default path is `multi_control_strategy="hls"`, which uses Qiskit's current
high-level synthesis workflow.

Use `multi_control_strategy="legacy-recursive"` only for historical
reproduction. Do not mix results from the two strategies in one study without
comparing equivalence, ancilla count, CX count, and brickwork depth.

## Graphix Compatibility

MasonQ targets `graphix>=0.3.5,<0.4`. If Graphix changes pattern-generation or
graph-extraction APIs again, compatibility updates will likely start in
`pattern_converter.py` and related plotting or graph export code.

## Plotting

Large Matplotlib figures may fail inside IDE plot proxies. For large outputs,
prefer saving to disk rather than interactive rendering.

```python
result.plot(save_path="images/graphs/circuit.pdf", show=False)
```

## Experimental Modules

QRS and HHL helper modules remain research-oriented. Validate them carefully
before using them in external claims, customer demos, or benchmark studies.
