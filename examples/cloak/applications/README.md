# Application Demos

These examples are larger, stitched workflows built from the same selective
cloaking patterns shown in the smaller examples.

## Included Demos

- `20_hedge_fund_constrained_qaoa.py`
  Portfolio optimisation with confidential side-constraints.
- `21_drug_screening_grover.py`
  Proprietary hit-criterion logic inside a public search workflow.
- `22_rl_trading_policy.py`
  Hidden control policy inside a repeated optimisation loop.
- `23_confidential_optimization_runtime.py`
  Multi-stage composed workflow showing how cloaked patches can be chained.

## When To Use These

Use these demos when you want:

- a stronger customer-facing narrative;
- a more complete workflow than the compact `01` to `04` examples;
- a reference for composing multiple cloaked regions into one pipeline.

## Run

From the MasonQ repository root:

```bash
PYTHONPATH=src python examples/cloak/applications/20_hedge_fund_constrained_qaoa.py
```

## Related Reading

- Compact example index: [`../README.md`](../README.md)
- Strategy and market-fit guide:
  [`../../../docs/veil_opportunities.md`](../../../docs/veil_opportunities.md)
