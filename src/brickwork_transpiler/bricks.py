"""Hand-built brickwork primitives for tests and pedagogical examples.

These are the canonical 5-column brick patterns the transpiler produces
implicitly. Exporting them as standalone Graphix patterns lets the test
suite verify the angle table for each archetype against a tiny known
state, without going through the full Qiskit-to-pattern pipeline.

All patterns follow the convention used throughout the package:
measurement angles are negated relative to the circuit convention so they
match Graphix's measurement-angle sign convention.
"""

from . import graph_builder
from .pattern_converter import generate_from_graph


def arbitrary_brick(a: float, b: float, c: float, with_input: bool = False):
    """Single-qubit Euler brick implementing `Rz(a) Rx(b) Rz(c)`.

    Two of the original six measurements cancel because adjacent Hadamards
    fuse, leaving four measurements in the `(a, b, c, 0)` slot pattern.
    """
    inside_graph = graph_builder.create_tuple_node_graph(1, 5)
    angles = {
        (0, 0): -a,
        (0, 1): -b,
        (0, 2): -c,
        (0, 3): 0.0,  # final teleport (J(0) Hadamard)
    }
    inputs = [(0, 0)] if with_input else []
    outputs = [(0, 4)]
    return generate_from_graph(inside_graph, angles, inputs, outputs)


def arbitrary_prep_brick(a: float, b: float, c: float):
    """Same as `arbitrary_brick` with the input qubit fixed to `|+>`."""
    inside_graph = graph_builder.create_tuple_node_graph(1, 5)
    angles = {
        (0, 0): -a,
        (0, 1): -b,
        (0, 2): -c,
        (0, 3): 0.0,
    }
    inputs: list = []
    outputs = [(0, 4)]
    return generate_from_graph(inside_graph, angles, inputs, outputs)


def CX_bottom_target_brick(with_inputs: bool = False):
    """CNOT brick where the target sits on the bottom row (rows 0=ctrl, 1=tgt).

    Layout::

        (0, 0) -- (0, 1) -- (0, 2) -- (0, 3) -- (0, 4)
                              |                   |
        (1, 0) -- (1, 1) -- (1, 2) -- (1, 3) -- (1, 4)
    """
    inside_graph = graph_builder.create_tuple_node_graph(2, 5)
    inside_graph.add_edge((0, 2), (1, 2))
    inside_graph.add_edge((0, 4), (1, 4))

    angles = {
        (0, 0): 0.0,
        (0, 1): 0.0,
        (0, 2): -1 / 4,
        (0, 3): 0.0,
        (1, 0): 0.0,
        (1, 1): -1 / 4,
        (1, 2): 0.0,
        (1, 3): 1 / 4,
    }
    inputs = [(0, 0), (1, 0)] if with_inputs else []
    outputs = [(0, 4), (1, 4)]
    return generate_from_graph(inside_graph, angles, inputs, outputs)


def CX_top_target_brick(with_inputs: bool = False):
    """CNOT brick where the target sits on the top row (rows 0=tgt, 1=ctrl).

    Same node layout as `CX_bottom_target_brick`; the angle table is
    transposed across the two rows to swap the control/target roles.
    """
    inside_graph = graph_builder.create_tuple_node_graph(2, 5)
    inside_graph.add_edge((0, 2), (1, 2))
    inside_graph.add_edge((0, 4), (1, 4))

    angles = {
        (0, 0): 0.0,
        (0, 1): -1 / 4,
        (0, 2): 0.0,
        (0, 3): 1 / 4,
        (1, 0): 0.0,
        (1, 1): 0.0,
        (1, 2): -1 / 4,
        (1, 3): 0.0,
    }
    inputs = [(0, 0), (1, 0)] if with_inputs else []
    outputs = [(0, 4), (1, 4)]
    return generate_from_graph(inside_graph, angles, inputs, outputs)
