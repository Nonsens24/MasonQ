# Scientist Quickstart

## Install

```bash
python -m pip install -e ".[viz,qrs]"
```

For IBM Quantum Runtime access:

```bash
python -m pip install -e ".[ibm]"
```

Use `qiskit-ibm-runtime`; the old `qiskit-ibm-provider` and
`qiskit-ibmq-provider` packages are deprecated and should not be installed in
new environments.

For development:

```bash
python -m pip install -e ".[dev,viz,qrs]"
```

## Recommended API

Use the structured result object for notebooks and scripts:

```python
from brickwork_transpiler import transpile

result = transpile(
    qc,
    input_vector,
    routing_method="sabre",
    layout_method="trivial",
    with_ancillas=True,
    fallback_opt=1,
    return_result=True,
)

pattern = result.pattern
decomposed_qc = result.decomposed_circuit
resources = result.resources
```

Common result methods:

```python
result.plot(save_path="images/graphs/my_circuit.pdf", show=False)
statevector = result.simulate_statevector()
verification = result.verify()
reference = result.qiskit_reference_statevector()
permutation = result.output_permutation()
result.save_pattern_text("outputs/my_pattern.txt")
```

`transpile(...)` itself does not simulate. Use `simulate_statevector()` or
`verify()` only when you explicitly want simulation.

For reproducibility in papers or benchmark notebooks:

```python
import brickwork_transpiler as bwt

bwt.show_versions()
```

The legacy tuple return is still supported:

```python
pattern, colour_map, decomposed_qc = transpile(qc, input_vector)
```

## Correctness Workflow

For small circuits, compare the Graphix simulation against the layout-aware
Qiskit reference state:

```python
verification = result.verify(tolerance=1e-8)
print(verification.equivalent)
print(verification.fidelity)
```

For larger circuits, prefer structural validation and resource metrics over
full statevector simulation. Full simulation scales exponentially.

To inspect the comparison manually:

```python
brickwork_state = result.simulate_statevector()
qiskit_reference = result.qiskit_reference_statevector()
permutation = result.output_permutation()

print(permutation)
```

Both `brickwork_state` and `qiskit_reference` are in Graphix output order. The
permutation tells you how the decomposed Qiskit output was reordered to match
Graphix.

If Qiskit optimisation level 3 hits numerical synthesis failures, MasonQ falls
back to optimisation level 1 by default. For large benchmark circuits you can
start directly at level 1:

```python
transpile(qc, opt=1)
```

To fail immediately instead of falling back:

```python
transpile(qc, opt=3, fallback_opt=None)
```

## Decomposition Choice

Use the default first:

```python
transpile(qc, multi_control_strategy="hls")
```

Use the historical recursive path when reproducing older runs:

```python
transpile(qc, multi_control_strategy="legacy-recursive")
```

Record semantic equivalence on small cases, number of ancillas, decomposed `cx`
count, Qiskit circuit depth, brickwork matrix width, and total graph nodes.
Do not compare only circuit depth; the brickwork layout cost is the relevant
resource for this package.

The implemented ancilla policy is:

- HLS MCX operations get no package-added ancilla operands.
- Multi-controlled phase rewrites get one phase workspace qubit.
- Legacy recursive decomposition uses one scratch qubit only for controls
  `>= 5`.

See [HLS decomposition](hls_decomposition.md) for details.

The structured result exposes the core resource estimate:

```python
result.resources
```

## Layout Methods

Use `layout_method="trivial"` when you want the easiest debugging story:
logical qubits stay in the natural row order as much as Qiskit allows.

Use `layout_method="sabre"` with `routing_method="sabre"` when studying more
realistic line-layout routing:

```python
result = transpile(
    qc,
    input_vector,
    layout_method="sabre",
    routing_method="sabre",
    return_result=True,
)
```

`result.verify()` is layout-aware. It simulates the Graphix brickwork pattern,
computes the Qiskit reference from `result.decomposed_circuit`, and permutes
that reference into Graphix output order. For manual checks, use
`result.output_permutation()` and `result.qiskit_reference_statevector()`.
