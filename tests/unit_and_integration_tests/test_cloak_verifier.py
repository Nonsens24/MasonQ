"""Tests for the planar trap/dummy embedding and trap-outcome checker."""

import numpy as np
import pytest

from brickwork_transpiler.cloak.verifier import (
    NodeKind,
    TrapEmbedding,
    check_trap_outcomes,
)


class _FakePattern:
    """Minimal duck-type stand-in for a Graphix Pattern.

    Only the bits the verifier actually touches: ``input_nodes``,
    ``output_nodes``, and a sequence with entanglement-like commands so the
    neighbour lookup can find adjacency.
    """

    def __init__(self, input_nodes, output_nodes, edges):
        self.input_nodes = list(input_nodes)
        self.output_nodes = list(output_nodes)
        self._edges = edges

        class _E:
            def __init__(self, nodes):
                self.nodes = list(nodes)

        self._Pattern__seq = [_E(e) for e in edges]

    def extract_nodes(self):
        nodes = set(self.input_nodes) | set(self.output_nodes)
        for e in self._edges:
            nodes.update(e)
        return sorted(nodes)


def _line_pattern(n: int) -> _FakePattern:
    """Linear graph 0-1-2-...-n-1, first node is input, last is output."""
    edges = [(i, i + 1) for i in range(n - 1)]
    return _FakePattern(input_nodes=[0], output_nodes=[n - 1], edges=edges)


def test_embed_planar_trap_chooses_interior_node_and_labels_neighbours():
    from brickwork_transpiler.cloak.verifier import embed_planar_trap

    pat = _line_pattern(5)
    rng = np.random.default_rng(0)
    emb = embed_planar_trap(pat, rng=rng)

    assert emb.trap_node not in pat.input_nodes
    assert emb.trap_node not in pat.output_nodes
    assert emb.node_kinds[emb.trap_node] is NodeKind.TRAP
    # Every dummy in the embedding is a neighbour of the trap.
    for n in emb.dummy_bits:
        assert n in emb.metadata["neighbours"]
        assert emb.node_kinds[n] is NodeKind.DUMMY
    # All other nodes are computation.
    for n, kind in emb.node_kinds.items():
        if n != emb.trap_node and n not in emb.dummy_bits:
            assert kind is NodeKind.COMPUTATION


def test_check_trap_outcomes_honest_server_passes():
    emb = TrapEmbedding(
        trap_node=7,
        trap_theta=0.5,
        expected_outcome=1,
        dummy_bits={6: 1, 8: 0},
        node_kinds={6: NodeKind.DUMMY, 7: NodeKind.TRAP, 8: NodeKind.DUMMY},
    )
    outcomes = [{7: 1}]
    assert check_trap_outcomes([emb], outcomes) is True


def test_check_trap_outcomes_cheating_server_fails():
    emb = TrapEmbedding(
        trap_node=7,
        trap_theta=0.5,
        expected_outcome=1,
        dummy_bits={},
        node_kinds={7: NodeKind.TRAP},
    )
    outcomes = [{7: 0}]
    assert check_trap_outcomes([emb], outcomes) is False


def test_check_trap_outcomes_round_count_mismatch_raises():
    emb = TrapEmbedding(
        trap_node=1, trap_theta=0.0, expected_outcome=0, dummy_bits={}, node_kinds={1: NodeKind.TRAP}
    )
    with pytest.raises(ValueError, match="rounds count mismatch"):
        check_trap_outcomes([emb, emb], [{1: 0}])


def test_embed_planar_trap_seed_reproducibility():
    from brickwork_transpiler.cloak.verifier import embed_planar_trap

    pat = _line_pattern(6)
    e1 = embed_planar_trap(pat, rng=np.random.default_rng(123))
    e2 = embed_planar_trap(pat, rng=np.random.default_rng(123))
    assert e1.trap_node == e2.trap_node
    assert e1.dummy_bits == e2.dummy_bits
    assert e1.expected_outcome == e2.expected_outcome
