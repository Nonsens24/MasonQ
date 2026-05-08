from fractions import Fraction
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import matplotlib.image as mpimg
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import matplotlib.patches as mpatches

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


def _pattern_graph(pattern):
    """Return `(nodes, edges)` for both legacy and current Graphix Pattern APIs."""
    if hasattr(pattern, "get_graph"):
        return pattern.get_graph()
    graph = pattern.extract_graph()
    return list(graph.nodes), list(graph.edges)


def _pattern_angles(pattern):
    """Return measurement angles in units of pi for legacy/current Graphix APIs."""
    if hasattr(pattern, "get_angles"):
        return pattern.get_angles()
    try:
        measurements = pattern.extract_opengraph().measurements
    except Exception:
        return {}
    return {
        node: float(measurement.to_bloch().angle)
        for node, measurement in measurements.items()
    }


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
    if node_colours is None:
        node_colours = {}

    print("Visualising from pattern structure...")

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
        labels = {node: f"({r},{c})\n{angles[node]:.2f}π" if show_angles and node in angles else f"({r},{c})" for node, (r, c) in zip(nodes, nodes)}
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



def plot_brickwork_graph_encrypted(
        bw_pattern,
        node_image_path: str = 'images/lock_delta_nobg_2.png',
        use_locks: bool = True,
        edge_color: str = 'gray',
        font_size: int = 9,
        figsize: tuple = None,
        cell_size: float = 0.7,
        node_spacing: float = 1.8,
        margin: float = 1.2,
        title: str = "UBQC structure",
        show_angles: bool = False,
        save_plot: bool = True,
        show: bool = True,
        close: bool = True,
    ):
    # Get the graph
    nodes, edges = _pattern_graph(bw_pattern)
    G = nx.Graph()
    G.add_nodes_from(nodes)
    G.add_edges_from(edges)

    # Grid size
    rows = [r for (r, _) in nodes]
    cols = [c for (_, c) in nodes]
    n_rows, n_cols = max(rows) + 1, max(cols) + 1

    # Figure size
    legend_height = 0.8
    if figsize is None:
        spacing = cell_size * node_spacing
        total_width = spacing * (n_cols + 2 * margin)
        total_height = spacing * (n_rows + 2 * margin) + legend_height
        figsize = (total_width, total_height)

    # Create figure
    fig = plt.figure(figsize=figsize, dpi=200)
    gs = fig.add_gridspec(
        2, 1,
        height_ratios=[n_rows * cell_size * node_spacing, legend_height],
        hspace=0.1
    )
    ax = fig.add_subplot(gs[0, 0])
    legend_ax = fig.add_subplot(gs[1, 0])
    legend_ax.axis('off')

    # Compute positions
    pos = {
        (r, c): (c * node_spacing, r * node_spacing)
        for (r, c) in nodes
    }

    # Draw edges
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color=edge_color, width=3.0)

    plt.rcParams['mathtext.fontset'] = 'cm'  # Use Computer Modern
    plt.rcParams['mathtext.rm'] = 'serif'  # Use serif font for normal text

    if use_locks:
        # Load the image
        img = mpimg.imread(node_image_path)
        imagebox = OffsetImage(img, zoom=0.09)  # adjust zoom as needed

        # Define vertical offset
        y_offset = (-0.1 * node_spacing)  # adjust if needed

        # Add image with vertical shift
        for node, (x, y) in pos.items():
            ab = AnnotationBbox(imagebox, (x, y + y_offset), frameon=False)
            ax.add_artist(ab)

    else:

        pos = {
            (r, c): (c * node_spacing, r * node_spacing)
            for (r, c) in nodes
        }

        nx.draw_networkx_edges(G, pos, ax=ax, edge_color=edge_color, width=4.0)


        nx.draw_networkx_nodes(
            G, pos, ax=ax,
            node_size=1500,
            node_color='#e9e9f9',
            edgecolors='black', linewidths=2.0
        )

        # labels = {node: rf"$\delta$" for node, (r, c) in zip(nodes, nodes)}
        # labels = {}
        if show_angles:
            angles = bw_pattern.get_angles() if show_angles else {}

            labels = {node: f"({r},{c})\n{angles[node]:.2f}π" if show_angles and node in angles else f"({r},{c})" for
                      node, (r, c) in zip(nodes, nodes)}
        else:
            labels = {node: rf"$\theta_{{{node[0]},{node[1]}}}$" for node in nodes}

        nx.draw_networkx_labels(
            G, pos, labels=labels,
            font_size=font_size,
            font_family='serif',
            ax=ax,
            font_weight='medium'
        )


    # Final plot settings
    ax.set_aspect('equal')
    ax.invert_yaxis()
    ax.set_xlim(-margin * node_spacing, (n_cols - 1 + margin) * node_spacing)
    ax.set_ylim((n_rows - 1 + margin) * node_spacing, -margin * node_spacing)
    ax.set_title(title, fontsize=16, fontweight='bold')
    ax.axis('off')

    # Add LaTeX equation to the legend
    equation = (r"$\{|+_{\delta_{x,y}}\rangle, |-_{\delta_{x,y}}\rangle\},$" r"$\quad$" 
                r"$\delta_{x,y} = \phi'_{x,y} + \theta_{x,y} + \pi r_{x,y}$")
    legend_ax.text(
        0.5, 1, equation,
        fontsize=25,  # <-- constant size for readability
        ha='center', va='center',
    bbox=dict(facecolor='white', edgecolor='black', boxstyle='round,pad=0.5')
    )

    if save_plot:
        _safe_savefig(fig, f"images/graphs/{title}_enc.pdf", format="pdf", bbox_inches="tight")
        _safe_savefig(fig, f"images/graphs/{title}_enc.png", format="png", dpi=300, bbox_inches="tight")

    _safe_show(fig, show=show, close=close)

# plot_graphix_pattern_scalar_index.py

# plot_graphix_pattern_scalar_index.py

def plot_graphix_noise_graph(
        pattern,
        show_angles: bool = True,
        node_size: float = 1500,
        edge_color: str = 'gray',
        font_size: int = 9,
        figsize: tuple = None,
        cell_size: float = 0.7,
        node_spacing: float = 1.8,
        margin: float = 1.2,
        title: str = "Shaded Noise Graph",
        cmap_name: str = 'viridis',  # dark-blue to dark-red continuous spectrum
        vmin: float = None,
        vmax: float = None,
        show_colorbar: bool = True,
        save: bool = False,
        show: bool = True,
        close: bool = True,
):
    """
    Plot a Graphix Pattern object, using measurement angles to color-code nodes as a continuous heatmap.

    The colormap 'jet' spans dark blue → light blue → yellow → light red → dark red.
    The colorbar shows only start/end ticks labeled in π units for clarity.
    """
    import networkx as nx
    import matplotlib.pyplot as plt
    from matplotlib import cm
    from matplotlib.colors import Normalize

    # Build graph
    nodes, edges = _pattern_graph(pattern)
    G = nx.Graph()
    G.add_nodes_from(nodes)
    G.add_edges_from(edges)

    # Measurement angles (multiples of π)
    angles = _pattern_angles(pattern)

    # Prepare heatmap values and normalization
    values = [angles.get(n, 0.0) for n in G.nodes()]
    vmin_val = min(values) if vmin is None else vmin
    vmax_val = max(values) if vmax is None else vmax
    norm = Normalize(vmin=vmin_val, vmax=vmax_val)
    cmap = cm.get_cmap(cmap_name)
    node_colors = [cmap(norm(val)) for val in values]

    # Layout: compute layers
    depth, layers = pattern.get_layers()
    node_layer = {n: layer for layer, nset in layers.items() for n in nset}
    for o in getattr(pattern, 'output_nodes', []):
        node_layer[o] = depth + 1
    max_width = max(
        len([n for n, l in node_layer.items() if l == layer])
        for layer in range(depth + 2)
    )

    # Setup figure and gridspec
    legend_height = 0.6 if show_colorbar else 0.0
    if figsize is None:
        total_width = cell_size * node_spacing * (depth + 1 + 2 * margin)
        total_height = cell_size * node_spacing * (max_width - 1 + 2 * margin) + legend_height
        figsize = (total_width, total_height)
    fig = plt.figure(figsize=figsize)
    gs = fig.add_gridspec(
        2, 1,
        height_ratios=[
            cell_size * node_spacing * (max_width - 1 + 2 * margin),
            legend_height
        ],
        hspace=0.05
    )
    ax = fig.add_subplot(gs[0, 0])
    cax = fig.add_subplot(gs[1, 0]) if show_colorbar else None

    unique_layers = sorted(set(node_layer.values()))
    layer_to_idx = {layer: i for i, layer in enumerate(unique_layers)}

    pos = {}
    for layer in unique_layers:
        nodes_in_layer = sorted(n for n, l in node_layer.items() if l == layer)
        for idx, n in enumerate(nodes_in_layer):
            x = layer_to_idx[layer] * node_spacing * cell_size
            y = idx * node_spacing * cell_size
            pos[n] = (x, y)

    # Draw edges and nodes
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color=edge_color)
    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_size=node_size,
        node_color=node_colors
    )

    # Draw labels
    labels = {}
    for n in G.nodes():
        if show_angles and n in angles:
            labels[n] = f"{n}\n{angles[n]:.2f}π"
        else:
            labels[n] = str(n)
    # nx.draw_networkx_labels(G, pos, labels, font_size=font_size, ax=ax)

    from matplotlib.colors import rgb_to_hsv

    # Assign dynamic font colors based on background brightness
    font_colors = []
    for color in node_colors:
        r, g, b, _ = color
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        font_colors.append('white' if luminance < 0.5 else 'black')

    # Draw labels with adjusted font color
    for idx, (n, label) in enumerate(labels.items()):
        ax.text(pos[n][0], pos[n][1], label,
                fontsize=font_size,
                ha='center', va='center',
                color=font_colors[idx])

    # Axis tweaks
    ax.set_aspect('equal')
    ax.invert_yaxis()
    ax.set_xlim(-margin * node_spacing * cell_size,
                (depth + margin) * node_spacing * cell_size)
    ax.set_ylim(
        (max_width - 1 + margin) * node_spacing * cell_size,
        -margin * node_spacing * cell_size
    )
    ax.set_title(title)
    ax.axis('off')

    # Colorbar: continuous with start/end ticks
    if show_colorbar and cax:
        sm = cm.ScalarMappable(norm=norm, cmap=cmap)
        sm.set_array(values)
        cbar = plt.colorbar(
            sm,
            cax=cax,
            orientation='horizontal',

            # alternatively:
        )
        cbar.set_label('Measurement angle noise', labelpad=8)
        # Show only start and end
        cbar.set_ticks([vmin_val, vmax_val])
        cbar.set_ticklabels([f"{vmin_val:.2f}π", f"{vmax_val:.2f}π"])
        # Ensure axis line is visible

        # --- shrink the colour‑bar’s width to a % and keep it centred ----
        box = cax.get_position()  # current [x0, y0, width, height] in figure‑coords
        new_width = box.width * 0.80  # % of the present length
        dx = (box.width - new_width) / 2  # equal margin left & right
        cax.set_position([box.x0 + dx, box.y0, new_width, box.height])

        cbar.ax.xaxis.set_ticks_position('bottom')
        cbar.ax.xaxis.set_label_position('bottom')

    # Save if requested
    if save:
        _safe_savefig(fig, "noise_graph.pdf", bbox_inches='tight')
        _safe_savefig(fig, "noise_graph.png", dpi=300, bbox_inches='tight')

    _safe_show(fig, show=show, close=close)


def format_angle(angle, denom=4):
    """Return a string representing angle as a multiple of π/denom."""
    frac = Fraction(angle / np.pi).limit_denominator(denom)
    n = frac.numerator
    d = frac.denominator

    if n == 0:
        return "0"
    elif abs(n) == 1 and d == 1:
        return "π" if n > 0 else "-π"
    elif d == 1:
        return f"{n}π"
    elif abs(n) == 1:
        return f"π/{d}" if n > 0 else f"-π/{d}"
    else:
        return f"{n}π/{d}"
