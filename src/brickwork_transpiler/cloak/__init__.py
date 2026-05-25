"""MasonQ Cloak — subcircuit blinder for cloud quantum execution.

The cloak layer wraps the MasonQ brickwork transpiler with three additional
guarantees on the *sensitive* portion of a user's Qiskit circuit:

  - **Blindness** in the Broadbent-Fitzsimons-Kashefi sense — random per-qubit
    `|+_theta>` preparations and measurement-angle masking
    (re-uses :mod:`brickwork_transpiler.bfk_encoder`).
  - **Verifiability** via a single trap qubit embedded in the planar
    brickwork pattern (Fitzsimons & Kashefi 2017, Protocol 3, planar variant);
    soundness is amplified by running independent rounds and demanding all
    trap outcomes pass.
  - **Compatibility with Remote State Preparation** through an
    :class:`RSPClient` abstraction that consumes
    :class:`~brickwork_transpiler.bfk_encoder.BFKQubitPreparation` lists.

The remainder of the user's circuit runs under a Quantum One-Time Pad,
glued to the BQC regions via Type 0 / Type 1 / Type 2 connectors as defined
in Lee & Chung 2025, "Partial Blind Quantum Computation".

Public entry points:

    cloak_compile(qc, ...) -> CloakedJob
    verify_session(job, server_results) -> (ok, output)

See :mod:`brickwork_transpiler.cloak.annotations` for marking sensitive
subcircuits.
"""

from __future__ import annotations

from .annotations import Sensitive, sensitive
from .slicer import BoundaryType, SlicePlan, Sub, slice_circuit
from .rsp import (
    LocalRSPClient,
    PreparationHandle,
    RemoteRSPClient,
    RSPClient,
)
from .metrics import BlindShare, compute_blind_share
from .visualisation import cloak_style, draw_cloaked, summarize_cloaked

__all__ = [
    "Sensitive",
    "sensitive",
    "slice_circuit",
    "SlicePlan",
    "Sub",
    "BoundaryType",
    "RSPClient",
    "LocalRSPClient",
    "RemoteRSPClient",
    "PreparationHandle",
    "simulate_cloaked",
    "assemble_honest_circuit",
    "draw_cloaked",
    "summarize_cloaked",
    "cloak_style",
    "BlindShare",
    "compute_blind_share",
]


def cloak_compile(*args, **kwargs):  # noqa: D401 — re-exported lazily
    """Compile a Qiskit circuit into a partially-blind verifiable job.

    Imported lazily so the top-level :mod:`brickwork_transpiler.cloak`
    namespace does not pay the cost of pulling in the full Graphix/Qiskit
    pipeline at import time.
    """
    from .blinder import cloak_compile as _impl

    return _impl(*args, **kwargs)


def verify_session(*args, **kwargs):
    """Check trap outcomes from a server run and decrypt the output state."""
    from .blinder import verify_session as _impl

    return _impl(*args, **kwargs)


def simulate_cloaked(*args, **kwargs):
    """Cloak-compile then simulate the resulting honest-server circuit."""
    from .simulate import simulate_cloaked as _impl

    return _impl(*args, **kwargs)


def assemble_honest_circuit(*args, **kwargs):
    """Rebuild the equivalent plaintext circuit from a CloakedJob."""
    from .simulate import assemble_honest_circuit as _impl

    return _impl(*args, **kwargs)
