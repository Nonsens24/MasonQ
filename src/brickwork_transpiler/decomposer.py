import heapq
import logging
from collections import Counter, defaultdict
from math import pi
from qiskit.circuit.instruction import Instruction
from typing import Dict, List, Optional, Tuple

from qiskit import AncillaRegister, transpile
from qiskit.circuit import QuantumCircuit, Qubit
from qiskit.circuit.library import MCXGate, PhaseGate
from qiskit.converters import circuit_to_dag
from qiskit.dagcircuit.dagnode import DAGOpNode
from qiskit.transpiler import CouplingMap

try:
    from qiskit.transpiler.passes import HLSConfig
except ImportError:  # Qiskit 0.46 compatibility.
    from qiskit.transpiler.passes.synthesis import HLSConfig

try:
    from qiskit.circuit.library import MCXRecursive
except ImportError:  # Current Qiskit prefers high-level synthesis for MCX.
    MCXRecursive = None

logger = logging.getLogger(__name__)

Matrix = List[List[List[Instruction]]]


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
    return inst.name.lower() in ("mcu1", "mcphase", "cp", "cphase") and qarg_count > 2


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
        elif inst.name.lower() in ("mcu1", "mcphase") and len(qargs) > 2:
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
    row_map: Optional[Dict[Qubit, int]] = None,
    ignore_1q: bool = True,
) -> Tuple[Dict[int, int], List[int], Dict[str, int]]:
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
    dmax_per_col: List[int] = []

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


def decompose_qc_to_bricks_qiskit(
    qc: QuantumCircuit,
    opt: int = 3,
    draw: bool = False,
    routing_method: str = "basic",
    layout_method: str = "trivial",
    file_writer=None,
    with_ancillas: bool = True,
    verbose: bool = False,
    multi_control_strategy: str = "hls",
    fallback_opt: int | None = 1,
):
    if verbose:
        logger.setLevel(logging.INFO)

    logger.info("Original gate counts: %s", qc.count_ops())

    # BEFORE selective_decompose:
    H0, dmax_cols0, stats0 = compute_brick_distances(qc)  # <— use qc, not qc_sel
    logger.info("Original distance histogram H(d): %s", H0)
    logger.info("Original d_max per column preview: %s", dmax_cols0[:10])
    logger.info("Original brick-depth estimate: %s", stats0["brick_depth_est"])

    # ---- Non-decomposed (logical) circuit ----
    qc_sel = selective_decompose(qc)
    logger.info("Selectively decomposed gate counts: %s", qc_sel.count_ops())

    # Distance metrics on the *logical* circuit
    H_logical, dmax_cols_logical, stats_logical = compute_brick_distances(qc_sel)
    logger.info("Logical distance histogram H(d): %s", H_logical)
    logger.info("Logical max d over columns: %s", stats_logical["max_d"])
    logger.info("Logical avg d: %.3f", stats_logical["avg_d"])
    logger.info("Logical columns: %s", stats_logical["num_columns"])
    logger.info("Logical brick-depth estimate: %s", stats_logical["brick_depth_est"])

    if file_writer:
        file_writer.set("d_avg", stats_logical["avg_d"])

    if with_ancillas:
        qc_lin = linearise_multi_ctrl(
            qc_sel,
            multi_control_strategy=multi_control_strategy,
        )
        logger.info("After multi-control linearisation: %s", qc_lin.count_ops())

    else:
        qc_lin = qc_sel

    hls_cfg = HLSConfig()

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

    logger.info("Qiskit transpile optimisation level: %s", opt)
    logger.info("Qiskit layout method: %s", layout_method)
    logger.info("Qiskit routing method: %s", routing_method)
    logger.info("Transpiling with Qiskit...")
    try:
        qc_final = transpile(
            qc_lin,
            basis_gates=basis,
            coupling_map=coupling,
            layout_method=layout_method,
            routing_method=routing_method,
            hls_config=hls_cfg,
            optimization_level=opt,  # 3 for consistent merging of single qubit gates
        )

    except Exception as e:
        if fallback_opt is None:
            raise
        logger.info(
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
            hls_config=hls_cfg,
            optimization_level=fallback_opt,
        )

    if draw:
        from matplotlib import pyplot as plt

        logger.info("Drawing decomposed circuit...")
        qc_final.draw(output="mpl", fold=40, style="iqp")
        plt.savefig(f"images/Circuits/Decomposed_hhl_circ.png", dpi=300, bbox_inches="tight")
        plt.show()

    logger.info("Post-HLS/transpile gate counts: %s", qc_final.count_ops())

    if file_writer:
        file_writer.set("decomposed_depth", qc_final.depth())
        file_writer.set("num_gates_transpiled", sum(qc_final.count_ops().values()))
        file_writer.set("num_gates_original", sum(qc_sel.count_ops().values()))

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

    scheduled = set()
    columns = []

    while ready_rot or ready_cx:  # until every op scheduled
        col_nodes, busy = [], set()

        # -------- 1) drain all ready rotations *recursively* ---------------
        while ready_rot:
            _, node = heapq.heappop(ready_rot)
            col_nodes.append(node)
            scheduled.add(node)

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
            scheduled.add(node)

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
            control_qubit = True
            for q in qargs:
                # Use mutable copies so endpoint tags do not mutate Qiskit's
                # original instruction singletons.
                instr_mut = instr.to_mutable()
                if instr_mut.name == "cx" and control_qubit:
                    instr_mut.name = f"cx{cx_idx}c"
                    cx_matrix[qubit_index[q]][c_idx].append(instr_mut)
                    control_qubit = False
                elif instr_mut.name == "cx" and not control_qubit:
                    instr_mut.name = f"cx{cx_idx}t"
                    cx_matrix[qubit_index[q]][c_idx].append(instr_mut)

                matrix[qubit_index[q]][c_idx].append(instr_mut)
            if instr.name == "cx":
                cx_idx += 1

    return matrix, cx_matrix


def align_cx_matrix(cx_matrix: Matrix) -> Matrix:
    """Move CX endpoints to parity-compatible brick columns.

    Brickwork CX gadgets occupy adjacent rows. The top row determines the
    required column parity: even top rows live in even brick columns and odd top
    rows live in odd brick columns. The algorithm preserves each CX group's
    original order on every touched row by tracking the maximum delay already
    introduced on that row.
    """

    n_rows = len(cx_matrix)
    n_cols = max((len(r) for r in cx_matrix), default=0)

    group_info: Dict[str, Dict] = {}
    for r in range(n_rows):
        for c in range(n_cols):
            for instr in (cx_matrix[r][c] if c < len(cx_matrix[r]) else []):
                if instr.name.startswith("cx"):
                    gid = instr.name[2:-1]
                    info = group_info.setdefault(gid, {"rows": set(), "orig_col": c})
                    info["rows"].add(r)
                    info["orig_col"] = min(info["orig_col"], c)

    bricks = [
        {
            "gid": gid,
            "rows": sorted(info["rows"]),
            "orig_col": info["orig_col"],
            "top": min(info["rows"]),
        }
        for gid, info in group_info.items()
    ]
    bricks.sort(key=lambda b: (b["orig_col"], int(b["gid"]), b["top"]))

    # 2.  Fast placement using per‑row aggregates

    aligned: Matrix = [[] for _ in range(n_rows)]

    row_max_delta: Dict[int, int] = {}  # row -> max(placed - orig)
    row_same_orig: Dict[int, Dict[int, int]] = {}  # row -> {orig_col: placed}

    for brick in bricks:
        gid, rows, ocol, top_row = (
            brick["gid"],
            brick["rows"],
            brick["orig_col"],
            brick["top"],
        )

        # 1) Parity-aligned base column.
        base_col = ocol if (ocol % 2) == (top_row % 2) else ocol + 1

        # 2) Spacing floor from row aggregates. For each touched row, a later
        # original CX cannot be placed before an earlier original CX after both
        # have been delayed by alignment.
        floor = 0
        for r in rows:
            if r in row_max_delta:
                floor = max(floor, row_max_delta[r] + ocol)

            # special case: previous brick at *same* original column
            if (same := row_same_orig.get(r, {}).get(ocol)) is not None:
                floor = max(floor, same + 1)

        # 3) Minimal column >= both base_col and floor, keeping parity.
        place = max(base_col, floor)
        if place % 2 != top_row % 2:
            place += 1

        # 4) Ensure output grid is wide enough.
        for r in aligned:
            while len(r) <= place:
                r.append([])

        # 5) Copy exactly the CX endpoints that belong to this brick.
        for r in rows:
            instrs = [
                instr
                for instr in cx_matrix[r][ocol]
                if instr.name.startswith(f"cx{gid}")
            ]
            aligned[r][place] = instrs

            # Update per-row aggregates.
            delta = place - ocol
            row_max_delta[r] = max(row_max_delta.get(r, -1), delta)
            row_same_orig.setdefault(r, {})[ocol] = place

    return aligned


def insert_rotations_adjecant_to_cx(
    aligned_cx: Matrix,
    original: Matrix,
) -> Matrix:
    """Insert rotation bricks around their neighbouring CX bricks.

    Qiskit's SU(2) decomposition emits local `rz/rx/rz` rotations between CX
    layers. After CX alignment, rotations are reattached to the nearest aligned
    neighbouring CX on the same qubit:

    - if the original left neighbour was a CX, place after that aligned CX;
    - else if the original right neighbour was a CX, place before it;
    - otherwise place in the leading all-rotation column.

    This is intentionally conservative. It avoids commuting rotations through
    CX gates, which would be a circuit optimisation and requires separate
    algebraic validation.
    """
    new_mat: Matrix = [[list(cell) for cell in row] for row in aligned_cx]

    n_rows = len(new_mat)
    if n_rows == 0:
        return new_mat

    width = max(len(r) for r in new_mat)

    # Per-row lookup: CX endpoint instruction name -> aligned column.
    cx_col: List[Dict[str, int]] = []
    for row in new_mat:
        lookup: Dict[str, int] = {}
        for c, cell in enumerate(row):
            for ins in cell:
                if ins.name.startswith("cx") and ins.name not in lookup:
                    lookup[ins.name] = c
        cx_col.append(lookup)

    for i in range(n_rows):
        row_orig = original[i]
        lookup = cx_col[i]

        for j, cell in enumerate(row_orig):
            rots = [ins for ins in cell if not ins.name.startswith("cx")]
            if not rots:
                continue

            dest = 0
            if j > 0:
                for ins in row_orig[j - 1]:
                    if ins.name.startswith("cx"):
                        dest = lookup[ins.name] + 1
                        break

            if dest == 0 and j + 1 < len(row_orig):
                for ins in row_orig[j + 1]:
                    if ins.name.startswith("cx"):
                        dest = max(lookup[ins.name] - 1, 0)
                        break

            if dest >= width:
                extra = dest - width + 1
                for r in new_mat:
                    r.extend([[]] * extra)
                width += extra

            new_mat[i][dest].extend(rots)

    return new_mat


def insert_rotations_adjacent_to_cx(aligned_cx: Matrix, original: Matrix) -> Matrix:
    """Correctly spelled alias for `insert_rotations_adjecant_to_cx`."""
    return insert_rotations_adjecant_to_cx(aligned_cx, original)


def align_bricks(cx_mat, orig):
    cx_mat_aligned = align_cx_matrix(cx_mat)
    qc_mat_aligned = insert_rotations_adjacent_to_cx(cx_mat_aligned, orig)

    return qc_mat_aligned
