"""Mark sensitive sub-circuits inside a Qiskit ``QuantumCircuit``.

A :class:`Sensitive` instruction is an opaque container around an inner
``QuantumCircuit``.  The cloak slicer later strips these containers out of
the outer circuit, hands each inner circuit to the brickwork transpiler,
wraps the resulting pattern with trap/dummy verification, and stitches the
result back into the outer flow via the QHE-bridge composer.

Example::

    from qiskit import QuantumCircuit
    from brickwork_transpiler.cloak import sensitive

    qc = QuantumCircuit(3)
    qc.h([0, 1, 2])
    with sensitive(qc, [0, 1, 2], label="oracle") as oracle:
        oracle.ccx(0, 1, 2)
        oracle.x(2)
    qc.h([0, 1, 2])

The ``oracle`` block round-trips through Qiskit transpiler passes because
``Sensitive`` provides a ``definition`` and is treated as a composite gate.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional, Sequence

from qiskit import QuantumCircuit
from qiskit.circuit import Instruction, Qubit


class Sensitive(Instruction):
    """A Qiskit instruction wrapping a sub-circuit that must run blindly.

    The wrapper is *opaque*: Qiskit transpiler passes that respect
    ``definition`` boundaries (``optimization_level=0`` or any pass that does
    not descend into custom gates) will leave the sensitive block intact, so
    the cloak slicer can recover it later.
    """

    def __init__(
        self,
        definition: QuantumCircuit,
        *,
        label: Optional[str] = None,
    ) -> None:
        if definition.num_clbits != 0:
            raise ValueError(
                "Sensitive sub-circuits must not contain classical bits; "
                "classical feed-forward is not supported under BQC."
            )
        super().__init__(
            name="sensitive",
            num_qubits=definition.num_qubits,
            num_clbits=0,
            params=[],
            label=label,
        )
        self._sensitive_body = definition.copy()
        self._definition = self._sensitive_body

    @property
    def sensitive_body(self) -> QuantumCircuit:
        """The wrapped sub-circuit, in its own qubit space (0..n-1)."""
        return self._sensitive_body

    def _define(self) -> None:  # pragma: no cover — definition pre-built
        self._definition = self._sensitive_body


def _resolve_qubits(
    qc: QuantumCircuit, qubits: Optional[Sequence[int | Qubit]]
) -> list[Qubit]:
    if qubits is None:
        return list(qc.qubits)
    resolved: list[Qubit] = []
    for q in qubits:
        if isinstance(q, Qubit):
            resolved.append(q)
        else:
            resolved.append(qc.qubits[int(q)])
    return resolved


@contextmanager
def sensitive(
    qc: QuantumCircuit,
    qubits: Optional[Sequence[int | Qubit]] = None,
    *,
    label: Optional[str] = None,
) -> Iterator[QuantumCircuit]:
    """Context manager that captures gates into a :class:`Sensitive` block.

    The yielded ``inner`` circuit lives in its own qubit space ``0..n-1``;
    on exit, those gates become a single ``Sensitive`` instruction appended
    to ``qc`` on the requested global qubits.

    ``qubits`` may be a list of integer indices or :class:`qiskit.circuit.Qubit`
    objects; if omitted, all qubits of ``qc`` are used.
    """
    target_qubits = _resolve_qubits(qc, qubits)
    inner = QuantumCircuit(len(target_qubits), name=label or "sensitive")
    try:
        yield inner
    finally:
        qc.append(Sensitive(inner, label=label), target_qubits)
