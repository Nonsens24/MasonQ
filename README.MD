[![PyPI](https://img.shields.io/badge/pypi-not_released-lightgrey.svg)](#)
[![Python](https://img.shields.io/badge/python-3.10--3.12-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-proprietary-lightgrey.svg)](#)
[![Docs](https://img.shields.io/badge/docs-local-blue.svg)](docs/README.md)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://black.readthedocs.io/)
[![mypy](https://img.shields.io/badge/mypy-checked-informational)](http://mypy-lang.org/)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen)](https://docs.pytest.org/)

# MasonQ

**A planar brickwork transpiler with a *subcircuit cloaking* layer for
cheap, verifiable, partially-blind cloud quantum execution.**

MasonQ has two layers:

1. **The transpiler** — converts a Qiskit `QuantumCircuit` into a planar
   brickwork measurement-based quantum computation (MBQC) pattern. It
   lowers to the `rz`/`rx`/`cx`/`id` basis, schedules the gates into a
   brickwork instruction matrix, builds the graph, and emits a Graphix
   pattern with measurement angles. This is the original MasonQ.

2. **`cloak/`** — a product layer on top that lets you mark *only the
   sensitive sub-circuits* (the oracle, the secret function, the bit
   you'd rather a cloud provider didn't see) and have those — and only
   those — compiled into small blind, verifiable brickwork patches. The
   rest of your circuit runs in the clear, so you pay UBQC overhead only
   on the bytes that actually need it.

The motivation is straightforward: **applying full Universal Blind
Quantum Computation (UBQC) to an entire circuit is prohibitively
expensive**, because MBQC blows up qubit count linearly and adds round-
trip classical interaction per measurement. In most real algorithms —
Grover's, Shor's, variational eigensolvers — only one or two
sub-circuits (the oracle, the function call, the state-preparation
unitary) need to stay private. Lee & Chung 2025
("Partial Blind Quantum Computation") formalised this observation;
MasonQ Cloak is a working implementation of it on top of a planar
brickwork transpiler.

---

## Why partial blindness?

| Approach | Server learns | Client cost | Hardware ask |
| --- | --- | --- | --- |
| **Plaintext** | the whole circuit + inputs | none | tiny |
| **Full UBQC** | nothing (modulo size) | huge: every gate becomes O(n) measurement-pattern bricks + one classical round-trip per qubit | enormous |
| **MasonQ Cloak** (this) | the *public* part of the circuit only | proportional to how much you marked sensitive | proportional to the sensitive part |

UBQC's overhead scales with the size of the part you blind. So if your
oracle is 12 gates inside a 500-gate algorithm, you pay UBQC overhead
on those 12 gates — not on the 500. That is the entire pitch.

Cloak adds three guarantees on top of the marked sub-circuits, all
backed by published protocols:

- **Blindness** — Broadbent / Fitzsimons / Kashefi BFK09. Each blinded
  sub-circuit is a planar brickwork pattern whose measurement angles are
  randomised so the server learns only an upper bound on the circuit
  size of the sub-circuit. (Re-uses MasonQ's existing
  [`bfk_encoder.py`](src/brickwork_transpiler/bfk_encoder.py).)
- **Verifiability** — Fitzsimons & Kashefi 2017, Protocol 3, *planar*
  variant. One trap qubit per round, embedded in the brickwork graph
  alongside dummy neighbours; honest servers always produce a
  predictable trap bit. Soundness is amplified by repeated rounds
  (`rounds=k` ⇒ undetected-cheat probability ≤ `(1 - p_det)^k`).
- **Partial-blind composition** — Lee & Chung 2025 Type 0 / Type 1 /
  Type 2 connectors. Sensitive subs receive their inputs encrypted under
  a Quantum One-Time Pad (Type 0), pass their outputs along under a new
  QOTP (Type 1), and back-to-back blinded blocks fold the previous
  block's decryption *into* the next block (Type 2) so plaintext never
  leaks to the server.

The third item is the part where naive "just use UBQC on the oracle"
gets it wrong — the boundaries between blinded and unblinded regions
are where private information escapes if you're not careful. Cloak
implements them as first-class objects.

---

## Is QHE necessary? No.

Full Quantum Homomorphic Encryption (in the strong sense — Fisher
et al. 2014 with `T`-gadgets, one ancilla per non-Clifford gate plus a
classical round-trip) is **opt-in** in MasonQ Cloak and **off by
default**.

What Cloak runs by default for the unprotected portion of your circuit
is:

- `qhe="off"` (default): unprotected gates execute in the clear. The
  server sees them. This is fine if your only privacy concern is the
  oracle / sensitive sub. **This is the cheap "small patches" mode that
  the rest of this README assumes.**
- `qhe="qotp"`: the client classically tracks Pauli one-time-pad keys
  through every Clifford gate (see Lee & Chung 2025 Table 1). Zero
  quantum overhead — it's literally `XOR` updates on integers. The
  server still sees the gates but the qubit *states* in the unprotected
  region are hidden. Use this when the *data* flowing through the
  unprotected portion is sensitive too.
- Full T-gadget QHE: not the default and not the goal. If you need it,
  put those gates inside a `sensitive(...)` block — that's already the
  cheaper option.

In short: when people say "QHE is expensive" they mean the T-gadget
variant. Cloak does not use it by default; the QOTP-tracking mode is a
classical bookkeeping layer that adds nothing measurable to the wire
cost.

---

## Quickstart (the genuinely-three-lines kind)

```python
from qiskit import QuantumCircuit
from brickwork_transpiler.cloak import sensitive, simulate_cloaked

qc = QuantumCircuit(2)
qc.h([0, 1])
with sensitive(qc, [0, 1], label="oracle") as oracle:
    oracle.cx(0, 1)          # ← this block becomes a blind, verifiable patch
qc.h([0, 1])

state = simulate_cloaked(qc, seed=0)
print(state)
```

That's it. The `with sensitive(qc, ...)` context manager marks the
gates inside it as the part you want hidden from the cloud provider.
`simulate_cloaked` does the whole partial-blind compile + honest-server
simulation locally and returns a Qiskit `Statevector`, so you can
verify your annotated circuit still computes what you expected before
shipping it off.

### Going one step deeper

When you're ready to actually delegate to a server, switch from
`simulate_cloaked` to `cloak_compile`:

```python
from brickwork_transpiler.cloak import cloak_compile, verify_session
from brickwork_transpiler.cloak.rsp import LocalRSPClient

job = cloak_compile(qc, rsp=LocalRSPClient(), rounds=4, seed=0)
# job.subs             : the blinded brickwork patches, one per `sensitive` block
# job.outer_qhe_circuit: the unprotected outer skeleton (plaintext gates)
# job.rsp_plan         : per-round |+_theta> preparation specs for RSP
# job.qotp_state       : QOTP keys for decrypting the server's final state
# job.boundary_types   : Type 0 / Type 1 / Type 2 splice classification

# … hand `job` to your server, receive measurement outcomes …
ok, qotp = verify_session(job, server_results)
```

`rounds=4` is the soundness amplifier from Fitzsimons & Kashefi 2017
§VI: four independent trap-embedded copies of each sensitive sub, all
of which must report the predicted trap bit before the client trusts
the output.

### Visualising cloaked circuits

`draw_cloaked` is a drop-in replacement for `QuantumCircuit.draw` that
marks every `sensitive(...)` block with a 🔒 prefix in any backend, and
fills it with a distinct colour in the matplotlib backend. The rest of
the circuit renders exactly as Qiskit would normally render it.

```python
from qiskit import QuantumCircuit
from brickwork_transpiler.cloak import sensitive, draw_cloaked, summarize_cloaked

qc = QuantumCircuit(3, name="grover-toy")
qc.h([0, 1, 2])
with sensitive(qc, [0, 1, 2], label="oracle") as oracle:
    oracle.cx(0, 1)
    oracle.x(2)
qc.h([0, 1, 2])

print(draw_cloaked(qc, output="text"))
print(summarize_cloaked(qc))
```

```
     ┌───┐┌───────────┐┌───┐
q_0: ┤ H ├┤0          ├┤ H ├
     ├───┤│           │├───┤
q_1: ┤ H ├┤1 🔒 oracle ├┤ H ├
     ├───┤│           │├───┤
q_2: ┤ H ├┤2          ├┤ H ├
     └───┘└───────────┘└───┘

Circuit 'grover-toy': 1 cloaked block(s) across 7 operation(s)
  [  3] 'oracle' on qubits [0, 1, 2]: 3 qubits, 2 gates
```

Multiple cloaked blocks per circuit are handled naturally — every one
gets its own 🔒 marker and its own row in the summary:

```
     ┌───┐┌────────────────┐┌───┐
q_0: ┤ H ├┤0               ├┤ H ├────────────────────────
     ├───┤│  🔒 alpha-model │└───┘       ┌───┐
q_1: ┤ H ├┤1               ├──■─────────┤ H ├────────────
     ├───┤└────────────────┘┌─┴─┐┌──────┴───┴──────┐┌───┐
q_2: ┤ H ├──────────────────┤ X ├┤0                ├┤ H ├
     ├───┤                  └───┘│  🔒 risk-factors │├───┤
q_3: ┤ H ├───────────────────────┤1                ├┤ H ├
     └───┘                       └─────────────────┘└───┘
```

Pass `output="mpl"` for a matplotlib figure (cloaked blocks fill in
deep purple); pass `marker=""` to suppress the lock prefix; pass any
other Qiskit `draw` kwarg (e.g. `fold=80`) through transparently.
`cloak_style()` returns the underlying style dict if you want to merge
it into a broader Qiskit MPL style of your own.

### How much of my circuit will run blindly?

Every `cloak_compile` call reports a **blind share** — the fraction of
the circuit that ends up under UBQC on the brickwork graph. The number
appears in `summarize_cloaked(qc)`, in `job.metadata["blind_share"]`,
and in the CLI `compile` output:

```python
from brickwork_transpiler.cloak import sensitive, summarize_cloaked, cloak_compile

qc = QuantumCircuit(3, name="mixed-demo")
qc.h([0, 1, 2])                        # 3 clear gates
with sensitive(qc, [0, 1, 2], label="oracle") as oracle:
    oracle.cx(0, 1)
    oracle.x(2)
    oracle.cx(1, 2)                    # 3 blind gates
qc.h([0, 1, 2]); qc.cx(0, 1)           # 4 more clear gates

print(summarize_cloaked(qc))
job = cloak_compile(qc, rounds=3, seed=0)
print(job.metadata["blind_share"].format())
```

```
Circuit 'mixed-demo': 1 cloaked block(s) across 8 operation(s)
  blind share:  30.0% of source gates (3/10)
  [  3] 'oracle' on qubits [0, 1, 2]: 3 qubits, 3 gates

blind share:  30.0% of source gates (3/10); 81 brickwork-graph nodes total across 1 sub(s) × 3 round(s)
```

Two numbers are reported on purpose. The **gate-share percentage**
(`3/10 = 30%`) is the easy-to-quote headline: this is the fraction of
your *source* circuit that ends up under UBQC. The
**brickwork-graph node total** (`81`) is the real server-side cost —
every blinded gate explodes into roughly `4 * brick_columns + 1`
measurement layers, and you pay that for every trap round. If you crank
`rounds` up for stronger soundness, this number scales linearly with
it; the gate-share percentage stays the same. Use `compute_blind_share`
directly if you want the underlying :class:`BlindShare` dataclass.

### Market-scenario examples

Four runnable demos under [`examples/cloak/`](examples/cloak/) cover the
near-term wedges where partial blindness actually pays for itself:

| Example | Market | What gets cloaked |
| --- | --- | --- |
| [`01_finance_qaoa.py`](examples/cloak/01_finance_qaoa.py) | Hedge-fund portfolio QAOA | The alpha-model matrix Q — every ZZ-rotation angle of the cost separator |
| [`02_pharma_vqe.py`](examples/cloak/02_pharma_vqe.py) | Drug / materials VQE | The molecular Hamiltonian — one- and two-electron integrals as Trotter angles |
| [`03_defence_logistics.py`](examples/cloak/03_defence_logistics.py) | Defence target / route assignment | The classified capability-graph edge weights |
| [`04_qml_kernel.py`](examples/cloak/04_qml_kernel.py) | Confidential QML inference | The data-embedding layer (per-query input lives in the rotation angles) |

Each example marks the proprietary structure with `sensitive(...)` and
leaves the public algorithmic scaffolding (Hadamards, mixers, trained
ansätze) running in the clear. Run any of them with:

```bash
PYTHONPATH=src python examples/cloak/01_finance_qaoa.py
```

### How do I simulate a whole circuit now?

Three options, in increasing depth:

1. `simulate_cloaked(qc)` — runs the whole cloak round-trip under an
   honest server and returns a `Statevector`. Verifies cloak preserves
   your circuit's semantics. **Use this for development.**
2. `assemble_honest_circuit(job)` — gives you back the reconstructed
   plaintext Qiskit circuit (each `sensitive` block replaced by its
   brickwork-decomposed equivalent). Plug it into Aer, Statevector,
   density matrices, whatever you already use.
3. Per-sub Graphix simulation: for each `BlindedSub` in `job.subs`, you
   can pull the underlying brickwork pattern out and call MasonQ's
   `TranspileResult.simulate_statevector(...)` on it. This is what a
   real server's execution corresponds to. Use it when you want to
   probe trap soundness or measurement statistics on an individual
   patch.

---

## Installation

MasonQ is **not yet published on PyPI**. Install from a local checkout:

```bash
git clone https://github.com/Nonsens24/brickwork_transpiler.git MasonQ
cd MasonQ
pip install -e .                          # core transpiler + cloak layer
pip install -e ".[dev]"                   # tests, coverage, formatting, typing
pip install -e ".[ibm]"                   # IBM Runtime if you need cloud backends
```

Python 3.10–3.12. The default install does *not* pull in IBM Runtime;
add the `ibm` extra only if your scripts need cloud-backend
authentication.

> **Don't run `pip install masonq` yet** — that name is not published.
> If it appears to "succeed" it has installed something else; uninstall
> and use the editable local install above.

### PyCharm: using the right interpreter

PyCharm has its own per-project Python interpreter and will happily
ignore the one your terminal uses. If you see *"Unresolved reference
'qiskit'"* in the editor after running the install commands, it means
PyCharm is pointing at a different Python than your shell did.

To fix it:

1. **Find the Python that has masonq installed.** In a terminal:
   ```bash
   python -c "import brickwork_transpiler, sys; print(sys.executable)"
   ```
   Copy that path.
2. **Point PyCharm at it.** *Settings → Project: MasonQ → Python
   Interpreter → ⚙ → Add Interpreter → Add Local Interpreter → Select
   existing → Path: paste from step 1*.
3. PyCharm will reindex; the red squiggles disappear.

Alternative: have PyCharm create a fresh `.venv/` for the project and
re-run the install commands above with that interpreter activated.
The empty `.venv/` PyCharm may have auto-created when you first opened
the project does *not* have masonq installed — that is the most common
cause of the import error.

### CLI

```bash
masonq-cloak compile your_circuit.py --rounds 4 --out job.json
masonq-cloak verify  job.json results.json
```

The `compile` subcommand expects a Python file defining a top-level
`qc: QuantumCircuit` or a `build_circuit()` callable returning one.
`verify` is currently a structural check; full server-roundtrip
verification will land once we ship a binary Graphix-pattern
serialiser.

---

## What's inside the cloak layer

```
src/brickwork_transpiler/cloak/
  annotations.py     Sensitive(Instruction) + `with sensitive(qc): ...`
  slicer.py          Split circuit into outer skeleton + Subs; Type 0/1/2 classification
  verifier.py        Planar trap/dummy embedding, trap-outcome checker (FK17 §VI)
  blinder.py         cloak_compile / verify_session; per-sub blinding pipeline
  qhe.py             Classical QOTP key tracking (Lee & Chung Table 1) + T-gadget stub
  composer.py        Walks the outer skeleton; threads QOTP across boundaries
  rsp.py             RSPClient ABC + LocalRSPClient + RemoteRSPClient stub
  simulate.py        simulate_cloaked / assemble_honest_circuit
  visualisation.py   draw_cloaked / summarize_cloaked / cloak_style
  metrics.py         BlindShare / compute_blind_share (blind-fraction reporting)
  cli.py             masonq-cloak entry point
  detection/         Future-work: auto blind-spot detection (heuristics shipping today)
    heuristics.py    oracle-name + T-density + secret-input taint
    learner.py       Stage B placeholder
```

The original transpiler entry point (`transpile(qc, return_result=True)`)
is unchanged; it remains the right tool when you want a single brickwork
pattern for the whole circuit rather than partial-blind composition.

---

## Automatic blind-spot detection (roadmap)

`cloak.detection` ships Stage A today:

```python
from brickwork_transpiler.cloak.detection import propose_sensitive_blocks

report = propose_sensitive_blocks(qc, secret_qubits=[0, 1])
for candidate in report.candidates:
    print(candidate.start, candidate.end, candidate.rationale, candidate.score)
```

It flags subcircuits as candidates using three signals:
oracle-shaped instructions by name (`oracle`, `mcx`, `mcmt`, `ccx`,
`phase_oracle`, …), sliding-window `T`-gate density (non-Clifford
density is a strong proxy for "this is the secret part"), and forward
causal-cone taint from user-tagged secret input qubits. The output is a
list of candidate ranges with rationales; you decide whether to wrap
them in `sensitive(...)`.

Stage B (learned policy from prior annotations + verification outcomes)
and Stage C (cost-aware policy search) are scaffolded as module stubs
so the interface stays stable.

---

## When to use which mode

```
        Are the inputs/outputs themselves sensitive?
            │
            ├── No  →  qhe="off"   (default; cheapest; server sees outer gates)
            │
            └── Yes →  Are unprotected gates all Clifford+T?
                          │
                          ├── Yes →  qhe="qotp"   (classical OTP tracking, zero quantum cost)
                          │
                          └── No  →  Put the non-Clifford parts inside sensitive(...)

How many traps?
    rounds=1     fine for development & demos
    rounds=k     undetected-cheat probability ≤ (1 - p_det)^k
                 (planar single-trap; see FK17 §VI for p_det bounds)
```

---

## Original transpiler API (unchanged)

```python
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
from brickwork_transpiler import transpile

qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)

result = transpile(qc, Statevector.from_label("++"), return_result=True)
print(result.resources)
print(result.verify().equivalent, result.verify().fidelity)
```

See the [Scientist guide](docs/scientist_quickstart.md) for the full
scientific workflow on the bare transpiler: transpilation options,
layout/routing choices, return types, decomposition strategies,
sparse matrices, and BFK metadata.

## Documentation

- [Scientist quickstart](docs/scientist_quickstart.md)
- [Architecture](docs/architecture.md)
- [HLS decomposition and ancilla policy](docs/hls_decomposition.md)
- [Sparse instruction matrix](docs/sparse_matrix.md)
- [Limitations](docs/limitations.md)
- [Transpiler file guide](docs/transpiler_file_guide.md)

## Development

```bash
pytest tests/unit_and_integration_tests -m "not slow and not system"   # fast suite
pytest tests/unit_and_integration_tests -m slow                        # slow Graphix sims
pytest tests/system_tests                                              # full equivalence
```

```python
import brickwork_transpiler as bwt
bwt.show_versions()
```

## License

Proprietary. See [LICENSE](LICENSE).

## References

- Universal Blind Quantum Computation — Broadbent, Fitzsimons, Kashefi 2009.
  <https://arxiv.org/abs/0807.4154>
- Unconditionally Verifiable Blind Quantum Computation — Fitzsimons,
  Kashefi 2017. <https://doi.org/10.1103/PhysRevA.96.012303>
- Partial Blind Quantum Computation — Lee, Chung 2025.
  <https://arxiv.org/abs/2503.10007>
- Quantum Homomorphic Encryption for Polynomial-Sized Circuits — Fisher
  et al. 2014.
- The Measurement Calculus — Danos, Kashefi, Panangaden 2007.
  <https://arxiv.org/abs/0704.1263>
- Graphix — <https://github.com/TeamGraphix/graphix>
- Qiskit — <https://www.ibm.com/quantum/qiskit>
