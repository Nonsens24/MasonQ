# MasonQ Documentation

Use this index to choose the right level of detail. The README is intentionally
short; the pages below carry the practical API and maintenance details.

## For Users And Scientists

1. [Scientist guide](scientist_quickstart.md)
   - Install and version checks.
   - Transpilation options.
   - Layout and routing choices.
   - Return types and intermediate stages.
   - Decomposition methods and ancilla policy summary.
   - Verification, plotting, sparse matrices, and BFK metadata.
2. [Sparse instruction matrix](sparse_matrix.md)
   - Space-efficient matrix output for large resource sweeps.
   - Dense-versus-sparse tradeoffs and API details.
3. [Limitations](limitations.md)
   - Supported circuit surface.
   - Verification cost.
   - Plotting caveats.
   - Experimental module status.
4. [Dependency migration](dependency_migration.md)
   - Qiskit 2.x environments.
   - NumPy/Numba/llvmlite bounds.
   - Deprecated IBM package removal.

## For Maintainers

1. [Architecture](architecture.md)
   - Pipeline stages, invariants, graph-depth objective, and test layers.
2. [HLS decomposition](hls_decomposition.md)
   - Qiskit high-level synthesis, multi-control handling, and implemented
     ancilla policy.
3. [Transpiler file guide](transpiler_file_guide.md)
   - Purpose of every source file and where to make changes.

## Key Rules

- New code should use `transpile(..., return_result=True)`.
- The MBQC object is `result.pattern`.
- The Qiskit-side lowered circuit is `result.decomposed_circuit`.
- `transpile(...)` does not simulate automatically.
- `result.verify()` is an explicit, expensive simulation-based check.
- Use `progress=True` on long-running transpilation, simulation, and
  verification calls when users need terminal/notebook feedback.
- `multi_control_strategy="hls"` is the default.
- Explicit package-added ancillas are demand-driven.
- The CX brick alignment pass must remain linear in the number of CX groups.
- MasonQ's scheduler objective is minimal graph depth:
  `graph_depth = 4 * brick_columns + 1`.
- Use `return_stage="resources"` for resource sweeps that do not need Graphix
  pattern materialization.
- Use `return_stage="sparse_matrix"` to inspect large aligned matrices without
  storing empty cells.
