# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import timeit
from math import comb

import numpy as np


from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Utils.NumericalMethods.MVRSM_mo_pareto import MVRSM_mo_pareto
from VeraGridEngine.Simulations.InvestmentsEvaluation.investments_evaluation_results import InvestmentsEvaluationResults
from VeraGridEngine.Simulations.InvestmentsEvaluation.investments_evaluation_options import InvestmentsEvaluationOptions
from VeraGridEngine.Simulations.InvestmentsEvaluation.Methods.NSGA_3 import NSGA_3
from VeraGridEngine.Simulations.InvestmentsEvaluation.Methods.mixed_variable_NSGA_2 import NSGA_2
from VeraGridEngine.Simulations.InvestmentsEvaluation.Methods.random_eval import random_trial
from VeraGridEngine.Simulations.InvestmentsEvaluation.Methods.toot_pint_cba import (
    TOOT_PINT_CBA,
    get_toot_pint_seed_population,
)
from VeraGridEngine.Simulations.InvestmentsEvaluation.Problems.black_box_problem_template import BlackBoxProblemTemplate
from VeraGridEngine.enumerations import EngineType, InvestmentEvaluationMethod, InvestmentsEvaluationObjectives, SimulationTypes
from VeraGridEngine.basic_structures import IntVec, IntMat, Vec, Mat
from VeraGridEngine.Compilers.Gslv.activation import GSLV_AVAILABLE, GSLV_UNAVAILABLE_REASON
from VeraGridEngine.Compilers.Gslv.Simulations.investments import gslv_investments_evaluation

class InvestmentsEvaluationDriver(DriverTemplate):
    __slots__ = (
        "options",
        "problem",
    )

    name = 'Investments evaluation'
    tpe = SimulationTypes.InvestmentsEvaluation_run

    def __init__(self,
                 grid: MultiCircuit,
                 options: InvestmentsEvaluationOptions,
                 problem: BlackBoxProblemTemplate,
                 engine: EngineType = EngineType.VeraGrid):
        """
        InputsAnalysisDriver class constructor
        :param grid: MultiCircuit instance
        :param options: InvestmentsEvaluationOptions
        :param problem: BlackBoxProblemTemplate
        :param engine: EngineType
        """

        super().__init__(grid=grid, engine=engine)

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

    def initialize(self, max_iter: int):
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

        if self.is_cancel():
            objectives: Vec = np.zeros(len(self.problem.get_objectives_names()), dtype=float)
        else:
            objectives = self.problem.objective_function(x)

            if record_results:
                self.results.add(x_vec=x, f_vec=objectives)
                self.report_progress2(self.results.current_evaluation, self.results.max_eval)
            else:
                pass

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
        Evaluate projects with a CBA-like reference/PINT/TOOT ranking and then build a cumulative portfolio.
        """
        self.report_text("Evaluating investments with a CBA-like independent sequence...")
        dim: int = self.problem.n_vars()
        n_cumulative_evaluations: int = dim - 1 if dim > 0 else 0

        # The displayed metrics must come from the active problem, so the results object is initialized with the
        # problem objective names and every stored evaluation comes from self.objective_function().
        self.initialize(max_iter=1 + dim + n_cumulative_evaluations)

        best_combination: IntVec = TOOT_PINT_CBA(
            obj_func=self.objective_function,
            n_var=dim,
            lb=self.problem.x_min,
            ub=self.problem.x_max,
            n_obj=len(self.problem.get_objectives_names()),
            objective_names=self.problem.get_objectives_names(),
            variable_names=self.problem.get_vars_names(),
            report_text=self.report_text,
            logger=self.logger,
            cancel_checker=self.is_cancel,
        )

        if self.is_cancel():
            pass
        else:
            self.results.set_best_combination(combination=best_combination)

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
            args=(),
            cancel_checker=self.is_cancel
        )

        if not self.is_cancel() and len(sorted_x_) > 0:
            self.results.set_best_combination(combination=sorted_x_[0, :])
        else:
            pass

    def optimized_evaluation_nsga3(self) -> None:
        """
        Run an optimized investment evaluation with NSGA3
        """
        self.report_text("Evaluating investments with NSGA3...")
        dim = self.problem.n_vars()
        pop_size = int(round(dim))  # for the ieee 118 bus grid make this * 3

        # compile the snapshot (+1 for the baseline evaluation)
        self.initialize(max_iter=self.options.max_eval + 1)

        # add baseline
        ret = self.objective_function(x=np.zeros(self.problem.n_vars(), dtype=int))

        # find the largest n_partitions such that ref_dirs <= pop_size
        # ref_dirs = C(n_partitions + n_obj - 1, n_obj - 1) with das-dennis
        n_obj = len(ret)
        n_partitions = 1
        while comb(n_partitions + 1 + n_obj - 1, n_obj - 1) <= pop_size:
            n_partitions += 1

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
            cancel_checker=self.is_cancel,
        )

        if not self.is_cancel() and X is not None and len(X) > 0:
            self.results.set_best_combination(combination=X[:, 0])
        else:
            pass

    def optimized_evaluation_pint_toot_nsga3(self) -> None:
        """
        Run an NSGA3 search warm-started with the direct PINT and TOOT evaluations.
        """
        self.report_text("Evaluating investments with PINT/TOOT-seeded NSGA3...")
        dim: int = self.problem.n_vars()
        pop_size: int = int(round(dim))
        n_obj: int = len(self.problem.get_objectives_names())

        # Record the evaluated warm-start points first and then leave the remaining budget to NSGA3 itself.
        self.initialize(max_iter=self.options.max_eval + 2 * dim + 2)

        seed_population: IntMat
        seed_objectives: Mat
        seed_population, seed_objectives = get_toot_pint_seed_population(
            obj_func=self.objective_function,
            n_var=dim,
            lb=self.problem.x_min,
            ub=self.problem.x_max,
            n_obj=n_obj,
            objective_names=self.problem.get_objectives_names(),
            variable_names=self.problem.get_vars_names(),
            pop_size=pop_size,
            report_text=self.report_text,
            logger=self.logger,
            record_results=True,
            cancel_checker=self.is_cancel,
        )

        # Find the largest number of reference partitions compatible with the selected population size.
        n_partitions: int = 1
        while comb(n_partitions + 1 + n_obj - 1, n_obj - 1) <= pop_size:
            n_partitions += 1

        X, obj_values = NSGA_3(
            obj_func=self.objective_function,
            n_partitions=n_partitions,
            n_var=dim,
            lb=self.problem.x_min,
            ub=self.problem.x_max,
            n_obj=n_obj,
            max_evals=self.options.max_eval,
            pop_size=pop_size,
            crossover_prob=0.8,
            mutation_probability=0.1,
            eta=30,
            initial_population=seed_population,
            initial_objectives=seed_objectives,
            cancel_checker=self.is_cancel,
        )

        if not self.is_cancel() and X is not None and len(X) > 0:
            self.results.set_best_combination(combination=X[:, 0])
        else:
            pass

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
            cancel_checker=self.is_cancel,
        )

        if not self.is_cancel() and len(X) > 0:
            self.results.set_best_combination(combination=X[:, 0])
        else:
            pass

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
            cancel_checker=self.is_cancel,
            # crossover_prob=0.8,
            # mutation_probability=0.1,
            # eta=30,
        )

        res_x = []
        if X is not None:
            for i, v in enumerate(X):
                if isinstance(v, dict):
                    vall = list(v.values())[0]
                    res_x.append(vall)
                else:
                    res_x.append(v)
        else:
            pass

        if not self.is_cancel() and len(res_x) > 0:
            self.results.set_best_combination(combination=np.array(res_x))
        else:
            pass

    def run(self) -> None:
        """
        run the QThread
        """

        self.tic()
        self.report_text("Compiling and configuring...")

        self.logger.add_info(msg="Solver", value=f"{self.options.solver.value}")
        self.logger.add_info(msg="Max evaluations", value=f"{self.options.max_eval}")

        if self.engine == EngineType.GSLV and not GSLV_AVAILABLE:
            self.engine = EngineType.VeraGrid
            self.logger.add_warning(f'GSLV unavailable: {GSLV_UNAVAILABLE_REASON}; falling back to VeraGrid')
        else:
            pass

        if self.engine == EngineType.GSLV:
            if self.options.objf_tpe not in (
                    InvestmentsEvaluationObjectives.PowerFlow,
                    InvestmentsEvaluationObjectives.TimeSeriesPowerFlow,
                    InvestmentsEvaluationObjectives.LinearOptimalPowerFlowTimeSeries):
                self.engine = EngineType.VeraGrid
                self.logger.add_warning(
                    'GSLV investments evaluation does not support this objective, falling back to VeraGrid'
                )
            else:
                pass
        else:
            pass

        if self.engine == EngineType.GSLV and self.options.solver == InvestmentEvaluationMethod.FromPlugin:
            self.engine = EngineType.VeraGrid
            self.logger.add_warning(
                'GSLV investments evaluation does not support VeraGrid plugin solvers, falling back to VeraGrid'
            )
        else:
            pass

        if self.engine == EngineType.GSLV:
            self.report_text("Evaluating investments with GSLV...")
            self.results = gslv_investments_evaluation(
                circuit=self.grid,
                options=self.options,
                logger=self.logger,
            )

        elif self.options.solver == InvestmentEvaluationMethod.CBA_PINT_TOOT:
            self.independent_evaluation()

        elif self.options.solver == InvestmentEvaluationMethod.MVRSM:
            self.optimized_evaluation_mvrsm_pareto()

        elif self.options.solver == InvestmentEvaluationMethod.NSGA3:
            self.optimized_evaluation_nsga3()

        elif self.options.solver == InvestmentEvaluationMethod.PINT_TOOT_NSGA3:
            self.optimized_evaluation_pint_toot_nsga3()

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
        if self.engine != EngineType.GSLV:
            self.results.finalize()
        else:
            pass

        # report the combination
        if self.problem is not None:
            inv_list = self.problem.get_investments_for_combination(x=self.results.f_best)
        else:
            inv_list = list()
        for inv in inv_list:
            self.logger.add_info(msg=f"Best combination", device=inv.idtag, value=inv.name)

        self.toc()
        if self.is_cancel():
            self.report_done("Cancelled!")
        else:
            self.report_done()

    def cancel(self) -> None:
        """
        Request cancellation without emitting completion from the caller thread.

        :return: None.
        """
        DriverTemplate.cancel(self)
