import unittest

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from brickwork_transpiler import utils
from brickwork_transpiler.utils import (
    get_qiskit_permutation,
    get_qubit_entries,
    pad_with_plus_for_transpiled,
)


def test_identical_states():
    a = [1, 0]
    b = [1, 0]

    assert utils.assert_equal_up_to_global_phase(a, b) is True


def test_global_phase_equivalence():
    a = [1/np.sqrt(2), 1j/np.sqrt(2)]
    global_phase = np.exp(1j * np.pi / 4)
    b = [x * global_phase for x in a]

    assert utils.assert_equal_up_to_global_phase(a, b) is True


def test_not_equal_states():
    a = [1, 0]
    b = [0, 1]

    with pytest.raises(
        AssertionError,
        match="States are not equal up to global phase"
    ):
        utils.assert_equal_up_to_global_phase(a, b)


def test_zero_norm_vector_raises():
    a = [0, 0]
    b = [1, 0]

    with pytest.raises(
        AssertionError,
        match=r"One of the states' norms is zero \(cannot compare\)"
    ):
        utils.assert_equal_up_to_global_phase(a, b)


def test_numerical_tolerance():
    a = [1/np.sqrt(2), 1/np.sqrt(2)]
    noise = 1e-7
    b = [1/np.sqrt(2) + noise, 1/np.sqrt(2) - noise]

    assert utils.assert_equal_up_to_global_phase(a, b, tol=1e-5) is True


def test_at_border_tolerance():
    a = [1/np.sqrt(2), 1/np.sqrt(2)]
    noise = 1e-6
    b = [1/np.sqrt(2) + noise, 1/np.sqrt(2) - noise]

    assert utils.assert_equal_up_to_global_phase(a, b) is True


def test_next_to_border_tolerance():
    a = [1/np.sqrt(2), 1/np.sqrt(2)]

    # make noise large enough that epsilon^2 > 1e-6
    noise = 1e-3 + 1e-4
    b = [1/np.sqrt(2) + noise, 1/np.sqrt(2) - noise]

    with pytest.raises(AssertionError):
        utils.assert_equal_up_to_global_phase(a, b)


def test_global_phase_4d():
    # a 4-dimensional state
    raw = np.array([1, 1j, -1, 0.5j], dtype=complex)
    state = raw / np.linalg.norm(raw)

    # apply a π/3 global phase
    phase = np.exp(1j * np.pi / 3)
    phased = phase * state

    # should return True
    assert utils.assert_equal_up_to_global_phase(state, phased) is True


def test_state_overlap_accepts_statevectors_and_arrays():
    sv = Statevector.from_label("+")
    overlap = utils.state_overlap(sv, np.asarray(sv.data))
    assert overlap == pytest.approx(1.0)


class TestInputStateVectorExtender(unittest.TestCase):
    def test_returns_same_object_when_widths_match(self):
        """If transpiled width equals original, the function should return the same object."""
        qc = QuantumCircuit(2)
        transpiled_qc = QuantumCircuit(2)
        sv_in = Statevector.from_label('++')

        sv_out = pad_with_plus_for_transpiled(sv_in, qc, transpiled_qc)

        assert sv_out is sv_in  # exact same object
        assert sv_out.num_qubits == 2

    def test_array_input_is_converted(self):
        """A plain array of amplitudes is accepted and converted to a Statevector."""
        qc = QuantumCircuit(1)
        transpiled_qc = QuantumCircuit(1)

        sv_out = pad_with_plus_for_transpiled(np.array([1.0, 0.0]), qc, transpiled_qc)

        assert isinstance(sv_out, Statevector)
        assert sv_out.num_qubits == 1

    def test_raises_when_transpiled_smaller_than_original(self):
        """If transpiled circuit has fewer qubits, raise ValueError."""
        qc = QuantumCircuit(3)
        transpiled_qc = QuantumCircuit(2)
        sv_in = Statevector.from_label('+++')

        with pytest.raises(ValueError, match="fewer qubits"):
            _ = pad_with_plus_for_transpiled(sv_in, qc, transpiled_qc)

    def test_input_is_unmodified_and_output_is_distinct_when_padding_occurs(self):
        """When k>0, the function must not mutate sv_in, and must return a different object."""
        qc = QuantumCircuit(1)
        transpiled_qc = QuantumCircuit(3)
        sv_in = Statevector.from_label('0')
        sv_in_copy = Statevector(sv_in.data.copy(), dims=[2])

        sv_out = pad_with_plus_for_transpiled(sv_in, qc, transpiled_qc)

        # Original unchanged
        assert np.allclose(sv_in.data, sv_in_copy.data)
        # Different object when padding happens
        assert sv_out is not sv_in
        # Correct dimension
        assert sv_out.num_qubits == 3


class DummyBWPattern:
    """Mock object to simulate bw_pattern with output_nodes."""
    def __init__(self, output_nodes):
        self.output_nodes = output_nodes


class TestHelperFunctions(unittest.TestCase):

    def test_get_qubit_entries_valid(self):
        """Ensure correct extraction of qubit indices from bw_pattern."""
        bw_pattern = DummyBWPattern(output_nodes=[(0,), (2,), (4,)])
        self.assertEqual(get_qubit_entries(bw_pattern), [0, 2, 4])

    def test_get_qubit_entries_none(self):
        """Ensure None input raises AssertionError."""
        with self.assertRaises(AssertionError):
            get_qubit_entries(None)

    def test_get_qiskit_permutation_valid(self):
        """Test permutation from bw_pattern matches Qiskit inversion logic."""
        bw_pattern = DummyBWPattern(output_nodes=[(0,), (1,), (2,)])
        result = get_qiskit_permutation(bw_pattern)
        self.assertEqual(result, [2, 1, 0])  # reversed and inverted

    def test_get_qiskit_permutation_none(self):
        """Ensure None input raises AssertionError."""
        with self.assertRaises(AssertionError):
            get_qiskit_permutation(None)
