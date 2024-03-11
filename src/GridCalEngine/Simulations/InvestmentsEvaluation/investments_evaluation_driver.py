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
import hyperopt
import functools

from typing import List, Dict, Union
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from GridCalEngine.Simulations.driver_types import SimulationTypes
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Devices.Aggregation.investment import Investment
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.Simulations.InvestmentsEvaluation.NumericalMethods.MVRSM_mo_scaled import MVRSM_mo_scaled
from GridCalEngine.Simulations.InvestmentsEvaluation.NumericalMethods.MVRSM_mo_pareto import MVRSM_mo_pareto
from GridCalEngine.Simulations.InvestmentsEvaluation.NumericalMethods.stop_crits import StochStopCriterion
from GridCalEngine.Simulations.InvestmentsEvaluation.investments_evaluation_results import InvestmentsEvaluationResults
from GridCalEngine.Simulations.InvestmentsEvaluation.investments_evaluation_options import InvestmentsEvaluationOptions
from GridCalEngine.basic_structures import IntVec, Vec
from GridCalEngine.enumerations import InvestmentEvaluationMethod


def get_overload_score(loading, branches):
    """
    Compute overload score by multiplying the loadings above 100% by the associated branch cost.
    :param loading: load results
    :param branches: all branch elements from studied grid
    :return: sum of all costs associated to branch overloads
    """
    branches_cost = np.array([e.Cost for e in branches], dtype=float)
    branches_loading = np.abs(loading)

    # get lines where loading is above 1 -- why not 0.9 ?
    branches_idx = np.where(branches_loading > 1)[0]

    # multiply by the load or only the overload?
    cost = branches_cost[branches_idx] * branches_loading[branches_idx]

    return np.sum(cost)


def get_voltage_module_score(voltage, buses):
    """
    Compute voltage module score by multiplying the voltages outside limits by the associated bus costs.
    :param voltage: voltage results
    :param buses: all bus elements from studied grid
    :return: sum of all costs associated to voltage module deviation
    """
    bus_cost = np.array([e.Vm_cost for e in buses], dtype=float)
    vmax = np.array([e.Vmax for e in buses], dtype=float)
    vmin = np.array([e.Vmin for e in buses], dtype=float)
    vm = np.abs(voltage)
    vmax_diffs = np.array(vm - vmax).clip(min=0)
    vmin_diffs = np.array(vmin - vm).clip(min=0)
    cost = (vmax_diffs + vmin_diffs) * bus_cost

    return np.sum(cost)


def get_voltage_phase_score(voltage, buses):
    """
    Compute voltage phase score by multiplying the phases outside limits by the associated bus costs.
    :param voltage: voltage results
    :param buses: all bus elements from studied grid
    :return: sum of all costs associated to voltage module deviation
    """
    bus_cost = np.array([e.angle_cost for e in buses], dtype=float)
    vpmax = np.array([e.angle_max for e in buses], dtype=float)
    vpmin = np.array([e.angle_min for e in buses], dtype=float)
    vp = np.angle(voltage)
    vpmax_diffs = np.array(vp - vpmax).clip(min=0)
    vpmin_diffs = np.array(vpmin - vp).clip(min=0)
    cost = (vpmax_diffs + vpmin_diffs) * bus_cost

    return np.sum(cost)


class InvestmentsEvaluationDriver(DriverTemplate):
    name = 'Investments evaluation'
    tpe = SimulationTypes.InvestmestsEvaluation_run

    def __init__(self,
                 grid: MultiCircuit,
                 options: InvestmentsEvaluationOptions):
        """
        InputsAnalysisDriver class constructor
        :param grid: MultiCircuit instance
        :param options: InvestmentsEvaluationOptions
        """
        DriverTemplate.__init__(self, grid=grid)

        # options object
        self.options = options

        # results object
        self.results = InvestmentsEvaluationResults(investment_groups_names=grid.get_investment_groups_names(),
                                                    max_eval=0)

        self.__eval_index = 0

        # dictionary of investment groups
        self.investments_by_group: Dict[int, List[Investment]] = self.grid.get_investmenst_by_groups_index_dict()

        # dimensions
        self.dim = len(self.grid.investments_groups)

        # numerical circuit
        self.nc: Union[NumericalCircuit, None] = None

        # gather a dictionary of all the elements, this serves for the investments generation
        self.get_all_elements_dict = self.grid.get_all_elements_dict()

    def get_steps(self):
        """

        :return:
        """
        return self.results.get_index()

    def objective_function(self, combination: IntVec) -> Vec:
        """
        Function to evaluate a combination of investments
        :param combination: vector of investments (yes/no). Length = number of investment groups
        :return: objective function criteria values
        """

        # add all the investments of the investment groups reflected in the combination
        inv_list = list()
        for i, active in enumerate(combination):
            if active == 1:
                inv_list += self.investments_by_group[i]

        # enable the investment
        self.grid.set_investments_status(investments_list=inv_list,
                                         status=True,
                                         all_elemnts_dict=self.get_all_elements_dict)

        branches = self.grid.get_branches_wo_hvdc()
        buses = self.grid.get_buses()

        # do something
        driver = PowerFlowDriver(grid=self.grid, options=self.options.pf_options)
        driver.run()
        res = driver.results

        # compute scores
        losses_score = np.sum(res.losses.real)
        overload_score = get_overload_score(res.loading, branches)
        voltage_module_score = get_voltage_module_score(res.voltage, buses)
        voltage_angle_score = get_voltage_phase_score(res.voltage, buses)
        capex_array = np.array([inv.CAPEX for inv in inv_list])
        opex_array = np.array([inv.OPEX for inv in inv_list])

        # get arrays for first iteration
        if self.__eval_index == 0:
            capex_array = np.array([0])
            opex_array = np.array([0])

        capex_score = np.sum(capex_array)
        opex_score = np.sum(opex_array)

        all_scores = np.array([losses_score,
                               overload_score,
                               voltage_module_score,
                               voltage_angle_score,
                               capex_score,
                               opex_score])

        # revert to disabled
        self.grid.set_investments_status(investments_list=inv_list,
                                         status=False,
                                         all_elemnts_dict=self.get_all_elements_dict)

        # increase evaluations
        self.__eval_index += 1

        self.report_progress2(self.__eval_index, self.options.max_eval)

        return all_scores

    def objective_function_so(self, combination: IntVec):
        """

        :param combination:
        :return:
        """
        res_vec = self.objective_function(combination=combination)

        return res_vec.sum()

    def independent_evaluation(self) -> None:
        """
        Run a one-by-one investment evaluation without considering multiple evaluation groups at a time
        """
        # compile the snapshot
        self.nc = compile_numerical_circuit_at(circuit=self.grid, t_idx=None)
        self.results = InvestmentsEvaluationResults(investment_groups_names=self.grid.get_investment_groups_names(),
                                                    max_eval=len(self.grid.investments_groups) + 1)
        # disable all status
        self.nc.set_investments_status(investments_list=self.grid.investments, status=0)

        # evaluate the investments
        self.__eval_index = 0

        # add baseline
        self.objective_function(combination=np.zeros(self.results.n_groups, dtype=int))

        dim = len(self.grid.investments_groups)

        for k in range(dim):
            self.report_text("Evaluating investment group {}...".format(k))

            combination = np.zeros(dim, dtype=int)
            combination[k] = 1

            self.objective_function(combination=combination)

        self.report_done()

    def optimized_evaluation_hyperopt(self) -> None:
        """
        Run an optimized investment evaluation without considering multiple evaluation groups at a time
        """

        # configure hyperopt:

        # number of random evaluations at the beginning
        rand_evals = round(self.dim * 1.5)

        # binary search space
        space = [hyperopt.hp.randint(f'x_{i}', 2) for i in range(self.dim)]

        if self.options.max_eval == rand_evals:
            algo = hyperopt.rand.suggest
        else:
            algo = functools.partial(hyperopt.tpe.suggest, n_startup_jobs=rand_evals)

        # compile the snapshot
        self.nc = compile_numerical_circuit_at(circuit=self.grid, t_idx=None)
        self.results = InvestmentsEvaluationResults(investment_groups_names=self.grid.get_investment_groups_names(),
                                                    max_eval=self.options.max_eval + 1)
        # disable all status
        self.nc.set_investments_status(investments_list=self.grid.investments, status=0)

        # evaluate the investments
        self.__eval_index = 0

        # add baseline
        self.objective_function_so(combination=np.zeros(self.results.n_groups, dtype=int))

        hyperopt.fmin(self.objective_function_so, space, algo, self.options.max_eval)

        self.report_done()

    def optimized_evaluation_bayesian(self) -> None:
        """
        Run an optimized investment evaluation without considering multiple evaluation groups at a time
        """

        # configure hyperopt:

        # number of random evaluations at the beginning
        rand_evals = round(self.dim * 1.5)

        # binary search space
        space = [hyperopt.hp.randint(f'x_{i}', 2) for i in range(self.dim)]

        if self.options.max_eval == rand_evals:
            algo = hyperopt.rand.suggest
        else:
            algo = functools.partial(hyperopt.tpe.suggest, n_startup_jobs=rand_evals)

        # compile the snapshot
        self.nc = compile_numerical_circuit_at(circuit=self.grid, t_idx=None)
        self.results = InvestmentsEvaluationResults(investment_groups_names=self.grid.get_investment_groups_names(),
                                                    max_eval=self.options.max_eval + 1)
        # disable all status
        self.nc.set_investments_status(investments_list=self.grid.investments, status=0)

        # evaluate the investments
        self.__eval_index = 0

        # add baseline
        self.objective_function_so(combination=np.zeros(self.results.n_groups, dtype=int))

        hyperopt.fmin(self.objective_function_so, space, algo, self.options.max_eval)

        self.report_done()

    def optimized_evaluation_mvrsm(self) -> None:
        """
        Run an optimized investment evaluation without considering multiple evaluation groups at a time
        """

        # configure MVRSM:

        # number of random evaluations at the beginning
        rand_evals = round(self.dim * 1.5)
        lb = np.zeros(self.dim)
        ub = np.ones(self.dim)
        rand_search_active_prob = 0.5
        conf_dist = 0.0
        conf_level = 0.95
        stop_crit = StochStopCriterion(conf_dist, conf_level)
        x0 = np.random.binomial(1, rand_search_active_prob, self.dim)

        # compile the snapshot
        self.nc = compile_numerical_circuit_at(circuit=self.grid, t_idx=None)
        self.results = InvestmentsEvaluationResults(investment_groups_names=self.grid.get_investment_groups_names(),
                                                    max_eval=self.options.max_eval)
        # disable all status
        self.nc.set_investments_status(investments_list=self.grid.investments, status=0)

        # evaluate the investments
        self.__eval_index = 0

        # add baseline
        self.objective_function(combination=np.zeros(self.results.n_groups, dtype=int))

        # optimize
        sorted_y_, sorted_x_, y_population_, x_population_, f_population_ = MVRSM_mo_scaled(
            obj_func=self.objective_function,
            x0=x0,
            lb=lb,
            ub=ub,
            num_int=self.dim,
            max_evals=self.options.max_eval,
            rand_evals=rand_evals,
            args=(),
            stop_crit=stop_crit,
            n_objectives=6
        )

        self.results.set_at(eval_idx=np.arange(len(y_population_)),
                            capex=y_population_[:, 4],
                            opex=y_population_[:, 5],
                            losses=y_population_[:, 0],
                            overload_score=y_population_[:, 1],
                            voltage_score=y_population_[:, 2],
                            objective_function=f_population_,
                            combination=x_population_,
                            index_name=np.array(['Evaluation {}'.format(i) for i in range(len(y_population_))]))

        self.report_done()

    def optimized_evaluation_mvrsm_pareto(self) -> None:
        """
        Run an optimized investment evaluation without considering multiple evaluation groups at a time
        """

        # configure MVRSM:

        # number of random evaluations at the beginning
        rand_evals = round(self.dim * 1.5)
        lb = np.zeros(self.dim)
        ub = np.ones(self.dim)
        rand_search_active_prob = 0.5
        x0 = np.random.binomial(1, rand_search_active_prob, self.dim)

        # compile the snapshot
        self.nc = compile_numerical_circuit_at(circuit=self.grid, t_idx=None)
        self.results = InvestmentsEvaluationResults(investment_groups_names=self.grid.get_investment_groups_names(),
                                                    max_eval=self.options.max_eval)
        # disable all status
        self.nc.set_investments_status(investments_list=self.grid.investments, status=0)

        # evaluate the investments
        self.__eval_index = 0

        # add baseline
        self.objective_function(combination=np.zeros(self.results.n_groups, dtype=int))

        sorted_y_, sorted_x_, y_population_, x_population_ = MVRSM_mo_pareto(
            obj_func=self.objective_function,
            x0=x0,
            lb=lb,
            ub=ub,
            num_int=self.dim,
            max_evals=self.options.max_eval,
            n_objectives=6,
            rand_evals=rand_evals,
            args=()
        )

        self.results.set_at(eval_idx=np.arange(len(y_population_)),
                            capex=y_population_[:, 4],
                            opex=y_population_[:, 5],
                            losses=y_population_[:, 0],
                            overload_score=y_population_[:, 1],
                            voltage_score=y_population_[:, 2],
                            objective_function=y_population_[:, 4] * 0.00001 + y_population_[:, 0],
                            combination=x_population_,
                            index_name=np.array(['Evaluation {}'.format(i) for i in range(len(y_population_))]))

        self.report_done()

    def run(self):
        """
        run the QThread
        :return:
        """

        self.tic()

        if self.options.solver == InvestmentEvaluationMethod.Independent:
            self.independent_evaluation()

        elif self.options.solver == InvestmentEvaluationMethod.Hyperopt:
            self.optimized_evaluation_hyperopt()

        elif self.options.solver == InvestmentEvaluationMethod.MVRSM:
            self.optimized_evaluation_mvrsm()

        elif self.options.solver == InvestmentEvaluationMethod.MVRSM_multi:
            self.optimized_evaluation_mvrsm_pareto()

        else:
            raise Exception('Unsupported method')

        self.toc()

    def cancel(self):
        self.__cancel__ = True
