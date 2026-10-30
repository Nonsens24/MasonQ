"""Build Toeplitz HHL circuits (B-QML env: qiskit 0.46 + linear_solvers) and export them as JSON.

Mirrors linear_solvers.HHL.construct_circuit (exact reciprocal, neg_vals=True, epsilon=1e-2)
except that the clock register size nl is a parameter. Qiskit's default is nl = n + 2.

usage: python build_circuits.py NL N_MAX [FIDELITY_N_MAX] [EPSILON]   (NL = "default" for n + 2)

EPSILON (default 1e-2) is HHL's epsilon; for the Toeplitz matrix it only sets the Hamiltonian
simulation tolerance epsilon/6, from which the Trotter step count ~ epsilon^(-1/2) follows.
"""
import json, sys, time, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import numpy as np
from qiskit import QuantumCircuit, QuantumRegister, AncillaRegister
from qiskit.circuit.library import PhaseEstimation, ExactReciprocal
from qiskit.quantum_info import Statevector
from linear_solvers import HHL
from linear_solvers.matrices import TridiagonalToeplitz

OUT = Path(__file__).resolve().parent


def toeplitz_hhl(n, nl, epsilon=1e-2):
    A = TridiagonalToeplitz(n, 1.0, -1 / 6, trotter_steps=2)
    A.tolerance = epsilon / 6                   # HHL's epsilon_a; HHL resets the Trotter steps from it
    lmin, lmax = A.eigs_bounds()
    delta = HHL()._get_delta(nl - 1, lmin, lmax)
    A.evolution_time = 2 * np.pi * delta / lmin / 2
    recip = ExactReciprocal(nl, delta, neg_vals=True)
    na = A.num_ancillas
    qb, ql, qf = QuantumRegister(n, "b"), QuantumRegister(nl, "clock"), QuantumRegister(1, "flag")
    qa = AncillaRegister(na, "anc") if na else None
    qc = QuantumCircuit(*([qb, ql] + ([qa] if qa else []) + [qf]))
    qc.h(qb)                                    # |b> = uniform superposition
    pe = PhaseEstimation(nl, A)
    tgt = ql[:] + qb[:] + (qa[:] if qa else [])
    qc.append(pe, tgt)
    qc.append(recip, ql[::-1] + [qf[0]])
    qc.append(pe.inverse(), tgt)
    return qc, A.matrix


def sel_decompose(qc, keep=("mcx", "mcu1", "mcphase")):
    """Expand every composite gate, keeping multi-controlled gates whole (as in the experiments)."""
    out = QuantumCircuit(qc.num_qubits)
    for ins in qc.data:
        op = ins.operation
        qubits = [qc.find_bit(q).index for q in ins.qubits]
        if op.name.lower() in keep or not op.definition:
            out.append(op, qubits)
        else:
            out.compose(sel_decompose(op.definition, keep), qubits=qubits, inplace=True)
    return out


def solution_fidelity(qc, matrix, n, nl):
    """Overlap of the post-selected HHL output with A^-1 b (flag = 1, clock and ancillas = 0)."""
    psi = Statevector(qc).data
    width = qc.num_qubits
    flag_bit = 1 << (width - 1)
    amps = np.array([psi[flag_bit | k] for k in range(2**n)])
    x = np.linalg.solve(matrix, np.ones(2**n) / np.sqrt(2**n))
    x /= np.linalg.norm(x)
    return float(abs(np.vdot(x, amps / np.linalg.norm(amps))) ** 2), float(np.linalg.norm(amps) ** 2)


def main():
    nl_arg, n_max = sys.argv[1], int(sys.argv[2])
    fid_max = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    epsilon = float(sys.argv[4]) if len(sys.argv) > 4 else 1e-2
    tag = "default" if nl_arg == "default" else f"nl{nl_arg}"
    if len(sys.argv) > 4:
        tag += f"_eps{epsilon:g}"
    for n in range(1, n_max + 1):
        t0 = time.time()
        nl = n + 2 if nl_arg == "default" else int(nl_arg)
        qc, matrix = toeplitz_hhl(n, nl, epsilon)
        flat = sel_decompose(qc)
        ops = [[i.operation.name, [float(p) for p in i.operation.params],
                [flat.find_bit(q).index for q in i.qubits]] for i in flat.data]
        names = {o[0] for o in ops}
        assert names <= {"u", "cx", "h"}, f"unexpected gates {names}"
        meta = {"n": n, "N": 2**n, "nl": nl, "epsilon": epsilon, "width": flat.num_qubits,
                "num_gates_original": len(ops), "original_depth": qc.depth()}
        if n <= fid_max:
            meta["fidelity"], meta["success_probability"] = solution_fidelity(qc, matrix, n, nl)
        (OUT / f"{tag}_n{n}.json").write_text(json.dumps({"meta": meta, "ops": ops}))
        print(json.dumps(meta), f"({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
