"""Public entry point: a Qiskit circuit in, a Graphix brickwork pattern out."""

import logging
from collections.abc import Callable

from qiskit import QuantumCircuit

from . import decomposer, graph_builder, pattern_converter
from .progress import ProgressReporter
from .resources import estimate_resources
from .result import TranspileResult
from .sparse import SparseInstructionMatrix
from .validation import (
    validate_brickwork_graph_data,
    validate_instruction_matrix,
    validate_pattern_outputs,
)

logger = logging.getLogger(__name__)

_STAGES = (
    "decomposed_circuit",
    "matrix",
    "instruction_matrix",
    "sparse_matrix",
    "resources",
    "graph_data",
    "networkx_graph",
)


def transpile(
    qc: QuantumCircuit,
    input_vector=None,
    *,
    routing_method: str | None = None,
    layout_method: str | None = None,
    with_ancillas: bool = True,
    opt: int = 3,
    multi_control_strategy: str = "hls",
    fallback_opt: int | None = 1,
    validate: bool = True,
    return_result: bool = False,
    return_stage: str | None = None,
    progress: bool | Callable[[str], None] = False,
):
    """Transpile a Qiskit circuit into a Graphix brickwork pattern.

    The pattern prepares every qubit in |+>, so it computes U|+...+>.
    `input_vector` is only stored on the result as the reference input of
    `verify()`; leave it `None` (the default, |+>^n) unless you want to be
    explicit.

    The default return value is the historical tuple
    `(pattern, colour_map, decomposed_circuit)`. Set `return_result=True` for a
    named `TranspileResult`. Use `return_stage` to stop at an intermediate
    representation: `"decomposed_circuit"`, `"matrix"`, `"sparse_matrix"`,
    `"resources"`, `"graph_data"` or `"networkx_graph"`.
    """
    if return_stage is not None and return_stage not in _STAGES:
        raise ValueError(
            "return_stage must be None or one of: " + ", ".join(repr(s) for s in _STAGES) + "."
        )
    reporter = ProgressReporter(progress)
    reporter.emit(
        f"Starting transpilation: {qc.num_qubits} qubits, "
        f"{sum(qc.count_ops().values())} operations."
    )

    # Decompose to CX, rzrxrz, id   -   Need opt = 3 for SU(2) rotation merging
    logger.info("Decomposing circuit...")
    with reporter.step(
        "Decomposing and routing circuit with Qiskit.",
        "Qiskit decomposition complete",
    ):
        decomposed_qc = decomposer.decompose_qc_to_bricks_qiskit(
            qc,
            opt=opt,
            routing_method=routing_method,
            layout_method=layout_method,
            with_ancillas=with_ancillas,
            multi_control_strategy=multi_control_strategy,
            fallback_opt=fallback_opt,
        )
    if return_stage == "decomposed_circuit":
        reporter.emit("Returning decomposed circuit.")
        return decomposed_qc

    logger.info("Creating instruction matrix from DAG...")
    with reporter.step(
        "Building dependency-ordered instruction matrix.",
        "Instruction matrix built",
    ):
        qc_mat, cx_mat = decomposer.instructions_to_matrix_dag(decomposed_qc)

    logger.info("Aligning instruction matrix...")
    with reporter.step("Aligning gates to brickwork columns.", "Brickwork alignment complete"):
        qc_mat_aligned = decomposer.align_bricks(cx_mat, qc_mat)
        if validate:
            validate_instruction_matrix(qc_mat_aligned)

    if return_stage in {"matrix", "instruction_matrix"}:
        reporter.emit("Returning dense instruction matrix.")
        return qc_mat_aligned
    if return_stage == "sparse_matrix":
        reporter.emit("Returning sparse instruction matrix.")
        return SparseInstructionMatrix.from_dense(qc_mat_aligned)
    if return_stage == "resources":
        reporter.emit("Returning resource estimate.")
        return estimate_resources(decomposed_qc, qc_mat_aligned)

    logger.info("Building graph structure...")
    with reporter.step("Building brickwork graph data.", "Brickwork graph data built"):
        bw_graph_data = graph_builder.generate_brickwork_graph_from_instruction_matrix(
            qc_mat_aligned
        )
        if validate:
            validate_brickwork_graph_data(
                bw_graph_data,
                rows=len(qc_mat_aligned),
                brick_cols=len(qc_mat_aligned[0]) if qc_mat_aligned else 0,
            )
    if return_stage == "graph_data":
        reporter.emit("Returning graph data.")
        return bw_graph_data

    with reporter.step("Converting graph data to NetworkX graph.", "NetworkX graph built"):
        bw_nx_graph = graph_builder.to_networkx_graph(bw_graph_data)
    if return_stage == "networkx_graph":
        reporter.emit("Returning NetworkX graph.")
        return bw_nx_graph

    logger.info("Calculating measurement angles and building the pattern...")
    with reporter.step("Converting graph to Graphix pattern.", "Graphix pattern built"):
        bw_pattern, col_map = pattern_converter.to_pattern(qc_mat_aligned, bw_nx_graph)
        if validate:
            validate_pattern_outputs(
                bw_pattern,
                rows=len(qc_mat_aligned),
                brick_cols=len(qc_mat_aligned[0]) if qc_mat_aligned else 0,
            )

    result = TranspileResult(
        pattern=bw_pattern,
        colour_map=col_map,
        decomposed_circuit=decomposed_qc,
        instruction_matrix=qc_mat_aligned,
        source_circuit=qc,
        input_state=input_vector,
    )
    reporter.emit("Transpilation complete.")
    if return_result:
        return result
    return tuple(result)
