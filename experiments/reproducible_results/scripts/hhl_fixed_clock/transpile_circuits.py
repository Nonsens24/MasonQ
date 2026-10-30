"""Transpile exported HHL circuits with the current MasonQ (masonq-qiskit24 env) and append to a CSV.

usage: python transpile_circuits.py TAG N_FIRST N_LAST OUT_CSV
"""
import csv, json, sys, time
from pathlib import Path

from qiskit import QuantumCircuit
from brickwork_transpiler import brickwork_transpiler

HERE = Path(__file__).resolve().parent
FIELDS = ["N", "n", "nl", "epsilon", "width", "num_gates_original", "original_depth", "transpiled_depth",
          "fidelity", "seconds"]


def load(tag, n):
    data = json.loads((HERE / f"{tag}_n{n}.json").read_text())
    meta = data["meta"]
    qc = QuantumCircuit(meta["width"])
    for name, params, qubits in data["ops"]:
        getattr(qc, name)(*params, *qubits)
    assert len(qc.data) == meta["num_gates_original"]
    return qc, meta


def main():
    tag, first, last, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4])
    new = not out.exists()
    with out.open("a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        for n in range(first, last + 1):
            qc, meta = load(tag, n)
            t0 = time.time()
            matrix = brickwork_transpiler.transpile(
                qc, routing_method="sabre", layout_method="sabre", return_stage="matrix",
                with_ancillas=True, opt=1,
            )
            row = {k: meta.get(k, "") for k in FIELDS}
            row["transpiled_depth"] = len(matrix[0])
            row["seconds"] = round(time.time() - t0, 1)
            writer.writerow(row)
            fh.flush()
            print(row, flush=True)


if __name__ == "__main__":
    main()
