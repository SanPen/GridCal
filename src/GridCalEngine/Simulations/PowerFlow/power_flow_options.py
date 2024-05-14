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

from GridCalEngine.enumerations import BranchImpedanceMode, ReactivePowerControlMode, SolverType, TapsControlMode


class PowerFlowOptions:
    """
    Power flow options
    """

    def __init__(self,
                 solver_type: SolverType = SolverType.NR,
                 retry_with_other_methods=True,
                 verbose=0,
                 initialize_with_existing_solution=False,
                 tolerance=1e-6,
                 max_iter=25,
                 max_outer_loop_iter=100,
                 control_q=ReactivePowerControlMode.NoControl,
                 control_taps=TapsControlMode.NoControl,
                 multi_core=False,
                 dispatch_storage=False,
                 control_p=False,
                 apply_temperature_correction=False,
                 branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
                 q_steepness_factor=30,
                 distributed_slack=False,
                 ignore_single_node_islands=False,
                 trust_radius=1.0,
                 backtracking_parameter=0.05,
                 use_stored_guess=False,
                 override_branch_controls=False,
                 generate_report=False,
                 generalised_pf=False):
        """
        Power flow options class
        :param solver_type: Solver type
        :param retry_with_other_methods: Use a battery of methods to tackle the problem if the main solver_type fails
        :param verbose: Print additional details in the console (0: no details, 1: some details, 2: all details)
        :param initialize_with_existing_solution: Use the existing solution from the Bus class (Vm0, Va0)
        :param tolerance: Solution tolerance for the power flow numerical methods
        :param max_iter: Maximum number of iterations for the power flow numerical method
        :param max_outer_loop_iter: Maximum number of iterations for the controls outer loop
        :param control_q: Control mode for the PV nodes reactive power limits
        :param control_taps: Control mode for the transformer taps equipped with a voltage regulator
                             (as part of the outer loop)
        :param multi_core: Use multi-core processing? applicable for time series
        :param dispatch_storage: Dispatch storage? (obsolete)
        :param control_p: Control active power (optimization dispatch)
        :param apply_temperature_correction: Apply the temperature correction to the resistance of the Branches?
        :param branch_impedance_tolerance_mode: Type of modification of the Branches impedance
        :param q_steepness_factor: Steepness factor :math:`k` for the :ref:`ReactivePowerControlMode<q_control>` iterative control (obsolete)
        :param distributed_slack: Applies the redistribution of the slack power proportionally among the controlled generators
        :param ignore_single_node_islands: If True the islands of 1 node are ignored
        :param trust_radius:
        :param backtracking_parameter: parameter used to correct the "bad" iterations, typically 0.5
        :param use_stored_guess:
        :param override_branch_controls:
        :param generate_report:
        :param generalised_pf:
        """

        self.solver_type = solver_type

        self.retry_with_other_methods = retry_with_other_methods

        self.tolerance = tolerance

        self.max_iter = max_iter

        self.max_outer_loop_iter = max_outer_loop_iter

        self.control_Q = control_q

        self.control_P = control_p

        self.verbose = verbose

        self.initialize_with_existing_solution = initialize_with_existing_solution

        self.multi_thread = multi_core

        self.dispatch_storage = dispatch_storage

        self.control_taps = control_taps

        self.apply_temperature_correction = apply_temperature_correction

        self.branch_impedance_tolerance_mode = branch_impedance_tolerance_mode

        self.q_steepness_factor = q_steepness_factor

        self.distributed_slack = distributed_slack

        self.ignore_single_node_islands = ignore_single_node_islands

        self.trust_radius = trust_radius

        self.backtracking_parameter = backtracking_parameter

        self.use_stored_guess = use_stored_guess

        self.override_branch_controls = override_branch_controls

        self.generate_report = generate_report

        self.generalised_pf = generalised_pf

    def __str__(self):
        return "PowerFlowOptions"
