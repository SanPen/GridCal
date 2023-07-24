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
import numpy as np
from typing import List
from GridCal.Engine.Simulations.driver_template import DriverTemplate
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.InvestmentsEvaluation.investments_evaluation_results import InvestmentsEvaluationResults
from GridCal.Engine.Core.Devices.multi_circuit import MultiCircuit
from GridCal.Engine.Core.Devices.Aggregation.investment import Investment
from GridCal.Engine.Core.DataStructures.numerical_circuit import NumericalCircuit
from GridCal.Engine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions, multi_island_pf_nc
from GridCal.Engine.basic_structures import IntVec, InvestmentEvaluationMethod


class InvestmentsEvaluationDriver(DriverTemplate):
    name = 'Investments evaluation'
    tpe = SimulationTypes.InvestmestsEvaluation_run

    def __init__(self, grid: MultiCircuit, method: InvestmentEvaluationMethod, max_eval: int,
                 pf_options: PowerFlowOptions):
        """
        InputsAnalysisDriver class constructor
        :param grid: MultiCircuit instance
        :param method: InvestmentEvaluationMethod
        :param max_eval: Maximum number of evaluations
        """
        DriverTemplate.__init__(self, grid=grid)

        self.method: InvestmentEvaluationMethod = method

        self.max_eval: int = max_eval

        self.pf_options: PowerFlowOptions = pf_options

        self.results = InvestmentsEvaluationResults(grid=grid, max_eval=0)

        self.__eval_index = 0

    def get_steps(self):
        """

        :return:
        """
        return self.results.get_index()

    def objective_function(self,
                           combination: IntVec,
                           inv_list: List[Investment],
                           nc: NumericalCircuit):
        """
        Function to evaluate a combination of investments
        :param combination:
        :param inv_list: list of investment objects
        :param nc: NumericalCircuit
        :return: objective function value
        """
        # enable the investment
        nc.set_investments_status(investments_list=inv_list, status=1)

        # do something
        res = multi_island_pf_nc(nc=nc, options=self.pf_options)
        total_losses = np.sum(res.losses.real)
        f = total_losses

        # store the results
        self.results.set_at(eval_idx=self.__eval_index,
                            capex=sum([inv.CAPEX for inv in inv_list]),
                            opex=sum([inv.OPEX for inv in inv_list]),
                            losses=total_losses,
                            objective_function=f,
                            combination=combination,
                            index_name="Evaluation {}".format(self.__eval_index))

        # revert to disabled
        nc.set_investments_status(investments_list=inv_list, status=0)

        return f

    def independent_evaluation(self) -> None:
        """
        Run a one-by-one investment evaluation without considering multiple evaluation groups at a time
        """
        # compile the snapshot
        nc = compile_numerical_circuit_at(circuit=self.grid, t_idx=None)
        self.results = InvestmentsEvaluationResults(grid=self.grid,
                                                    max_eval=len(self.grid.investments_groups) + 1)
        # disable all status
        nc.set_investments_status(investments_list=self.grid.investments, status=0)

        # get investments by investment group
        inv_by_groups_list = self.grid.get_investmenst_by_groups()

        # evaluate the investments
        self.__eval_index = 0

        combination = np.zeros(self.results.n_groups, dtype=int)

        # add baseline
        self.objective_function(combination=combination, inv_list=[], nc=nc)

        self.__eval_index += 1

        for k, (inv_group, inv_list) in enumerate(inv_by_groups_list):
            self.progress_text.emit("Evaluating " + inv_group.name + '...')

            combination = np.zeros(self.results.n_groups, dtype=int)
            combination[k] = 1

            self.objective_function(combination=combination, inv_list=inv_list, nc=nc)

            # increase evaluations
            self.__eval_index += 1

            self.progress_signal.emit((k + 1) / len(inv_by_groups_list) * 100.0)
        self.progress_text.emit("Done!")
        self.progress_signal.emit(0.0)

    def optimized_evaluation(self) -> None:
        """
        Run an optimized investment evaluation without considering multiple evaluation groups at a time
        """
        # compile the snapshot
        nc = compile_numerical_circuit_at(circuit=self.grid, t_idx=None)
        self.results = InvestmentsEvaluationResults(grid=self.grid,
                                                    max_eval=self.max_eval + 1)
        # disable all status
        nc.set_investments_status(investments_list=self.grid.investments, status=0)

        # get investments by investment group
        inv_by_groups_list = self.grid.get_investmenst_by_groups()

        # evaluate the investments
        self.__eval_index = 0

        combination = np.zeros(self.results.n_groups, dtype=int)

        # add baseline
        self.objective_function(combination=combination, inv_list=[], nc=nc)

        self.__eval_index += 1

        for k, (inv_group, inv_list) in enumerate(inv_by_groups_list):
            self.progress_text.emit("Evaluating " + inv_group.name + '...')

            combination = np.zeros(self.results.n_groups, dtype=int)
            combination[k] = 1

            self.objective_function(combination=combination, inv_list=inv_list, nc=nc)

            # increase evaluations
            self.__eval_index += 1

            self.progress_signal.emit((k + 1) / len(inv_by_groups_list) * 100.0)
        self.progress_text.emit("Done!")
        self.progress_signal.emit(0.0)

    def run(self):
        """
        run the QThread
        :return:
        """

        self.tic()

        if self.method == InvestmentEvaluationMethod.Independent:
            self.independent_evaluation()

        elif self.method == InvestmentEvaluationMethod.MVRSM:
            self.optimized_evaluation()

        else:
            raise Exception('Unsupported method')

        self.toc()

    def cancel(self):
        self.__cancel__ = True


