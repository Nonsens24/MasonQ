import unittest
import qiskit
from brickwork_transpiler import circuits, brickwork_transpiler


class TestSingleGates(unittest.TestCase):

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


    def test_matrix_with_ancillae(self):

        experiment, _ = circuits.qft(4)
        return_matrix = brickwork_transpiler.transpile(experiment, routing_method='basic',
                                                             layout_method='trivial',
                                                             with_ancillas=True, plot_decomposed=False,
                                                             return_mat = True,
                                                       )

        # Assert type is correct
        self.assertTrue(self.assert_is_3d_list_of(return_matrix, qiskit.circuit.Instruction))

        # Assert size is correct
        self.assertEqual((len(return_matrix), len(return_matrix[0])), (6, 75))

    def test_matrix_without_ancillae(self):

        experiment, _ = circuits.qft(4)
        return_matrix = brickwork_transpiler.transpile(experiment, routing_method='basic',
                                                       layout_method='trivial',
                                                       with_ancillas=False, plot_decomposed=False,
                                                       return_mat=True,
                                                       )

        # Assert type is correct
        self.assertTrue(self.assert_is_3d_list_of(return_matrix, qiskit.circuit.Instruction))

        # Assert size is correct
        self.assertEqual((len(return_matrix), len(return_matrix[0])), (4, 75))
