"""Sparse representation for aligned brick instruction matrices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator


@dataclass(frozen=True)
class SparseInstructionMatrix:
    """Sparse aligned brick matrix.

    The dense matrix is indexed as `matrix[row][column] -> list[instructions]`.
    This sparse form stores only cells whose instruction list is non-empty while
    retaining the original row/column dimensions.
    """

    rows: int
    columns: int
    cells: dict[tuple[int, int], tuple[Any, ...]]

    @classmethod
    def from_dense(cls, matrix: list[list[list[Any]]]) -> "SparseInstructionMatrix":
        rows = len(matrix)
        columns = len(matrix[0]) if matrix else 0
        cells: dict[tuple[int, int], tuple[Any, ...]] = {}
        for row_index, row in enumerate(matrix):
            if len(row) != columns:
                raise ValueError("Dense instruction matrix must be rectangular.")
            for column_index, cell in enumerate(row):
                if cell:
                    cells[(row_index, column_index)] = tuple(cell)
        return cls(rows=rows, columns=columns, cells=cells)

    @property
    def shape(self) -> tuple[int, int]:
        return self.rows, self.columns

    @property
    def non_empty_cells(self) -> int:
        return len(self.cells)

    @property
    def occupancy(self) -> float:
        total = self.rows * self.columns
        return 0.0 if total == 0 else self.non_empty_cells / total

    def cell(self, row: int, column: int) -> tuple[Any, ...]:
        if row < 0 or row >= self.rows:
            raise IndexError(f"row {row} outside sparse matrix with {self.rows} rows")
        if column < 0 or column >= self.columns:
            raise IndexError(
                f"column {column} outside sparse matrix with {self.columns} columns"
            )
        return self.cells.get((row, column), ())

    def iter_non_empty(self) -> Iterator[tuple[int, int, tuple[Any, ...]]]:
        for row, column in sorted(self.cells):
            yield row, column, self.cells[(row, column)]

    def to_dense(self) -> list[list[list[Any]]]:
        matrix = [[[] for _ in range(self.columns)] for _ in range(self.rows)]
        for (row, column), cell in self.cells.items():
            matrix[row][column] = list(cell)
        return matrix
