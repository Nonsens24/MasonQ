"""Validation helpers for internal brickwork representations."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .cx_tags import cx_group_id, cx_role, is_cx_endpoint
from .exceptions import BrickworkValidationError


def _instruction_name(instr: Any) -> str:
    name = getattr(instr, "name", None)
    if not isinstance(name, str):
        raise BrickworkValidationError(f"Instruction without a string name: {instr!r}")
    return name


def validate_instruction_matrix(matrix: list[list[list[Any]]]) -> None:
    """Validate the scheduled brick matrix before graph conversion."""

    if not isinstance(matrix, list):
        raise BrickworkValidationError("Instruction matrix must be a list of rows.")
    if not matrix:
        return

    width = len(matrix[0])
    if width == 0:
        raise BrickworkValidationError("Instruction matrix rows must not be empty.")

    cx_locations: dict[str, list[tuple[int, int, str]]] = defaultdict(list)

    for row_idx, row in enumerate(matrix):
        if len(row) != width:
            raise BrickworkValidationError(
                f"Instruction matrix must be rectangular; row 0 has width {width}, "
                f"row {row_idx} has width {len(row)}."
            )
        for col_idx, cell in enumerate(row):
            if not isinstance(cell, list):
                raise BrickworkValidationError(
                    f"Matrix cell ({row_idx}, {col_idx}) must be a list."
                )
            names = [_instruction_name(instr) for instr in cell]
            has_cx = any(is_cx_endpoint(name) for name in names)
            if has_cx and len(cell) > 1:
                raise BrickworkValidationError(
                    f"CX cell ({row_idx}, {col_idx}) must not contain extra operations: {cell!r}."
                )
            for name in names:
                if name in {"rz", "rx", "id"}:
                    continue
                if is_cx_endpoint(name):
                    cx_locations[cx_group_id(name)].append((row_idx, col_idx, cx_role(name)))
                    continue
                raise BrickworkValidationError(
                    f"Unsupported instruction {name!r} at ({row_idx}, {col_idx})."
                )

    for gid, locations in cx_locations.items():
        if len(locations) != 2:
            raise BrickworkValidationError(
                f"CX group {gid!r} must have exactly two endpoints, found {locations}."
            )
        (r0, c0, role0), (r1, c1, role1) = locations
        if c0 != c1:
            raise BrickworkValidationError(
                f"CX group {gid!r} endpoints must share a column, found {locations}."
            )
        if abs(r0 - r1) != 1:
            raise BrickworkValidationError(
                f"CX group {gid!r} endpoints must be on adjacent rows, found {locations}."
            )
        if {role0, role1} != {"c", "t"}:
            raise BrickworkValidationError(
                f"CX group {gid!r} must have one control and one target, found {locations}."
            )


def validate_brickwork_graph_data(graph_data: dict[str, Any], *, rows: int, brick_cols: int) -> None:
    expected_width = brick_cols * 4 + 1
    expected_nodes = rows * expected_width

    if graph_data.get("height") != rows:
        raise BrickworkValidationError(
            f"Graph height {graph_data.get('height')} does not match matrix rows {rows}."
        )
    if graph_data.get("width") != expected_width:
        raise BrickworkValidationError(
            f"Graph width {graph_data.get('width')} does not match expected {expected_width}."
        )

    nodes = graph_data.get("nodes")
    edges = graph_data.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise BrickworkValidationError("Graph data must contain list-valued nodes and edges.")
    if len(nodes) != expected_nodes:
        raise BrickworkValidationError(
            f"Graph node count {len(nodes)} does not match expected {expected_nodes}."
        )
    node_set = set(nodes)
    missing = [
        endpoint
        for edge in edges
        for endpoint in edge
        if endpoint not in node_set
    ]
    if missing:
        raise BrickworkValidationError(f"Graph edges reference unknown nodes: {missing[:5]}.")


def validate_pattern_outputs(pattern: Any, *, rows: int, brick_cols: int) -> None:
    expected_outputs = [(row, brick_cols * 4) for row in range(rows)]
    outputs = list(getattr(pattern, "output_nodes", []))
    if len(outputs) != len(expected_outputs) or set(outputs) != set(expected_outputs):
        raise BrickworkValidationError(
            f"Pattern outputs {outputs!r} do not match expected {expected_outputs!r}."
        )
