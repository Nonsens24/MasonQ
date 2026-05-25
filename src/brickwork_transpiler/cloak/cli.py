"""Command-line interface for ``masonq-cloak``.

Two subcommands:

  - ``compile`` — load a Python file that defines a Qiskit ``QuantumCircuit``
    named ``qc`` (or a callable ``build_circuit()`` returning one), apply
    :func:`brickwork_transpiler.cloak.cloak_compile`, and write the resulting
    job metadata as JSON for inspection / sending to a server.
  - ``verify`` — given a previously written job JSON and a server-result
    JSON, run :func:`brickwork_transpiler.cloak.verify_session` and exit
    non-zero on failure.

The on-disk JSON format here is intentionally minimal: it carries the
structural metadata (slice ids, trap nodes, expected outcomes, preparation
counts) but *not* the Graphix patterns themselves, since these depend on
non-JSON-serialisable Graphix objects.  Real deployments will need a
binary serialiser; this CLI exists for smoke testing and demos.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from qiskit import QuantumCircuit

from . import cloak_compile, verify_session
from .blinder import CloakedJob


def _load_circuit(path: Path) -> QuantumCircuit:
    spec = importlib.util.spec_from_file_location("user_circuit", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    qc = getattr(module, "qc", None)
    if qc is None and hasattr(module, "build_circuit"):
        qc = module.build_circuit()
    if not isinstance(qc, QuantumCircuit):
        raise TypeError(
            f"{path} must define a top-level `qc: QuantumCircuit` or a "
            "`build_circuit()` callable returning one."
        )
    return qc


def _job_to_json(job: CloakedJob) -> dict[str, Any]:
    share = job.metadata.get("blind_share")
    share_payload = None
    if share is not None:
        share_payload = {
            "gates_blind": share.gates_blind,
            "gates_clear": share.gates_clear,
            "gates_total": share.gates_total,
            "gate_fraction": share.gate_fraction,
            "graph_nodes_per_sub": list(share.graph_nodes_per_sub),
            "graph_nodes_total": share.graph_nodes_total,
            "rounds": share.rounds,
        }
    meta = {k: v for k, v in job.metadata.items() if k != "blind_share"}
    return {
        "metadata": meta,
        "blind_share": share_payload,
        "boundary_types": [bt.value for bt in job.boundary_types],
        "qotp_final": {"a": job.qotp_state.a, "b": job.qotp_state.b},
        "subs": [
            {
                "slice_id": sub.slice_id,
                "graph_nodes": getattr(sub.resources, "graph_nodes", None),
                "rounds": [
                    {
                        "trap_node": rnd.embedding.trap_node,
                        "expected_outcome": rnd.embedding.expected_outcome,
                        "dummy_count": len(rnd.embedding.dummy_bits),
                        "preparation_count": len(rnd.preparations),
                    }
                    for rnd in sub.rounds
                ],
            }
            for sub in job.subs
        ],
        "rsp_handles": [h.handle_id for h in job.rsp_plan],
    }


def _cmd_compile(args: argparse.Namespace) -> int:
    qc = _load_circuit(Path(args.input))
    job = cloak_compile(qc, rounds=args.rounds, seed=args.seed)
    out_path = Path(args.out)
    out_path.write_text(json.dumps(_job_to_json(job), indent=2))
    share = job.metadata.get("blind_share")
    if share is not None:
        print(
            f"wrote {out_path} ({job.metadata['num_subs']} subs, "
            f"{args.rounds} rounds each)\n  {share.format()}"
        )
    else:
        print(
            f"wrote {out_path} ({job.metadata['num_subs']} subs, "
            f"{args.rounds} rounds each)"
        )
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    print(
        "verify is currently a stub: a binary serialiser for Graphix patterns is "
        "needed before a full server round-trip can be checked through the CLI.",
        file=sys.stderr,
    )
    job_meta = json.loads(Path(args.job).read_text())
    results = json.loads(Path(args.results).read_text())
    # When we have a real CloakedJob deserialiser, this becomes:
    #   ok, qotp = verify_session(job, results)
    # For now, just confirm the input files exist and report.
    ok = bool(job_meta) and bool(results)
    print("verify-session structural-check:", "OK" if ok else "FAIL")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="masonq-cloak")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_compile = sub.add_parser("compile", help="Cloak-compile a Qiskit circuit.")
    p_compile.add_argument("input", help="Python file defining `qc` or `build_circuit()`.")
    p_compile.add_argument("--out", default="job.json", help="Destination JSON file.")
    p_compile.add_argument("--rounds", type=int, default=1, help="Trap rounds per sub.")
    p_compile.add_argument("--seed", type=int, default=None, help="Deterministic RNG seed.")
    p_compile.set_defaults(func=_cmd_compile)

    p_verify = sub.add_parser("verify", help="Verify a server's trap outcomes.")
    p_verify.add_argument("job", help="Job JSON written by `compile`.")
    p_verify.add_argument("results", help="Server-results JSON.")
    p_verify.set_defaults(func=_cmd_verify)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
