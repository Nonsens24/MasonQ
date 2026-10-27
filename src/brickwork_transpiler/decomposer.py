"""Circuit lowering, brick scheduling and CX alignment.

Stages, in pipeline order:

1. `selective_decompose` and `linearise_multi_ctrl` prepare the circuit;
2. `decompose_qc_to_bricks_qiskit` lets Qiskit lower it to `rz`/`rx`/`cx`
   on a line coupling map;
3. `instructions_to_matrix_dag` schedules the result into a per-qubit,
   per-column instruction matrix;
4. `align_bricks` moves the CX bricks to parity-compatible columns and
   re-attaches the rotations next to them.
"""

from __future__ import annotations

import heapq
import logging
from collections import Counter, defaultdict
from math import pi

from qiskit import AncillaRegister, transpile
from qiskit.circuit import QuantumCircuit, Qubit
from qiskit.circuit.instruction import Instruction
from qiskit.circuit.library import MCXGate, PhaseGate
from qiskit.converters import circuit_to_dag
from qiskit.dagcircuit.dagnode import DAGOpNode
from qiskit.transpiler import CouplingMap

from .cx_tags import cx_group_id, is_cx_endpoint, tag_cx

try:
    from qiskit.circuit.library import MCXRecursive
except ImportError:  # Removed in Qiskit 3.0; only the legacy-recursive strategy uses it.
    MCXRecursive = None

logger = logging.getLogger(__name__)

Matrix = list[list[list[Instruction]]]


# -------------------------------------------------------------------
# 1) strip “Q” composite wrappers but keep MCX / MCU1 in place
# -------------------------------------------------------------------
def selective_decompose(qc, keep=("mcx", "mcu1", "mcphase")):
    out = QuantumCircuit(*qc.qregs, *qc.cregs, name=qc.name)
    for instruction in qc.data:
        inst = instruction.operation
        q = instruction.qubits
        c = instruction.clbits
        if inst.name.lower() in keep:
            out.append(inst, q, c)
        elif inst.definition:
            out.compose(
                selective_decompose(inst.definition, keep), qubits=q, inplace=True
            )
        else:
            out.append(inst, q, c)
    return out


def _append_mcx(
    out: QuantumCircuit,
    num_controls: int,
    qargs,
    cargs,
    strategy: str,
) -> None:
    if strategy == "hls":
        out.append(MCXGate(num_controls), qargs, cargs)
        return
    if strategy != "legacy-recursive":
        raise ValueError(
            "multi_control_strategy must be 'legacy-recursive' or 'hls', "
            f"got {strategy!r}."
        )
    if MCXRecursive is None:
        logger.warning(
            "MCXRecursive is unavailable; falling back to MCXGate and Qiskit's "
            "high-level synthesis."
        )
        out.append(MCXGate(num_controls), qargs, cargs)
        return
    out.append(MCXRecursive(num_controls), qargs, cargs)


def _mcx_qargs_for_strategy(ctrls, target, scratch_anc, strategy: str):
    """Return Qiskit qargs for a k-control X under the selected synthesis path.

    `MCXGate(k)` has no explicit ancilla operands; Qiskit's high-level
    synthesis pass decides whether and how to use available auxiliary qubits.
    The legacy `MCXRecursive(k)` path has one explicit clean ancilla for
    k >= 5 and expects the order controls, target, ancilla.
    """
    if strategy == "hls" or len(ctrls) < 5:
        return list(ctrls) + [target]
    return list(ctrls) + [target, scratch_anc]


def _is_multi_control_phase(inst: Instruction, qarg_count: int) -> bool:
    return inst.name.lower() in ("mcu1", "mcphase") and qarg_count > 2


def _required_explicit_ancillas(qc: QuantumCircuit, strategy: str) -> int:
    """Return how many explicit ancillas `linearise_multi_ctrl` needs.

    HLS-controlled X gates do not need explicit ancilla operands; Qiskit decides
    synthesis internally. Multi-controlled phase rewrites still need one
    explicit phase workspace qubit because this package lowers them via
    compute-phase-uncompute. The legacy recursive path additionally needs a
    clean scratch ancilla for controls >= 5.
    """
    required = 0
    for instruction in qc.data:
        inst = instruction.operation
        qarg_count = len(instruction.qubits)
        if isinstance(inst, MCXGate) and inst.num_ctrl_qubits > 2:
            if strategy == "legacy-recursive" and inst.num_ctrl_qubits >= 5:
                required = max(required, 1)
        elif _is_multi_control_phase(inst, qarg_count):
            controls = qarg_count - 1
            required = max(required, 1)
            if strategy == "legacy-recursive" and controls >= 5:
                required = max(required, 2)
    return required


def _copy_with_required_ancillas(qc: QuantumCircuit, required: int) -> tuple[QuantumCircuit, list[Qubit]]:
    """Create an output circuit and add only the missing explicit ancillas."""
    out = QuantumCircuit(*qc.qregs, *qc.cregs, name=qc.name)
    ancillas = [
        qubit
        for register in out.qregs
        if register.name.startswith("anc")
        for qubit in register
    ]
    missing = required - len(ancillas)
    if missing > 0:
        existing_names = {register.name for register in out.qregs}
        name = "anc" if "anc" not in existing_names else "anc_ext"
        if name in existing_names:
            idx = 2
            while f"{name}_{idx}" in existing_names:
                idx += 1
            name = f"{name}_{idx}"
        extra = AncillaRegister(missing, name)
        out.add_register(extra)
        ancillas.extend(extra)
    return out, ancillas


def linearise_multi_ctrl(
    qc: QuantumCircuit,
    *,
    multi_control_strategy: str = "hls",
) -> QuantumCircuit:
    """Linear-depth replacements for MCX (>2-ctrl) and MCU1/MCP (>1-ctrl)."""
    if multi_control_strategy not in {"hls", "legacy-recursive"}:
        raise ValueError(
            "multi_control_strategy must be 'legacy-recursive' or 'hls', "
            f"got {multi_control_strategy!r}."
        )

    required_ancillas = _required_explicit_ancillas(qc, multi_control_strategy)
    out, ancillas = _copy_with_required_ancillas(qc, required_ancillas)
    phase_anc = ancillas[0] if required_ancillas >= 1 else None
    scratch_anc = ancillas[1] if required_ancillas >= 2 else None

    for instruction in qc.data:
        inst = instruction.operation
        qargs = list(instruction.qubits)
        cargs = list(instruction.clbits)

        # ---------- MCX (>2 controls) ----------
        if isinstance(inst, MCXGate) and inst.num_ctrl_qubits > 2:
            k = inst.num_ctrl_qubits
            ctrls, target = qargs[:-1], qargs[-1]
            _append_mcx(
                out,
                k,
                _mcx_qargs_for_strategy(ctrls, target, phase_anc, multi_control_strategy),
                cargs,
                multi_control_strategy,
            )

        # ---------- MCU1 / MCPhase (>1 control) ----------
        elif _is_multi_control_phase(inst, len(qargs)):
            theta = float(inst.params[0]) % (2 * pi)
            ctrls, target = qargs[:-1], qargs[-1]
            k = len(ctrls)
            if phase_anc is None:
                raise RuntimeError("Internal error: multi-controlled phase requires a phase ancilla.")

            # Step 1: compute AND of controls into phase_anc
            _append_mcx(
                out,
                k,
                _mcx_qargs_for_strategy(ctrls, phase_anc, scratch_anc, multi_control_strategy),
                [],
                multi_control_strategy,
            )

            # Step 2: controlled-phase from phase_anc to target
            out.append(PhaseGate(theta).control(1), [phase_anc, target])

            # Step 3: un-compute phase_anc
            _append_mcx(
                out,
                k,
                _mcx_qargs_for_strategy(ctrls, phase_anc, scratch_anc, multi_control_strategy),
                [],
                multi_control_strategy,
            )

        # ---------- everything else ----------
        else:
            out.append(inst, qargs, cargs)

    return out


def compute_brick_distances(
    qc: QuantumCircuit,
    row_map: dict[Qubit, int] | None = None,
    ignore_1q: bool = True,
) -> tuple[dict[int, int], list[int], dict[str, int]]:
    """
    Compute:
      - H(d): histogram of vertical row separations d for multi-qubit ops
      - d_max(c): per-column (layer) maximum separation
      - summary stats including a brickwork-depth estimate: 2 * sum_c (6 d_max(c) + 2)

    Args:
        qc:           circuit to analyze (typically the *non-decomposed* logical circuit)
        row_map:      optional mapping Qubit -> row index (0..m-1). If None, use enumeration order.
        ignore_1q:    ignore single-qubit ops (True by default)

    Returns:
        (hist, dmax_per_col, stats) where
          - hist is a dict {d: count}
          - dmax_per_col is a list [d_max(0), d_max(1), ...]
          - stats has keys:
                'brick_depth_est', 'avg_d', 'max_d', 'multiq_gate_count', 'num_columns'
    """
    # default row assignment: circuit order
    if row_map is None:
        row_map = {q: i for i, q in enumerate(qc.qubits)}

    dag = circuit_to_dag(qc)
    hist = Counter()
    dmax_per_col: list[int] = []

    # Qiskit DAG layers: each item is {'graph': DAGCircuit,...}
    for layer in dag.layers():
        G = layer["graph"]
        layer_dmax = 0
        # consider only operation nodes (skip barriers, measures if you wish)
        for node in G.op_nodes():
            qargs = list(node.qargs)
            if ignore_1q and len(qargs) < 2:
                continue
            # Distance = row-span of the qubits this op touches
            rows = [row_map[q] for q in qargs]
            d = max(rows) - min(rows) if rows else 0
            if d > 0:
                hist[d] += 1
                if d > layer_dmax:
                    layer_dmax = d
        dmax_per_col.append(layer_dmax)

    # Brickwork depth estimate from per-column maxima
    brick_depth_est = 2 * sum(6 * d + 2 for d in dmax_per_col)
    multiq_total = sum(hist.values())
    avg_d = (sum(d * c for d, c in hist.items()) / multiq_total) if multiq_total else 0
    max_d = max(dmax_per_col) if dmax_per_col else 0

    stats = dict(
        brick_depth_est=brick_depth_est,
        avg_d=avg_d,
        max_d=max_d,
        multiq_gate_count=multiq_total,
        num_columns=len(dmax_per_col),
    )
    # Return a plain dict for H(d), sorted by d for readability
    hist_dict = dict(sorted(hist.items()))
    return hist_dict, dmax_per_col, stats


def _log_brick_distances(label: str, qc: QuantumCircuit) -> None:
    """INFO-level diagnostics on the row spans of the multi-qubit gates in `qc`."""
    if not logger.isEnabledFor(logging.INFO):
        return
    hist, dmax_per_col, stats = compute_brick_distances(qc)
    logger.info("%s gate counts: %s", label, qc.count_ops())
    logger.info("%s distance histogram H(d): %s", label, hist)
    logger.info("%s d_max per column preview: %s", label, dmax_per_col[:10])
    logger.info(
        "%s max d: %s, avg d: %.3f, columns: %s, brick-depth estimate: %s",
        label,
        stats["max_d"],
        stats["avg_d"],
        stats["num_columns"],
        stats["brick_depth_est"],
    )


def decompose_qc_to_bricks_qiskit(
    qc: QuantumCircuit,
    opt: int = 3,
    routing_method: str | None = "basic",
    layout_method: str | None = "trivial",
    with_ancillas: bool = True,
    multi_control_strategy: str = "hls",
    fallback_opt: int | None = 1,
) -> QuantumCircuit:
    """Decompose `qc` into the brickwork-compatible basis on a line coupling.

    Steps:
      1. `selective_decompose` opens composite gates while keeping multi-CTRL
         operations intact for downstream policy.
      2. `linearise_multi_ctrl` (when `with_ancillas=True`) rewrites large
         multi-controlled X / phase gates with the chosen strategy.
      3. Qiskit transpiles the result onto `[rz, rx, cx, id]` over a line
         coupling map at the requested `opt` level. On failure, retries at
         `fallback_opt` (when not `None`), since high-`opt` synthesis can hit
         numerical edge cases on borderline matrices.

    Diagnostics go to this module's logger at INFO level.
    """
    _log_brick_distances("Original circuit:", qc)

    qc_sel = selective_decompose(qc)
    _log_brick_distances("Selectively decomposed circuit:", qc_sel)

    if with_ancillas:
        qc_lin = linearise_multi_ctrl(
            qc_sel,
            multi_control_strategy=multi_control_strategy,
        )
        logger.info("After multi-control linearisation: %s", qc_lin.count_ops())
    else:
        qc_lin = qc_sel

    # simple line-coupling (up and down)
    basis = ["rz", "rx", "cx", "id"]
    coupling = (
        CouplingMap(
            [[i, i + 1] for i in range(qc_lin.num_qubits - 1)]
            + [[i + 1, i] for i in range(qc_lin.num_qubits - 1)]
        )
        if qc_lin.num_qubits > 1
        else None
    )

    logger.info(
        "Transpiling with Qiskit: optimisation level %s, layout %s, routing %s",
        opt,
        layout_method,
        routing_method,
    )
    try:
        qc_final = transpile(
            qc_lin,
            basis_gates=basis,
            coupling_map=coupling,
            layout_method=layout_method,
            routing_method=routing_method,
            optimization_level=opt,  # 3 for consistent merging of single qubit gates
        )
    except Exception as e:
        if fallback_opt is None:
            raise
        logger.warning(
            "Qiskit transpile with optimisation_level=%s failed; retrying with "
            "optimisation_level=%s. This usually indicates a numerical issue in "
            "Qiskit's high-optimisation synthesis path, not necessarily an invalid "
            "input circuit. Error: %s",
            opt,
            fallback_opt,
            e,
        )
        qc_final = transpile(
            qc_lin,
            basis_gates=basis,
            coupling_map=coupling,
            layout_method=layout_method,
            routing_method=routing_method,
            optimization_level=fallback_opt,
        )

    logger.info("Post-HLS/transpile gate counts: %s", qc_final.count_ops())
    return qc_final


def group_with_dag_atomic_mixed(qc: QuantumCircuit):
    """Schedule DAG operations into brickwork-preparation columns.

    The scheduler is dependency preserving, but intentionally biased:
    all currently ready single-qubit rotations are drained first, then
    compatible CX gates are greedily packed into the same column. This creates a
    compact pre-brick matrix while preserving Qiskit's topological order inside
    each operation class.
    """
    dag = circuit_to_dag(qc)
    op_nodes = list(dag.topological_op_nodes())
    idx = {node: i for i, node in enumerate(op_nodes)}  # stable order key
    qubit_index = {qubit: i for i, qubit in enumerate(qc.qubits)}

    # --- build static dependency graph ---------------------------------------
    indeg = {}  # remaining unscheduled predecessors
    succs = defaultdict(list)  # forward adjacency
    for n in op_nodes:
        preds = [p for p in dag.predecessors(n) if isinstance(p, DAGOpNode)]
        indeg[n] = len(preds)
        for p in preds:
            succs[p].append(n)

    # --- two priority queues keep the ready set partitioned by gate type -----
    ready_rot, ready_cx = [], []  # (topo_index, node)

    def push_ready(node):
        """Put node into the correct ready queue, preserving topo order."""
        h = ready_rot if node.op.name in ("rz", "rx") else ready_cx
        heapq.heappush(h, (idx[node], node))

    for n in op_nodes:  # initial ready set
        if indeg[n] == 0:
            push_ready(n)

    columns = []

    while ready_rot or ready_cx:  # until every op scheduled
        col_nodes, busy = [], set()

        # -------- 1) drain all ready rotations *recursively* ---------------
        while ready_rot:
            _, node = heapq.heappop(ready_rot)
            col_nodes.append(node)

            for suc in succs[node]:
                indeg[suc] -= 1
                if indeg[suc] == 0:
                    push_ready(suc)

        # Mark rotation qubits busy for the CX-packing phase. This keeps a
        # rotation and a CX that touches the same qubit out of the same brick
        # column, which preserves the local Euler-brick interpretation.
        busy.update(qubit_index[q] for n in col_nodes for q in n.qargs)

        # -------- 2) greedily pack compatible ready CXs ---------------------
        tmp = []
        while ready_cx:
            _, node = heapq.heappop(ready_cx)
            qidx = [qubit_index[q] for q in node.qargs]
            if any(q in busy for q in qidx):  # conflict -> next column
                tmp.append((idx[node], node))
                continue

            # schedule this CX
            col_nodes.append(node)
            busy.update(qidx)

            for suc in succs[node]:
                indeg[suc] -= 1
                if indeg[suc] == 0:
                    push_ready(suc)

        # left‑over CXs still ready but blocked by busy qubits
        for item in tmp:
            heapq.heappush(ready_cx, item)

        if not col_nodes:  # should never happen
            raise RuntimeError("Stalled scheduling: circular dependency detected.")

        columns.append([(n.op, n.qargs, n.cargs) for n in col_nodes])

    return columns


def instructions_to_matrix_dag(qc: QuantumCircuit):
    """Build per-qubit x per-column instruction matrices.

    `matrix` contains all supported operations. `cx_matrix` contains only CX
    endpoints and is used by the parity alignment pass. CX instructions are
    copied to mutable instructions and tagged as `cx{id}c` / `cx{id}t` so the
    two endpoints can be tracked after column movement.
    """

    cols = group_with_dag_atomic_mixed(qc)

    n_q = qc.num_qubits
    n_c = len(cols)
    qubit_index = {qubit: i for i, qubit in enumerate(qc.qubits)}
    matrix = [[[] for _ in range(n_c)] for _ in range(n_q)]
    cx_matrix = [[[] for _ in range(n_c)] for _ in range(n_q)]
    cx_idx = 0  # Unique CX identifier.
    for c_idx, col in enumerate(cols):  # c_idx is the column index

        for instr, qargs, _ in col:  # qargs[0] is the control qubit for Qiskit CX
            if instr.name == "cx":
                # CX produces two distinct endpoint instances with different
                # tagged names. Only CXs need mutable copies; the originals
                # stay untouched.
                control_qubit = True
                for q in qargs:
                    instr_mut = instr.to_mutable()
                    if control_qubit:
                        instr_mut.name = tag_cx(cx_idx, "c")
                        control_qubit = False
                    else:
                        instr_mut.name = tag_cx(cx_idx, "t")
                    cx_matrix[qubit_index[q]][c_idx].append(instr_mut)
                    matrix[qubit_index[q]][c_idx].append(instr_mut)
                cx_idx += 1
            else:
                # Non-CX instructions are appended unchanged. Downstream code
                # only reads `.name` and `.params`; no mutable copy needed.
                for q in qargs:
                    matrix[qubit_index[q]][c_idx].append(instr)

    return matrix, cx_matrix


def align_cx_matrix(
    cx_matrix: Matrix,
    orig_matrix: Matrix | None = None,
) -> Matrix:
    """Move CX endpoints to parity-compatible brick columns.

    Brickwork CX gadgets occupy adjacent rows. The top row determines the
    required column parity: even top rows live in even brick columns and odd
    top rows live in odd brick columns.

    The placement floor for a brick `B` on row `r` is the smallest column
    that respects three constraints:
      (i)  parity matches the brick's top-row parity;
      (ii) `B` lands strictly after every same-row predecessor `A`
           (`place_B >= place_A + 1`);
      (iii) if a *rotation cell* on row `r` lives in the original matrix
           strictly between `A`'s and `B`'s original columns, that rotation
           must have an empty slot to land in after alignment, so
           `place_B >= place_A + 2`.

    The third constraint replaces the older `row_max_delta + ocol`
    formulation, which preserved every original column gap (often producing
    columns no rotation needed). The rotation-aware bound is tight: it only
    reserves a slot when one will actually be claimed by
    `insert_rotations_adjacent_to_cx`.

    `orig_matrix`, when supplied, is the full instruction matrix containing
    rotations and CX endpoints (typically `qc_mat` from
    `instructions_to_matrix_dag`). When `None`, the function falls back to
    the gap-preserving rule for backwards compatibility with callers that
    only have the CX-only matrix.
    """

    n_rows = len(cx_matrix)
    if n_rows == 0:
        return []

    n_cols = max((len(r) for r in cx_matrix), default=0)

    # ---- 1) Discover CX groups: rows touched and earliest original column ---
    group_info: dict[str, dict] = {}
    for r in range(n_rows):
        row = cx_matrix[r]
        for c in range(min(n_cols, len(row))):
            for instr in row[c]:
                if is_cx_endpoint(instr.name):
                    gid = cx_group_id(instr.name)
                    info = group_info.get(gid)
                    if info is None:
                        group_info[gid] = {"rows": [r], "orig_col": c}
                    else:
                        if r not in info["rows"]:
                            info["rows"].append(r)
                        if c < info["orig_col"]:
                            info["orig_col"] = c

    bricks = [
        {
            "gid": gid,
            "rows": sorted(info["rows"]),
            "orig_col": info["orig_col"],
            "top": min(info["rows"]),
        }
        for gid, info in group_info.items()
    ]
    # Sort by (original column, integer gid). The integer gid breaks ties
    # in the order Qiskit emitted the CX gates, preserving per-row order.
    bricks.sort(key=lambda b: (b["orig_col"], int(b["gid"]), b["top"]))

    # ---- 1b) Per-row sorted list of original columns containing rotations --
    rot_cols_per_row: list[list[int]] = [[] for _ in range(n_rows)]
    if orig_matrix is not None:
        for r in range(min(n_rows, len(orig_matrix))):
            row = orig_matrix[r]
            for c, cell in enumerate(row):
                has_rot = False
                for instr in cell:
                    if not is_cx_endpoint(instr.name):
                        has_rot = True
                        break
                if has_rot:
                    rot_cols_per_row[r].append(c)

    # ---- 2) Pre-allocate the output grid -----------------------------------
    # Upper bound on final width: every brick can shift by at most 1 column
    # to fix parity, plus 1 per same-row predecessor for rotation reservation,
    # capped at the brick count. `n_cols + 2*n_bricks + 1` is a strict bound.
    upper_bound = n_cols + 2 * len(bricks) + 1
    aligned: Matrix = [[[] for _ in range(upper_bound)] for _ in range(n_rows)]
    used_width = 0  # inclusive max column index actually written

    # row -> (last placed column, original column of that brick)
    row_last_placed: dict[int, tuple[int, int]] = {}

    for brick in bricks:
        gid = brick["gid"]
        rows = brick["rows"]
        ocol = brick["orig_col"]
        top_row = brick["top"]
        top_parity = top_row & 1

        base_col = ocol if (ocol & 1) == top_parity else ocol + 1

        floor = 0
        for r in rows:
            entry = row_last_placed.get(r)
            if entry is None:
                continue
            prev_placed, prev_ocol = entry
            if orig_matrix is None:
                # Backwards-compat: preserve the original column gap on this
                # row. Equivalent to the legacy `row_max_delta + ocol` for
                # the most-recent same-row brick.
                row_floor = prev_placed + max(1, ocol - prev_ocol)
            else:
                # Rotation-aware: only reserve an extra slot if a rotation
                # cell on this row lives between the two original columns.
                gap = 1
                if ocol - prev_ocol > 1:
                    rot_cols = rot_cols_per_row[r]
                    # rot_cols is sorted; check for any column strictly in
                    # (prev_ocol, ocol).
                    lo, hi = prev_ocol, ocol
                    for rc in rot_cols:
                        if rc <= lo:
                            continue
                        if rc >= hi:
                            break
                        gap = 2
                        break
                row_floor = prev_placed + gap
            if row_floor > floor:
                floor = row_floor

        place = base_col if base_col >= floor else floor
        if (place & 1) != top_parity:
            place += 1

        # Defensive grow if our upper bound was somehow too small.
        if place >= len(aligned[0]):
            extra = place + 1 - len(aligned[0])
            for row in aligned:
                row.extend([[] for _ in range(extra)])

        # Copy exactly the endpoints of this group from the original column.
        for r in rows:
            cell = cx_matrix[r][ocol]
            instrs = [
                instr
                for instr in cell
                if is_cx_endpoint(instr.name)
                and cx_group_id(instr.name) == gid
            ]
            aligned[r][place] = list(aligned[r][place]) + instrs
            row_last_placed[r] = (place, ocol)

        if place > used_width:
            used_width = place

    # ---- 3) Trim trailing empty columns ------------------------------------
    final_width = used_width + 1 if bricks else 0
    if final_width != len(aligned[0]):
        aligned = [row[:final_width] for row in aligned]

    return aligned


def insert_rotations_adjacent_to_cx(
    aligned_cx: Matrix,
    original: Matrix,
) -> Matrix:
    """Insert rotation bricks around their neighbouring CX bricks.

    Qiskit's SU(2) decomposition emits local `rz/rx/rz` rotations between CX
    layers. After CX alignment, rotations are reattached to the nearest
    aligned neighbouring CX on the same qubit:

    - if the original left neighbour is a CX, place just after that aligned
      CX (`place_cx + 1`);
    - else if the original right neighbour is a CX, place just before it
      (`max(place_cx - 1, 0)`);
    - otherwise place just after the nearest preceding CX on the same row, or
      in the leading column (column 0) if the row has no CX before it.

    With the rotation-aware floor of `align_cx_matrix` every destination is
    free of CX endpoints and per-row operation order is preserved for any
    row-isolated input. The DAG scheduler additionally keeps each run of
    single-qubit gates in the cell right after its preceding CX, so in the
    compiled pipeline the adjacent-cell cases always apply.

    This is intentionally conservative. It avoids commuting rotations through
    CX gates, which would be a circuit optimisation and requires separate
    algebraic validation.

    The aligned CX matrix is rectangular (every row has the same length), so
    the width is read from `len(new_mat[0])` rather than recomputed each
    iteration. Growth (when a rotation needs an extra column) is tracked
    incrementally and applied to all rows in one slice.
    """
    n_rows = len(aligned_cx)
    if n_rows == 0:
        return []
    width = len(aligned_cx[0]) if aligned_cx else 0

    # Deep copy of the aligned grid so callers may freely mutate the result.
    new_mat: Matrix = [[list(cell) for cell in row] for row in aligned_cx]

    # Per-row lookup: CX endpoint instruction name -> aligned column.
    cx_col: list[dict[str, int]] = []
    for row in new_mat:
        lookup: dict[str, int] = {}
        for c, cell in enumerate(row):
            for ins in cell:
                if is_cx_endpoint(ins.name) and ins.name not in lookup:
                    lookup[ins.name] = c
        cx_col.append(lookup)

    def _grow_to(new_width: int) -> None:
        nonlocal width
        if new_width <= width:
            return
        extra = new_width - width
        pad = [[] for _ in range(extra)]
        for r in new_mat:
            r.extend([list(cell) for cell in pad])
        width = new_width

    for i in range(n_rows):
        row_orig = original[i] if i < len(original) else []
        lookup = cx_col[i]

        for j, cell in enumerate(row_orig):
            rots = [ins for ins in cell if not is_cx_endpoint(ins.name)]
            if not rots:
                continue

            left_dest: int | None = None
            if j > 0:
                for ins in row_orig[j - 1]:
                    if is_cx_endpoint(ins.name):
                        left_dest = lookup[ins.name] + 1
                        break

            right_dest: int | None = None
            if j + 1 < len(row_orig):
                for ins in row_orig[j + 1]:
                    if is_cx_endpoint(ins.name):
                        right_dest = max(lookup[ins.name] - 1, 0)
                        break

            # Choose the destination that is currently *not* occupied by a
            # CX endpoint on this row. The aligner reserves a rotation slot
            # next to every CX that has rotations, so at least one side is
            # safe; if both sides are safe, prefer left (legacy behaviour).
            candidates: list[int] = []
            for cand in (left_dest, right_dest):
                if cand is None:
                    continue
                cell_at_cand = (
                    new_mat[i][cand] if cand < width else []
                )
                cand_clear = not any(
                    is_cx_endpoint(x.name) for x in cell_at_cand
                )
                if cand_clear:
                    candidates.append(cand)
            if candidates:
                dest = candidates[0]
            elif left_dest is not None:
                dest = left_dest
            elif right_dest is not None:
                dest = right_dest
            else:
                # No CX in either adjacent cell. Attach after the nearest
                # preceding CX on this row so the rotation cannot move ahead
                # of a CX it originally followed; a rotation that precedes
                # every CX on its row goes to the leading column.
                dest = 0
                for jj in range(j - 2, -1, -1):
                    prev = next((x for x in row_orig[jj] if is_cx_endpoint(x.name)), None)
                    if prev is not None:
                        dest = lookup[prev.name] + 1
                        break

            if dest >= width:
                _grow_to(dest + 1)

            new_mat[i][dest].extend(rots)

    return new_mat


def align_bricks(cx_mat: Matrix, orig: Matrix) -> Matrix:
    """Align the CX bricks of `cx_mat`, then re-attach the rotations of `orig` next to them."""
    aligned_cx = align_cx_matrix(cx_mat, orig_matrix=orig)
    return insert_rotations_adjacent_to_cx(aligned_cx, orig)
