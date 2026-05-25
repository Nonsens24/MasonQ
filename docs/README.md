# Documentation

This documentation set is split by audience so the main README can stay short
and product-facing.

## Fast Paths

- New user: start with [Scientist and user guide](scientist_quickstart.md)
- Product review: read [VEIL / cloak opportunity catalogue](veil_opportunities.md)
- Maintainer: go to [Architecture](architecture.md)

## Start Here

1. [Scientist and user guide](scientist_quickstart.md)
2. [Limitations](limitations.md)
3. [Cloak strategy and pattern catalogue](veil_opportunities.md)
4. [Roadmap](roadmap.md)

## User Guides

### Core usage

- [Scientist and user guide](scientist_quickstart.md)
  Covers installation, recommended workflows, transpilation options, and the
  main result objects.
- [Sparse instruction matrix](sparse_matrix.md)
  Covers the lightweight matrix view used for diagnostics and resource sweeps.
- [Dependency migration](dependency_migration.md)
  Notes for environment upgrades and Qiskit 2.x dependency constraints.

### Example navigation

- [Cloak examples overview](../examples/cloak/README.md)
- [Application demos](../examples/cloak/applications/README.md)

## Product And Strategy

- [VEIL / cloak opportunity catalogue](veil_opportunities.md)
  Commercially relevant partial-blind patterns, where they fit, and which
  examples implement them.
- [Roadmap](roadmap.md)
  Short product-direction view of where MasonQ and VEIL are headed.

## Technical Reference

- [Architecture](architecture.md)
  Pipeline stages, invariants, scheduling objective, and testing guidance.
- [HLS decomposition](hls_decomposition.md)
  Multi-control policy and Qiskit decomposition details.
- [Transpiler file guide](transpiler_file_guide.md)
  Source-tree map for maintainers.

## Practical Reading Paths

### If you are evaluating the product

1. Read the top-level `README.MD`
2. Read [Scientist and user guide](scientist_quickstart.md)
3. Read [VEIL / cloak opportunity catalogue](veil_opportunities.md)
4. Run one example from `examples/cloak/`

### If you are integrating MasonQ into scripts or notebooks

1. Read [Scientist and user guide](scientist_quickstart.md)
2. Check [Limitations](limitations.md)
3. Use [Sparse instruction matrix](sparse_matrix.md) if you need diagnostics or
   large sweeps

### If you are modifying the transpiler

1. Read [Architecture](architecture.md)
2. Read [HLS decomposition](hls_decomposition.md)
3. Use [Transpiler file guide](transpiler_file_guide.md)

## Stable Surfaces

- `transpile(..., return_result=True)`
- `TranspileResult`
- `brickwork_transpiler.cloak`

Everything else should be treated as internal or research-grade unless the docs
explicitly describe it as public.
