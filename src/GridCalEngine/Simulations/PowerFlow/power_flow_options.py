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

from GridCalEngine.enumerations import BranchImpedanceMode, SolverType
from GridCalEngine.Simulations.options_template import OptionsTemplate


class PowerFlowOptions(OptionsTemplate):
    """
    Power flow options
    """

    def __init__(self,
                 solver_type: SolverType = SolverType.NR,
                 retry_with_other_methods: bool = True,
                 verbose: int = 0,
                 initialize_with_existing_solution: bool = False,
                 tolerance: float = 1e-6,
                 max_iter: int = 25,
                 max_outer_loop_iter: int = 100,
                 control_q: bool = False,
                 control_taps_modules: bool = False,
                 control_taps_phase: bool = False,
                 apply_temperature_correction: bool = False,
                 branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
                 distributed_slack: bool = False,
                 ignore_single_node_islands: bool = False,
                 trust_radius: float = 1.0,
                 backtracking_parameter: float = 0.05,
                 use_stored_guess: bool = False,
                 generate_report: bool = False):
        """
        Power flow options class
        :param solver_type: Solver type
        :param retry_with_other_methods: Use a battery of methods to tackle the problem if the main solver_type fails
        :param verbose: Print additional details in the console (0: no details, 1: some details, 2: all details)
        :param tolerance: Solution tolerance for the power flow numerical methods
        :param max_iter: Maximum number of iterations for the power flow numerical method
        :param max_outer_loop_iter: Maximum number of iterations for the controls outer loop
        :param control_q: Control mode for the PV nodes reactive power limits
        :param apply_temperature_correction: Apply the temperature correction to the resistance of the Branches?
        :param branch_impedance_tolerance_mode: Type of modification of the Branches impedance
        :param distributed_slack: Applies the redistribution of the slack power proportionally among the controlled generators
        :param ignore_single_node_islands: If True the islands of 1 node are ignored
        :param trust_radius:
        :param backtracking_parameter: parameter used to correct the "bad" iterations, typically 0.5
        :param use_stored_guess: Use the existing solution from the Bus class (Vm0, Va0)
        :param generate_report: Generate the power flow report after the solution?
        """
        OptionsTemplate.__init__(self, name='PowerFlowOptions')

        self.solver_type = solver_type

        self.retry_with_other_methods = retry_with_other_methods

        self.tolerance = tolerance

        self.max_iter = max_iter

        self.max_outer_loop_iter = max_outer_loop_iter

        self.control_Q = control_q

        self.verbose = verbose

        self.initialize_with_existing_solution = initialize_with_existing_solution

        self.control_taps_modules = control_taps_modules

        self.control_taps_phase = control_taps_phase

        self.apply_temperature_correction = apply_temperature_correction

        self.branch_impedance_tolerance_mode = branch_impedance_tolerance_mode

        self.distributed_slack = distributed_slack

        self.ignore_single_node_islands = ignore_single_node_islands

        self.trust_radius = trust_radius

        self.backtracking_parameter = backtracking_parameter

        self.use_stored_guess = use_stored_guess

        self.generate_report = generate_report

        self.register(key="solver_type", tpe=SolverType)
        self.register(key="retry_with_other_methods", tpe=bool)
        self.register(key="tolerance", tpe=float)
        self.register(key="max_iter", tpe=int)
        self.register(key="max_outer_loop_iter", tpe=int)
        self.register(key="control_Q", tpe=bool)
        self.register(key="verbose", tpe=int)
        self.register(key="initialize_with_existing_solution", tpe=bool)
        self.register(key="control_taps_modules", tpe=bool)
        self.register(key="control_taps_phase", tpe=bool)
        self.register(key="apply_temperature_correction", tpe=bool)
        self.register(key="branch_impedance_tolerance_mode", tpe=BranchImpedanceMode)
        self.register(key="distributed_slack", tpe=bool)
        self.register(key="ignore_single_node_islands", tpe=bool)
        self.register(key="trust_radius", tpe=float)
        self.register(key="backtracking_parameter", tpe=float)
        self.register(key="use_stored_guess", tpe=bool)
        self.register(key="generate_report", tpe=bool)
