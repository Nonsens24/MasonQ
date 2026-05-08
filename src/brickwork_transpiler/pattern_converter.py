import os
import tempfile

import numpy as np

generate_from_graph = None


def _prepare_graphix_runtime() -> None:
    """Make Graphix's optional simulation stack import reliably in conda envs."""
    os.environ.setdefault(
        "NUMBA_CACHE_DIR",
        os.path.join(tempfile.gettempdir(), "masonq-numba-cache"),
    )
    os.environ.setdefault(
        "MPLCONFIGDIR",
        os.path.join(tempfile.gettempdir(), "masonq-mpl-cache"),
    )
    os.environ.setdefault(
        "XDG_CACHE_HOME",
        os.path.join(tempfile.gettempdir(), "masonq-cache"),
    )


def _generate_from_graph(structure_graph, angles, inputs, outputs):
    """Import Graphix lazily so package imports do not require simulator setup."""
    global generate_from_graph
    if generate_from_graph is None:
        _prepare_graphix_runtime()
        try:
            from graphix import generate_from_graph as graphix_generate_from_graph
        except ImportError:
            from graphix.measurements import Measurement
            from graphix.opengraph import OpenGraph

            def graphix_generate_from_graph(graph, angle_map, input_nodes, output_nodes):
                output_set = set(output_nodes)
                measurements = {
                    node: Measurement.XY(angle)
                    for node, angle in angle_map.items()
                    if node not in output_set
                }
                return OpenGraph(
                    graph=graph,
                    input_nodes=list(input_nodes),
                    output_nodes=list(output_nodes),
                    measurements=measurements,
                ).to_pattern()

        generate_from_graph = graphix_generate_from_graph
    return generate_from_graph(structure_graph, angles, inputs, outputs)


def _cx_group_id(name: str) -> str:
    return name[2:-1]


def parse_euler_angles(cell):
    """Map a cell's local Qiskit Euler rotations to four brick measurements.

    The Qiskit basis entering this function is restricted to `rz` and `rx`.
    A single brick represents the sequence `Rz(a) Rx(b) Rz(c)` plus the final
    teleportation measurement. Angles are negated because Graphix uses the
    opposite measurement-angle convention from the circuit convention used here.
    """

    rotations = [0.0, 0.0, 0.0, 0.0]
    index = 0
    if cell[0].name == "rx":  # case of rxrz
        index += 1
    for instr in cell:
        if instr.name == "rz":
            if index != 0 and index != 2:
                raise AssertionError(
                    f"Index wrong: {index}, instuction: {instr}\n "
                    f"Probably shifted cx into a rotation brick"
                )
            rotations[index] = -float(instr.params[0]) / np.pi
        elif instr.name == "rx":
            rotations[1] = -float(instr.params[0]) / np.pi
        index = index + 1

    return rotations


def inject_angles(angles, brick_type, r, c, cell, node_colours):

    if brick_type == "id":
        angles.update(
            {
                (r, (c * 4) + 0): 0.0,
                (r, (c * 4) + 1): 0.0,
                (r, (c * 4) + 2): 0.0,
                (r, (c * 4) + 3): 0.0,
            }
        )
        node_colours.update(
            {
                (r, (c * 4) + 0): "lightblue",
                (r, (c * 4) + 1): "lightblue",
                (r, (c * 4) + 2): "lightblue",
                (r, (c * 4) + 3): "lightblue",
            }
        )
    elif brick_type == "euler_rot":
        local_angles = parse_euler_angles(cell)
        angles.update(
            {
                (r, (c * 4) + 0): local_angles[0],
                (r, (c * 4) + 1): local_angles[1],
                (r, (c * 4) + 2): local_angles[2],
                (r, (c * 4) + 3): local_angles[3],
            }
        )
        node_colours.update(
            {
                (r, (c * 4) + 0): "lightgreen",
                (r, (c * 4) + 1): "lightgreen",
                (r, (c * 4) + 2): "lightgreen",
                (r, (c * 4) + 3): "lightgreen",
            }
        )
    # CX target top
    elif brick_type == "CXtt":
        angles.update({
            (r, (c * 4) + 0): 0.0,
            (r, (c * 4) + 1): 1 / 2,
            (r, (c * 4) + 2): 0.0,
            (r, (c * 4) + 3): -1 / 2,

            (r + 1, (c * 4) + 0): 0.0,
            (r + 1, (c * 4) + 1): 0.0,
            (r + 1, (c * 4) + 2): 1 / 2,
            (r + 1, (c * 4) + 3): 0.0,
        })
        node_colours.update({
            (r, (c * 4) + 0): "LightSalmon",
            (r, (c * 4) + 1): "LightSalmon",
            (r, (c * 4) + 2): "LightSalmon",
            (r, (c * 4) + 3): "LightSalmon",

            (r + 1, (c * 4) + 0): "LightSalmon",
            (r + 1, (c * 4) + 1): "LightSalmon",
            (r + 1, (c * 4) + 2): "LightSalmon",
            (r + 1, (c * 4) + 3): "LightSalmon",
        })
    # CX target bottom
    elif brick_type == "CXct":
        angles.update({
            (r, (c * 4) + 0): 0.0,
            (r, (c * 4) + 1): 0.0,
            (r, (c * 4) + 2): 1 / 2,
            (r, (c * 4) + 3): 0.0,

            (r + 1, (c * 4) + 0): 0.0,
            (r + 1, (c * 4) + 1): 1 / 2,
            (r + 1, (c * 4) + 2): 0.0,
            (r + 1, (c * 4) + 3): -1 / 2,
        })
        node_colours.update({
            (r, (c * 4) + 0): "lightcoral",
            (r, (c * 4) + 1): "lightcoral",
            (r, (c * 4) + 2): "lightcoral",
            (r, (c * 4) + 3): "lightcoral",

            (r + 1, (c * 4) + 0): "lightcoral",
            (r + 1, (c * 4) + 1): "lightcoral",
            (r + 1, (c * 4) + 2): "lightcoral",
            (r + 1, (c * 4) + 3): "lightcoral",
        })
    else:
        raise AssertionError(f"Unknown brick type: {brick_type} instuction type: {cell}")


def _cell_cx_endpoint(cell):
    endpoints = [
        instr for instr in cell if instr.name.startswith("cx") and instr.name[-1:] in {"c", "t"}
    ]
    if not endpoints:
        return None
    if len(endpoints) != len(cell):
        raise AssertionError(f"CX and rotations occupy the same brick cell: {cell!r}")
    return endpoints[0]


def _index_cx_groups_by_column(instruction_matrix):
    groups_by_col = []
    num_rows = len(instruction_matrix)
    num_cols = len(instruction_matrix[0]) if instruction_matrix else 0
    for c in range(num_cols):
        groups = {}
        for r in range(num_rows):
            for instr in instruction_matrix[r][c]:
                if instr.name.startswith("cx") and instr.name[-1:] in {"c", "t"}:
                    groups.setdefault(_cx_group_id(instr.name), []).append((r, instr.name[-1]))
        groups_by_col.append(groups)
    return groups_by_col


def to_pattern(instruction_matrix, structure_graph):
    """Inject measurement angles and create a Graphix pattern.

    CX bricks are two-row gadgets. We resolve each CX group explicitly and
    inject it only from its top row so the angle table is independent of whether
    the control or target endpoint appears first in row-major iteration.
    """

    num_qubits = len(instruction_matrix)
    num_cols = len(instruction_matrix[0]) if instruction_matrix else 0
    angles = {}
    node_colours = {}
    placed_cx_groups = set()
    cx_groups_by_col = _index_cx_groups_by_column(instruction_matrix)

    for c in range(num_cols):
        cx_groups = cx_groups_by_col[c]
        for r in range(num_qubits):
            cell = instruction_matrix[r][c]

            if not cell:
                inject_angles(
                    angles=angles,
                    brick_type="id",
                    r=r,
                    c=c,
                    cell=None,
                    node_colours=node_colours,
                )
                continue

            cx_endpoint = _cell_cx_endpoint(cell)
            if cx_endpoint is None:
                inject_angles(
                    angles=angles,
                    brick_type="euler_rot",
                    r=r,
                    c=c,
                    cell=cell,
                    node_colours=node_colours,
                )
                continue

            gid = _cx_group_id(cx_endpoint.name)
            if gid in placed_cx_groups:
                continue

            partner_rows = cx_groups.get(gid, [])
            if len(partner_rows) != 2:
                raise AssertionError(f"CX group {gid!r} has invalid endpoints: {partner_rows}")

            top_row = min(row for row, _ in partner_rows)
            top_role = next(role for row, role in partner_rows if row == top_row)
            if top_role == "t":
                brick_type = "CXtt"
            elif top_role == "c":
                brick_type = "CXct"
            else:
                raise AssertionError(f"Unknown CX endpoint role: {top_role!r}")

            inject_angles(
                angles=angles,
                brick_type=brick_type,
                r=top_row,
                c=c,
                cell=cell,
                node_colours=node_colours,
            )
            placed_cx_groups.add(gid)

    inputs = []  # Initialise to the |+> state as with ubqc
    outputs = [(i, (num_cols * 4)) for i in range(num_qubits)]

    brickwork_pattern = _generate_from_graph(structure_graph, angles, inputs, outputs)

    return brickwork_pattern, node_colours
