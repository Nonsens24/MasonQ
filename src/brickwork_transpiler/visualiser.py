"""Plotting of brickwork graphs and text dumps of instruction matrices."""

import logging
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import networkx as nx

logger = logging.getLogger(__name__)


def _safe_savefig(fig, path, **kwargs):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, **kwargs)


def _safe_show(fig, *, show=True, close=True):
    """Display a figure without letting IDE display-proxy failures crash code."""
    if show:
        try:
            plt.show()
        except Exception as exc:
            logger.warning(
                "Matplotlib display failed; the figure was not shown interactively. "
                "This often happens when PyCharm's plot proxy rejects a large figure. "
                "Use show=False/save_plot=True for large plots. Error: %s",
                exc,
            )
    if close:
        plt.close(fig)


def _open_graph(pattern):
    """The pattern as a Graphix open graph (`to_opengraph` from Graphix 0.4, `extract_opengraph` before)."""
    convert = getattr(pattern, "to_opengraph", None) or pattern.extract_opengraph
    return convert()


def _pattern_graph(pattern):
    """Return `(nodes, edges)` of the pattern's resource graph."""
    graph = _open_graph(pattern).graph
    return list(graph.nodes), list(graph.edges)


def _pattern_angles(pattern):
    """Return the measurement angle of every measured node, in units of pi."""
    try:
        measurements = _open_graph(pattern).measurements
    except Exception as exc:  # e.g. a pattern Graphix cannot express as an open graph
        logger.debug("Could not extract measurement angles: %s", exc)
        return {}
    return {node: float(measurement.to_bloch().angle) for node, measurement in measurements.items()}


def plot_graph(G, cell_size=0.5, margin=0.5, show: bool = True, close: bool = True):
    """
    Draw G so that each adjacent node pair is spaced by `cell_size` inches.

    Parameters
    ----------
    G : networkx.Graph
        Graph whose nodes are (row, col) tuples.
    cell_size : float, optional
        Size in inches of each grid cell (distance between adjacent nodes).
    margin : float, optional
        Extra padding around the grid, in grid‐cells.
    """
    # 1) figure out grid dimensions
    rows = [r for (r, _) in G.nodes()]
    cols = [c for (_, c) in G.nodes()]
    n_rows = max(rows) + 1
    n_cols = max(cols) + 1

    # 2) build pos mapping (x = col, y = row)
    pos = {(r, c): (c, r) for (r, c) in G.nodes()}

    # 3) compute figure size so each cell is cell_size inches
    fig_w = cell_size * (n_cols + 2 * margin)
    fig_h = cell_size * (n_rows + 2 * margin)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    # 4) draw with constant node spacing
    nx.draw(
        G,
        pos=pos,
        with_labels=True,
        node_color='lightblue',
        node_size=600,
        font_size=8,
        ax=ax
    )

    # 5) square aspect & invert so row=0 is at top
    ax.set_aspect('equal')
    ax.invert_yaxis()

    # 6) pad the axes so nodes aren’t flush to the border
    ax.set_xlim(-margin, n_cols - 1 + margin)
    ax.set_ylim(n_rows - 1 + margin, -margin)

    plt.tight_layout()
    _safe_show(fig, show=show, close=close)


def print_matrix(matrix):
    """
    Print the qubit-major matrix as a table:
      rows = qubits, columns = grouped stages
    """
    if not matrix:
        print("No data to display.")
        return
    num_qubits = len(matrix)
    num_cols   = len(matrix[0])

    # build header
    header = ["Qubit \\ Gate Group"] + [f"Group {c}" for c in range(num_cols)]

    # build rows
    rows = []
    for q in range(num_qubits):
        row = [f"Qubit {q}"]
        for c in range(num_cols):
            ops = matrix[q][c]
            # convert any Gate obj → its name
            row.append(", ".join(op.name if hasattr(op, "name") else str(op)
                                 for op in ops)
                       if ops else "-")
        rows.append(row)

    # compute column widths
    cols = [header] + rows
    col_widths = [max(len(r[i]) for r in cols) for i in range(len(header))]

    # print header
    sep_line = "|-" + "-|-".join("-" * w for w in col_widths) + "-|"
    header_line = "| " + " | ".join(header[i].ljust(col_widths[i])
                                   for i in range(len(header))) + " |"
    print(header_line)
    print(sep_line)

    # print each row
    for row in rows:
        print("| " + " | ".join(row[i].ljust(col_widths[i])
                                for i in range(len(row))) + " |")


def plot_brickwork_graph_from_pattern(
        bw_pattern,
        show_angles: bool = True,
        node_size: float = 1500,
        node_color: str = 'skyblue',
        edge_color: str = 'gray',
        font_size: int = 9,
        figsize: tuple = None,
        cell_size: float = 0.7,
        node_spacing: float = 1.8,
        margin: float = 1.2,
        title: str = "Brickwork Graph",
        use_node_colours: bool = False,
        node_colours: dict = None,
        save_plot: bool = False,
        save_path: str | None = None,
        show: bool = True,
        close: bool = True,
    ):
    """Draw the brickwork graph of `bw_pattern` with its measurement angles.

    With `save_path` the figure is written there; otherwise `save_plot=True`
    writes `images/graphs/<title>.pdf` and `.png` under the current directory.
    """
    if node_colours is None:
        node_colours = {}

    logger.info("Visualising from pattern structure...")

    nodes, edges = _pattern_graph(bw_pattern)
    G = nx.Graph()
    G.add_nodes_from(nodes)
    G.add_edges_from(edges)

    angles = _pattern_angles(bw_pattern) if show_angles else {}

    rows = [r for (r, _) in nodes]
    cols = [c for (_, c) in nodes]
    n_rows, n_cols = max(rows) + 1, max(cols) + 1

    legend_height = 0.8
    if figsize is None:
        spacing = cell_size * node_spacing
        total_width = spacing * (n_cols + 2 * margin)
        total_height = spacing * (n_rows + 2 * margin) + legend_height
        figsize = (total_width, total_height)

    fig = plt.figure(figsize=figsize, dpi=200)
    gs = fig.add_gridspec(
        2, 1,
        height_ratios=[n_rows * cell_size * node_spacing, legend_height],
        hspace=0.1
    )
    ax = fig.add_subplot(gs[0, 0])
    legend_ax = fig.add_subplot(gs[1, 0])
    legend_ax.axis('off')

    pos = {
        (r, c): (c * node_spacing, r * node_spacing)
        for (r, c) in nodes
    }

    nx.draw_networkx_edges(G, pos, ax=ax, edge_color=edge_color, width=3.0)

    colours = [node_colours.get(node, node_color) for node in G.nodes()] if use_node_colours else node_color
    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_size=node_size,
        node_color=colours,
        edgecolors='black', linewidths=2.0
    )

    if show_angles:
        labels = {
            node: f"({r},{c})\n{angles[node]:.2f}π" if node in angles else f"({r},{c})"
            for node in nodes
            for (r, c) in [node]
        }
    else:
        labels = {}

    nx.draw_networkx_labels(
        G, pos, labels=labels,
        font_size=font_size,
        font_family='DejaVu Sans',
        ax=ax,
        font_weight='medium'
    )

    ax.set_aspect('equal')
    ax.invert_yaxis()
    ax.set_xlim(-margin * node_spacing, (n_cols - 1 + margin) * node_spacing)
    ax.set_ylim((n_rows - 1 + margin) * node_spacing, -margin * node_spacing)
    ax.set_title(title, fontsize=16, fontweight='bold')
    ax.axis('off')

    if use_node_colours:
        handles = [
            mpatches.Patch(color='lightcoral', label='CX gate - ⊕ top'),
            mpatches.Patch(color='lightsalmon', label='CX gate - ⊕ bot'),
            mpatches.Patch(color='lightblue', label='Identity'),
            mpatches.Patch(color='lightgreen', label='Euler rotation'),
            mpatches.Patch(color='skyblue', label='Output qubits'),
        ]
        legend_ax.legend(
            handles=handles,
            title="Gate types",
            loc='center',
            ncol=3,
            frameon=False,
            fontsize=11,
            title_fontsize=12
        )

    if save_path is not None:
        _safe_savefig(fig, save_path, bbox_inches="tight")
    elif save_plot:
        _safe_savefig(fig, f"images/graphs/{title}.pdf", format="pdf", bbox_inches="tight")
        _safe_savefig(fig, f"images/graphs/{title}.png", format="png", dpi=300, bbox_inches="tight")

    _safe_show(fig, show=show, close=close)
