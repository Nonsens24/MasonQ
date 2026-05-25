"""Automatic blind-spot detection for cloak.

In the long run we want a user to hand us a Qiskit circuit *without*
explicit :class:`~brickwork_transpiler.cloak.Sensitive` annotations and have
the cloak layer figure out which subcircuits to blind on its own.  This
package collects three stages of that pipeline; only Stage A is implemented
in the current release.

  - **Stage A — heuristics**: oracle / MCX detection, T-count clustering,
    and forward-cone taint analysis from user-tagged ``secret`` inputs.
  - **Stage B — learned policy** (stub): a small classifier trained on
    user-supplied annotations + verification outcomes.
  - **Stage C — cost-aware policy search** (stub): pick the minimum-overhead
    subset of subcircuits that covers all high-privacy operations.

Both Stage B and Stage C only ship module skeletons today; the data plumbing
(``cloak_compile`` recording per-job features) will arrive when Stage B is
wired up.
"""

from .heuristics import HeuristicReport, Candidate, propose_sensitive_blocks
from .learner import LearnedPolicy  # noqa: F401 — re-exported placeholder

__all__ = [
    "HeuristicReport",
    "Candidate",
    "propose_sensitive_blocks",
    "LearnedPolicy",
]
