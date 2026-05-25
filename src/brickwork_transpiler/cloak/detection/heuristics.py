"""Stage A heuristics: cheap, syntactic blind-spot proposals.

Three signals contribute to a *candidate* score:

  1. **Oracle-shaped instructions**: anything that looks like an oracle by
     name (``oracle``, ``mcx``, ``mcmt``, ``mcphase``, ``phase_oracle``) is
     a strong privacy candidate — it usually encodes the function the user
     is trying to keep private.
  2. **T-count density**: Clifford operations are public-key-friendly under
     QHE; non-Clifford ``T`` gates carry the irreversible non-linear logic
     that makes a region "really computing something secret".  A sliding
     window with high T-density is a soft candidate.
  3. **Forward taint** from user-tagged secret inputs: any qubit reachable
     in the causal cone of a qubit the user has marked as ``secret`` becomes
     a candidate set.  Inputs are tagged on the ``QuantumRegister`` via the
     ``register.metadata`` dictionary (Qiskit allows arbitrary attributes)
     or via a parallel ``secret_qubits`` argument to
     :func:`propose_sensitive_blocks`.

The output is a list of :class:`Candidate` ranges (start instruction index,
end instruction index, touched qubits, score, rationale).  The user is
expected to review them before adding ``Sensitive`` blocks — Stage A never
mutates the input circuit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence

from qiskit import QuantumCircuit


_ORACLE_NAMES = frozenset(
    {"oracle", "mcx", "mcmt", "mcphase", "phase_oracle", "mcx_gray", "mcu1", "ccx"}
)


@dataclass
class Candidate:
    """A contiguous run of gates that the heuristics flag as sensitive."""

    start: int
    end: int  # exclusive
    qubits: List[int]
    score: float
    rationale: str
    metadata: dict = field(default_factory=dict)


@dataclass
class HeuristicReport:
    """Bundle of all candidates produced by Stage A."""

    candidates: List[Candidate]
    t_count: int
    total_gates: int

    @property
    def coverage_qubits(self) -> List[int]:
        seen: set = set()
        for c in self.candidates:
            seen.update(c.qubits)
        return sorted(seen)


def _instr_qubits(qc: QuantumCircuit, instr) -> List[int]:
    index = {q: i for i, q in enumerate(qc.qubits)}
    return [index[q] for q in instr.qubits]


def _propose_oracle_blocks(qc: QuantumCircuit) -> List[Candidate]:
    out: List[Candidate] = []
    for i, instr in enumerate(qc.data):
        name = instr.operation.name.lower()
        if name in _ORACLE_NAMES:
            out.append(
                Candidate(
                    start=i,
                    end=i + 1,
                    qubits=_instr_qubits(qc, instr),
                    score=1.0,
                    rationale=f"oracle-shaped instruction '{name}'",
                )
            )
    return out


def _propose_t_clusters(
    qc: QuantumCircuit,
    *,
    window: int = 8,
    min_density: float = 0.25,
) -> List[Candidate]:
    """Sliding-window T-density detector.

    The window-size and density default are deliberately conservative; users
    can tune both via the :func:`propose_sensitive_blocks` keyword args.
    """
    if window <= 0 or len(qc.data) < window:
        return []

    flags = [1 if instr.operation.name.lower() in ("t", "tdg") else 0 for instr in qc.data]
    out: List[Candidate] = []
    i = 0
    while i + window <= len(flags):
        density = sum(flags[i : i + window]) / window
        if density >= min_density:
            end = i + window
            qubits = sorted(
                {q for j in range(i, end) for q in _instr_qubits(qc, qc.data[j])}
            )
            out.append(
                Candidate(
                    start=i,
                    end=end,
                    qubits=qubits,
                    score=density,
                    rationale=f"T-density {density:.2f} >= {min_density}",
                )
            )
            i = end
        else:
            i += 1
    return out


def _forward_cone(
    qc: QuantumCircuit, seed_qubits: Sequence[int]
) -> tuple[List[Candidate], List[int]]:
    """Return the causal-cone candidate plus the full tainted-qubit set."""
    tainted = set(seed_qubits)
    start: Optional[int] = None
    for i, instr in enumerate(qc.data):
        qs = _instr_qubits(qc, instr)
        if any(q in tainted for q in qs):
            tainted.update(qs)
            if start is None:
                start = i
    if start is None:
        return [], sorted(tainted)
    return [
        Candidate(
            start=start,
            end=len(qc.data),
            qubits=sorted(tainted),
            score=0.5,
            rationale=f"forward cone of secret qubits {sorted(seed_qubits)}",
        )
    ], sorted(tainted)


def propose_sensitive_blocks(
    qc: QuantumCircuit,
    *,
    secret_qubits: Iterable[int] = (),
    t_window: int = 8,
    t_min_density: float = 0.25,
) -> HeuristicReport:
    """Run all Stage A heuristics and return the union of candidates."""
    candidates: List[Candidate] = []
    candidates.extend(_propose_oracle_blocks(qc))
    candidates.extend(_propose_t_clusters(qc, window=t_window, min_density=t_min_density))
    if secret_qubits:
        cone_candidates, _ = _forward_cone(qc, list(secret_qubits))
        candidates.extend(cone_candidates)

    t_count = sum(1 for instr in qc.data if instr.operation.name.lower() in ("t", "tdg"))
    return HeuristicReport(candidates=candidates, t_count=t_count, total_gates=len(qc.data))
