# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
import uuid
import warnings
from typing import List, Union, Tuple, Iterable
import numpy as np
from uuid import uuid4

from scipy.sparse import csc_matrix
from GridCalEngine.Utils.MIP.SimpleMip.lpobjects import LpExp, LpCst, LpVar
from GridCalEngine.Utils.MIP.SimpleMip.highs import HIGHS_AVAILABLE, solve_with_highs
from GridCalEngine.basic_structures import Vec, Logger
from GridCalEngine.enumerations import MIPSolvers


def get_available_mip_solvers() -> List[str]:
    """
    Get a list of candidate solvers
    :return: list of solver names
    """
    res = list()

    if HIGHS_AVAILABLE:
        res.append('HIGHS')

    return res


def set_var_bounds(var: LpVar, lb: float, ub: float):
    """
    Modify the bounds of a variable
    :param var: LpVar instance to modify
    :param lb: lower bound value
    :param ub: upper bound value
    """
    var.lower_bound = lb
    var.upper_bound = ub


class LpModel:
    """
    SimpleMIP
    """
    OPTIMAL = 100
    INFINITY = 1e20
    originally_infesible = False

    def __init__(self, solver_type: MIPSolvers = MIPSolvers.HIGHS):

        if solver_type not in [MIPSolvers.HIGHS]:
            warnings.warn(f"Unsupported solver {solver_type.value}, falling back to highs.")
            self.solver_type = MIPSolvers.HIGHS
        else:
            self.solver_type = solver_type
        self.objective: Union[LpExp, None] = None
        self.constraints: List[LpCst] = []
        self.variables: List[LpVar] = []
        self.relaxed_slacks: List[Tuple[int, LpVar, float]] = []
        self._is_minimize = True
        self._is_mip = False

        # solution vars
        self._col_value = np.empty(0)
        self._col_dual = np.empty(0)
        self._row_value = np.empty(0)
        self._row_dual = np.empty(0)
        self._objective_value = 0.0
        self._is_optimal = False

        self.logger = Logger()

    def is_minimize(self) -> bool:
        """
        Minimize?
        :return: bool
        """
        return self._is_minimize

    def copy(self, copy_results: bool = False) -> "LpModel":
        """
        Deep copy of this
        :param copy_results: copy the results too?
        :return: LpModel
        """
        cpy = LpModel(self.solver_type)

        cpy._is_minimize = self._is_minimize
        cpy._is_mip = self._is_mip
        cpy.objective = self.objective.copy()

        for var in self.variables:
            cpy.variables.append(var.copy())

        for cst in self.constraints:
            cpy.constraints.append(cst.copy())

        if copy_results:
            cpy._col_value = self._col_value
            cpy._col_dual = self._col_dual
            cpy._row_value = self._row_value
            cpy._row_dual = self._row_dual
            cpy._objective_value = self._objective_value
            cpy._is_optimal = self._is_optimal

        return cpy

    def get_obj_coefficient(self, var: LpVar) -> float:
        """
        Get the coefficient of a variable, if not found, return 0.0
        """
        return self.objective.terms.get(var, 0.0)

    def _add_variable(self, lb: float = 0.0, ub: float = 1e20, name: str = "", is_int: bool = False):
        """
        Add a variable to the problem
        :param lb:
        :param ub:
        :param name:
        :param is_int:
        :return: Variable instance
        """
        var = LpVar(name=name, lower_bound=lb, upper_bound=ub, is_integer=is_int, hash_id=uuid4().int)
        self.variables.append(var)
        return var

    def add_int(self, lb: int, ub: int, name: str = "") -> LpVar:
        """
        Make integer LP var
        :param lb: lower bound
        :param ub: upper bound
        :param name: name (optional)
        :return: LpVar
        """
        return self._add_variable(lb=lb, ub=ub, name=name, is_int=True)

    def add_var(self, lb: float = 0.0, ub: float = 1e20, name: str = "") -> LpVar:
        """
        Make floating point LP var
        :param lb: lower bound
        :param ub: upper bound
        :param name: name (optional)
        :return: LpVar
        """
        return self._add_variable(lb=lb, ub=ub, name=name, is_int=False)

    def add_vars(self, size: int, lb: float = 0.0, ub: float = 1e20, name: str = "", is_int=False) -> List[LpVar]:
        """
        Make array of LP vars
        :param size: number of variables
        :param lb: lower bound
        :param ub: upper bound
        :param name: name (optional)
        :param is_int: create integer variables
        :return: LpVar
        """
        return [self._add_variable(lb=lb, ub=ub, name=f"{name}_{i}", is_int=is_int)
                for i in range(size)]

    def _set_objective(self, expression: LpExp, is_minimize=True):
        """
        Set the objective function
        :param expression: Expression
        :param is_minimize: minimize?
        """
        self.objective = expression
        self._is_minimize = is_minimize

    def minimize(self, obj_function: LpExp):
        """
        Set the objective to minimize
        :param obj_function: Expression
        """
        self._set_objective(obj_function, is_minimize=True)

    def maximize(self, obj_function: LpExp):
        """
        Set the objective to maximize
        :param obj_function: Expression
        """
        self._set_objective(obj_function, is_minimize=False)

    def add_cst(self, cst: Union[LpCst, bool], name: str = "") -> Union[LpCst, int]:
        """
        Add constraint to the model
        :param cst: constraint object (or general expression)
        :param name: name of the constraint (optional)
        :return: Constraint object
        """
        if isinstance(cst, LpCst):
            cst.name = name
            self.constraints.append(cst)
            return cst
        else:
            raise ValueError("Only Constraint instances can be added.")

    @staticmethod
    def sum(expr: Union[LpExp, Iterable]) -> LpExp:
        """
        create sum of the expression
        :param expr: LpExp object (or general expression)
        :return: LpExp object
        """
        if isinstance(expr, LpExp):
            return expr
        elif isinstance(expr, Iterable):
            res = LpExp()
            for elm in expr:
                res += elm
            return res
        else:
            raise ValueError("Only iterables can be used with sum.")

    def save_model_to_lp(self, filename: str):
        """
        Save model to LP file
        :param filename: LP file path
        """
        with open(filename, 'w') as file:
            # Write Objective Function
            obj_type = "Minimize" if self._is_minimize else "Maximize"
            objective_expression = " + ".join([f"{coeff}*{var.name}"
                                               for var, coeff
                                               in self.objective.terms.items()])

            if self.objective.offset != 0.0:  # Add constant term if exists
                objective_expression += f" + {self.objective.offset}"
            file.write(f"{obj_type}\n obj: {objective_expression}\n")

            # Write Constraints
            file.write("\nSubject To\n")
            for i, constraint in enumerate(self.constraints):
                expression = constraint.linear_expression
                constraint_expression = " + ".join([f"{coeff}*{var.name}"
                                                    for var, coeff
                                                    in expression.terms.items()])

                if expression.offset != 0.0:  # Add constant term if exists
                    objective_expression += f" + {expression.offset}"

                cname = constraint.name.replace(" ", "_")
                file.write(f"{cname}: {constraint_expression} {constraint.sense} {constraint.coefficient}\n")

            # Write Bounds
            file.write("\nBounds\n")
            for var in self.variables:
                lb = var.lower_bound if var.lower_bound is not None else "-inf"
                ub = var.upper_bound if var.upper_bound is not None else "inf"
                file.write(f" {lb} <= {var.name} <= {ub}\n")

            # Write Variable Types
            file.write("\nGenerals\n")
            for var in self.variables:
                if var.is_integer:
                    file.write(f" {var.name}\n")
            file.write("End\n")

    def save_model_to_mps(self, filename):
        """
        Save the model to MPS
        :param filename: MPS file path
        """
        with open(filename, 'w') as file:
            # Write the header
            file.write("NAME          MIPMODEL\n")

            # Write the ROWS section
            file.write("ROWS\n")
            file.write(" N  COST\n")
            for i in range(len(self.constraints)):
                sense = self.constraints[i].sense
                if sense == '<=':
                    file.write(f" L  C{i}\n")
                elif sense == '>=':
                    file.write(f" G  C{i}\n")
                elif sense == '==':
                    file.write(f" E  C{i}\n")

            # Write the COLUMNS section
            file.write("COLUMNS\n")
            for var in self.variables:
                file.write(f"    {var.name}    COST    {self.objective.terms.get(var, 0)}\n")
                for i, constraint in enumerate(self.constraints):
                    coeff = constraint.linear_expression.terms.get(var, 0)
                    if coeff != 0:
                        file.write(f"    {var.name}    C{i}    {coeff}\n")

            # Write the RHS section
            file.write("RHS\n")
            for i, constraint in enumerate(self.constraints):
                file.write(f"    RHS1    C{i}    {constraint.coefficient}\n")

            # Write the BOUNDS section
            file.write("BOUNDS\n")
            for var in self.variables:
                lb = var.lower_bound
                ub = var.upper_bound
                if var.is_integer:
                    file.write(f" UI BND1    {var.name}    {ub}\n")
                    file.write(f" LI BND1    {var.name}    {lb}\n")
                else:
                    file.write(f" UP BND1    {var.name}    {ub}\n")
                    file.write(f" LO BND1    {var.name}    {lb}\n")

            # Optionally add the RANGES section
            # ...

            # Write the ENDATA section
            file.write("ENDATA\n")

    def save_model(self, file_name="ntc_opf_problem.lp"):
        """
        Save model in lp or mps format
        :param file_name: name of the file
        """
        if file_name.endswith(".lp"):
            self.save_model_to_lp(filename=file_name)

        elif file_name.endswith(".mps"):
            self.save_model_to_lp(filename=file_name)

        else:
            raise Exception(f"Unrecognized file format to save {file_name}")

    def __str__(self):
        """
        Formulate MIP
        :return:
        """
        res = ""
        res += "\nVars:\n"
        for var in self.variables:
            var_type = "Integer" if var.is_integer else "Continuous"
            res += f"{var.name}: {var_type}\n"

        res += "\nObjective:\n"
        obj_type = "Minimize" if self._is_minimize else "Maximize"

        objective_expression = " + ".join([f"{coeff} * {var.name}"
                                           for var, coeff
                                           in self.objective.terms.items()])

        if self.objective.offset != 0.0:  # Add constant term if exists
            objective_expression += f" + {self.objective.offset}"

        res += f"{obj_type}: {objective_expression}\n"

        res += "\nConstraints:\n"
        for i, constraint in enumerate(self.constraints):
            # Create the constraint expression
            expression = constraint.linear_expression
            constraint_expression = " + ".join([f"{coeff}*{var.name}"
                                                for var, coeff
                                                in expression.terms.items()])

            if expression.offset != 0.0:  # Add constant term if exists
                constraint_expression += f" + {expression.offset}"

            res += f"Constraint {i}: {constraint_expression} {constraint.sense} {constraint.coefficient}\n"

        res += "\nBounds:\n"
        for var in self.variables:
            bounds = f"{var.lower_bound} <= {var.name} <= {var.upper_bound}"
            res += bounds + "\n"

        return res

    def get_coefficients_data(self) -> Tuple[np.ndarray, csc_matrix, np.ndarray]:
        """
        Returns the coefficients matrix
        :return:
        """

        # Initialize lists to hold the row indices, column indices, and data for the A matrix
        row_indices = []
        col_indices = []
        data = []

        n = len(self.constraints)
        lower = np.empty(n)
        upper = np.empty(n)

        # Iterate through each constraint, populating the lists
        for i, constraint in enumerate(self.constraints):

            lower[i], upper[i] = constraint.get_bounds()
            constraint.set_index(i)

            for var, coeff in constraint.linear_expression.terms.items():
                if var is not None:  # Skip if it's the constant term
                    # Row index is the constraint number
                    row_indices.append(i)

                    # Column index is the variable's index
                    col_indices.append(self.variables.index(var))

                    # Coefficient is the data
                    data.append(coeff)

        # Create the A matrix in CSC format
        A_csc = csc_matrix((data, (row_indices, col_indices)),
                           shape=(len(self.constraints), len(self.variables)))

        return lower, A_csc, upper

    def get_var_data(self) -> Tuple[Vec, Vec, Vec, List[int]]:
        """
        Get arrays related to the variable bounds and the objective function coefficients
        :return: lower bounds, f obj coefficients, upper bounds, list of integer vars' indices
        """
        n = len(self.variables)
        lower = np.empty(n)
        coeff = np.empty(n)
        upper = np.empty(n)
        is_int = list()

        for i, var in enumerate(self.variables):
            lower[i] = var.lower_bound
            coeff[i] = self.get_obj_coefficient(var)
            upper[i] = var.upper_bound
            var.set_index(i)
            if var.is_integer:
                is_int.append(i)

        return lower, coeff, upper, is_int

    def is_optimal(self) -> bool:
        """

        :return:
        """
        return self._is_optimal

    def _solve(self, model: "LpModel"):

        if self.solver_type == MIPSolvers.HIGHS:
            solve_with_highs(model)

        else:
            raise Exception(f"Unsupported solver {self.solver_type.value}")

    def solve(self, robust=True) -> int:
        """
        Solve the model
        :param robust: Relax the problem if infeasible
        :return: integer value matching OPTIMAL or not
        """

        self._solve(model=self)

        if not self.is_optimal():

            self.originally_infesible = True

            if robust:
                """
                We are going to create a deep clone of the model,
                add a slack variable to each constraint and minimize
                the sum of the newly added slack vars.
                This LP model will be always optimal.
                After the solution, we inspect the slack vars added
                if any of those is > 0, then the constraint where it
                was added needs "slacking", therefore we add that slack
                to the original model, and add the slack to the original 
                objective function. This way we relax the model while
                bringing it to optimality.
                """

                # deep copy of the original model
                debug_model = self.copy()

                # modify the original to detect the bad constraints
                slacks = list()
                debugging_f_obj = LpExp()
                for i, cst in enumerate(debug_model.constraints):

                    # create a new slack var in the problem
                    sl = debug_model.add_var(0, 1e20, name='Slackkk{}'.format(i))

                    # add the variable to the new objective function
                    debugging_f_obj += sl

                    # add the variable to the current constraint
                    cst.add_var(sl)

                    # store for later
                    slacks.append(sl)

                # set the objective function as the summation of the new slacks
                debug_model.minimize(debugging_f_obj)

                # solve the debug model
                self._solve(debug_model)

                debug_optimal = debug_model.is_optimal()

                # clear the relaxed slacks list
                self.relaxed_slacks: List[Tuple[int, LpVar, float]] = []

                if debug_optimal:

                    # pick the original objectve function
                    main_f = self.objective

                    for i, sl in enumerate(slacks):

                        # get the debugging slack value
                        val = debug_model.get_value(sl)

                        if val > 1e-10:

                            # add the slack in the main model
                            sl2 = self.add_var(0, 1e20, name='Slackkk{}'.format(i))
                            self.relaxed_slacks.append((i, sl2, 0.0))  # the 0.0 value will be read later

                            # add the slack to the original objective function
                            main_f += sl2

                            # alter the matching constraint
                            self.constraints[i].add_var(sl2)

                            # logg this
                            # self.logger.add_warning("Relaxed problem",
                            #                         device=self.model.linear_constraint_from_index(i).name)

                    # set the modified (original) objective function
                    self.minimize(main_f)

                    # solve the modified (original) model
                    self._solve(self)

                    if self.is_optimal():

                        for i in range(len(self.relaxed_slacks)):
                            k, var, _ = self.relaxed_slacks[i]
                            val = self.get_value(var)
                            self.relaxed_slacks[i] = (k, var, val)

                            # logg this
                            self.logger.add_warning("Relaxed problem",
                                                    device=self.constraints[i].name,
                                                    value=val)

                else:
                    self.logger.add_warning("Unable to relax the model, the debug model failed")

            else:
                pass

        return self.OPTIMAL if self.is_optimal() else 0

    def set_solution(self, col_values: Vec, col_duals: Vec,
                     row_values: Vec, row_duals: Vec,
                     f_obj: float, is_optimal: bool):
        """
        Set solution from the MIP solver
        :param col_values: array of variables' values
        :param col_duals: array of variable dual values
        :param row_values: array of constraint values
        :param row_duals: array of constraint dual values
        :param f_obj: value of the objective function
        :param is_optimal: is optimal
        """
        self._col_value = col_values
        self._col_dual = col_duals
        self._row_value = row_values
        self._row_dual = row_duals
        self._objective_value = f_obj
        self._is_optimal = is_optimal

    def fobj_value(self) -> float:
        """
        Get the objective function value
        :return:
        """
        return self._objective_value

    def is_mip(self):
        """
        Is this model a MIP?
        :return:
        """

        return self._is_mip

    def get_objective_value(self) -> float:
        """
        Get the objective function value
        :return: float
        """

        return self._objective_value

    def get_value(self, var: LpVar) -> float:
        """
        Get the value of a variable
        :param var: LpVar object
        :return: float
        """
        if isinstance(var, LpVar):
            return self._col_value[var.get_index()]
        elif isinstance(var, LpCst):
            return self._row_value[var.get_index()]
        elif isinstance(var, LpExp):
            val = var.offset
            for var2, coeff in var.terms.items():
                val += coeff * self._col_value[var2.get_index()]
            return val
        elif isinstance(var, int) or isinstance(var, float):
            return var
        else:
            raise TypeError("Unsupported variable type {0}".format(type(var)))

    def get_dual_value(self, var: LpVar) -> float:
        """
        Get the dual value of a variable
        :param var: LpVar object
        :return: float
        """
        if isinstance(var, LpVar):
            return self._col_dual[var.get_index()]
        elif isinstance(var, LpCst):
            return self._row_dual[var.get_index()]
        elif isinstance(var, LpExp):
            val = var.offset
            for var2, coeff in var.terms.items():
                val += coeff * self._col_dual[var2.get_index()]
            return val
        elif isinstance(var, int) or isinstance(var, float):
            return var
        else:
            raise TypeError("Unsupported variable type {0}".format(type(var)))

    def get_array_value(self, arr: Union[List[LpVar]]) -> np.ndarray:
        """
        Get the array of var values
        :param arr: array of variables
        :return:
        """
        res = np.empty(len(arr))
        for i, var in enumerate(arr):
            res[i] = self.get_value(var)
        return res


    def solution_available(self) -> bool:
        """
        Is there a solution loaded?
        :return: true / false
        """
        return len(self._col_value) == len(self.variables)

    def print_solution(self):
        """
        Print available solution
        """
        if self.solution_available():
            print("Solution")
            for var in self.variables:
                print(f"{var.name}: {self._col_value[var.get_index()]}")
        else:
            print("No solution available, solve first")
