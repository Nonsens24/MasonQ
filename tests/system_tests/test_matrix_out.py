import unittest

import qiskit

from brickwork_transpiler import brickwork_transpiler, circuits
from brickwork_transpiler.cx_tags import cx_role, is_cx_endpoint
from brickwork_transpiler.validation import validate_instruction_matrix


class TestMatrixOut(unittest.TestCase):
    """The dense matrix stage of a 4-qubit QFT, with and without package ancillas.

    The width depends on Qiskit's synthesis (79 columns on Qiskit 2.4, 81 on
    2.6), so the shape is checked structurally rather than against fixed numbers.
    """

    # Helper 3d List assertion
    def assert_is_3d_list_of(self, return_matrix, elem_type):
        assert isinstance(return_matrix, list)
        for level1 in return_matrix:
            assert isinstance(level1, list)
            for level2 in level1:
                assert isinstance(level2, list)
                for item in level2:
                    assert isinstance(item, elem_type), f"Expected {elem_type}, got {type(item)}"
        return True

    def _check_qft4_matrix(self, with_ancillas):
        experiment, _ = circuits.qft(4)
        options = dict(routing_method="basic", layout_method="trivial", with_ancillas=with_ancillas)
        return_matrix = brickwork_transpiler.transpile(experiment, return_stage="matrix", **options)
        resources = brickwork_transpiler.transpile(experiment, return_stage="resources", **options)

        # Assert type is correct
        self.assertTrue(self.assert_is_3d_list_of(return_matrix, qiskit.circuit.Instruction))

        # Assert structure is correct: a valid brick matrix, four rows (a QFT has
        # only two-qubit controlled phases, so the demand-driven ancilla policy
        # adds no qubits either way), a width that agrees with the resource stage,
        # and one CX brick per routed CX gate.
        validate_instruction_matrix(return_matrix)
        self.assertEqual(len(return_matrix), 4)
        self.assertEqual(resources.qubits, 4)
        self.assertEqual(len(return_matrix[0]), resources.brick_columns)
        cx_bricks = sum(
            1
            for row in return_matrix
            for cell in row
            for instr in cell
            if is_cx_endpoint(instr.name) and cx_role(instr.name) == "c"
        )
        self.assertEqual(cx_bricks, resources.cx_gates)

    def test_matrix_with_ancillae(self):
        self._check_qft4_matrix(with_ancillas=True)

    def test_matrix_without_ancillae(self):
        self._check_qft4_matrix(with_ancillas=False)
