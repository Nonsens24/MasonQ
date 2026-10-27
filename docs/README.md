# Documentation

## Start Here

1. [Scientist and user guide](scientist_quickstart.md)
2. [Limitations](limitations.md)
3. [Roadmap](roadmap.md)

## User Guides

- [Scientist and user guide](scientist_quickstart.md)
  Covers installation, recommended workflows, transpilation options, and the
  main result objects.
- [Sparse instruction matrix](sparse_matrix.md)
  Covers the lightweight matrix view used for diagnostics and resource sweeps.
- [Dependency migration](dependency_migration.md)
  Notes for environment upgrades and Qiskit 2.x dependency constraints.

Runnable examples live in `examples/`, from `01_basic_transpile.py` to
`04_save_pattern.py`.

## Technical Reference

- [Architecture](architecture.md)
  Pipeline stages, invariants, scheduling objective, and testing guidance.
- [HLS decomposition](hls_decomposition.md)
  Multi-control policy and Qiskit decomposition details.
- [Transpiler file guide](transpiler_file_guide.md)
  Source-tree map for maintainers.

## Practical Reading Paths

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

Everything else should be treated as internal or research-grade unless the docs
explicitly describe it as public.
