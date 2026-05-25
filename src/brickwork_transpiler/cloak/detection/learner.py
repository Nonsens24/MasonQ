"""Stage B learned blind-spot policy (placeholder).

Roadmap (not yet implemented):

  - Feature extraction from a Qiskit ``QuantumCircuit`` window:
    ``(T-count, depth, qubit-width, gate-type histogram, causal-cone size,
    taint flags)``.
  - Training data bootstrapped from user ``Sensitive`` annotations and the
    verification outcomes recorded on every prior ``cloak_compile`` call.
  - A small classifier (random forest / gradient-boosted trees) returning a
    per-window sensitivity probability that the user can threshold.

The class is exposed today so dependent code can import the name; calling
:meth:`LearnedPolicy.predict` raises ``NotImplementedError`` until Stage B
ships.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from qiskit import QuantumCircuit


@dataclass
class LearnedPolicy:
    """Placeholder for the future Stage B classifier."""

    model: Any = None
    feature_log: List[Dict[str, Any]] = field(default_factory=list)

    def record(self, features: Dict[str, Any], label: int) -> None:
        """Append one training example for later offline fit."""
        self.feature_log.append({"features": dict(features), "label": int(label)})

    def predict(self, qc: QuantumCircuit) -> List[float]:  # pragma: no cover — stub
        raise NotImplementedError(
            "LearnedPolicy.predict is part of Stage B (planned). "
            "Use propose_sensitive_blocks (Stage A heuristics) in the meantime."
        )
