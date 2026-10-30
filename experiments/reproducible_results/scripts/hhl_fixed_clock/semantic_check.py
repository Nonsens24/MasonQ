"""Check that MasonQ's aligned brick matrix implements its routed circuit (random input states)."""
import sys
import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector, random_statevector
from brickwork_transpiler import decomposer
from transpile_circuits import load


def circuit_from_matrix(mat):
    qc = QuantumCircuit(len(mat))
    for c in range(len(mat[0])):
        done = set()
        cx = {}
        for r in range(len(mat)):
            for ins in mat[r][c]:
                name = ins.name
                if name == "id":
                    continue
                if name in ("rz", "rx"):
                    getattr(qc, name)(float(ins.params[0]), r)
                else:
                    cx.setdefault(name[2:-1], {})[name[-1]] = r
        for gid, ends in cx.items():
            if gid not in done:
                qc.cx(ends["c"], ends["t"])
                done.add(gid)
    return qc


tag = sys.argv[1]
for n in map(int, sys.argv[2:]):
    qc, meta = load(tag, n)
    routed = decomposer.decompose_qc_to_bricks_qiskit(
        qc, opt=1, routing_method="sabre", layout_method="sabre", with_ancillas=True)
    qc_mat, cx_mat = decomposer.instructions_to_matrix_dag(routed)
    aligned = decomposer.align_bricks(cx_mat, qc_mat)
    rebuilt = circuit_from_matrix(aligned)
    worst = 1.0
    for seed in range(2):
        psi = random_statevector(2**routed.num_qubits, seed=seed)
        a, b = psi.evolve(routed), psi.evolve(rebuilt)
        worst = min(worst, abs(np.vdot(a.data, b.data)) ** 2)
    print(f"{tag} n={n}: rows={len(aligned)} brick columns={len(aligned[0])} "
          f"routed ops={len(routed.data)} rebuilt ops={len(rebuilt.data)} min overlap={worst:.12f}", flush=True)
