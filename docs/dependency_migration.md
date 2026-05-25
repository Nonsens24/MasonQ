# Dependency Migration Notes

## Current Target Stack

MasonQ now targets the current Qiskit 2.x packaging model:

```bash
pip install masonq
```

Core targets:

- Python >= 3.10, < 3.13
- NumPy >= 2, < 2.3
- Qiskit >= 2.4.1, < 3
- Graphix >= 0.3.5, < 0.4
- Numba >= 0.61, < 0.62 and llvmlite >= 0.44, < 0.45 for Quimb/Graphix
- Qiskit Aer >= 0.17.2, < 0.18 for local simulation helpers
- qiskit-algorithms >= 0.4.0, < 0.5 for QRS/Grover helpers
- matplotlib >= 3.9, pylatexenc, pandas, and scipy for normal scientific workflows
- qiskit-ibm-runtime >= 0.46.1, < 0.47 only for optional IBM cloud/backend access

## Deprecated Packages To Remove

Do not install these in new environments:

- `qiskit-terra`
- `qiskit-ibm-provider`
- `qiskit-ibmq-provider`
- `graphix-ibmq`

The `qiskit` package is the supported SDK install target in Qiskit 2.x. IBM
hardware/runtime access moved to `qiskit-ibm-runtime`.

## Clean Environment Recommendation

The safest upgrade is a fresh environment. Mixing Qiskit 0.46/Terra-era
packages with Qiskit 2.x packages can leave stale provider entry points behind.

```bash
conda env create -f environment.yml
conda activate masonq-qiskit24
```

The environment file installs `numba`/`llvmlite` from conda before pip installs
Graphix and Quimb. This avoids fragile source builds on macOS.

If pip tries to build `numba` or `llvmlite` from source, the environment is not
using the intended dependency bounds. Use Python 3.10-3.12 and reinstall with
the current `pyproject.toml`, or create the conda environment from
`environment.yml`.

IBM Runtime is optional. MasonQ's core transpiler and local verification path do
not call it. Install it only in environments where your own scripts need IBM
Quantum service authentication or cloud backend access:

```bash
python -m pip install -e ".[ibm]"
```

If you must repair the existing environment:

```bash
python -m pip uninstall -y qiskit-terra qiskit-ibm-provider qiskit-ibmq-provider graphix-ibmq
python -m pip install --upgrade "numpy>=2,<2.3" "matplotlib>=3.9,<4" \
  "qiskit>=2.4.1,<3" \
  "qiskit-aer>=0.17.2,<0.18" "qiskit-algorithms>=0.4.0,<0.5" \
  "graphix>=0.3.5,<0.4" "numba>=0.61,<0.62" "llvmlite>=0.44,<0.45"
python -m pip install -e .
```

## Warning About `pkg_resources`

This warning:

```text
qiskit_ibm_provider/api/session.py: pkg_resources is deprecated as an API
```

comes from the deprecated `qiskit-ibm-provider` package. MasonQ suppresses the
deprecated provider and uses `qiskit-ibm-runtime` instead. If this warning
appears, the active Python environment still contains the deprecated provider
and should be repaired with the commands above.
