"""Tests for the blind-share metric."""

import pytest
from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import (
    BlindShare,
    compute_blind_share,
    sensitive,
    summarize_cloaked,
)


def test_blind_share_zero_for_circuit_without_sensitive():
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    share = compute_blind_share(qc)
    assert share.gates_blind == 0
    assert share.gates_clear == 2
    assert share.gates_total == 2
    assert share.gate_fraction == 0.0


def test_blind_share_full_when_everything_inside_sensitive():
    qc = QuantumCircuit(2)
    with sensitive(qc, [0, 1], label="oracle") as inner:
        inner.h(0)
        inner.cx(0, 1)
        inner.x(1)
    share = compute_blind_share(qc)
    assert share.gates_blind == 3
    assert share.gates_clear == 0
    assert share.gate_fraction == 1.0


def test_blind_share_mixed_split():
    qc = QuantumCircuit(3)
    qc.h([0, 1, 2])  # 3 clear gates
    with sensitive(qc, [0, 1, 2]) as inner:
        inner.cx(0, 1)
        inner.x(2)  # 2 blind gates
    qc.h([0, 1, 2])  # 3 more clear gates
    share = compute_blind_share(qc)
    assert share.gates_blind == 2
    assert share.gates_clear == 6
    assert share.gates_total == 8
    assert share.gate_fraction == pytest.approx(2.0 / 8.0)


def test_blind_share_format_includes_percentage():
    share = BlindShare(gates_blind=4, gates_clear=6)
    line = share.format()
    assert "40.0%" in line
    assert "4/10" in line


def test_blind_share_handles_empty_circuit():
    qc = QuantumCircuit(0)
    share = compute_blind_share(qc)
    assert share.gates_total == 0
    assert share.gate_fraction == 0.0


def test_summarize_cloaked_includes_blind_share_line():
    qc = QuantumCircuit(2)
    qc.h([0, 1])
    with sensitive(qc, [0, 1]) as inner:
        inner.cx(0, 1)
    summary = summarize_cloaked(qc)
    assert "blind share" in summary
    # 1 blind gate, 2 clear gates -> ~33%
    assert "33.3%" in summary


@pytest.mark.slow
def test_cloaked_job_metadata_carries_blind_share():
    from brickwork_transpiler.cloak import cloak_compile

    qc = QuantumCircuit(2)
    qc.h([0, 1])
    with sensitive(qc, [0, 1]) as inner:
        inner.cx(0, 1)
    job = cloak_compile(qc, rounds=2, seed=0)

    assert "blind_share" in job.metadata
    share = job.metadata["blind_share"]
    assert isinstance(share, BlindShare)
    assert share.gates_total > 0
    # Brickwork graph node counts should be reported post-compile.
    assert len(share.graph_nodes_per_sub) == 1
    assert share.graph_nodes_per_sub[0] > 0
    assert share.rounds == 2
    assert share.graph_nodes_total == share.graph_nodes_per_sub[0] * 2
