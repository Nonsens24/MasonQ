"""QOTP key tracking for unprotected segments under partial-blind composition.

The unprotected (non-:class:`Sensitive`) portion of the user's circuit is
executed by the server under a Quantum One-Time Pad: every qubit carries
classical encryption keys ``(a_i, b_i)`` such that the *plaintext* state
``|psi>`` is encoded on the wire as ``X^{a_i} Z^{b_i} |psi>``.

Lee & Chung 2025, Table 1, gives the per-gate key-update rules that let the
client follow Clifford operations homomorphically.  Non-Clifford ``T`` gates
use the FBS+14 gadget (paper §2.2, Fig. 3): one round of classical
interaction per ``T`` to update the key.

This module is deliberately classical: it never touches a quantum state.
The composer feeds it the outer-circuit gate list, and it returns the
updated :class:`QOTPState` plus any classical control bits the server needs
for ``T``-gadget evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from qiskit import QuantumCircuit


@dataclass
class QOTPState:
    """Per-qubit classical Pauli keys ``(a_i, b_i)`` for the current wire state."""

    a: List[int]
    b: List[int]

    @classmethod
    def zero(cls, num_qubits: int) -> "QOTPState":
        return cls(a=[0] * num_qubits, b=[0] * num_qubits)

    @property
    def num_qubits(self) -> int:
        return len(self.a)

    def copy(self) -> "QOTPState":
        return QOTPState(a=list(self.a), b=list(self.b))

    def refresh(
        self,
        *,
        num_qubits: Optional[int] = None,
        rng: Optional[np.random.Generator] = None,
    ) -> "QOTPState":
        """Resample the QOTP keys (used at every BQC-region output boundary).

        The fresh keys here represent ``(a', b')`` produced by the BQC region
        per Protocol 1 of FK17; the client retains them so subsequent QHE
        evaluation stays correct.
        """
        if rng is None:
            rng = np.random.default_rng()
        n = num_qubits if num_qubits is not None else self.num_qubits
        return QOTPState(
            a=[int(rng.integers(0, 2)) for _ in range(n)],
            b=[int(rng.integers(0, 2)) for _ in range(n)],
        )

    def apply_clifford(self, gate_name: str, qubits: List[int]) -> None:
        """Update keys in place for a Clifford gate; see Lee & Chung Table 1."""
        gate = gate_name.lower()
        if gate in ("x", "z", "id", "barrier"):
            return  # X and Z are themselves Paulis: no change to (a, b).
        if gate in ("y",):
            return
        if gate == "h":
            q = qubits[0]
            self.a[q], self.b[q] = self.b[q], self.a[q]
            return
        if gate == "s":
            q = qubits[0]
            # S: (a, b) -> (a, a ^ b)
            self.b[q] ^= self.a[q]
            return
        if gate in ("sdg", "sdag"):
            q = qubits[0]
            self.b[q] ^= self.a[q]
            return
        if gate in ("cx", "cnot"):
            c, t = qubits
            # (a1, b1)(a2, b2) -> (a1, b1 ^ b2)(a1 ^ a2, b2)
            self.b[c] ^= self.b[t]
            self.a[t] ^= self.a[c]
            return
        if gate in ("cz",):
            c, t = qubits
            # CZ is Clifford; under QOTP: (a1, b1)(a2, b2) ->
            #   (a1, b1 ^ a2)(a2, b2 ^ a1)
            self.b[c] ^= self.a[t]
            self.b[t] ^= self.a[c]
            return
        raise NotImplementedError(
            f"QOTP update for gate '{gate_name}' is not yet implemented; "
            "wrap the gate in a Sensitive block or extend QOTPState."
        )


@dataclass
class TGadgetInteraction:
    """One round of classical interaction required by an FBS+14 ``T`` gadget."""

    qubit: int
    control_bit: int
    """``x = a XOR y`` sent to the server before the auxiliary measurement."""

    expected_aux_key: Tuple[int, int]
    """``(a'', b'')`` the client will use to update the QOTP after the server
    returns the auxiliary measurement bit ``c``."""


@dataclass
class QHEPlan:
    """Result of running QOTP tracking over an unprotected gate list."""

    final_state: QOTPState
    t_gadgets: List[TGadgetInteraction] = field(default_factory=list)


def track_qotp_through(
    circuit: QuantumCircuit,
    initial: QOTPState,
    *,
    rng: Optional[np.random.Generator] = None,
) -> QHEPlan:
    """Walk ``circuit`` and update the QOTP keys per-gate.

    ``T`` gates produce a :class:`TGadgetInteraction` placeholder; a future
    iteration will wire these to the actual server-client interaction
    protocol.  All other Clifford gates are absorbed silently.
    """
    if rng is None:
        rng = np.random.default_rng()

    state = initial.copy()
    gadgets: List[TGadgetInteraction] = []
    qubit_index: Dict = {q: i for i, q in enumerate(circuit.qubits)}

    for instr in circuit.data:
        name = instr.operation.name
        qubits = [qubit_index[q] for q in instr.qubits]
        if name in ("t", "tdg"):
            q = qubits[0]
            y = int(rng.integers(0, 2))
            x = state.a[q] ^ y
            c_simulated = int(rng.integers(0, 2))
            a_old, b_old = state.a[q], state.b[q]
            a_new = a_old ^ c_simulated
            b_new = a_old * (c_simulated ^ y ^ 1) ^ b_old ^ int(name == "t") ^ y
            state.a[q], state.b[q] = a_new, b_new & 1
            gadgets.append(
                TGadgetInteraction(
                    qubit=q,
                    control_bit=x,
                    expected_aux_key=(a_new, b_new & 1),
                )
            )
        else:
            state.apply_clifford(name, qubits)

    return QHEPlan(final_state=state, t_gadgets=gadgets)
