# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List
import numpy as np
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.basic_structures import Vec, IntVec, StrVec
from VeraGridEngine.Simulations.InvestmentsEvaluation.Problems.black_box_problem_template import BlackBoxProblemTemplate
from VeraGridEngine.Utils.scores import (get_overload_score, get_voltage_phase_score, get_voltage_module_score,
                                         TechnoEconomicScores)
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Devices.Aggregation.investment import Investment


def power_flow_function(inv_list: List[Investment],
                        grid: MultiCircuit,
                        pf_options: PowerFlowOptions,
                        branches_cost,
                        vm_cost: Vec,
                        vm_max: Vec,
                        vm_min: Vec,
                        va_cost: Vec,
                        va_max: Vec,
                        va_min: Vec) -> TechnoEconomicScores:
    """
    Compute the power flow of the grid given an investments group
    :param inv_list: list of Investments
    :param grid: MultiCircuit grid
    :param pf_options: Power flow options
    :param branches_cost: Array with all overloading cost for the branches
    :param vm_cost: Array with all the bus voltage module violation costs
    :param vm_max: Array with the Vm min values
    :param vm_min: Array with the Vm max values
    :param va_cost: Array with all the bus voltage angles violation costs
    :param va_max: Array with the Va max values
    :param va_min: Array with the Va min values
    :return: InvestmentScores
    """

    driver = PowerFlowDriver(grid=grid, options=pf_options)
    driver.run()

    scores = TechnoEconomicScores()

    # compute scores
    scores.losses_score = np.sum(driver.results.losses.real)
    scores.overload_score = get_overload_score(loading=driver.results.loading,
                                               branches_cost=branches_cost)
    # scores.overload_score = 0
    scores.voltage_module_score = get_voltage_module_score(voltage=driver.results.voltage,
                                                           vm_cost=vm_cost,
                                                           vm_max=vm_max,
                                                           vm_min=vm_min)

    scores.voltage_angle_score = get_voltage_phase_score(voltage=driver.results.voltage,
                                                         va_cost=va_cost,
                                                         va_max=va_max,
                                                         va_min=va_min)

    scores.capex_score = sum([inv.CAPEX for inv in inv_list])
    scores.opex_score = 0.0

    return scores


class PowerFlowInvestmentProblem(BlackBoxProblemTemplate):

    def __init__(self, grid: MultiCircuit, pf_options: PowerFlowOptions):
        """
        Constructor
        :param grid: MultiCircuit
        :param pf_options: PowerFlowOptions
        """
        super().__init__(grid=grid,
                         x_dim=len(grid.investments_groups),
                         plot_x_idx=4, plot_y_idx=5)

        # options object
        self.pf_options = pf_options

        # gather a dictionary of all the elements, this serves for the investments generation
        self.get_all_elements_dict, dict_ok = self.grid.get_all_elements_dict()

        # compose useful arrays
        self.vm_cost = np.array([e.Vm_cost for e in grid.get_buses()], dtype=float)
        self.vm_max = np.array([e.Vmax for e in grid.get_buses()], dtype=float)
        self.vm_min = np.array([e.Vmin for e in grid.get_buses()], dtype=float)

        self.va_cost = np.array([e.angle_cost for e in grid.get_buses()], dtype=float)
        self.va_max = np.array([e.angle_max for e in grid.get_buses()], dtype=float)
        self.va_min = np.array([e.angle_min for e in grid.get_buses()], dtype=float)

        self.branches_cost = np.array([e.Cost for e in
                                       grid.get_branches(add_hvdc=False, add_vsc=False, add_switch=True)],
                                      dtype=float)

    def n_objectives(self) -> int:
        """
        Number of objectives (size of f)
        :return:
        """
        return 6

    def n_vars(self) -> int:
        """
        Number of variables (size of x)
        :return:
        """
        return self.x_dim

    def get_objectives_names(self) -> StrVec:
        """
        Get a list of names for the elements of f
        :return:
        """
        return np.array(["losses score", "overload score",
                         "voltage module_score", "voltage angle score",
                         "financial score", "Technical score"])

    def get_vars_names(self) -> StrVec:
        """
        Get a list of names for the elements of x
        :return:
        """
        return np.array([e.name for e in self.grid.investments_groups])


    def objective_function(self, x: Vec | IntVec) -> Vec:
        """
        Evaluate x and return f(x)
        :param x: array of variable values
        :return: array of objectives
        """
        inv_list: List[Investment] = self.get_investments_for_combination(x=x)

        # enable the investment
        self.grid.set_investments_status(investments_list=inv_list,
                                         status=True,
                                         all_elements_dict=self.get_all_elements_dict)

        scores = power_flow_function(inv_list=inv_list,
                                     grid=self.grid,
                                     pf_options=self.pf_options,
                                     branches_cost=self.branches_cost,
                                     vm_cost=self.vm_cost,
                                     vm_max=self.vm_max,
                                     vm_min=self.vm_min,
                                     va_cost=self.va_cost,
                                     va_max=self.va_max,
                                     va_min=self.va_min)

        # revert to the initial state
        self.grid.set_investments_status(investments_list=inv_list,
                                         status=False,
                                         all_elements_dict=self.get_all_elements_dict)

        return scores.arr()
