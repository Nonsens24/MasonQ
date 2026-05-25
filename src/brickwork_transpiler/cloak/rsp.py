"""Remote State Preparation handoff for cloak's BFK qubit preparations.

The cloak blinder produces a list of
:class:`~brickwork_transpiler.bfk_encoder.BFKQubitPreparation` per round —
each one names a graph node and the :math:`|+_\\theta>` (or :math:`|0>` /
:math:`|1>` for dummies) state Alice must inject.  RSP lets a remote prover
emit those single-qubit states, freeing the client from needing a quantum
state generator.

This module defines a small abstract protocol, plus two implementations:

- :class:`LocalRSPClient` — Alice prepares the qubits herself (current
  MasonQ assumption; the resulting handle is a thin wrapper around the
  preparation list and is the default).
- :class:`RemoteRSPClient` — placeholder for a third-party RSP backend; the
  current implementation raises :class:`NotImplementedError` on
  ``prepare(...)`` so callers wire it up consciously.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Protocol, runtime_checkable
from uuid import uuid4

from ..bfk_encoder import BFKQubitPreparation


@dataclass(frozen=True)
class PreparationHandle:
    """Opaque handle that downstream stages use to refer to one RSP batch."""

    handle_id: str
    preparations: List[BFKQubitPreparation]
    backend: str = "local"
    metadata: dict = field(default_factory=dict)

    @property
    def num_qubits(self) -> int:
        return len(self.preparations)


@runtime_checkable
class RSPClient(Protocol):
    """Anything that knows how to prepare a batch of BFK qubits remotely."""

    def prepare(self, specs: List[BFKQubitPreparation]) -> PreparationHandle:
        ...


class LocalRSPClient:
    """Alice prepares the qubits herself; the handle just bundles the spec."""

    def prepare(self, specs: List[BFKQubitPreparation]) -> PreparationHandle:
        return PreparationHandle(
            handle_id=f"local-{uuid4().hex[:8]}",
            preparations=list(specs),
            backend="local",
        )


class RemoteRSPClient:
    """Stub for a real RSP backend; raises until wired to a provider."""

    def __init__(self, endpoint: str | None = None) -> None:
        self.endpoint = endpoint

    def prepare(self, specs: List[BFKQubitPreparation]) -> PreparationHandle:
        raise NotImplementedError(
            "RemoteRSPClient is a placeholder; supply a concrete RSP backend."
        )
