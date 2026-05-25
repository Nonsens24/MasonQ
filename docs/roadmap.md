# Roadmap

This page keeps the product direction short and readable.

## Near Term

- Guided protection recommendations.
  Scan a user algorithm, use ML-assisted pattern detection at least in part,
  suggest a few privacy levels, identify candidate blind regions, and explain
  likely value and cost tradeoffs in a way that is easy for non-experts to use.
- Better delegated-execution packaging, verification flows, and clearer trust
  reporting.
- Clearer QHE mode options and guidance for when to use `off`, QOTP-style
  protection, or heavier protection modes.
- Clearer example-to-product paths across the docs and demos.

## Mid Term

- Cylindrical brickwork support.
- Stronger automation for blind-spot detection, patch selection, and protection
  recommendation quality.
- More polished customer-facing workflow demos in finance, defence, and QML.

## Longer Term

- Easier end-to-end orchestration for confidential quantum workflows.
- Broader productisation of selective blindness plus verification as one user
  experience.
- Position MasonQ and VEIL as secure quantum execution infrastructure rather
  than a research-only transpiler.

## Product Direction

The guiding principle stays simple:

> Protect small, high-leverage quantum semantic regions inside mostly public
> workflows.

That is the strongest commercial path for selective blindness. For the broader
strategic framing, see [VEIL / cloak opportunity catalogue](veil_opportunities.md).

For related background, see the partial blind quantum computation paper:
<https://arxiv.org/pdf/2503.10007>
