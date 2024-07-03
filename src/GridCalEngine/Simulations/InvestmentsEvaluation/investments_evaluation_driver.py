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

from typing import List, Dict, Union
from GridCalEngine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from GridCalEngine.Simulations.PowerFlow.power_flow_ts_driver import PowerFlowTimeSeriesDriver
from GridCalEngine.Simulations.OPF.opf_ts_results import OptimalPowerFlowTimeSeriesResults
from GridCalEngine.Simulations.Clustering.clustering_results import ClusteringResults
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Devices.Aggregation.investment import Investment
from GridCalEngine.Utils.NumericalMethods.MVRSM_mo_scaled import MVRSM_mo_scaled
from GridCalEngine.Utils.NumericalMethods.MVRSM_mo_pareto import MVRSM_mo_pareto
from GridCalEngine.Simulations.InvestmentsEvaluation.Methods.stop_crits import StochStopCriterion
from GridCalEngine.Simulations.InvestmentsEvaluation.investments_evaluation_results import InvestmentsEvaluationResults
from GridCalEngine.Simulations.InvestmentsEvaluation.investments_evaluation_options import InvestmentsEvaluationOptions
from GridCalEngine.Simulations.InvestmentsEvaluation.Methods.NSGA_3 import NSGA_3
from GridCalEngine.Simulations.InvestmentsEvaluation.Methods.random_eval import random_trial
from GridCalEngine.Utils.scores import get_overload_score, get_voltage_phase_score, get_voltage_module_score
from GridCalEngine.enumerations import (InvestmentEvaluationMethod, SimulationTypes, EngineType,
                                        InvestmentsEvaluationObjectives)
from GridCalEngine.basic_structures import IntVec, Vec


class InvestmentScores:
    """
    InvestmentScores
    """

    def __init__(self) -> None:
        """
        Constructor
        """
        self.capex_score: float = 0.0
        self.opex_score: float = 0.0
        self.losses_score: float = 0.0
        self.overload_score: float = 0.0
        self.voltage_module_score: float = 0.0
        self.voltage_angle_score: float = 0.0

    # @property
    # def electrical_score(self) -> float:
    #     return self.losses_score + self.overload_score + self.voltage_module_score + self.voltage_angle_score

    @property
    def financial_score(self) -> float:
        """
        Get the financial score: CAPEX + OPEX
        :return: float
        """
        return self.capex_score + self.opex_score

    def arr(self) -> Vec:
        """
        Return multidimensional metrics for the optimization
        :return: array of 2 values
        """
        # return np.array([self.electrical_score, self.financial_score])
        return np.array([self.losses_score, self.overload_score, self.voltage_module_score, self.voltage_angle_score,
                         self.financial_score])


def power_flow_function(inv_list: List[Investment],
                        grid: MultiCircuit,
                        pf_options: PowerFlowOptions,
                        branches_cost,
                        vm_cost: Vec,
                        vm_max: Vec,
                        vm_min: Vec,
                        va_cost: Vec,
                        va_max: Vec,
                        va_min: Vec) -> InvestmentScores:
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

    scores = InvestmentScores()

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
    scores.opex_score = sum([inv.OPEX for inv in inv_list])

    return scores


def power_flow_ts_function(inv_list: List[Investment],
                           grid: MultiCircuit,
                           pf_options: PowerFlowOptions,
                           time_indices: IntVec,
                           opf_time_series_results: Union[None, OptimalPowerFlowTimeSeriesResults],
                           clustering_results: Union[ClusteringResults, None],
                           engine: EngineType,
                           branches_cost,
                           vm_cost: Vec,
                           vm_max: Vec,
                           vm_min: Vec,
                           va_cost: Vec,
                           va_max: Vec,
                           va_min: Vec) -> InvestmentScores:
    """
    Compute the power flow of the grid given an investments group
    :param inv_list: list of Investments
    :param grid: MultiCircuit grid
    :param pf_options: Power flow options
    :param time_indices: Time indices of the investments
    :param opf_time_series_results: Optimal power flow results
    :param clustering_results: Clustering results
    :param engine: Engine type
    :param branches_cost: Array with all overloading cost for the branches
    :param vm_cost: Array with all the bus voltage module violation costs
    :param vm_max: Array with the Vm min values
    :param vm_min: Array with the Vm max values
    :param va_cost: Array with all the bus voltage angles violation costs
    :param va_max: Array with the Va max values
    :param va_min: Array with the Va min values
    :return: InvestmentScores
    """
    driver = PowerFlowTimeSeriesDriver(grid=grid,
                                       options=pf_options,
                                       time_indices=time_indices,
                                       opf_time_series_results=opf_time_series_results,
                                       clustering_results=clustering_results,
                                       engine=engine)
    driver.run()

    scores = InvestmentScores()

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
    scores.opex_score = sum([inv.OPEX for inv in inv_list])

    return scores


class InvestmentsEvaluationDriver(TimeSeriesDriverTemplate):
    name = 'Investments evaluation'
    tpe = SimulationTypes.InvestmentsEvaluation_run

    def __init__(self,
                 grid: MultiCircuit,
                 options: InvestmentsEvaluationOptions,
                 time_indices: Union[IntVec, None] = None,
                 opf_time_series_results: Union[None, OptimalPowerFlowTimeSeriesResults] = None,
                 clustering_results: Union[ClusteringResults, None] = None,
                 engine: EngineType = EngineType.GridCal):
        """
        InputsAnalysisDriver class constructor
        :param grid: MultiCircuit instance
        :param options: InvestmentsEvaluationOptions
        :param time_indices: Time indices of the investments
        :param opf_time_series_results: Optimal power flow results
        :param clustering_results: Clustering results
        """
        TimeSeriesDriverTemplate.__init__(self,
                                          grid=grid,
                                          time_indices=time_indices,
                                          clustering_results=clustering_results,
                                          engine=engine,
                                          check_time_series=False)

        # options object
        self.options = options

        # Optional, previously computed OPF results
        self.opf_time_series_results: Union[None, OptimalPowerFlowTimeSeriesResults] = opf_time_series_results

        # results object
        self.results = InvestmentsEvaluationResults(investment_groups_names=grid.get_investment_groups_names(),
                                                    max_eval=0)

        # dictionary of investment groups
        self.investments_by_group: Dict[int, List[Investment]] = self.grid.get_investmenst_by_groups_index_dict()

        # dimensions
        self.dim = len(self.grid.investments_groups)

        # max iter
        self.max_iter = options.max_eval

        # gather a dictionary of all the elements, this serves for the investments generation
        self.get_all_elements_dict = self.grid.get_all_elements_dict()

        # compose useful arrays
        self.vm_cost = np.array([e.Vm_cost for e in grid.get_buses()], dtype=float)
        self.vm_max = np.array([e.Vmax for e in grid.get_buses()], dtype=float)
        self.vm_min = np.array([e.Vmin for e in grid.get_buses()], dtype=float)

        self.va_cost = np.array([e.angle_cost for e in grid.get_buses()], dtype=float)
        self.va_max = np.array([e.angle_max for e in grid.get_buses()], dtype=float)
        self.va_min = np.array([e.angle_min for e in grid.get_buses()], dtype=float)

        self.branches_cost = np.array([e.Cost for e in grid.get_branches_wo_hvdc()], dtype=float)

    def get_steps(self):
        """

        :return:
        """
        return self.results.get_index()

    def get_investments_for_combination(self, combination: IntVec) -> List[Investment]:
        """
        Get the list of the investments that belong to a certain combination
        :param combination: array of 0/1
        :return: list of investments objects
        """
        # add all the investments of the investment groups reflected in the combination
        inv_list: List[Investment] = list()

        for i, active in enumerate(combination):
            if active == 1:
                inv_list += self.investments_by_group[i]
            if active == 0:
                pass
            else:
                # raise Exception('Value different from 0 and 1!')
                # print('Value different from 0 and 1!', active)
                pass
        return inv_list

    def objective_function(self, combination: IntVec) -> Vec:
        """
        Function to evaluate a combination of investments
        :param combination: vector of investments (yes/no). Length = number of investment groups
        :return: multi-objective function criteria values
        """

        inv_list: List[Investment] = self.get_investments_for_combination(combination)

        # enable the investment
        self.grid.set_investments_status(investments_list=inv_list,
                                         status=True,
                                         all_elements_dict=self.get_all_elements_dict)

        # do something
        if self.options.objf_tpe == InvestmentsEvaluationObjectives.PowerFlow:
            scores = power_flow_function(inv_list=inv_list,
                                         grid=self.grid,
                                         pf_options=self.options.pf_options,
                                         branches_cost=self.branches_cost,
                                         vm_cost=self.vm_cost,
                                         vm_max=self.vm_max,
                                         vm_min=self.vm_min,
                                         va_cost=self.va_cost,
                                         va_max=self.va_max,
                                         va_min=self.va_min)

        elif self.options.objf_tpe == InvestmentsEvaluationObjectives.TimeSeriesPowerFlow:

            scores = power_flow_ts_function(inv_list=inv_list,
                                            grid=self.grid,
                                            pf_options=self.options.pf_options,
                                            time_indices=self.time_indices,
                                            opf_time_series_results=self.opf_time_series_results,
                                            clustering_results=self.clustering_results,
                                            engine=self.engine,
                                            branches_cost=self.branches_cost,
                                            vm_cost=self.vm_cost,
                                            vm_max=self.vm_max,
                                            vm_min=self.vm_min,
                                            va_cost=self.va_cost,
                                            va_max=self.va_max,
                                            va_min=self.va_min)
        else:
            raise Exception(f'Unknown investments objective function type {self.options.objf_tpe}')

        # revert to the initial state
        self.grid.set_investments_status(investments_list=inv_list,
                                         status=False,
                                         all_elements_dict=self.get_all_elements_dict)

        # record the evaluation
        self.results.add(capex=scores.capex_score,
                         opex=scores.opex_score,
                         losses=scores.losses_score,
                         overload_score=scores.overload_score,
                         voltage_score=scores.voltage_module_score,
                         # electrical=scores.electrical_score,
                         financial=scores.financial_score,
                         objective_function_sum=scores.arr().sum(),
                         combination=combination)

        # Report the progress
        self.report_progress2(self.results.current_evaluation, self.max_iter)

        return scores.arr()

    def objective_function_so(self, combination: IntVec) -> float:
        """
        Single objective version of the objective function
        :param combination:
        :return:
        """
        res_vec = self.objective_function(combination=combination)

        return res_vec.sum()

    def independent_evaluation(self) -> None:
        """
        Run a one-by-one investment evaluation without considering multiple evaluation groups at a time
        """
        self.max_iter = len(self.grid.investments_groups) + 1

        # declare the results
        self.results = InvestmentsEvaluationResults(investment_groups_names=self.grid.get_investment_groups_names(),
                                                    max_eval=self.max_iter)

        # add baseline
        self.objective_function(combination=np.zeros(self.results.n_groups, dtype=int))

        dim = len(self.grid.investments_groups)

        # add one at a time
        for k in range(dim):
            self.report_text("Evaluating investment group {}...".format(k))

            combination = np.zeros(dim, dtype=int)
            combination[k] = 1

            self.objective_function(combination=combination)

        # self.results.pareto_sort()

        self.report_done()

    def optimized_evaluation_mvrsm(self) -> None:
        """
        Run an optimized investment evaluation without considering multiple evaluation groups at a time
        """

        self.report_text("Evaluating investments with MVRSM...")

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
        self.results = InvestmentsEvaluationResults(investment_groups_names=self.grid.get_investment_groups_names(),
                                                    max_eval=self.options.max_eval + 1)

        # add baseline
        ret = self.objective_function(combination=np.zeros(self.results.n_groups, dtype=int))

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
            n_objectives=len(ret)
        )

        self.results.set_best_combination(combination=sorted_x_[0, :])

        self.report_done()

    def optimized_evaluation_mvrsm_pareto(self) -> None:
        """
        Run an optimized investment evaluation without considering multiple evaluation groups at a time
        """

        self.report_text("Evaluating investments with multi-objective MVRSM...")

        # number of random evaluations at the beginning
        rand_evals = round(self.dim * 1.5)
        lb = np.zeros(self.dim)
        ub = np.ones(self.dim)
        rand_search_active_prob = 0.5
        x0 = np.random.binomial(1, rand_search_active_prob, self.dim)

        # compile the snapshot
        self.results = InvestmentsEvaluationResults(investment_groups_names=self.grid.get_investment_groups_names(),
                                                    max_eval=self.options.max_eval + 2)

        # add baseline
        ret = self.objective_function(combination=np.zeros(self.results.n_groups, dtype=int))

        sorted_y_, sorted_x_, y_population_, x_population_ = MVRSM_mo_pareto(
            obj_func=self.objective_function,
            x0=x0,
            lb=lb,
            ub=ub,
            num_int=self.dim,
            max_evals=self.options.max_eval,
            n_objectives=len(ret),
            rand_evals=rand_evals,
            args=()
        )

        self.results.set_best_combination(combination=sorted_x_[0, :])

        self.report_done()

    def optimized_evaluation_nsga3(self) -> None:
        """
        Run an optimized investment evaluation with NSGA3
        """
        self.report_text("Evaluating investments with NSGA3...")

        pop_size = int(round(self.dim))  # if needed, divide by 5 for ideal grid
        n_partitions = int(round(pop_size))

        # compile the snapshot
        self.results = InvestmentsEvaluationResults(investment_groups_names=self.grid.get_investment_groups_names(),
                                                    max_eval=self.options.max_eval * 2)

        # add baseline
        ret = self.objective_function(combination=np.zeros(self.results.n_groups, dtype=int))

        # optimize
        X, obj_values = NSGA_3(
            obj_func=self.objective_function,
            n_partitions=n_partitions,
            n_var=self.dim,
            n_obj=len(ret),
            max_evals=self.options.max_eval,  # termination
            pop_size=pop_size,
            crossover_prob=0.8,
            mutation_probability=0.1,
            eta=30,
        )

        self.results.set_best_combination(combination=X[:, 0])

        self.results.trim()

        self.report_done()

    def randomized_evaluation(self) -> None:
        """
        Run purely random evaluations, without any optimization
        """
        self.report_text("Randomly evaluating investments...")

        # compile the snapshot
        self.results = InvestmentsEvaluationResults(investment_groups_names=self.grid.get_investment_groups_names(),
                                                    max_eval=self.options.max_eval * 2)

        # add baseline
        ret = self.objective_function(combination=np.zeros(self.results.n_groups, dtype=int))

        # optimize
        X, obj_values = random_trial(
            obj_func=self.objective_function,
            n_var=self.dim,
            n_obj=len(ret),
            max_evals=self.options.max_eval,
        )

        self.results.set_best_combination(combination=X[:, 0])

        self.report_done()

    def run(self) -> None:
        """
        run the QThread
        """

        self.tic()

        self.logger.add_info(msg="Solver", value=f"{self.options.solver.value}")
        self.logger.add_info(msg="Max evaluations", value=f"{self.options.max_eval}")

        if self.options.solver == InvestmentEvaluationMethod.Independent:
            self.independent_evaluation()

        elif self.options.solver == InvestmentEvaluationMethod.MVRSM:
            self.optimized_evaluation_mvrsm_pareto()

        elif self.options.solver == InvestmentEvaluationMethod.NSGA3:
            self.optimized_evaluation_nsga3()

        elif self.options.solver == InvestmentEvaluationMethod.Random:
            self.randomized_evaluation()

        else:
            raise Exception('Unsupported method')

        # report the combination
        inv_list = self.get_investments_for_combination(combination=self.results.best_combination)
        for inv in inv_list:
            self.logger.add_info(msg=f"Best combination", device=inv.idtag, value=inv.name)

        # this stores the pareto indices in the solution object for later usage
        self.results.get_pareto_indices()

        self.toc()
