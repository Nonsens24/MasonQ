# Dependency Migration Notes

## Current Target Stack

MasonQ now targets the current Qiskit 2.x packaging model:

```bash
python -m pip install -e .
```

Core targets:

- Python >= 3.10, < 3.13
- NumPy >= 2
- Qiskit >= 2.4.1, < 3
- Graphix >= 0.3.5, < 0.5 (which pulls in Quimb, Numba and llvmlite). Graphix 0.4
  needs numba >= 0.65.1, which has no Intel macOS wheels, so pip resolves to
  Graphix 0.3.5 on Intel Macs; to run 0.4 there, install numba and llvmlite from
  conda-forge first (`environment-graphix04.yml` does this, followed by
  `pip install --no-deps -e .`).
- matplotlib >= 3.9 and pylatexenc for plotting (`[viz]`)
- qiskit-ibm-runtime >= 0.46.1, < 0.47 only for optional IBM cloud/backend access (`[ibm]`)

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
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Numba stopped publishing Intel macOS wheels at 0.63 and llvmlite at 0.46, so on
an Intel Mac `pyproject.toml` bounds `numba<0.63`, which brings llvmlite 0.45,
NumPy 2.3 and Graphix 0.3.5 with it. If pip still tries to build `numba` or
`llvmlite` from source, the environment is not using the current
`pyproject.toml`: reinstall with it. For Graphix 0.4 on an Intel Mac, create
the conda-forge environment from `environment-graphix04.yml` instead; it
installs numba and llvmlite from conda, after which the package goes in with
`python -m pip install --no-deps -e .`.

IBM Runtime is optional. MasonQ's core transpiler and local verification path do
not call it. Install it only in environments where your own scripts need IBM
Quantum service authentication or cloud backend access:

```bash
python -m pip install -e ".[ibm]"
```

If you must repair the existing environment:

```bash
python -m pip uninstall -y qiskit-terra qiskit-ibm-provider qiskit-ibmq-provider graphix-ibmq
python -m pip install --upgrade "qiskit>=2.4.1,<3" "graphix>=0.3.5,<0.5"
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
