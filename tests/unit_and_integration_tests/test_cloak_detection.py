"""Stage A heuristic tests for `propose_sensitive_blocks`."""

import pytest
from qiskit import QuantumCircuit

from brickwork_transpiler.cloak.detection import propose_sensitive_blocks


def test_oracle_named_instruction_is_flagged():
    qc = QuantumCircuit(3)
    qc.h([0, 1, 2])
    qc.mcx([0, 1], 2)
    qc.h([0, 1, 2])

    report = propose_sensitive_blocks(qc)
    oracle_candidates = [c for c in report.candidates if "oracle-shaped" in c.rationale]
    assert len(oracle_candidates) == 1
    assert oracle_candidates[0].score == pytest.approx(1.0)
    assert set(oracle_candidates[0].qubits) == {0, 1, 2}


def test_t_density_window_flags_a_t_cluster():
    qc = QuantumCircuit(1)
    qc.h(0)
    qc.h(0)
    for _ in range(4):
        qc.t(0)
    qc.h(0)
    qc.h(0)
    qc.h(0)
    qc.h(0)
    report = propose_sensitive_blocks(qc, t_window=4, t_min_density=0.5)
    t_candidates = [c for c in report.candidates if "T-density" in c.rationale]
    assert any(c.score >= 0.5 for c in t_candidates)


def test_taint_cone_extends_from_secret_qubits():
    qc = QuantumCircuit(3)
    qc.cx(0, 1)
    qc.cx(1, 2)
    report = propose_sensitive_blocks(qc, secret_qubits=[0])
    cone = next(c for c in report.candidates if "forward cone" in c.rationale)
    assert cone.qubits == [0, 1, 2]


def test_report_counts_total_and_t_gates():
    qc = QuantumCircuit(1)
    qc.h(0)
    qc.t(0)
    qc.tdg(0)
    report = propose_sensitive_blocks(qc)
    assert report.total_gates == 3
    assert report.t_count == 2
