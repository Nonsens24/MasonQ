from types import SimpleNamespace

from brickwork_transpiler import pattern_converter


class _Instr:
    def __init__(self, name, params=None):
        self.name = name
        self.params = params or []


def test_to_pattern_injects_cx_from_top_row_independent_of_role(monkeypatch):
    captured = {}

    def fake_generate_from_graph(graph, angles, inputs, outputs):
        captured["angles"] = angles
        captured["inputs"] = inputs
        captured["outputs"] = outputs
        return SimpleNamespace(output_nodes=outputs)

    monkeypatch.setattr(pattern_converter, "generate_from_graph", fake_generate_from_graph)

    matrix = [
        [[_Instr("cx0c")]],
        [[_Instr("cx0t")]],
    ]

    pattern, colours = pattern_converter.to_pattern(matrix, structure_graph=object())

    assert pattern.output_nodes == [(0, 4), (1, 4)]
    assert captured["angles"][(0, 2)] == 1 / 2
    assert captured["angles"][(1, 1)] == 1 / 2
    assert colours[(0, 0)] == "lightcoral"


def test_to_pattern_rejects_mixed_cx_rotation_cell(monkeypatch):
    monkeypatch.setattr(
        pattern_converter,
        "generate_from_graph",
        lambda graph, angles, inputs, outputs: SimpleNamespace(output_nodes=outputs),
    )

    matrix = [
        [[_Instr("cx0c"), _Instr("rz", [0.1])]],
        [[_Instr("cx0t")]],
    ]

    try:
        pattern_converter.to_pattern(matrix, structure_graph=object())
    except AssertionError as exc:
        assert "CX and rotations occupy the same brick cell" in str(exc)
    else:
        raise AssertionError("Expected mixed CX/rotation cell to be rejected")
