# MasonQ Documentation

Start here when using or maintaining MasonQ.

## User Path

1. [Scientist quickstart](scientist_quickstart.md): install, run a first
   conversion, inspect resources, and verify small circuits.
2. [Limitations](limitations.md): supported circuit surface, verification cost,
   plotting caveats, and experimental modules.
3. [Dependency migration](dependency_migration.md): Qiskit 2.x environment
   setup and deprecated package removal.

## Developer Path

1. [Architecture](architecture.md): pipeline stages and invariants.
2. [HLS decomposition](hls_decomposition.md): Qiskit high-level synthesis,
   multi-control handling, and ancilla policy.
3. [Transpiler file guide](transpiler_file_guide.md): purpose of every source
   file and where to make changes.

## Key Rules

- New code should use `transpile(..., return_result=True)`.
- The MBQC object is `result.pattern`.
- The Qiskit-side lowered circuit is `result.decomposed_circuit`.
- `transpile(...)` does not simulate automatically.
- `result.verify()` is an explicit, expensive simulation-based check.
- `multi_control_strategy="hls"` is the default.
- Explicit package-added ancillas are demand-driven, not unconditional.
- The CX brick alignment pass must remain linear in the number of CX groups.
