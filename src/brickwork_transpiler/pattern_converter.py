"""Measurement angles for an aligned brick matrix, and the Graphix pattern.

Each brick cell becomes four measured graph nodes. Rotation cells are read
off as an `Rz Rx Rz` Euler triple, CX cells use the fixed angle tables of
the brickwork CX gadget, and empty cells are identity bricks.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

import numpy as np
from graphix.measurements import Measurement
from graphix.opengraph import OpenGraph
from graphix.pattern import Pattern
from qiskit.synthesis import OneQubitEulerDecomposer

from .cx_tags import cx_group_id, cx_role, is_cx_endpoint

_ZXZ_DECOMPOSER = OneQubitEulerDecomposer("ZXZ")
# Cells already in the brick's Rz-Rx-Rz form (or a sub-sequence of it that the
# slot assignment in `parse_euler_angles` reads off correctly).
_DIRECT_EULER_FORMS = frozenset(
    {("rz",), ("rx",), ("rz", "rx"), ("rx", "rz"), ("rz", "rx", "rz")}
)
# Measurement angles of the two-row CX bricks, in units of pi: four angles for
# the top row and four for the row below it. "CXtt" has the target on top,
# "CXct" the control.
_CX_BRICK_ANGLES = {
    "CXtt": ((0.0, 0.5, 0.0, -0.5), (0.0, 0.0, 0.5, 0.0)),
    "CXct": ((0.0, 0.0, 0.5, 0.0), (0.0, 0.5, 0.0, -0.5)),
}
_BRICK_COLOURS = {
    "id": "lightblue",
    "euler_rot": "lightgreen",
    "CXtt": "lightsalmon",
    "CXct": "lightcoral",
}


def generate_from_graph(
    structure_graph: Any,
    angles: Mapping[Any, float],
    inputs: Iterable[Any],
    outputs: Iterable[Any],
) -> Pattern:
    """Build a Graphix pattern from a graph and XY-plane measurement angles (units of pi)."""
    output_nodes = list(outputs)
    output_set = set(output_nodes)
    measurements = {
        node: Measurement.XY(angle) for node, angle in angles.items() if node not in output_set
    }
    return OpenGraph(
        graph=structure_graph,
        input_nodes=list(inputs),
        output_nodes=output_nodes,
        measurements=measurements,
    ).to_pattern()


def _cell_unitary(cell):
    """Return the 2x2 unitary of a single-qubit cell, gates applied in list order."""
    unitary = np.eye(2, dtype=complex)
    for instr in cell:
        if instr.name == "id":
            continue
        half = float(instr.params[0]) / 2
        c, s = np.cos(half), np.sin(half)
        if instr.name == "rz":
            gate = np.array([[c - 1j * s, 0], [0, c + 1j * s]])
        elif instr.name == "rx":
            gate = np.array([[c, -1j * s], [-1j * s, c]])
        else:
            raise AssertionError(f"Unsupported instruction in rotation brick: {instr.name!r}")
        unitary = gate @ unitary
    return unitary


def parse_euler_angles(cell):
    """Map a cell's single-qubit rotations to four brick measurements.

    The Qiskit basis entering this function is restricted to `rz` and `rx`.
    A single brick represents the sequence `Rz(a) Rx(b) Rz(c)` plus the final
    teleportation measurement. Cells already in that form are read off
    directly. Any other sequence -- Qiskit can emit the equivalent `Rx Rz Rx`
    Euler form -- is multiplied out and re-expressed as one exact Z-X-Z triple,
    which is always possible because a product of `rz`/`rx` rotations is a
    single SU(2) element up to global phase. Angles are negated because Graphix
    uses the opposite measurement-angle convention from the circuit convention
    used here.
    """

    if tuple(instr.name for instr in cell) not in _DIRECT_EULER_FORMS:
        theta, phi, lam = _ZXZ_DECOMPOSER.angles(_cell_unitary(cell))
        # U = Rz(phi) Rx(theta) Rz(lam): lam acts first, phi last.
        return [-lam / np.pi, -theta / np.pi, -phi / np.pi, 0.0]

    rotations = [0.0, 0.0, 0.0, 0.0]
    index = 0
    if cell[0].name == "rx":  # case of rxrz
        index += 1
    for instr in cell:
        if instr.name == "rz":
            if index != 0 and index != 2:
                raise AssertionError(
                    f"Index wrong: {index}, instruction: {instr}\n "
                    f"Probably shifted cx into a rotation brick"
                )
            rotations[index] = -float(instr.params[0]) / np.pi
        elif instr.name == "rx":
            rotations[1] = -float(instr.params[0]) / np.pi
        index = index + 1

    return rotations


def inject_angles(angles, brick_type, r, c, cell, node_colours):
    """Write the measurement angles and colour of one brick at row `r`, column `c`.

    `angles` and `node_colours` map graph nodes `(row, graph_column)` to a
    value; CX bricks fill two rows, the other brick types one.
    """
    if brick_type == "id":
        rows = ((0.0, 0.0, 0.0, 0.0),)
    elif brick_type == "euler_rot":
        rows = (tuple(parse_euler_angles(cell)),)
    elif brick_type in _CX_BRICK_ANGLES:
        rows = _CX_BRICK_ANGLES[brick_type]
    else:
        raise AssertionError(f"Unknown brick type: {brick_type} instruction type: {cell}")

    colour = _BRICK_COLOURS[brick_type]
    for row_offset, row_angles in enumerate(rows):
        for k, angle in enumerate(row_angles):
            node = (r + row_offset, 4 * c + k)
            angles[node] = angle
            node_colours[node] = colour


def _cell_cx_endpoint(cell):
    endpoints = [instr for instr in cell if is_cx_endpoint(instr.name)]
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
                if is_cx_endpoint(instr.name):
                    groups.setdefault(cx_group_id(instr.name), []).append((r, cx_role(instr.name)))
        groups_by_col.append(groups)
    return groups_by_col


def to_pattern(instruction_matrix, structure_graph):
    """Inject measurement angles and create a Graphix pattern.

    CX bricks are two-row gadgets. We resolve each CX group explicitly and
    inject it only from its top row so the angle table is independent of whether
    the control or target endpoint appears first in row-major iteration.

    The pattern has no input nodes: every graph qubit starts in |+>, as in
    universal blind quantum computation, so the pattern computes U|+...+>.
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

            gid = cx_group_id(cx_endpoint.name)
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

    inputs = []  # No input nodes: every qubit is prepared in |+>, as in UBQC.
    outputs = [(i, (num_cols * 4)) for i in range(num_qubits)]

    brickwork_pattern = generate_from_graph(structure_graph, angles, inputs, outputs)

    return brickwork_pattern, node_colours
