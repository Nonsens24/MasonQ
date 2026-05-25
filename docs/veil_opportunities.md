# VEIL Quantum — Confidential patch opportunities

This is the canonical strategic reference for the cloak product layer:
the set of design patterns where small confidential quantum patches
controlling large public computations make commercial sense, and the
set of "anti-patterns" that look attractive but don't scale. Every
pattern is cross-referenced to the runnable example that implements
it; every example is sized to demonstrate the core property
``s << d`` (sensitive depth much smaller than total depth).

## Core principle

> Only protect small, high-leverage quantum semantic regions.

**Good.** Small confidential patch controlling a large public
computation.

**Bad.** Hiding most of the circuit.

The entire scalability story depends on ``s << d``. Every example in
this repository prints the source-gate blind share so this ratio is
visible at every step.

---

## Pattern catalogue

### 1. Hidden predicate / oracle kernels — *Very strong*

**Pattern.** A tiny hidden marking / scoring function inside a large
public search or amplification workflow.

    if secret_score(x) > threshold:
        mark(x)

**Public.** Grover / amplitude amplification scaffold, sampling,
post-processing.

**Private.** Tiny oracle, scoring function, threshold logic.

**Why it works.** Small gate count, enormous semantic leverage. The
diffusion operator scales with the search space; the oracle stays
constant.

**Best industries.** Finance, fraud detection, defence targeting,
logistics.

**Main competitor.** Trusted execution environments (Intel SGX, AMD
SEV, AWS Nitro). Main advantage over them: the oracle semantics stay
quantum-native, and the provider cannot directly inspect adaptive
marking logic.

**Implemented in.**
- Pattern demo: [`examples/cloak/patterns/10_hidden_predicate.py`](../examples/cloak/patterns/10_hidden_predicate.py) — 5.7% source-gate blind share.
- Production application: [`examples/cloak/applications/21_drug_screening_grover.py`](../examples/cloak/applications/21_drug_screening_grover.py) — 17.1%, drug-screening framing.
- Composed runtime stage 1: [`examples/cloak/applications/23_confidential_optimization_runtime.py`](../examples/cloak/applications/23_confidential_optimization_runtime.py).

---

### 2. Sparse penalty injection — *Strong*

**Pattern.** Mostly public optimisation Hamiltonian with small hidden
correction terms.

    H_total = H_public + λ · H_secret

**Public.** Optimisation scaffold, generic constraints, public cost
structure.

**Private.** Sparse penalty terms, hidden correlations, proprietary
objective adjustments.

**Why it works.** Tiny hidden term set, large impact on the
optimisation landscape.

**Best industries.** Portfolio optimisation, supply chains, routing,
scheduling.

**Main risk.** If most of the Hamiltonian becomes private, scalability
collapses — the result is functionally full-UBQC at full cost. Stay
sparse.

**Implemented in.**
- Pattern demo: [`examples/cloak/patterns/11_sparse_penalty.py`](../examples/cloak/patterns/11_sparse_penalty.py) — 13.0% source-gate blind share.
- Production application: [`examples/cloak/applications/20_hedge_fund_constrained_qaoa.py`](../examples/cloak/applications/20_hedge_fund_constrained_qaoa.py) — 23.2%, ESG / regulatory / concentration penalties over a 6-asset QAOA.
- Composed runtime stage 2: [`examples/cloak/applications/23_confidential_optimization_runtime.py`](../examples/cloak/applications/23_confidential_optimization_runtime.py).

---

### 3. Hidden adaptive control kernels — *Very strong*

**Pattern.** Public execution loop, private control / update policy.

    if hidden_metric(state):
        terminate()
    # or:
    next_params = secret_update(measurements)

**Public.** Quantum execution, measurement collection, optimisation
loop.

**Private.** Adaptive update logic, stopping criteria, branching
policy.

**Why it works.** Tiny confidential footprint, large workflow
influence. One classifier-shaped gate per epoch is plenty.

**Best industries.** Finance, QML, defence optimisation,
reinforcement learning.

**Implemented in.**
- Pattern demo: [`examples/cloak/patterns/12_hidden_control.py`](../examples/cloak/patterns/12_hidden_control.py) — 7.7% source-gate blind share.
- Production application: [`examples/cloak/applications/22_rl_trading_policy.py`](../examples/cloak/applications/22_rl_trading_policy.py) — 25.0%, multi-epoch RL loop with a hidden policy net.

---

### 4. Secure state injection (RSP) — *Extremely important*

**Pattern.** Public computation operating on hidden injected quantum
states. Proprietary feature states, hidden resource states, secret
initialisation structure.

**Public.** Large variational workflow, known graph execution.

**Private.** Injected state semantics.

**Why it works.** Confidentiality scales with state complexity, not
gate count. A 2-qubit proprietary resource state carries the same
secrecy weight whether it's consumed by a 10-gate or a 1000-gate
workflow.

**Best industries.** QML, chemistry, distributed quantum systems,
photonic MBQC.

**Why UBQC / RSP help.** Classical systems cannot naturally represent
hidden quantum state structure — this is the architectural moat.

**Implemented in.**
- Pattern demo: [`examples/cloak/patterns/13_state_injection.py`](../examples/cloak/patterns/13_state_injection.py) — 30.8% source-gate blind share, RSP-friendly preparation handles emitted.

---

### 5. MBQC measurement-angle concealment — *Core architectural advantage*

**Pattern.** Hide only selected measurement semantics inside public
graph-state execution.

    δ = φ + θ + π · r

**Public.** Brickwork graph, execution schedule, graph topology.

**Private.** Measurement-angle semantics, adaptive corrections.

**Why it works.** Tiny hidden angle sets can define the entire logical
behaviour of an MBQC computation. This is *why* MBQC and brickwork
patterns are the right substrate for cloak — computation is naturally
encoded in measurements, so hiding measurements is hiding semantics.

**Best industries.** Graph-state-native systems, photonic quantum
computing, distributed MBQC.

**Long-term importance.** Potentially massive if photonic or networked
quantum computing wins out as the dominant hardware modality. Today
this pattern is the *underlying mechanism* of the entire cloak layer;
the BFK encoder ([`src/brickwork_transpiler/bfk_encoder.py`](../src/brickwork_transpiler/bfk_encoder.py))
implements precisely the ``δ = φ + θ + π r`` rule.

**Implemented in.**
- Pattern demo: [`examples/cloak/patterns/14_angle_concealment.py`](../examples/cloak/patterns/14_angle_concealment.py) — 13.8% source-gate blind share.
- Mechanism: every cloaked block goes through `encode_pattern(...)` in
  `bfk_encoder.py`, which is the same calculation. Pattern #14 just
  makes the idea visible at the user-circuit level.

---

### 6. Sparse verification anchors — *Very practical*

**Pattern.** Mostly public computation with sparse hidden verification
traps / stabiliser checks.

**Public.** Ordinary delegated execution.

**Private.** Hidden traps, stabiliser checks, verification subgraphs.

**Why it works.** Tiny hidden overhead, strong trust leverage.

**Best industries.** Cloud quantum, defence, regulated finance.

**Potential.** Verification may become commercially important *before*
blindness itself — regulators ask "can you prove the cloud didn't lie"
before they ask "can you prove the cloud didn't see".

**Implemented in.**
- Pattern demo: [`examples/cloak/patterns/15_verification_anchors.py`](../examples/cloak/patterns/15_verification_anchors.py) — 21.4% source-gate blind share.
- Platform layer: the trap embedding in [`src/brickwork_transpiler/cloak/verifier.py`](../src/brickwork_transpiler/cloak/verifier.py) implements the analogous idea at the brickwork-graph level — `rounds=k` amplifies cheat-detection probability over independent trap-embedded rounds.

---

### 7. Quantum feature embeddings — *Moderately strong*

**Pattern.** Hide only the compact embedding layer of a QML pipeline,
not the whole model.

**Public.** Inference loop, training scaffold, optimisation.

**Private.** Feature geometry, kernel embeddings, proprietary
mappings.

**Why it works.** Embeddings can stay relatively compact — a handful
of basis-rotation angles defining how features map into Hilbert
space.

**Main risk.** If the full QML model becomes private, the hidden
region grows too large and the pattern collapses into a generic
"hide everything" trap.

**Best use.** Hide *only* the embeddings, the kernel-defining
parameters, and sparse parameter updates. Leave the inference and
post-processing public.

**Implemented in.**
- Pattern demo: [`examples/cloak/patterns/16_feature_embedding.py`](../examples/cloak/patterns/16_feature_embedding.py) — 13.3% source-gate blind share, compact kernel-only embedding.
- Naive contrast: [`examples/cloak/04_qml_kernel.py`](../examples/cloak/04_qml_kernel.py) hides the entire embedding layer — kept as a "what a customer would initially ask for" demo. See the *Naive vs. pattern* note below.

---

### 8. Hidden parameter injection — *Strong*

**Pattern.** Public circuit structure with hidden parameter schedules
over time.

    qc.rz(secret_theta_step_t, q)

**Public.** Ansatz structure, optimisation framework.

**Private.** Sparse parameters, hidden schedules, proprietary
training-trajectory updates.

**Why it works.** Parameters may encode most of the economic value of
a variational model while requiring very few gates to express.
Distinct from Pattern #5 (which hides a fixed angle set for a single
layer): Pattern #8 hides the *evolution* — each training step is one
small cloaked patch in time.

**Best industries.** Finance, QAOA, QML, adaptive variational
systems.

**Implemented in.**
- Pattern demo: [`examples/cloak/patterns/17_parameter_schedule.py`](../examples/cloak/patterns/17_parameter_schedule.py) — 34.3% source-gate blind share across 4 schedule steps, one cloaked patch per step.

---

## Naive vs. pattern: how the market-vertical examples relate

The four examples under [`examples/cloak/`](../examples/cloak/)
(`01_finance_qaoa.py`, `02_pharma_vqe.py`, `03_defence_logistics.py`,
`04_qml_kernel.py`) are deliberately *naive* — they hide the full
proprietary parameter set rather than a sparse extract of it.

**Why we keep them.** They mirror what a customer in each vertical
would initially say they want: "hide the alpha matrix", "hide the
molecular Hamiltonian", "hide the capability graph", "hide the
embedding layer". Pointing at them and saying *"that's the initial
ask, here's why it doesn't scale, here's the pattern that does"*
is the cleanest way to teach the small-patch idiom.

**Why they fail at scale.** Each violates ``s << d``: the hidden
fraction grows linearly with problem size because the matrix /
Hamiltonian / graph itself grows linearly. Eventually they collapse
into full UBQC with extra steps.

**The right reframings** are the corresponding entries in
`patterns/` and `applications/` above. Pattern #2 + application 20
is the proper finance framing; pattern #1 + application 21 is the
proper pharma framing; etc.

---

## Anti-patterns (do not target)

These all violate ``s << d`` once the problem is sized realistically.
For each, the right thing to recommend is a classical secure-compute
solution (Intel SGX, AMD SEV, AWS Nitro, confidential VMs, secure
orchestration) — *not* cloak.

1. Full VQE confidentiality.
2. Full QAOA secrecy.
3. Full QML model hiding.
4. Large private Hamiltonians.
5. Classical proprietary logic.

The honest sales conversation is: "if your IP fits on classical
hardware, use classical confidentiality primitives. Cloak's value
proposition is *quantum-native* semantic kernels inside mostly public
quantum workflows."

---

## Strategic insight

VEIL Quantum only makes sense when *quantum-native confidential
semantics are compact but high-leverage*. The strongest future
direction is:

> Confidential semantic kernels inside mostly public quantum
> workflows.

Not:

> Universally blind quantum computing everywhere.

## Commercial positioning

**Category.** Secure quantum execution infrastructure.

**Core features that this codebase delivers today.**
- Selective blind patches — `sensitive(...)` annotation +
  `cloak_compile`.
- Semantic-confidentiality compilation — MasonQ brickwork transpiler
  applied per patch.
- RSP-backed hidden state injection — `BFKQubitPreparation` lists
  routed through the `RSPClient` interface.
- Sparse verification — planar trap embedding amplified by
  `rounds=k`.
- MBQC measurement concealment — BFK encoder per cloaked block.
- Leakage-aware orchestration — Type 0 / Type 1 / Type 2 boundary
  classification, QHE-off default for cheap composition.

**Core features still ahead.** Cylindrical brickwork (see main README
roadmap), automatic blind-spot detection Stage B/C
(`cloak.detection.learner`), a simple recommendation layer that scans a
user algorithm and suggests a few security levels with candidate blind
regions and expected value, and a binary Graphix-pattern serialiser for
end-to-end CLI verification.

## Test alignment

The `s << d` property is asserted programmatically for every
in-tree pattern and application example in
[`tests/unit_and_integration_tests/test_cloak_pattern_examples.py`](../tests/unit_and_integration_tests/test_cloak_pattern_examples.py).
If a future change to one of the example files pushes the source-gate
blind share above 35%, that test fails. This keeps the doc and the
code synchronised: a pattern example cannot drift into "hide most of
the circuit" without the test catching it.
