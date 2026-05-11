# Sparse Instruction Matrix

`SparseInstructionMatrix` is a space-efficient view of MasonQ's aligned
brick instruction matrix. It is useful for resource sweeps, diagnostics, and
large circuits where most aligned matrix cells are empty.

The dense matrix has this shape:

```python
matrix[row][column] -> list[instructions]
```

The sparse matrix stores only non-empty cells:

```python
cells[(row, column)] -> tuple(instructions)
```

It still records the original number of rows and columns, so it can be compared
with resource estimates and converted back to the legacy dense form.

## Getting One

Use `return_stage="sparse_matrix"`:

```python
from brickwork_transpiler import transpile

sparse = transpile(qc, return_stage="sparse_matrix")
```

This stops after decomposition, brick-matrix construction, and alignment. It
does not build a Graphix pattern and does not simulate.

## API

```python
sparse.rows
sparse.columns
sparse.shape
sparse.non_empty_cells
sparse.occupancy
```

`shape` is `(rows, columns)`. `occupancy` is the fraction of non-empty cells:

```text
non_empty_cells / (rows * columns)
```

Read one cell:

```python
instructions = sparse.cell(row, column)
```

`cell(...)` returns a tuple of instructions. Empty cells return `()`.
Out-of-range indices raise `IndexError`.

Iterate over real scheduled work:

```python
for row, column, instructions in sparse.iter_non_empty():
    names = [instruction.name for instruction in instructions]
    print(row, column, names)
```

Convert back to the dense legacy layout:

```python
dense = sparse.to_dense()
```

## Dense Versus Sparse

Use `return_stage="matrix"` when you need the exact dense structure used by
older debugging scripts:

```python
dense = transpile(qc, return_stage="matrix")
```

Use `return_stage="sparse_matrix"` when you want to inspect or post-process
only non-empty cells:

```python
sparse = transpile(qc, return_stage="sparse_matrix")
```

Both describe the same aligned instruction matrix. The sparse object is not a
different scheduling algorithm; it is a storage representation of the current
aligned matrix.

## Resource Sweeps

For large benchmark loops, combine sparse output with resource estimates:

```python
resources = transpile(qc, return_stage="resources")
sparse = transpile(qc, return_stage="sparse_matrix")

print(resources.brick_columns)
print(resources.graph_depth)
print(sparse.shape)
print(sparse.occupancy)
```

`resources.graph_depth` is MasonQ's primary scheduling objective:

```text
graph_depth = 4 * brick_columns + 1
```

The sparse matrix helps inspect the scheduled operations behind that estimate
without materializing a large empty matrix in user code.

## Notes

- Sparse output is read-only by convention; the dataclass is frozen.
- Instruction tuples are preserved as tuples so empty and non-empty cells have
  stable value semantics.
- Pattern generation currently still uses the dense aligned matrix internally.
- `sparse.to_dense()` is intended for debugging and compatibility, not for
  large-memory workflows.
