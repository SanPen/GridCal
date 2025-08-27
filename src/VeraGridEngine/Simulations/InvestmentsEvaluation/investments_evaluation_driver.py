# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import timeit

import numpy as np

from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Utils.NumericalMethods.MVRSM_mo_pareto import MVRSM_mo_pareto
from VeraGridEngine.Simulations.InvestmentsEvaluation.investments_evaluation_results import InvestmentsEvaluationResults
from VeraGridEngine.Simulations.InvestmentsEvaluation.investments_evaluation_options import InvestmentsEvaluationOptions
from VeraGridEngine.Simulations.InvestmentsEvaluation.Methods.NSGA_3 import NSGA_3
from VeraGridEngine.Simulations.InvestmentsEvaluation.Methods.mixed_variable_NSGA_2 import NSGA_2
from VeraGridEngine.Simulations.InvestmentsEvaluation.Methods.random_eval import random_trial
from VeraGridEngine.Simulations.InvestmentsEvaluation.Problems.black_box_problem_template import BlackBoxProblemTemplate
from VeraGridEngine.enumerations import InvestmentEvaluationMethod, SimulationTypes
from VeraGridEngine.basic_structures import IntVec, Vec


class InvestmentsEvaluationDriver(DriverTemplate):
    name = 'Investments evaluation'
    tpe = SimulationTypes.InvestmentsEvaluation_run

    def __init__(self,
                 grid: MultiCircuit,
                 options: InvestmentsEvaluationOptions,
                 problem: BlackBoxProblemTemplate):
        """
        InputsAnalysisDriver class constructor
        :param grid: MultiCircuit instance
        :param options: InvestmentsEvaluationOptions
        :param problem: BlackBoxProblemTemplate
        """

        super().__init__(grid=grid)

        # options object
        self.options = options

        # problem definition
        self.problem: BlackBoxProblemTemplate = problem

        # results object
        if problem is not None:
            self.results = InvestmentsEvaluationResults(
                f_names=self.problem.get_objectives_names(),
                x_names=self.problem.get_vars_names(),
                plot_x_idx=self.problem.plot_x_idx,
                plot_y_idx=self.problem.plot_y_idx,
                max_eval=self.options.max_eval
            )
        else:
            self.results = InvestmentsEvaluationResults(
                f_names=np.array([]),
                x_names=np.array([]),
                plot_x_idx=0,
                plot_y_idx=0,
                max_eval=self.options.max_eval
            )
    def initialize(self, max_iter):
        """
        Initialize the results
        :param max_iter: Maximum iterations
        """
        self.results = InvestmentsEvaluationResults(
            f_names=self.problem.get_objectives_names(),
            x_names=self.problem.get_vars_names(),
            plot_x_idx=self.problem.plot_x_idx,
            plot_y_idx=self.problem.plot_y_idx,
            max_eval=max_iter
        )

    def get_steps(self):
        """

        :return:
        """
        return self.results.get_index()

    def objective_function(self, x: IntVec, record_results: bool = True) -> Vec:
        """
        Function to evaluate a combination of investments
        :param x: vector of investments (yes/no). Length = number of investment groups
        :param record_results: record the results or not
        :return: multi-objective function criteria values
        """

        objectives = self.problem.objective_function(x)

        if record_results:
            self.results.add(x_vec=x, f_vec=objectives)

        # Report the progress
        self.report_progress2(self.results.current_evaluation, self.results.max_eval)

        return objectives

    def objective_function_so(self, x: IntVec) -> float:
        """
        Single objective version of the objective function
        :param x: vector of investments (yes/no). Length = number of investment groups
        :return: summation of the objectives
        """
        res_vec = self.objective_function(x=x)

        return res_vec.sum()

    def evaluate_individual_investments(self):
        """
        Run a one-by-one investment evaluation without considering multiple evaluation groups at a time
        """
        results_with_combinations = list()
        dim = len(self.grid.investments_groups)
        self.objective_function(x=np.zeros(self.problem.n_vars(), dtype=int))
        baseline = self.objective_function(x=np.zeros(dim, dtype=int))
        results_with_combinations.append((baseline, np.zeros(dim, dtype=int)))
        st = timeit.default_timer()
        for k in range(dim):
            self.report_text(f"Evaluating investment group {k}...")
            combination = np.zeros(dim, dtype=int)
            combination[k] = 1
            results = self.objective_function(x=combination, record_results=False)
            results_with_combinations.append((results, combination))
        et = timeit.default_timer()
        print(f"Time taken to evaluate individual investments: {et - st}")
        return results_with_combinations

    def independent_evaluation(self) -> None:
        """
        Sort investments in order and then evaluate cumulative combinations of increasingly expensive investments
        """

        self.initialize(max_iter=(self.problem.n_vars() + 1) * 2)

        # Add baseline evaluation
        self.objective_function(x=np.zeros(self.problem.n_vars(), dtype=int))
        results_with_combinations = self.evaluate_individual_investments()

        # Sort the results in ascending financial score
        sorted_results_with_combinations = sorted(results_with_combinations, key=lambda x: x[0][4])

        dim = len(self.grid.investments_groups)
        cumulative_combination = np.zeros(dim, dtype=int)
        cumulative_combinations = []

        # Cumulative combinations

        for results, combination in sorted_results_with_combinations:
            cumulative_combination += combination
            # print(f"Combination: {combination}, Results: {results}, Cumulative Combination: {cumulative_combination}")
            cumulative_combinations.append(cumulative_combination.copy())

        st = timeit.default_timer()
        # Evaluate each cumulative combination
        for cumulative_combination in cumulative_combinations:
            self.report_text(f"Evaluating cumulative combination: {cumulative_combination}")
            self.objective_function(x=cumulative_combination, record_results=True)
        et = timeit.default_timer()
        print(f"Time taken to evaluate cumulative combinations: {et - st}")

    def optimized_evaluation_mvrsm_pareto(self) -> None:
        """
        Run an optimized investment evaluation without considering multiple evaluation groups at a time
        """

        self.report_text("Evaluating investments with multi-objective MVRSM...")

        # number of random evaluations at the beginning
        dim = self.problem.n_vars()
        rand_evals = round(dim)
        lb = self.problem.x_min
        ub = self.problem.x_max
        rand_search_active_prob = 0.5
        x0 = np.random.binomial(1, rand_search_active_prob, dim)

        # compile the snapshot
        self.initialize(max_iter=self.options.max_eval * 2)

        # add baseline
        ret = self.objective_function(x=np.zeros(self.problem.n_vars(), dtype=int))

        sorted_y_, sorted_x_, y_population_, x_population_ = MVRSM_mo_pareto(
            obj_func=self.objective_function,
            x0=x0,
            lb=lb,
            ub=ub,
            num_int=dim,
            max_evals=self.options.max_eval,
            n_objectives=len(ret),
            rand_evals=rand_evals,
            args=()
        )

        self.results.set_best_combination(combination=sorted_x_[0, :])

    def optimized_evaluation_nsga3(self) -> None:
        """
        Run an optimized investment evaluation with NSGA3
        """
        self.report_text("Evaluating investments with NSGA3...")
        dim = self.problem.n_vars()
        pop_size = int(round(dim))  # for the ieee 118 bus grid make this * 3
        n_partitions = int(round(pop_size))

        # compile the snapshot
        self.initialize(max_iter=self.options.max_eval * 2)

        # add baseline
        ret = self.objective_function(x=np.zeros(self.problem.n_vars(), dtype=int))

        # optimize
        X, obj_values = NSGA_3(
            obj_func=self.objective_function,
            n_partitions=n_partitions,
            n_var=dim,
            lb=self.problem.x_min,
            ub=self.problem.x_max,
            n_obj=len(ret),
            max_evals=self.options.max_eval,  # termination
            pop_size=pop_size,
            crossover_prob=0.8,
            mutation_probability=0.1,
            eta=30,
        )

        self.results.set_best_combination(combination=X[:, 0])

    def randomized_evaluation(self) -> None:
        """
        Run purely random evaluations, without any optimization
        """
        self.report_text("Randomly evaluating investments...")

        # compile the snapshot
        self.initialize(max_iter=self.options.max_eval)

        # add baseline
        ret = self.objective_function(x=np.zeros(self.problem.n_vars(), dtype=int))

        # optimize
        dim = self.problem.n_vars()
        X, obj_values = random_trial(
            obj_func=self.objective_function,
            n_var=dim,
            lb=self.problem.x_min,
            ub=self.problem.x_max,
            n_obj=len(ret),
            max_evals=self.options.max_eval,
        )

        self.results.set_best_combination(combination=X[:, 0])

    def optimized_evaluation_mixed_nsga2(self) -> None:
        """
        Run an optimized investment evaluation on mixed variables with NSGA2
        """
        self.report_text("Evaluating investments with NSGA2...")
        dim = self.problem.n_vars()
        pop_size = int(round(dim)) * 2

        # compile the snapshot
        self.initialize(max_iter=self.options.max_eval * 2)

        # add baseline
        ret = self.objective_function(x=np.zeros(self.problem.n_vars(), dtype=int))

        # optimize
        X, obj_values = NSGA_2(
            grid=self.grid,
            obj_func=self.objective_function,
            n_obj=len(ret),
            max_evals=self.options.max_eval,  # termination
            pop_size=pop_size,
            # crossover_prob=0.8,
            # mutation_probability=0.1,
            # eta=30,
        )

        res_x = []
        for i, v in enumerate(X):
            if isinstance(v, dict):
                vall = list(v.values())[0]
                res_x.append(vall)
            else:
                res_x.append(v)

        self.results.set_best_combination(combination=np.array(res_x))

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

        elif self.options.solver == InvestmentEvaluationMethod.MixedVariableGA:
            self.optimized_evaluation_mixed_nsga2()

        elif self.options.solver == InvestmentEvaluationMethod.FromPlugin:
            self.options.plugin_fcn_ptr(self)

        else:
            raise Exception('Unsupported method')

        # finalize
        self.report_text("Finalizing the results object...")
        self.results.finalize()

        # report the combination
        inv_list = self.problem.get_investments_for_combination(x=self.results.f_best)
        for inv in inv_list:
            self.logger.add_info(msg=f"Best combination", device=inv.idtag, value=inv.name)

        self.toc()
        self.report_done()
