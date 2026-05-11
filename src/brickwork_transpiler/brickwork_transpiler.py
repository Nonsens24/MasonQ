import logging

from qiskit import QuantumCircuit
from . import decomposer, graph_builder, pattern_converter
from .resources import estimate_resources
from .result import TranspileResult
from .sparse import SparseInstructionMatrix
from .validation import (
    validate_brickwork_graph_data,
    validate_instruction_matrix,
    validate_pattern_outputs,
)

logger = logging.getLogger(__name__)


def transpile(
    qc: QuantumCircuit,
    input_vector=None,
    routing_method=None,
    layout_method=None,
    return_mat: bool = False,
    file_writer=None,
    with_ancillas=True,
    plot_decomposed: bool = False,
    opt=3,
    verbose: bool = False,
    multi_control_strategy: str = "hls",
    fallback_opt: int | None = 1,
    validate: bool = True,
    return_result: bool = False,
    return_stage: str | None = None,
):
    """Transpile a Qiskit circuit into a Graphix brickwork pattern.

    The default return value is the historical tuple
    `(pattern, colour_map, decomposed_circuit)`. Set `return_result=True` for a
    named `TranspileResult`. Use `return_stage` to stop at an intermediate
    representation such as `"decomposed_circuit"`, `"matrix"`, `"resources"`,
    `"sparse_matrix"`, `"graph_data"`, or `"networkx_graph"`.
    """
    if verbose:
        logging.basicConfig(level=logging.INFO)
    if return_mat:
        return_stage = "matrix"
    valid_stages = {
        None,
        "decomposed_circuit",
        "matrix",
        "instruction_matrix",
        "sparse_matrix",
        "resources",
        "graph_data",
        "networkx_graph",
    }
    if return_stage not in valid_stages:
        raise ValueError(
            "return_stage must be one of None, 'decomposed_circuit', 'matrix', "
            "'instruction_matrix', 'sparse_matrix', 'resources', 'graph_data', "
            "or 'networkx_graph'."
        )

    # Decompose to CX, rzrxrz, id   -   Need opt = 3 for SU(2) rotation merging
    logger.info("Decomposing circuit...")
    decomposed_qc = decomposer.decompose_qc_to_bricks_qiskit(
        qc,
        opt=opt,
        routing_method=routing_method,
        layout_method=layout_method,
        file_writer=file_writer,
        with_ancillas=with_ancillas,
        draw=plot_decomposed,
        verbose=verbose,
        multi_control_strategy=multi_control_strategy,
        fallback_opt=fallback_opt,
    )
    if return_stage == "decomposed_circuit":
        return decomposed_qc

    logger.info("Creating instruction matrix from DAG...")
    # Optimise Instruction matrix with dependency graph
    qc_mat, cx_mat = decomposer.instructions_to_matrix_dag(decomposed_qc)

    logger.info("Aligning instruction matrix...")
    # Align gates according to brickwork topology
    qc_mat_aligned = decomposer.align_bricks(cx_mat, qc_mat)
    if validate:
        validate_instruction_matrix(qc_mat_aligned)

    if return_stage in {"matrix", "instruction_matrix"}:
        return qc_mat_aligned
    if return_stage == "sparse_matrix":
        return SparseInstructionMatrix.from_dense(qc_mat_aligned)
    if return_stage == "resources":
        return estimate_resources(decomposed_qc, qc_mat_aligned)

    logger.info("Building graph structure...")
    # Build the graph from the optimised and formatted instruction matrix
    bw_graph_data = graph_builder.generate_brickwork_graph_from_instruction_matrix(qc_mat_aligned)
    if validate:
        validate_brickwork_graph_data(
            bw_graph_data,
            rows=len(qc_mat_aligned),
            brick_cols=len(qc_mat_aligned[0]) if qc_mat_aligned else 0,
        )
    if return_stage == "graph_data":
        return bw_graph_data

    # Get the networkx graph structure
    bw_nx_graph = graph_builder.to_networkx_graph(bw_graph_data)
    if return_stage == "networkx_graph":
        return bw_nx_graph

    # Add angles and convert to Graphix pattern
    logger.info("Calculating measurement dependencies...")
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
    if return_result:
        return result
    return tuple(result)
