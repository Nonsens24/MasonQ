"""QOTP key-update tests against Lee & Chung 2025, Table 1."""

import numpy as np
import pytest
from qiskit import QuantumCircuit

from brickwork_transpiler.cloak.qhe import QOTPState, track_qotp_through


def test_qotp_zero_constructor():
    s = QOTPState.zero(3)
    assert s.a == [0, 0, 0]
    assert s.b == [0, 0, 0]
    assert s.num_qubits == 3


def test_qotp_x_and_z_are_no_ops():
    qc = QuantumCircuit(1)
    qc.x(0)
    qc.z(0)
    initial = QOTPState(a=[1], b=[1])
    plan = track_qotp_through(qc, initial)
    assert plan.final_state.a == [1]
    assert plan.final_state.b == [1]


def test_qotp_h_swaps_a_and_b():
    qc = QuantumCircuit(1)
    qc.h(0)
    plan = track_qotp_through(qc, QOTPState(a=[1], b=[0]))
    assert plan.final_state.a == [0]
    assert plan.final_state.b == [1]


def test_qotp_s_updates_b_to_a_xor_b():
    qc = QuantumCircuit(1)
    qc.s(0)
    plan = track_qotp_through(qc, QOTPState(a=[1], b=[1]))
    assert plan.final_state.a == [1]
    assert plan.final_state.b == [0]


def test_qotp_cx_updates_per_table_1():
    # CNOT: (a1, b1)(a2, b2) -> (a1, b1 XOR b2)(a1 XOR a2, b2)
    qc = QuantumCircuit(2)
    qc.cx(0, 1)
    plan = track_qotp_through(qc, QOTPState(a=[1, 0], b=[0, 1]))
    assert plan.final_state.a == [1, 1]  # a1, a1 XOR a2
    assert plan.final_state.b == [1, 1]  # b1 XOR b2, b2


def test_qotp_unknown_gate_raises_informative():
    qc = QuantumCircuit(1)
    qc.append(__import__("qiskit").circuit.library.RYGate(0.3), [0])
    with pytest.raises(NotImplementedError, match="not yet implemented"):
        track_qotp_through(qc, QOTPState.zero(1))


def test_qotp_t_gate_emits_gadget():
    qc = QuantumCircuit(1)
    qc.t(0)
    plan = track_qotp_through(qc, QOTPState(a=[1], b=[0]), rng=np.random.default_rng(42))
    assert len(plan.t_gadgets) == 1
    gadget = plan.t_gadgets[0]
    assert gadget.qubit == 0
    assert gadget.control_bit in (0, 1)
    assert gadget.expected_aux_key == (plan.final_state.a[0], plan.final_state.b[0])
