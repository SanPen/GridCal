# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from pymoo.core.problem import ElementwiseProblem
from pymoo.util.ref_dirs import get_reference_directions
from pymoo.optimize import minimize
from pymoo.algorithms.moo.nsga3 import NSGA3
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.repair.rounding import RoundingRepair
from pymoo.core.mixed import MixedVariableSampling
from pymoo.core.sampling import Sampling
from pymoo.operators.sampling.rnd import IntegerRandomSampling
from pymoo.core.mutation import Mutation
from VeraGridEngine.basic_structures import Vec, IntVec


class IntegerRandomSamplingVeraGrid(Sampling):
    def _do(self, problem, n_samples, **kwargs):
        xl = np.asarray(problem.xl, dtype=int)
        xu = np.asarray(problem.xu, dtype=int)

        n_var = len(xl)
        X = np.zeros((n_samples, n_var), dtype=int)

        for j in range(n_var):
            values = np.arange(xl[j], xu[j] + 1)
            for i in range(n_samples):
                X[i, j] = np.random.choice(values)

        return X


class UniformBinarySampling(Sampling):
    """
    UniformBinarySampling
    """

    def _do(self, problem, n_samples, **kwargs):
        num_ones = np.linspace(0, problem.n_var, n_samples, dtype=int)
        num_ones[-1] = problem.n_var
        ones_into_array = np.zeros((n_samples, problem.n_var), dtype=int)
        # Fill ones_into_array randomly
        for i, num in enumerate(num_ones):
            ones_into_array[i, :num] = 1
            np.random.shuffle(ones_into_array[i])

        return ones_into_array


class SkewedBinarySampling(Sampling):
    """
    SkewedBinarySampling
    """

    def _do(self, problem, n_samples, **kwargs):
        max_ones = int(problem.n_var * 1)
        num_ones = (np.linspace(0, 1, n_samples) ** 3 * max_ones).astype(int)
        num_ones[-1] = max_ones
        ones_into_array = np.zeros((n_samples, problem.n_var), dtype=int)

        # Fill ones_into_array randomly
        for i, num in enumerate(num_ones):
            ones_into_array[i, :num] = 1
            np.random.shuffle(ones_into_array[i])

        # # Add rows with only one '1'
        # additional_rows = 100
        # for _ in range(additional_rows):
        #     row = np.zeros(problem.n_var, dtype=int)
        #     row[np.random.randint(0, problem.n_var)] = 1
        #     ones_into_array = np.vstack([ones_into_array, row])

        return ones_into_array


class SkewedIntegerSamplingRange(Sampling):
    """
    SkewedIntegerSampling generates samples skewed toward the lower bounds
    but spread across the full lb–ub range. Works for integer variables.
    """

    def _do(self, problem, n_samples, **kwargs):
        xl = np.asarray(problem.xl, dtype=int)
        xu = np.asarray(problem.xu, dtype=int)

        n_var = len(xl)
        X = np.zeros((n_samples, n_var), dtype=int)

        # Generate skewed samples per variable
        for j in range(n_var):
            # Create skewed samples in [0, 1]
            skewed = (np.linspace(0, 1, n_samples) ** 3)

            # Scale to range [xl[j], xu[j]]
            range_j = xu[j] - xl[j]
            values = (skewed * range_j + xl[j]).astype(int)

            # Shuffle for diversity
            np.random.shuffle(values)
            X[:, j] = values

        return X


class QuadBinarySampling(Sampling):
    """
    QuadBinarySampling
    """

    def _do(self, problem, n_samples, **kwargs):
        max_ones = int(problem.n_var * 1)
        half_samples = n_samples // 2
        # Adjust the num_ones calculation to create a distribution that is quadratic in the first half
        num_ones = (np.linspace(0, 1, half_samples) * max_ones).astype(int)
        # Fill the rest of the array with 0s quadratically
        num_zeros = (np.linspace(1, 0, n_samples - half_samples) ** 3 * max_ones).astype(int)
        num_ones = np.concatenate([num_ones, num_zeros])
        ones_into_array = np.zeros((n_samples, problem.n_var), dtype=int)
        # Fill ones_into_array randomly
        for i, num in enumerate(num_ones):
            ones_into_array[i, :num] = 1
            np.random.shuffle(ones_into_array[i])

        return ones_into_array


class BitflipMutation(Mutation):
    """
    BitflipMutation
    """

    def _do(self, problem, x, **kwargs):
        mask = np.random.random(x.shape) < self.get_prob_var(problem)
        x[mask] = 1 - x[mask]
        return x


class GridNsga(ElementwiseProblem):
    """
    Problem formulation packaging to use the pymoo library
    """

    def __init__(self, obj_func, n_var, n_obj, lb: Vec | IntVec, ub: Vec | IntVec):
        """

        :param obj_func:
        :param n_var:
        :param n_obj:
        """
        super().__init__(n_var=n_var,
                         n_obj=n_obj,
                         n_ieq_constr=0,
                         xl=lb,
                         xu=ub,
                         vtype=int)
        self.obj_func = obj_func

    def _evaluate(self, x, out, *args, **kwargs):
        """

        :param x:
        :param out:
        :param args:
        :param kwargs:
        :return:
        """
        out["F"] = self.obj_func(x)


def NSGA_3(obj_func,
           n_var: int, lb: Vec | IntVec, ub: Vec | IntVec,
           n_obj: int,
           n_partitions: int = 100,
           max_evals: int = 30,
           pop_size: int = 1,
           crossover_prob: float = 0.05,
           mutation_probability=0.5,
           eta: float = 3.0):
    """
    NSGA3 designed for pareto investments
    :param obj_func: Objective function pointer [f(x)]
    :param n_partitions: Number of partitions
    :param n_var: Number of variables
    :param lb: Array of x lower boundaries
    :param ub: Array of x upper boundaries
    :param n_obj: Number of objectives
    :param max_evals: Maximum number of evaluations
    :param pop_size: Population size
    :param crossover_prob: Crossover probability
    :param mutation_probability: Mutation probability
    :param eta: eta parameter for the SBX crossover
    :return: X, f
    """
    problem = GridNsga(obj_func, n_var, n_obj, lb=lb, ub=ub)

    ref_dirs = get_reference_directions("reduction", n_obj, n_partitions, seed=1)

    algorithm = NSGA3(pop_size=pop_size,
                      sampling=SkewedIntegerSamplingRange(),
                      # IntegerRandomSamplingVeraGrid(), # SkewedBinarySampling(),
                      crossover=SBX(prob=crossover_prob,
                                    eta=eta,
                                    vtype=float,
                                    repair=RoundingRepair()),
                      mutation=BitflipMutation(prob=mutation_probability,
                                               prob_var=0.4,
                                               repair=RoundingRepair()),
                      eliminate_duplicates=True,
                      ref_dirs=ref_dirs)

    res = minimize(problem=problem,
                   algorithm=algorithm,
                   termination=('n_eval', max_evals),
                   seed=1,
                   verbose=True,
                   save_history=False)

    # import pandas as pd
    # dff = pd.DataFrame(res.F)
    # dff.to_excel('nsga.xlsx')
    return res.X, res.F
