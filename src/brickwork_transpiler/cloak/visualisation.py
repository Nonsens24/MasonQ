"""Visualise Qiskit circuits with :class:`Sensitive` blocks shown distinctly.

The native Qiskit drawer already renders a :class:`Sensitive` instruction
as a labelled box spanning its qubits.  This module adds two small
quality-of-life helpers on top:

  - :func:`draw_cloaked` — clones the circuit, prefixes every cloaked
    block's label with a recognisable marker (a lock glyph by default),
    and applies a distinct fill colour when the matplotlib backend is
    requested.  Returns whatever the underlying ``QuantumCircuit.draw``
    would return, so it slots straight into notebooks and scripts.
  - :func:`summarize_cloaked` — emits a short textual legend listing
    every cloaked block, the qubits it touches, and how many gates it
    contains.  Useful in logs and CI output where ASCII is the only
    medium.

A default colour palette (:func:`cloak_style`) is exposed for users who
want to compose it with their own matplotlib styling.
"""

from __future__ import annotations

from typing import Any, Optional

from qiskit import QuantumCircuit

from .annotations import Sensitive
from .metrics import compute_blind_share


_DEFAULT_MARKER = "🔒 "
_CLOAK_FILL = "#5B2A86"       # deep purple — unmistakable in the default palette
_CLOAK_TEXT = "#FFFFFF"


def cloak_style() -> dict[str, Any]:
    """Return a Qiskit matplotlib style dict highlighting cloaked blocks."""
    return {
        "displaycolor": {
            "sensitive": [_CLOAK_FILL, _CLOAK_TEXT],
        },
    }


def _marked_copy(qc: QuantumCircuit, marker: str) -> QuantumCircuit:
    """Return a shallow copy of ``qc`` with cloaked-block labels prefixed."""
    out = QuantumCircuit(qc.num_qubits, qc.num_clbits, name=qc.name)
    for instr in qc.data:
        op = instr.operation
        if isinstance(op, Sensitive):
            old_label = op.label or "sensitive"
            if old_label.startswith(marker):
                new_label = old_label
            else:
                new_label = f"{marker}{old_label}"
            marked = Sensitive(op.sensitive_body, label=new_label)
            out.append(marked, list(instr.qubits), list(instr.clbits))
        else:
            out.append(op, list(instr.qubits), list(instr.clbits))
    return out


def draw_cloaked(
    qc: QuantumCircuit,
    *,
    output: str = "text",
    marker: str = _DEFAULT_MARKER,
    style: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> Any:
    """Draw ``qc`` with cloaked subcircuits visually distinguished.

    Parameters
    ----------
    qc
        The circuit to draw.  Not mutated.
    output
        Any value accepted by :meth:`QuantumCircuit.draw` — typically
        ``"text"``, ``"mpl"``, or ``"latex"``.  ``"text"`` works without
        matplotlib and is the default.
    marker
        Prefix prepended to every cloaked block's label so the lock is
        visible in every backend, not just matplotlib.  Pass ``""`` to
        disable.
    style
        Additional matplotlib style overrides.  Merged on top of
        :func:`cloak_style` for the matplotlib backend; ignored
        otherwise.
    **kwargs
        Forwarded to :meth:`QuantumCircuit.draw`.

    Returns
    -------
    Whatever the underlying ``draw`` call returns: a
    :class:`qiskit.visualization.TextDrawing` for ``"text"``, a
    :class:`matplotlib.figure.Figure` for ``"mpl"``, etc.
    """
    marked = _marked_copy(qc, marker) if marker else qc
    if output == "mpl":
        merged_style = cloak_style()
        if style:
            for key, value in style.items():
                if isinstance(value, dict) and isinstance(merged_style.get(key), dict):
                    merged_style[key] = {**merged_style[key], **value}
                else:
                    merged_style[key] = value
        return marked.draw(output="mpl", style=merged_style, **kwargs)
    return marked.draw(output=output, **kwargs)


def summarize_cloaked(qc: QuantumCircuit) -> str:
    """Return a multi-line textual legend of every cloaked block in ``qc``.

    The summary is one line per :class:`Sensitive` block, with the index
    inside ``qc.data``, the user-supplied label, the global qubit indices
    touched, and the inner gate count.  When the circuit contains no
    cloaked blocks, a one-line "no cloaked blocks" notice is returned.
    """
    qubit_index = {q: i for i, q in enumerate(qc.qubits)}
    rows: list[str] = []
    sens_count = 0
    for i, instr in enumerate(qc.data):
        op = instr.operation
        if not isinstance(op, Sensitive):
            continue
        sens_count += 1
        qubits = [qubit_index[q] for q in instr.qubits]
        label = op.label or "(unlabelled)"
        body = op.sensitive_body
        rows.append(
            f"  [{i:3d}] '{label}' on qubits {qubits}: "
            f"{body.num_qubits} qubits, {len(body.data)} gates"
        )
    header = (
        f"Circuit '{qc.name}': {sens_count} cloaked block(s) "
        f"across {len(qc.data)} operation(s)"
    )
    share_line = f"  {compute_blind_share(qc).format()}"
    if not rows:
        return f"{header}\n{share_line}\n  (no cloaked blocks)"
    return "\n".join([header, share_line, *rows])
