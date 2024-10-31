# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCalEngine.Utils.MIP.SimpleMip.lpmodel import LpModel

try:
    import highspy
    HIGHS_AVAILABLE = True
except ImportError:
    highspy = None
    HIGHS_AVAILABLE = False


def solve_with_highs(problem: LpModel, verbose: int = 0):
    """
    Solve MIP using Highs via its python interface
    :param problem: Problem to be solved (results are inserted in-place)
    :param verbose: print info? for values > 0
    """
    if highspy is None:
        raise Exception("No highspy available, try installing with: pip install highspy")

    # declare the solver
    h = highspy.highs.Highs()

    # declare the LP problem
    lp = highspy.HighsLp()

    # set the sense
    lp.sense_ = highspy.highs.ObjSense.kMinimize if problem.is_minimize() else highspy.highs.ObjSense.kMaximize

    # set the var information
    lp.col_lower_, lp.col_cost_, lp.col_upper_, is_int_list = problem.get_var_data()
    lp.offset_ = problem.objective.offset

    for i in is_int_list:
        lp.integrality_.append(i)

    # set the constraints information
    lp.row_lower_, A, lp.row_upper_ = problem.get_coefficients_data()
    lp.num_col_ = A.shape[1]
    lp.num_row_ = A.shape[0]

    lp.a_matrix_.start_ = A.indptr
    lp.a_matrix_.index_ = A.indices
    lp.a_matrix_.value_ = A.data

    # send the model to the solver
    h.passModel(lp)

    # solve
    h.run()

    # gather results
    solution = h.getSolution()
    basis = h.getBasis()
    info = h.getInfo()
    model_status = h.getModelStatus()

    if verbose > 0:
        print("Model status = ", h.modelStatusToString(model_status))
        print("Optimal objective = ", info.objective_function_value)
        print("Iteration count = ", info.simplex_iteration_count)
        print("Primal solution status = ", h.solutionStatusToString(info.primal_solution_status))

    problem.set_solution(col_values=solution.col_value,
                         col_duals=solution.col_dual,
                         row_values=solution.row_value,
                         row_duals=solution.row_dual,
                         f_obj=info.objective_function_value,
                         is_optimal=model_status == highspy.HighsModelStatus.kOptimal)
