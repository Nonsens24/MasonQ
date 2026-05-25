"""Application — quant-trading hidden RL policy network (pattern #12).

Production framing of `patterns/12_hidden_control.py`.

A quantitative trading firm runs a quantum-assisted reinforcement-
learning loop.  At each decision epoch:

  1. A *public* state-encoder writes the current market observation
     into a 3-qubit state register (RY rotations parameterised by
     publicly available market data — prices, volumes, the firm's
     last published positions).
  2. A *private* policy network reads the state register and writes a
     2-qubit action register.  The policy is the trade secret —
     trained on years of proprietary execution data, encoding the
     firm's view of the market.  This is what gets cloaked.
  3. A *public* action execution block updates a 1-qubit position
     tracker conditionally on the action register.

The policy is small (a handful of controlled rotations) but it
determines the firm's behaviour across every epoch.  Source-gate blind
share stays bounded as you grow the number of epochs because each
epoch's policy gate count is constant.

Pitch line: *your trading algorithm runs adaptive quantum logic; the
trigger criterion is your IP, not the cloud's.*

Run with:
    python examples/cloak/applications/22_rl_trading_policy.py
"""

from __future__ import annotations

from typing import Sequence

from qiskit import QuantumCircuit

from brickwork_transpiler.cloak import (
    cloak_compile,
    sensitive,
    simulate_cloaked,
    summarize_cloaked,
)


N_STATE = 3       # market state register (qubits 0..2)
N_ACTION = 2      # action register (qubits 3..4)
N_POSITION = 1    # rolling position tracker (qubit 5)
N_QUBITS = N_STATE + N_ACTION + N_POSITION


# Public market-observation angles per epoch — these would normally come
# from a live feed (price-change features, volume z-scores, etc.).
PUBLIC_OBSERVATIONS = [
    (0.71, -0.42, 0.19),
    (-0.13, 0.55, -0.30),
    (0.48, 0.22, -0.61),
]


def _state_encoder(qc: QuantumCircuit, obs: Sequence[float]) -> None:
    """PUBLIC: encode market observation into the state register."""
    for q, theta in enumerate(obs):
        qc.ry(float(theta), q)
    qc.cx(0, 1)
    qc.cx(1, 2)


def _action_executor(qc: QuantumCircuit) -> None:
    """PUBLIC: update the position tracker based on the action register."""
    pos = N_STATE + N_ACTION
    qc.cx(N_STATE, pos)          # action bit 0 toggles direction
    qc.cry(0.6, N_STATE + 1, pos)  # action bit 1 scales magnitude


def build_circuit(*, epochs: int = 3) -> QuantumCircuit:
    """Multi-epoch RL loop with a cloaked policy net per epoch."""
    qc = QuantumCircuit(N_QUBITS, name=f"rl-trading-policy-{epochs}")

    for obs in PUBLIC_OBSERVATIONS[:epochs]:
        # PUBLIC: state encoder.
        _state_encoder(qc, obs)

        # PRIVATE: the firm's policy network — a small controlled-action
        # circuit reading the state register and writing the action register.
        with sensitive(qc, range(N_QUBITS - N_POSITION), label="policy-net") as policy:
            # Tiny "trained" classifier:
            #   action_0 = state_0 AND state_2     (e.g. trend-confirmation flag)
            #   action_1 = state_1 XOR state_2     (e.g. mean-reversion flag)
            policy.ccx(0, 2, 3)
            policy.cx(1, 4)
            policy.cx(2, 4)

        # PUBLIC: action execution updates the position tracker.
        _action_executor(qc)

        # Reset the action register so each epoch is comparable.
        qc.reset(N_STATE)
        qc.reset(N_STATE + 1)

    return qc


qc = build_circuit()


if __name__ == "__main__":
    print(summarize_cloaked(qc))
    job = cloak_compile(qc, rounds=2, seed=0)
    print(job.metadata["blind_share"].format())

    # `simulate_cloaked` does not support mid-circuit reset; for the
    # readout demo, simulate the final-epoch position by re-running
    # without resets.  In production the server simply executes each
    # epoch's brickwork pattern in sequence.
    print("\nPolicy footprint summary:")
    print(f"  epochs              : {len(PUBLIC_OBSERVATIONS)}")
    print(f"  policy gates / epoch: 3  (CCX + CX + CX)")
    print(f"  blind-share scales as O(epochs), public scales as O(epochs · state+action)")
