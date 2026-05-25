import pytest
from qiskit import QuantumCircuit
from brickwork_transpiler.utils import pad_with_plus_for_transpiled
from qiskit.quantum_info import Statevector

import unittest
import os
import csv
import tempfile

from brickwork_transpiler import utils
import numpy as np


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





class TestInputStateVectorExtender(unittest.TestCase):
    def test_returns_same_object_when_widths_match(self):
        """If transpiled width equals original, the function should return the same object."""
        qc = QuantumCircuit(2)
        transpiled_qc = QuantumCircuit(2)
        sv_in = Statevector.from_label('++')

        sv_out = pad_with_plus_for_transpiled(sv_in, qc, transpiled_qc)

        assert sv_out is sv_in  # exact same object
        assert sv_out.num_qubits == 2


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

from brickwork_transpiler.utils import BufferedCSVWriter


class TestBufferedCSVWriter(unittest.TestCase):

    def setUp(self):
        # Create a temporary file for each test
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()
        os.unlink(self.temp_file.name)  # Ensure it doesn't exist initially
        self.headers = ["a", "b", "c"]

    def tearDown(self):
        # Clean up temporary file after each test
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_header_written_on_init(self):
        """Ensure the header is written when the file does not exist."""
        writer = BufferedCSVWriter(self.temp_file.name, self.headers)
        with open(self.temp_file.name, newline='') as f:
            reader = csv.reader(f)
            header = next(reader)
        self.assertEqual(header, self.headers)

    def test_flush_writes_row(self):
        """Ensure flush() writes a buffered row to the CSV file."""
        writer = BufferedCSVWriter(self.temp_file.name, self.headers)
        writer.set("a", 1)
        writer.set("b", 2)
        writer.flush()

        with open(self.temp_file.name, newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["a"], "1")
        self.assertEqual(rows[0]["b"], "2")
        self.assertEqual(rows[0]["c"], "")  # Missing field should be empty string

    def test_row_buffer_cleared_after_flush(self):
        """Ensure the buffer is cleared after flushing."""
        writer = BufferedCSVWriter(self.temp_file.name, self.headers)
        writer.set("a", 42)
        writer.flush()
        self.assertEqual(writer.row, {})


from brickwork_transpiler.utils import (
    index_to_coordinates,
    map_indices_to_coordinates,
    get_qubit_entries,
    get_qiskit_permutation,
)

class DummyBWPattern:
    """Mock object to simulate bw_pattern with output_nodes."""
    def __init__(self, output_nodes):
        self.output_nodes = output_nodes


class TestHelperFunctions(unittest.TestCase):

    def test_index_to_coordinates_basic(self):
        """Check correct (row, col) mapping in a simple grid."""
        self.assertEqual(index_to_coordinates(0, 3), (0, 0))
        self.assertEqual(index_to_coordinates(2, 3), (0, 2))
        self.assertEqual(index_to_coordinates(3, 3), (1, 0))
        self.assertEqual(index_to_coordinates(7, 3), (2, 1))

    def test_index_to_coordinates_edge(self):
        """Ensure correct behavior for single-column or single-row cases."""
        self.assertEqual(index_to_coordinates(5, 1), (5, 0))  # single column
        self.assertEqual(index_to_coordinates(4, 10), (0, 4))  # single row

    def test_map_indices_to_coordinates(self):
        """Verify mapping for a list of indices."""
        indices = [0, 1, 2, 3]
        result = map_indices_to_coordinates(indices, 2)
        expected = {0: (0, 0), 1: (0, 1), 2: (1, 0), 3: (1, 1)}
        self.assertEqual(result, expected)

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

