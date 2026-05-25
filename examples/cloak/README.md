# Cloak Examples

This folder is intentionally small and commercially legible. The examples are
meant to show where selective cloaking fits, not to act as a long tutorial.

## Start With One Of These

- `01_finance_qaoa.py`
  Compact hidden optimisation terms inside a public QAOA scaffold.
- `02_pharma_vqe.py`
  Confidential chemistry parameters inside a VQE-style workflow.
- `03_defence_logistics.py`
  Hidden capability weights inside a public assignment circuit.
- `04_qml_kernel.py`
  Confidential feature embedding inside a public QML-style structure.

Each file defines `build_circuit()` and a ready-to-run `qc` so you can either
run the script directly or reuse the circuit construction in your own code.

## Run An Example

From the MasonQ repository root:

```bash
PYTHONPATH=src python examples/cloak/01_finance_qaoa.py
```

If you installed the package editable into your active environment, a plain
`python ...` invocation is also fine.

## What These Examples Show

Each example demonstrates the same product principle:

1. Keep the public algorithm scaffold in the clear.
2. Put only the high-value subcircuit inside `sensitive(...)`.
3. Measure the hidden fraction with blind-share reporting.

## Deeper Material

- Strategy and pattern catalogue:
  [`../../docs/veil_opportunities.md`](../../docs/veil_opportunities.md)
- Larger product-style workflows:
  [`applications/README.md`](applications/README.md)

## Example Families

### Market-facing examples

The four top-level scripts map to common commercial narratives: finance,
chemistry, defence, and QML.

### Application demos

The `applications/` folder contains bigger stitched workflows intended for
deeper evaluation or presentation use.
