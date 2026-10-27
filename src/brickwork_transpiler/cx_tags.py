"""Tagged CX endpoint names used throughout the brick matrices.

`decomposer.instructions_to_matrix_dag` gives every CX gate an integer group
id and renames its two endpoints `cx{id}c` (control row) and `cx{id}t`
(target row), so the pair can be tracked after columns move. These helpers
are the only place that format is produced or parsed.
"""

from __future__ import annotations


def tag_cx(group_id: int, role: str) -> str:
    """Return the endpoint name for `group_id` with role `"c"` or `"t"`."""
    return f"cx{group_id}{role}"


def is_cx_endpoint(name: str) -> bool:
    """True iff `name` is a tagged CX endpoint.

    A literal `cx` from raw Qiskit (no id, no role suffix) does not match;
    the alignment and placement passes never expect to see one.
    """
    return (
        len(name) > 3
        and name.startswith("cx")
        and name[-1] in ("c", "t")
        and name[2:-1].isdigit()
    )


def cx_group_id(name: str) -> str:
    """Return the group id of a tagged endpoint name."""
    return name[2:-1]


def cx_role(name: str) -> str:
    """Return `"c"` or `"t"` for a tagged endpoint name."""
    return name[-1]
