"""Unit tests for the Sensitive instruction and the `sensitive(...)` ctx mgr."""

import pytest
from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import Sensitive, sensitive


def test_sensitive_wraps_subcircuit_and_records_qubit_count():
    inner = QuantumCircuit(3)
    inner.h(0)
    inner.cx(0, 1)
    inner.ccx(0, 1, 2)

    op = Sensitive(inner, label="my-oracle")

    assert op.name == "sensitive"
    assert op.label == "my-oracle"
    assert op.num_qubits == 3
    assert op.num_clbits == 0
    assert op.definition is not None
    assert op.sensitive_body.num_qubits == 3
    # The wrapped body is a copy, not the original reference.
    assert op.sensitive_body is not inner


def test_sensitive_rejects_classical_bits():
    inner = QuantumCircuit(2, 1)
    inner.h(0)
    with pytest.raises(ValueError, match="classical bits"):
        Sensitive(inner)


def test_sensitive_context_manager_appends_single_instruction():
    qc = QuantumCircuit(3)
    qc.h(0)

    with sensitive(qc, [0, 1, 2], label="oracle") as inner:
        inner.h(0)
        inner.cx(0, 1)
        inner.ccx(0, 1, 2)

    qc.h(2)

    sensitive_ops = [
        instr for instr in qc.data if isinstance(instr.operation, Sensitive)
    ]
    assert len(sensitive_ops) == 1
    sub_op = sensitive_ops[0].operation
    assert sub_op.label == "oracle"
    assert sub_op.num_qubits == 3
    # The recorded body has the gates we appended inside the with-block.
    body = sub_op.sensitive_body
    body_names = [instr.operation.name for instr in body.data]
    assert body_names == ["h", "cx", "ccx"]


def test_sensitive_context_manager_qubit_subset():
    qc = QuantumCircuit(4)
    with sensitive(qc, [1, 3]) as inner:
        inner.cx(0, 1)  # inner qubits 0, 1 -> outer qubits 1, 3
    sens = next(instr for instr in qc.data if isinstance(instr.operation, Sensitive))
    sens_qubits = [qc.find_bit(q).index for q in sens.qubits]
    assert sens_qubits == [1, 3]
