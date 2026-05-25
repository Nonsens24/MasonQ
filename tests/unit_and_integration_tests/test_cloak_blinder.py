"""Smoke test for end-to-end cloak_compile on a small circuit.

This exercises the full pipeline against a tiny circuit with one
:class:`~brickwork_transpiler.cloak.Sensitive` block.  The brickwork
transpilation step is real (no mocking), so the test is marked ``slow`` to
keep the default fast-test sweep quick.
"""

import numpy as np
import pytest
from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import cloak_compile, sensitive
from brickwork_transpiler.cloak.blinder import CloakedJob


@pytest.mark.slow
def test_cloak_compile_returns_well_formed_job():
    qc = QuantumCircuit(2)
    qc.h([0, 1])
    with sensitive(qc, [0, 1], label="tiny-oracle") as oracle:
        oracle.cx(0, 1)
    qc.h([0, 1])

    job = cloak_compile(qc, rounds=2, seed=7)

    assert isinstance(job, CloakedJob)
    assert len(job.subs) == 1
    sub = job.subs[0]
    assert len(sub.rounds) == 2
    # Every round produced a trap embedding with at least one preparation per node.
    for rnd in sub.rounds:
        assert rnd.embedding.trap_node is not None
        assert len(rnd.preparations) >= 1
    # RSP plan has one handle per (sub, round).
    assert len(job.rsp_plan) == 2
    # Boundary classification: clear -> BQC -> clear.
    assert job.boundary_types[0].value == "unprotected_to_bqc"
    assert job.boundary_types[-1].value == "bqc_to_unprotected"


@pytest.mark.slow
def test_cloak_compile_seed_is_reproducible():
    qc = QuantumCircuit(2)
    with sensitive(qc, [0, 1]) as oracle:
        oracle.cx(0, 1)

    j1 = cloak_compile(qc, rounds=1, seed=99)
    j2 = cloak_compile(qc, rounds=1, seed=99)
    assert j1.subs[0].rounds[0].embedding.trap_node == j2.subs[0].rounds[0].embedding.trap_node
    assert j1.subs[0].rounds[0].embedding.expected_outcome == (
        j2.subs[0].rounds[0].embedding.expected_outcome
    )
