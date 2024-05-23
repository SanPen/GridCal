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
from typing import List, Dict
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver, PowerFlowOptions
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Devices.Aggregation.investment import Investment
from GridCalEngine.Simulations.InvestmentsEvaluation.NumericalMethods.MVRSM_mo_scaled import MVRSM_mo_scaled
from GridCalEngine.Simulations.InvestmentsEvaluation.NumericalMethods.MVRSM_mo_pareto import MVRSM_mo_pareto
from GridCalEngine.Simulations.InvestmentsEvaluation.NumericalMethods.stop_crits import StochStopCriterion
from GridCalEngine.Simulations.InvestmentsEvaluation.investments_evaluation_results import InvestmentsEvaluationResults
from GridCalEngine.Simulations.InvestmentsEvaluation.investments_evaluation_options import InvestmentsEvaluationOptions
from GridCalEngine.Simulations.InvestmentsEvaluation.NumericalMethods.NSGA_3 import NSGA_3
from GridCalEngine.enumerations import InvestmentEvaluationMethod, SimulationTypes
from GridCalEngine.basic_structures import IntVec, Vec, CxVec


def get_overload_score(loading: CxVec, branches_cost: Vec) -> float:
    """
    Compute overload score by multiplying the loadings above 100% by the associated branch cost.
    :param loading: load results
    :param branches_cost: all branch elements from studied grid
    :return: sum of all costs associated to branch overloads
    """
    branches_loading = np.abs(loading)

    # get lines where loading is above 1 -- why not 0.9 ?
    branches_idx = np.where(branches_loading > 1)[0]

    # multiply by the load or only the overload?
    cost = branches_cost[branches_idx] * branches_loading[branches_idx]

    return np.sum(cost)


def get_voltage_module_score(voltage: CxVec, vm_cost: Vec, vm_max: Vec, vm_min: Vec) -> float:
    """
    Compute voltage module score by multiplying the voltages outside limits by the associated bus costs.
    :param voltage: voltage results
    :param vm_cost: Vm cost array
    :param vm_max: maximum voltage
    :param vm_min: minimum voltage
    :return: sum of all costs associated to voltage module deviation
    """

    vm = np.abs(voltage)
    vmax_diffs = np.array(vm - vm_max).clip(min=0)
    vmin_diffs = np.array(vm_min - vm).clip(min=0)
    cost = (vmax_diffs + vmin_diffs) * vm_cost

    return cost.sum()


def get_voltage_phase_score(voltage: CxVec, va_cost: Vec, va_max: Vec, va_min: Vec) -> float:
    """
    Compute voltage phase score by multiplying the phases outside limits by the associated bus costs.
    :param voltage: voltage results
    :param va_cost: array of bus angles costs
    :param va_max: maximum voltage angles
    :param va_min: minimum voltage angles
    :return: sum of all costs associated to voltage module deviation
    """
    vp = np.angle(voltage)
    va_max_diffs = np.array(vp - va_max).clip(min=0)
    va_min_diffs = np.array(va_min - vp).clip(min=0)
    cost = (va_max_diffs + va_min_diffs) * va_cost

    return cost.sum()


class InvestmentScores:

    def __init__(self):
        self.capex_score: float = 0
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
        return self.capex_score + self.opex_score

    def arr(self) -> Vec:
        """
        Return multidimensional metrics for the optimization
        :return: array of 2 values
        """
        # return np.array([self.electrical_score, self.financial_score])
        return np.array([self.losses_score, self.overload_score, self.voltage_module_score, self.voltage_angle_score, self.financial_score])


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

        # dictionary of investment groups
        self.investments_by_group: Dict[int, List[Investment]] = self.grid.get_investmenst_by_groups_index_dict()

        # dimensions
        self.dim = len(self.grid.investments_groups)

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
                                         all_elemnts_dict=self.get_all_elements_dict)

        # do something
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

        # revert to the initial state
        self.grid.set_investments_status(investments_list=inv_list,
                                         status=False,
                                         all_elemnts_dict=self.get_all_elements_dict)

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
        self.report_progress2(self.results.current_evaluation, self.options.max_eval)

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
        # compile the snapshot
        self.results = InvestmentsEvaluationResults(investment_groups_names=self.grid.get_investment_groups_names(),
                                                    max_eval=len(self.grid.investments_groups) + 1)

        # add baseline
        self.objective_function(combination=np.zeros(self.results.n_groups, dtype=int))

        dim = len(self.grid.investments_groups)

        for k in range(dim):
            self.report_text("Evaluating investment group {}...".format(k))

            combination = np.zeros(dim, dtype=int)
            combination[k] = 1

            self.objective_function(combination=combination)

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

        pop_size = int(round(self.dim)) # divide by 5 for ideal grid
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

        else:
            raise Exception('Unsupported method')

        # report the combination
        inv_list = self.get_investments_for_combination(combination=self.results.best_combination)
        for inv in inv_list:
            self.logger.add_info(msg=f"Best combination", device=inv.idtag, value=inv.name)

        self.toc()
