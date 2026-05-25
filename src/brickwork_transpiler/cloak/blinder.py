"""Per-sub blinder and top-level cloak-compile / verify-session entry points.

For each :class:`~brickwork_transpiler.cloak.slicer.Sub`:

1. Hand the inner :class:`qiskit.QuantumCircuit` to the MasonQ brickwork
   transpiler to obtain a :class:`graphix.Pattern` and a
   :class:`~brickwork_transpiler.resources.ResourceEstimate`.
2. Embed a trap and its dummy neighbours into the planar brickwork pattern
   (:func:`~brickwork_transpiler.cloak.verifier.embed_planar_trap`).
3. Apply BFK angle blinding while pinning trap & dummy thetas
   (:func:`~brickwork_transpiler.cloak.verifier.blind_with_trap`).
4. Record per-round metadata and roll it up into a :class:`CloakedJob`.

For amplification, every sub is repeated ``rounds`` times with independent
trap choices and independent BFK randomness; the session passes verification
only if *all* rounds report the expected trap bit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from qiskit import QuantumCircuit

from .. import transpile as _bw_transpile
from ..bfk_encoder import BFKQubitPreparation
from ..resources import ResourceEstimate
from .composer import QHEMode, compose_outer
from .metrics import BlindShare, compute_blind_share
from .qhe import QOTPState
from .rsp import LocalRSPClient, PreparationHandle, RSPClient
from .slicer import BoundaryType, SlicePlan, Sub, slice_circuit
from .verifier import (
    NodeKind,
    TrapEmbedding,
    blind_with_trap,
    check_trap_outcomes,
    embed_planar_trap,
)


@dataclass
class BlindedRound:
    """One trap-embedded, BFK-blinded copy of a sensitive sub-circuit."""

    pattern: Any
    embedding: TrapEmbedding
    preparations: List[BFKQubitPreparation]
    measurement_info: List[Dict[str, Any]]


@dataclass
class BlindedSub:
    """All independent rounds of one sensitive sub-circuit, plus boundary keys."""

    slice_id: int
    rounds: List[BlindedRound]
    output_qotp: QOTPState
    """QOTP key the *outer* circuit must continue tracking after this sub."""

    decomposed_circuit: QuantumCircuit
    """The MasonQ-decomposed sub-circuit; useful for resource sanity checks."""

    original_body: Optional[QuantumCircuit] = None
    """The sub's pre-decomposition body — used by `simulate_cloaked` for a
    semantically faithful honest-server reference."""

    resources: Optional[ResourceEstimate] = None
    """Brickwork-graph resource estimate (rows, columns, depth, nodes)."""


@dataclass
class CloakedJob:
    """Bundle handed to an untrusted server and consumed by ``verify_session``."""

    subs: List[BlindedSub]
    outer_qhe_circuit: QuantumCircuit
    """The unprotected segment, gates remain in the clear but client tracks QOTP keys."""

    qotp_state: QOTPState
    """Final QOTP key the client uses to decrypt the server's output."""

    rsp_plan: List[PreparationHandle]
    """RSP-side preparation handles for every brickwork-graph qubit, all rounds."""

    boundary_types: List[BoundaryType]
    qhe_mode: QHEMode = "off"
    """Whether classical Pauli keys were tracked through unprotected gates."""

    metadata: Dict[str, Any] = field(default_factory=dict)


def _round_from_pattern(pattern: Any, rng: np.random.Generator) -> BlindedRound:
    embedding = embed_planar_trap(pattern, rng=rng)
    blinded_pattern, preparations, info = blind_with_trap(pattern, embedding, rng=rng)
    return BlindedRound(
        pattern=blinded_pattern,
        embedding=embedding,
        preparations=preparations,
        measurement_info=info,
    )


def _blind_sub(
    sub: Sub,
    *,
    rounds: int,
    rng: np.random.Generator,
    incoming_qotp: QOTPState,
) -> BlindedSub:
    base_result = _bw_transpile(sub.body, return_result=True)
    rounds_list = [_round_from_pattern(base_result.pattern, rng) for _ in range(rounds)]

    # Per BFK Protocol 1, the BQC output qubits carry residual `X^{a'} Z^{b'}`
    # encryption.  For this scaffold we model that as a uniform QOTP refresh
    # on every output qubit; a future iteration will derive `(a', b')` from
    # the measurement metadata of the round actually executed by the server.
    output_qotp = incoming_qotp.refresh(num_qubits=sub.num_qubits, rng=rng)

    return BlindedSub(
        slice_id=sub.slice_id,
        rounds=rounds_list,
        output_qotp=output_qotp,
        decomposed_circuit=base_result.decomposed_circuit,
        original_body=sub.body,
        resources=base_result.resources,
    )


def cloak_compile(
    qc: QuantumCircuit,
    *,
    rsp: Optional[RSPClient] = None,
    rounds: int = 1,
    seed: Optional[int] = None,
    qhe: QHEMode = "off",
) -> CloakedJob:
    """Compile a Qiskit circuit into a partially-blind verifiable job.

    The user is expected to have wrapped the privacy-critical subcircuits in
    :func:`~brickwork_transpiler.cloak.annotations.sensitive` blocks; this
    function does *not* perform automatic blind-spot detection (see
    :mod:`brickwork_transpiler.cloak.detection` for the optional heuristic
    layer).

    ``qhe`` controls how the *unprotected* segment of the circuit is
    handled.  The default ``"off"`` runs those gates in the clear (the
    cheap, "small patches only" mode that motivates this product).
    ``"qotp"`` additionally tracks classical Pauli keys per gate so the
    server learns the gates but not the qubit states; this adds zero
    quantum overhead but requires every unprotected gate to be Clifford
    or ``T`` / ``T†``.
    """
    if rounds < 1:
        raise ValueError("rounds must be at least 1")
    if rsp is None:
        rsp = LocalRSPClient()

    rng = np.random.default_rng(seed)
    plan = slice_circuit(qc)
    qotp = QOTPState.zero(num_qubits=qc.num_qubits)

    blinded_subs: List[BlindedSub] = []
    for sub in plan.subs:
        blinded = _blind_sub(sub, rounds=rounds, rng=rng, incoming_qotp=qotp)
        blinded_subs.append(blinded)
        qotp = blinded.output_qotp

    outer_qhe_circuit, qotp = compose_outer(plan, blinded_subs, qotp=qotp, rng=rng, qhe=qhe)

    all_preps: List[PreparationHandle] = []
    for sub in blinded_subs:
        for rnd in sub.rounds:
            all_preps.append(rsp.prepare(rnd.preparations))

    job = CloakedJob(
        subs=blinded_subs,
        outer_qhe_circuit=outer_qhe_circuit,
        qotp_state=qotp,
        rsp_plan=all_preps,
        boundary_types=plan.boundary_types,
        qhe_mode=qhe,
        metadata={
            "rounds": rounds,
            "num_subs": plan.num_subs,
            "num_qubits": qc.num_qubits,
            "qhe_mode": qhe,
        },
    )
    share = compute_blind_share(job)
    job.metadata["blind_share"] = share
    return job


def verify_session(
    job: CloakedJob,
    server_results: Mapping[int, Sequence[Mapping[Any, int]]],
) -> Tuple[bool, Optional[Any]]:
    """Check trap outcomes; return ``(ok, output)`` on success.

    ``server_results[slice_id]`` is the list of per-round outcome dicts the
    server reported for sub ``slice_id``; each dict maps graph node id to
    the measurement bit.  When all traps pass, this function returns the
    QOTP state the caller must apply to decrypt the final output (the
    actual decryption is deferred to the caller because the output medium —
    statevector, counts, density matrix — depends on the simulator).
    """
    for sub in job.subs:
        rounds_outcomes = list(server_results.get(sub.slice_id, []))
        if len(rounds_outcomes) != len(sub.rounds):
            return False, None
        embeddings = [r.embedding for r in sub.rounds]
        if not check_trap_outcomes(embeddings, rounds_outcomes):
            return False, None
    return True, job.qotp_state
