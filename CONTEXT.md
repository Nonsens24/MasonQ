# MasonQ Context Handoff

This file captures the current cleanup/professionalization work so a future
chat or developer can continue without reconstructing the session.

## Project Goal

Make MasonQ a proprietary, scientist-friendly Python package for converting
unitary Qiskit circuits into brickwork MBQC / Graphix patterns. Current focus:
package integrity, usability, maintainability, correctness checks, and
transpilation-pipeline reliability. Avoid circuit-level optimisation changes
unless they fix clear correctness bugs.

## Current Repo Location

```bash
/Users/rexfleur/Desktop/bwt-trades/gpt55/MasonQ
```

## Important User Constraints

- Do not run the slow system tests unless explicitly requested.
- The system tests under `tests/system_tests` are known to be expensive.
- Prefer fast syntax/static checks and targeted tests.
- The package should be proprietary, not open source.
- Focus on correctness and maintainability before circuit optimisation.

## Commands Already Run

Useful evidence from this session:

```bash
pytest -q
```

Failed at collection initially because the package was not importable without
installation or `PYTHONPATH=src`.

```bash
PYTHONPATH=src NUMBA_CACHE_DIR=/private/tmp/numba_cache pytest -q
```

Started passing tests but was too slow because system tests simulate full
Graphix/Qiskit workflows.

```bash
PYTHONPATH=src NUMBA_CACHE_DIR=/private/tmp/numba_cache pytest -q tests/unit_and_integration_tests
```

Reached 61% quickly, then slowed on integration-style tests. Interrupted by the
user.

Current lightweight checks used after edits:

```bash
python -m compileall -q src/brickwork_transpiler tests/unit_and_integration_tests
git diff --check
```

Both passed after the latest pipeline edits.

Black was attempted but unavailable in the current environment:

```bash
python -m black src/brickwork_transpiler pyproject.toml tests/conftest.py
```

Failed with `No module named black`.

## Major Changes Made

Packaging and usability:

- Rewrote `README.MD`.
- Added `LICENSE` as proprietary/all-rights-reserved.
- Added `MANIFEST.in`.
- Added `CITATION.cff`.
- Added `environment.yml` for a clean default conda environment without IBM
  Runtime installed by default.
- Added `docs/architecture.md`.
- Added `docs/scientist_quickstart.md`.
- Added `docs/dependency_migration.md`.
- Added `docs/limitations.md`.
- Updated `pyproject.toml`:
  - proprietary classifier,
  - `qiskit>=2.4.1,<3`,
  - core `graphix`, `networkx`,
  - extras: `viz`, `qrs`, `experiments`, `mbqc`,
  - `pythonpath = ["src"]`,
  - pytest markers,
  - typed package marker.
- Added `src/brickwork_transpiler/py.typed`.
- Added explicit `__init__.py` under algorithm packages.
- Replaced many `from src.brickwork_transpiler...` imports with installed-package imports.
- Added `tests/conftest.py` to mark `tests/system_tests` as `system` and `slow`.
- Updated CI to run fast unit/integration tests instead of full system tests.

Public API and support modules:

- Added `exceptions.py`.
- Added `result.py` with `TranspileResult`.
- Added `resources.py` with `ResourceEstimate`.
- Added `profiling.py`.
- Added `validation.py`.
- Added `_versions.py` with `show_versions()` for reproducibility reports.
- Public `transpile(..., return_result=True)` returns structured results.
- Legacy tuple return remains supported.
- `result.resources` reports qubits, Qiskit depth, gate count, CX count,
  brick rows/columns, and graph nodes.

Runtime output:

- Replaced noisy prints in core transpiler/decomposer path with logging.
- Removed debug print `EVEQWEVQWEQWE` from `utils.py`.

## Transpilation Pipeline State

Pipeline:

```text
Qiskit circuit
-> selective_decompose
-> optional linearise_multi_ctrl
-> Qiskit transpile to rz/rx/cx/id on line coupling
-> group_with_dag_atomic_mixed
-> instructions_to_matrix_dag
-> align_cx_matrix
-> insert_rotations_adjacent_to_cx
-> validate_instruction_matrix
-> generate_brickwork_graph_from_instruction_matrix
-> validate_brickwork_graph_data
-> pattern_converter.to_pattern
-> validate_pattern_outputs
```

## Correctness Bugs Fixed

1. Large multi-controlled phase rewrite bug:

For `k >= 5`, the old code passed:

```python
controls + [scratch_anc, phase_anc]
```

to `MCXRecursive(k)`. Qiskit expects controls, target, ancilla, so the AND was
computed into `scratch_anc` while the later phase gate read `phase_anc`. This
was semantically wrong. It now passes:

```python
controls + [phase_anc, scratch_anc]
```

2. HLS strategy qarg bug:

`multi_control_strategy="hls"` now passes only `controls + target` to
`MCXGate`; Qiskit HLS decides ancilla usage. It no longer attaches explicit
recursive ancillas to `MCXGate`.

3. Demand-driven ancillas:

`linearise_multi_ctrl` no longer mutates the input circuit and no longer adds
two ancillas up front. HLS MCX gets no explicit package ancilla, multi-controlled
phase rewrites get one phase workspace, and the legacy recursive path gets a
second scratch ancilla only when controls >= 5.

4. Qiskit private attribute risk:

Replaced `q._index` with an explicit stable map:

```python
qubit_index = {qubit: i for i, qubit in enumerate(qc.qubits)}
```

5. CX tagging precision:

CX ids now increment only when `instr.name == "cx"`, not broad
`startswith("cx")`.

6. Pattern converter orientation bug:

The old `cx_placed` row-skip state machine assumed the first encountered CX
endpoint was the top-row endpoint. `to_pattern` now indexes CX groups per column
and injects each CX exactly once from its top row.

7. Ambiguous mixed cells:

Validation and pattern conversion now reject cells containing both CX endpoints
and rotations.

8. CX linearity guard:

Fast tests now assert that brick alignment keeps exactly one two-endpoint brick
per CX group and that aligned brick width grows linearly with CX count.

## Important Design Decision

`multi_control_strategy="hls"` is now the default because current Qiskit
recommends constructing semantic `MCXGate` operations and letting high-level
synthesis choose the implementation. `multi_control_strategy="legacy-recursive"`
remains available only for reproducing older experiment/test behavior. Compare
equivalence, ancilla count, CX count, brick matrix width, and graph size before
mixing the two strategies in one study.

## Known Remaining Risks

- Full test suite has not been run after the latest changes.
- System tests are slow but should be run before release.
- The optional `qiskit-ibm-runtime` extra can emit plugin deprecation warnings
  from IBM Runtime itself. The default `environment.yml` does not install it;
  use `pip install -e ".[ibm]"` only when cloud runtime access is needed.
- Graphix/Numba cache issues may require:

```bash
NUMBA_CACHE_DIR=/private/tmp/numba_cache
```

- Some experiment modules remain research-script quality.
- `utils.py` still contains large commented historical blocks and should be
split later into layout/reference-state/data utilities.
- `decomposer.py` is improved but still relies on string-tagged instructions
like `cx12c` and `cx12t`. A typed internal IR would be the next major
maintainability upgrade.

## Recommended Next Steps

1. Install dev tools in the environment and run formatting:

```bash
python -m pip install -e ".[dev,viz,qrs]"
python -m black src tests
python -m isort src tests
```

2. Run targeted fast tests only:

```bash
pytest tests/unit_and_integration_tests/test_decomposer.py -q
pytest tests/unit_and_integration_tests/test_pattern_converter.py -q
```

3. Run the normal fast suite when ready:

```bash
pytest tests/unit_and_integration_tests -m "not slow and not system"
```

4. Before release, run system tests once:

```bash
NUMBA_CACHE_DIR=/private/tmp/numba_cache pytest tests/system_tests
```

5. Consider replacing instruction-name tagging with a typed internal
representation:

```python
BrickOp(kind="cx", group_id=12, role="control", params=..., source_col=...)
```

This would make scheduling, validation, and angle injection more robust.
