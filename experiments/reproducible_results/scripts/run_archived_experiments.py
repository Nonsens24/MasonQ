"""Run the archived experiment code of this branch for the first few problem sizes.

The scripts in src/brickwork_transpiler/experiments/ have no command-line entry points:
they were driven from an IDE, import the package as `src.brickwork_transpiler` (so the
repository root must be on sys.path) and write their CSVs to a path relative to the current
directory. This driver reproduces those conditions from a scratch directory, so that nothing
inside the repository is written to.

Environment: the one recorded in requirements-lock.txt at the repository root (Qiskit 0.46.3,
Graphix 0.3.1, NumPy 2.2.6, Python 3.11). The HHL step also needs the `linear_solvers`
package (Qiskit's HHL reference implementation).

usage:
    python run_archived_experiments.py <repository root> <scratch dir> <step> [<step> ...]

steps:
    qft    the loop that produced experiments_qft.csv, for n = 3..10 (it is commented out in
           the archived qft_transpilation.py; the loop below is that code)
    full   QRS with database encoding, single match (experiments_qrs_full_one_match.csv),
           first three database sizes L = 4, 8, 16
    nodb   QRS inference only, single match (experiments_qrs_no_db_one_match.csv), first
           three sizes. The 5 August 2025 run had the database-initialisation call inside
           qrs() commented out (commit d9dc034); at this branch's base that call is active
           again, so the driver disables it the same way.
    hhl    the live loop of hhl_transpilation.py (normalised Laplacian of a random 2-regular
           graph, seed 0; Qiskit HHL defaults; opt=1; with ancillas), n = 2, 3

The outputs appear under <scratch dir>/src/ubqc_brickwork_transpiler/experiments/data/output_data/.
Compare them with the files in ../data: gate counts should match exactly, brick depths to
within the SABRE routing noise (see ../README.md, section 5).
"""
import csv
import os
import sys
import time


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    root, scratch, steps = sys.argv[1], sys.argv[2], set(sys.argv[3:])
    sys.path.insert(0, root)
    for sub in ("src/ubqc_brickwork_transpiler", "src/brickwork_transpiler"):
        os.makedirs(os.path.join(scratch, sub, "experiments", "data", "output_data"), exist_ok=True)
    os.chdir(scratch)

    import src.brickwork_transpiler.utils as utils
    from src.brickwork_transpiler import brickwork_transpiler

    class TolerantWriter(utils.BufferedCSVWriter):
        """The code at this commit also writes a `d_avg` column, added for the October 2025
        HHL runs, which the older QFT and QRS CSV headers do not have."""

        def flush(self):
            with open(self.filename, "a", newline="") as fh:
                csv.DictWriter(fh, fieldnames=self.headers, restval="",
                               extrasaction="ignore").writerow(self.row)
            self.row = {}

    utils.BufferedCSVWriter = TolerantWriter

    def timed(label, fn):
        t0 = time.time()
        fn()
        print(f"{label} done ({time.time() - t0:.0f}s)", flush=True)

    if "qft" in steps:
        from qiskit.circuit.library import QFT
        from src.brickwork_transpiler.experiments import qft_transpilation as qft

        def run_qft():
            writer = qft.get_writer("experiments_qft.csv")
            for n in range(3, 11):
                qc = QFT(num_qubits=n, approximation_degree=0, do_swaps=True, inverse=False,
                         name=f"QFT_{n}")
                mat = brickwork_transpiler.transpile(qc, routing_method="sabre", layout_method="sabre",
                                                     return_mat=True, file_writer=writer)
                writer.set("transpiled_depth", len(mat[0]))
                writer.set("original_depth", qc.depth())
                writer.flush()
        timed("qft", run_qft)

    if "full" in steps:
        from src.brickwork_transpiler.experiments import qrs_full_transpilation as full

        def run_full():
            original = full.get_data
            full.get_data = lambda: original()[:3]
            full.experiment_qrs_full_one_matching_element()
        timed("full", run_full)

    if "nodb" in steps:
        from src.brickwork_transpiler.experiments import qrs_no_db_transpilation as nodb

        def run_nodb():
            nodb.qrs_knn_grover.initialise_database = lambda qc, *a, **k: qc
            original = nodb.get_data
            nodb.get_data = lambda: original()[:3]
            nodb.experiment_qrs_no_db_one_matching_element()
        timed("nodb", run_nodb)

    if "hhl" in steps:
        from src.brickwork_transpiler.experiments import hhl_transpilation as hhl

        def run_hhl():
            hhl.plot_single_hhl_dataset = lambda *a, **k: None
            hhl.experiment_hhl_transpilation(max_qubits=3)
        timed("hhl", run_hhl)


if __name__ == "__main__":
    main()
