"""Tests for the cloak visualisation helpers."""

import pytest
from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import (
    Sensitive,
    cloak_style,
    draw_cloaked,
    sensitive,
    summarize_cloaked,
)


def _build_qc_with_one_oracle() -> QuantumCircuit:
    qc = QuantumCircuit(3, name="qc-demo")
    qc.h([0, 1, 2])
    with sensitive(qc, [0, 1, 2], label="oracle") as oracle:
        oracle.cx(0, 1)
        oracle.x(2)
    qc.h([0, 1, 2])
    return qc


def test_cloak_style_returns_color_for_sensitive():
    style = cloak_style()
    assert "sensitive" in style["displaycolor"]
    fill, text = style["displaycolor"]["sensitive"]
    assert fill.startswith("#")
    assert text.startswith("#")


def test_summarize_cloaked_lists_block_and_qubits():
    qc = _build_qc_with_one_oracle()
    summary = summarize_cloaked(qc)
    assert "qc-demo" in summary
    assert "1 cloaked block" in summary
    assert "'oracle'" in summary
    assert "qubits [0, 1, 2]" in summary
    assert "2 gates" in summary


def test_summarize_cloaked_with_no_blocks():
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    summary = summarize_cloaked(qc)
    assert "0 cloaked block" in summary
    assert "no cloaked blocks" in summary


def test_draw_cloaked_text_includes_marker_prefix():
    qc = _build_qc_with_one_oracle()
    rendering = str(draw_cloaked(qc, output="text"))
    # The default marker is a lock; the user label "oracle" must appear too.
    assert "oracle" in rendering
    assert "🔒" in rendering
    # The H gates outside the sensitive block remain visible.
    assert "H" in rendering


def test_draw_cloaked_does_not_mutate_the_input():
    qc = _build_qc_with_one_oracle()
    before = [
        (instr.operation.name, getattr(instr.operation, "label", None))
        for instr in qc.data
    ]
    _ = draw_cloaked(qc, output="text")
    after = [
        (instr.operation.name, getattr(instr.operation, "label", None))
        for instr in qc.data
    ]
    assert before == after, "draw_cloaked should not mutate the original circuit"


def test_draw_cloaked_marker_can_be_disabled():
    qc = _build_qc_with_one_oracle()
    rendering = str(draw_cloaked(qc, output="text", marker=""))
    assert "🔒" not in rendering
    assert "oracle" in rendering
