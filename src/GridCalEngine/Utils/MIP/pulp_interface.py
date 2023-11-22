# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""
This module abstracts the synthax of ORTOOLS out
so that in the future it can be exchanged with some
other solver interface easily
"""

from typing import List, Union
import pulp
from pulp import LpAffineExpression as LpExp
from pulp import LpConstraint as LpCst
from pulp import LpVariable as LpVar
from GridCalEngine.basic_structures import MIPSolvers


def get_lp_var_value(x: Union[float, LpVar]) -> float:
    """
    Get the value of a variable stored in a numpy array of objects
    :param x: soe object (it may be a LP var or a number)
    :return: result or previous numeric value
    """
    if isinstance(x, pulp.LpVariable):
        return x.value()
    elif isinstance(x, pulp.LpAffineExpression):
        return x.value()
    elif isinstance(x, pulp.LpConstraint):
        return x.pi
    else:
        return x


def get_available_mip_solvers() -> List[str]:
    """
    Get a list of candidate solvers
    :return:
    """
    solvers = pulp.listSolvers(onlyAvailable=True)

    # elif self.solver_type == MIPSolvers.CBC:
    # solver = 'PULP_CBC_CMD'
    #
    # elif self.solver_type == MIPSolvers.HIGHS:
    # raise Exception("HiGHS is not supported by PuLP")
    # elif self.solver_type == MIPSolvers.SCIP:
    # solver = 'SCIP_CMD'
    # elif self.solver_type == MIPSolvers.CPLEX:
    # solver = 'CPLEX_CMD'
    # elif self.solver_type == MIPSolvers.GUROBI:
    # solver = 'GUROBI'
    # elif self.solver_type == MIPSolvers.XPRESS:
    # solver = 'XPRESS'

    solvers2 = list()
    for slv in solvers:
        if slv == 'PULP_CBC_CMD':
            solvers2.append(MIPSolvers.CBC.value)
        elif slv == 'SCIP_CMD':
            solvers2.append(MIPSolvers.SCIP.value)
        elif slv == 'CPLEX_CMD':
            solvers2.append(MIPSolvers.CPLEX.value)
        elif slv == 'GUROBI':
            solvers2.append(MIPSolvers.GUROBI.value)
        elif slv == 'XPRESS':
            solvers2.append(MIPSolvers.XPRESS.value)

    return solvers2


def set_var_bounds(var: LpVar, lb: float, ub: float):
    """
    Modify the bounds of a variable
    :param var: LpVar instance to modify
    :param lb: lower bound value
    :param ub: upper bound value
    """
    var.upBound = ub
    var.lowBound = lb


class LpModel:
    """
    LPModel implementation for ORTOOLS
    """
    OPTIMAL = pulp.LpStatusOptimal
    INFINITY = 1e20
    originally_infesible = False

    def __init__(self, solver_type: MIPSolvers):

        self.solver_type: MIPSolvers = solver_type

        self.model = pulp.LpProblem("myProblem", pulp.LpMinimize)

        if self.model is None:
            raise Exception("{} is not present".format(solver_type.value))

    def save_model(self, file_name="ntc_opf_problem.lp"):
        """
        Save problem in LP format
        :param file_name: name of the file (.lp or .mps supported)
        """
        # save the problem in LP format to debug
        if file_name.lower().endswith('.lp'):
            lp_content = self.model.writeLP(filename=file_name)
        elif file_name.lower().endswith('.mps'):
            lp_content = self.model.writeMPS(filename=file_name)
        else:
            raise Exception('Unsupported file format')

        with open(file_name, "w") as f:
            f.write(lp_content)

    def add_int(self, lb: int, ub: int, name: str = "") -> LpVar:
        """
        Make integer LP var
        :param lb: lower bound
        :param ub: upper bound
        :param name: name (optional)
        :return: LpVar
        """
        var = pulp.LpVariable(name=name, lowBound=lb, upBound=ub, cat=pulp.LpInteger)
        self.model.addVariable(var)
        return var

    def add_var(self, lb: float, ub: float, name: str = "") -> LpVar:
        """
        Make floating point LP var
        :param lb: lower bound
        :param ub: upper bound
        :param name: name (optional)
        :return: LpVar
        """
        var = pulp.LpVariable(name=name, lowBound=lb, upBound=ub, cat=pulp.LpContinuous)
        self.model.addVariable(var)
        return var

    def add_cst(self, cst: pulp.LpConstraint, name: str = "") -> LpExp:
        """
        Add constraint to the model
        :param cst: constraint object (or general expression)
        :param name: name of the constraint (optional)
        :return: Constraint object
        """
        return self.model.addConstraint(constraint=cst, name=name)

    def sum(self, cst) -> LpExp:
        """
        Add sum of the constraints to the model
        :param cst: constraint object (or general expression)
        :return: Constraint object
        """
        return pulp.lpSum(cst)

    def minimize(self, obj_function):
        """
        Set the objective function with minimization sense
        :param obj_function: expression to minimize
        """
        self.model.setObjective(obj=obj_function)

    def solve(self, robust: bool = False) -> int:
        """
        Solve the model
        :param robust: In this interface, this is useless
        :return:
        """

        # 'GLPK_CMD', 'PYGLPK', 'CPLEX_CMD', 'CPLEX_PY', 'CPLEX_DLL', 'GUROBI', 'GUROBI_CMD',
        # 'MOSEK', 'XPRESS', 'PULP_CBC_CMD', 'COIN_CMD', 'COINMP_DLL', 'CHOCO_CMD', 'MIPCL_CMD', 'SCIP_CMD'

        if self.solver_type == MIPSolvers.GLOP:
            raise Exception("GLOP is not supported by PuLP")
        elif self.solver_type == MIPSolvers.CBC:
            solver = 'PULP_CBC_CMD'
        elif self.solver_type == MIPSolvers.HIGHS:
            raise Exception("HiGHS is not supported by PuLP")
        elif self.solver_type == MIPSolvers.SCIP:
            solver = 'SCIP_CMD'
        elif self.solver_type == MIPSolvers.CPLEX:
            solver = 'CPLEX_CMD'
        elif self.solver_type == MIPSolvers.GUROBI:
            solver = 'GUROBI'
        elif self.solver_type == MIPSolvers.XPRESS:
            solver = 'XPRESS'
        else:
            raise Exception('PuLP Unsupported MIP solver ' + self.solver_type.value)

        status = self.model.solve(solver=pulp.getSolver(solver))

        if status != self.OPTIMAL:
            self.originally_infesible = True

        return status

    def fobj_value(self) -> float:
        """
        Get the objective function value
        :return:
        """
        return self.model.objective.value()

    def is_mip(self):
        """
        Is this odel a MIP?
        :return:
        """
        return self.model.isMIP()

    @staticmethod
    def get_value(x: Union[float, int, LpVar, LpExp, LpCst]) -> float:
        """
        Get the value of a variable stored in a numpy array of objects
        :param x: solver object (it may be a LP var or a number)
        :return: result or zero
        """
        if isinstance(x, LpVar):
            val = x.value()
        elif isinstance(x, LpExp):
            val = x.value()
        elif isinstance(x, float) or isinstance(x, int):
            return x
        else:
            raise Exception("Unrecognized type {}".format(x))

        if isinstance(val, float):
            return val
        else:
            return 0.0

    @staticmethod
    def get_dual_value(x: LpCst) -> float:
        """
        Get the dual value of a variable stored in a numpy array of objects
        :param x: constraint
        :return: result or zero
        """
        if isinstance(x, LpCst):
            val = x.pi
        else:
            raise Exception("Unrecognized type {}".format(x))

        if isinstance(val, float):
            return val
        else:
            return 0.0
