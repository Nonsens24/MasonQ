# Limitations

MasonQ is intended for research workflows that need transparent
circuit-to-brickwork conversion. The stable surface is the public
`transpile(..., return_result=True)` workflow and the `TranspileResult` helper
methods.

## Verification Cost

`transpile(...)` does not simulate automatically.

`TranspileResult.verify()` compares a Graphix simulation with a Qiskit
statevector reference. This is useful for small circuits, but it scales
exponentially with the number of output qubits.

For larger circuits, prefer structural validation and resource estimates:

```python
result = transpile(qc, return_result=True)
print(result.resources)
```

## Supported Circuit Surface

The core transpilation path lowers unitary circuits through Qiskit into an
`rz`/`rx`/`cx` brick basis. Dynamic circuits, mid-circuit measurement,
reset-heavy circuits, and classical control are not part of the current stable
API.

## Multi-Controlled Gates

The default multi-control path is `multi_control_strategy="hls"`, which uses
Qiskit's current high-level synthesis path:

```python
transpile(qc, multi_control_strategy="hls")
```

Use `multi_control_strategy="legacy-recursive"` only when reproducing
historical runs that depended on Qiskit's deprecated recursive MCX class.
Compare equivalence, CX count, ancilla count, and brickwork depth before mixing
results from the two strategies in one study.

The package adds explicit ancillas only when required by this pre-decomposition
step. HLS MCX operations do not receive package-added ancillas. Multi-controlled
phase rewrites use one phase workspace qubit, and the legacy recursive path uses
a second scratch qubit only for controls >= 5.

See [HLS decomposition](hls_decomposition.md) for the detailed policy.

The brick scheduler is expected to scale linearly in the number of CX groups it
places. The fast test suite includes regression tests that each CX contributes
exactly one two-endpoint brick and that aligned brick width grows linearly with
CX count.

## Experimental Algorithms

QRS and HHL helper modules are research examples, not stable public APIs. They
may need algorithm-specific validation before being used in a paper or
benchmark.

## Graphix Compatibility

MasonQ targets `graphix>=0.3.5,<0.4`. Graphix 0.3.5 changed
pattern-generation and graph-extraction APIs, so MasonQ carries a small
compatibility adapter. If Graphix changes these APIs again, update
`pattern_converter.py` and `visualiser.py` first.

## Plotting

Large Matplotlib figures can fail in IDE plot proxies. Prefer saving plots:

```python
result.plot(save_path="images/graphs/circuit.pdf", show=False)
```

Interactive display remains available with `show=True` for small graphs.
