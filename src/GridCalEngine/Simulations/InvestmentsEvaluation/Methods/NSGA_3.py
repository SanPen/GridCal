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
import numpy as np
from pymoo.core.problem import ElementwiseProblem
from pymoo.util.ref_dirs import get_reference_directions
from pymoo.optimize import minimize
from pymoo.algorithms.moo.nsga3 import NSGA3
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.repair.rounding import RoundingRepair
# from pymoo.operators.mutation.bitflip import BitflipMutation
from pymoo.core.sampling import Sampling
from pymoo.core.mutation import Mutation


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

    def __init__(self, obj_func, n_var, n_obj):
        """

        :param obj_func:
        :param n_var:
        :param n_obj:
        """
        super().__init__(n_var=n_var,
                         n_obj=n_obj,
                         n_ieq_constr=0,
                         xl=np.zeros(n_var),
                         xu=np.ones(n_var),
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
           n_partitions: int = 100,
           n_var: int = 1,
           n_obj: int = 2,
           max_evals: int = 30,
           pop_size: int = 1,
           crossover_prob: float = 0.05,
           mutation_probability=0.5,
           eta: float = 3.0):
    """

    :param obj_func:
    :param n_partitions:
    :param n_var:
    :param n_obj:
    :param max_evals:
    :param pop_size:
    :param crossover_prob:
    :param mutation_probability:
    :param eta:
    :return:
    """
    problem = GridNsga(obj_func, n_var, n_obj)

    ref_dirs = get_reference_directions("reduction", n_obj, n_partitions, seed=1)

    algorithm = NSGA3(pop_size=pop_size,
                      sampling=SkewedBinarySampling(),  # UniformBinarySampling() for ideal grid
                      crossover=SBX(prob=crossover_prob, eta=eta, vtype=float, repair=RoundingRepair()),
                      mutation=BitflipMutation(prob=mutation_probability, prob_var=0.4, repair=RoundingRepair()),
                      # selection=TournamentSelection(pressure=2),
                      eliminate_duplicates=True,
                      ref_dirs=ref_dirs)

    res = minimize(problem=problem,
                   algorithm=algorithm,
                   termination=('n_eval', max_evals),
                   seed=1,
                   verbose=True,
                   save_history=False)

    import pandas as pd
    dff = pd.DataFrame(res.F)
    dff.to_excel('nsga.xlsx')
    return res.X, res.F
