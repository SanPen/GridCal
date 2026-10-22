"""Export a CSC matrix and its right hand side to Matrix Market files."""
import os.path

import numpy as np
from scipy.io import mmwrite
from scipy.sparse import csc_matrix
from scipy.sparse import load_npz


def convert_to_matrix_market(matrix: csc_matrix, rhs: np.ndarray,
                             matrix_path: str, rhs_path: str) -> None:
    """Write a sparse coordinate matrix and a dense right hand side array.

    :param matrix: CSC system matrix.
    :param rhs: Matching vector or matrix of right hand sides.
    :param matrix_path: Destination matrix file.
    :param rhs_path: Destination right hand side file.
    :return: None.
    :raises ValueError: If dimensions or destination paths are incompatible.
    """
    # Validate the pair before writing either file.
    if rhs.ndim not in (1, 2) or rhs.shape[0] != matrix.shape[0]:
        raise ValueError("Right hand side must have one row per matrix row")
    elif os.path.realpath(matrix_path) == os.path.realpath(rhs_path):
        raise ValueError("Matrix and right hand side need different destination paths")
    else:
        # Matrix Market arrays are two-dimensional, including single RHS vectors.
        rhs_columns: np.ndarray = rhs.reshape((-1, 1)) if rhs.ndim == 1 else rhs
        mmwrite(matrix_path, matrix, precision=17, symmetry="general")
        mmwrite(rhs_path, rhs_columns, precision=17, symmetry="general")


if __name__ == "__main__":
    # Resolve the example files beside the script, independent of the working directory.
    folder: str = os.path.dirname(os.path.realpath(__file__))
    jacobian: csc_matrix = csc_matrix(load_npz(os.path.join(folder, "../../../../trunk/linear_algebra/J.npz")))
    with np.load(os.path.join(folder, "../../../../trunk/linear_algebra/F.npz")) as archive:
        right_hand_side: np.ndarray = archive["F"]
    convert_to_matrix_market(jacobian, right_hand_side,
                             os.path.join(folder, "../../../../trunk/linear_algebra/Spain_J.mtx"), os.path.join(folder,
                                                                                                                "../../../../trunk/linear_algebra/Spain_J_b.mtx"))
