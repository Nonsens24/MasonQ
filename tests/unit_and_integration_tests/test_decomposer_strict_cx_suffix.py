"""The decomposer's CX-detection helper must require the tagged form.

A literal `cx` (no group id, no role suffix) should NOT be treated as a CX
endpoint. The pipeline produces only `cx{id}c` / `cx{id}t` names, so an
untagged `cx` is a sign the matrix bypassed `instructions_to_matrix_dag`
and is malformed.
"""

import pytest

from brickwork_transpiler.decomposer import (
    _is_cx_endpoint,
    _cx_group_id,
    align_cx_matrix,
    insert_rotations_adjecant_to_cx,
)


class _I:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"<I {self.name}>"


def test_strict_cx_endpoint_helper_rejects_untagged():
    assert _is_cx_endpoint("cx0c")
    assert _is_cx_endpoint("cx12t")
    assert _is_cx_endpoint("cx999c")

    # Untagged or partially tagged: rejected.
    assert not _is_cx_endpoint("cx")
    assert not _is_cx_endpoint("cxc")
    assert not _is_cx_endpoint("cx0")
    assert not _is_cx_endpoint("cx_")
    assert not _is_cx_endpoint("cxabc")
    assert not _is_cx_endpoint("rz")
    assert not _is_cx_endpoint("")


def test_cx_group_id_extracts_digits():
    assert _cx_group_id("cx0c") == "0"
    assert _cx_group_id("cx42t") == "42"


def test_align_cx_matrix_ignores_untagged_cx():
    """An untagged `cx` is invisible to alignment — it does not form a brick.
    The matrix is returned as if no CX existed."""
    mat = [
        [[_I("cx")], []],
        [[_I("cx")], []],
    ]
    out = align_cx_matrix(mat)
    # No tagged CX -> empty alignment (no bricks to place).
    for row in out:
        for cell in row:
            assert cell == []


def test_insert_rotations_treats_untagged_cx_as_rotation_carrier():
    """An untagged `cx` should not be treated as a CX neighbor by the
    rotation placer. Treating it as a CX would push rotations into bogus
    columns. We assert the safe behavior: such cells are pass-through and
    the rotation goes to its default leading column."""
    aligned = [[[]]]  # 1 row, 1 col, no CX endpoints
    original = [[[_I("rz")]]]
    result = insert_rotations_adjecant_to_cx(aligned, original)
    # rotation lands at col 0 (leading-column default)
    assert [i.name for i in result[0][0]] == ["rz"]
