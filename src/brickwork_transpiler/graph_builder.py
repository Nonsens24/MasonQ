"""Build the structural NetworkX graph for a brickwork pattern.

The graph carries no measurement angles itself — angles are injected later
by `pattern_converter.to_pattern`. Two helpers live here:

  - `create_tuple_node_graph` builds a `rows x cols` grid with horizontal
    teleportation edges only. Used by the hand-built bricks in `bricks.py`.
  - `generate_brickwork_graph_from_instruction_matrix` builds the full
    rectangular brickwork graph, including the alternating brick-pair
    vertical edges, from an aligned brick instruction matrix.
"""

import networkx as nx


def create_tuple_node_graph(rows: int, cols: int) -> nx.Graph:
    """Return a `rows x cols` grid graph with horizontal-only edges.

    Nodes are `(row, col)` tuples. Each row carries `cols - 1` horizontal
    edges (the teleportation chain). No vertical edges are added.
    """
    g = nx.Graph()
    g.add_nodes_from((r, c) for r in range(rows) for c in range(cols))
    g.add_edges_from(
        ((r, c), (r, c + 1)) for r in range(rows) for c in range(cols - 1)
    )
    return g


def generate_brickwork_graph_from_instruction_matrix(matrix):
    """
    Build the rectangular brickwork graph for an aligned instruction matrix.

    Each instruction-matrix column expands to four measured graph columns. One
    extra unmeasured output column is appended at the end, giving
    `4 * n_instruction_cols + 1` graph columns.

    Returns a dict with:
      - 'nodes': list of (row, col) pairs
      - 'edges': list of ((row1, col1), (row2, col2))
      - 'width': number of graph columns
      - 'height': number of graph rows
    """

    n_rows = len(matrix)
    n_cols = len(matrix[0]) if matrix else 0
    n_cols = (n_cols * 4) + 1

    nodes = [(row, col) for row in range(n_rows) for col in range(n_cols)]

    edges = []

    # 1) Horizontal chains implement teleportation wires.
    for row in range(n_rows):
        for col in range(n_cols - 1):
            edges.append(((row, col), (row, col + 1)))

    # 2) Vertical brickwork links alternate by row parity every four graph
    # columns. `(col + 1) % 8` preserves the original paper's one-indexed
    # brick pattern while using zero-indexed Python coordinates.
    for col in range(n_cols):
        if (col + 1) % 8 == 3:
            for row in range(0, n_rows - 1, 2):
                edges.append(((row, col), (row + 1, col)))
                if col + 2 < n_cols:
                    edges.append(((row, col + 2), (row + 1, col + 2)))
        elif (col + 1) % 8 == 7:
            for row in range(1, n_rows - 1, 2):
                edges.append(((row, col), (row + 1, col)))
                if col + 2 < n_cols:
                    edges.append(((row, col + 2), (row + 1, col + 2)))

    return {"nodes": nodes, "edges": edges, "width": n_cols, "height": n_rows}


def to_networkx_graph(brickwork):
    G = nx.Graph()
    G.add_nodes_from(brickwork["nodes"])
    G.add_edges_from(brickwork["edges"])

    return G
