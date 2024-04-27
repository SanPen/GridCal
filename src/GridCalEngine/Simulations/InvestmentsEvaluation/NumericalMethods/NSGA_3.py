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
from pymoo.algorithms.moo.age import AGEMOEA
from pymoo.operators.crossover.pntx import TwoPointCrossover
from pymoo.operators.mutation.bitflip import BitflipMutation
from pymoo.operators.sampling.rnd import BinaryRandomSampling
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.repair.rounding import RoundingRepair
from pymoo.operators.sampling.rnd import IntegerRandomSampling, BinaryRandomSampling
from pymoo.visualization.scatter import Scatter
from pymoo.algorithms.moo.unsga3 import UNSGA3
import matplotlib.pyplot as plt
from inspect import signature


class GridNsga(ElementwiseProblem):
    """

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
           n_obj=2,
           max_evals: int = 30,
           pop_size: int = 1,
           crossover_prob: float = 0.05,
           mutation_probability=0.01,
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

    ref_dirs = get_reference_directions("energy", n_obj, n_partitions, seed=1)

    algorithm = UNSGA3(pop_size=pop_size,
                       sampling=BinaryRandomSampling(),
                       crossover=SBX(prob=crossover_prob, eta=eta, vtype=float, repair=RoundingRepair()),
                       mutation=PM(prob=mutation_probability, eta=eta, vtype=float, repair=RoundingRepair()),
                       eliminate_duplicates=True,
                       ref_dirs=ref_dirs)

    # algorithm = AGEMOEA(pop_size=pop_size,
    #                     sampling=BinaryRandomSampling(),
    #                     crossover=TwoPointCrossover(),
    #                     mutation=BitflipMutation(),
    #                     eliminate_duplicates=True)

    res = minimize(problem=problem,
                   algorithm=algorithm,
                   termination=('n_eval', max_evals),
                   seed=1,
                   verbose=True,
                   save_history=False)

    return res.X, res.F


def NSGA_3_debug(obj_func,
                 n_partitions: int = 100,
                 n_var: int = 1,
                 n_obj=2,
                 max_evals: int = 30,
                 pop_size: int = 1,
                 prob: float = 1.0,
                 eta: float = 3.0):
    """

    :param obj_func:
    :param n_partitions:
    :param n_var:
    :param n_obj:
    :param max_evals:
    :param pop_size:
    :param prob:
    :param eta:
    :return:
    """
    problem = GridNsga(obj_func, n_var, n_obj)
    # ref_dirs = get_reference_directions("das-dennis", n_obj, n_partitions=n_partitions)
    ref_dirs = get_reference_directions("energy", n_obj, n_partitions, seed=1)
    # algorithm = NSGA3(pop_size=pop_size,
    #                   sampling=IntegerRandomSampling(),
    #                   crossover=SBX(prob=prob, eta=eta, vtype=float, repair=RoundingRepair()),
    #                   mutation=PM(prob=prob, eta=eta, vtype=float, repair=RoundingRepair()),
    #                   eliminate_duplicates=True,
    #                   ref_dirs=ref_dirs)
    algorithm = UNSGA3(pop_size=pop_size,
                       sampling=IntegerRandomSampling(),
                       crossover=SBX(prob=prob, eta=eta, vtype=float, repair=RoundingRepair()),
                       mutation=PM(prob=prob, eta=eta, vtype=float, repair=RoundingRepair()),
                       eliminate_duplicates=True,
                       ref_dirs=ref_dirs)

    res = minimize(problem,
                   algorithm,
                   ('n_eval', max_evals),
                   seed=1,
                   verbose=True,
                   save_history=False)

    # _res = minimize(problem,
    #                 NSGA3(pop_size=pop_size, sampling=IntegerRandomSampling(),
    #                       crossover=SBX(prob=prob, eta=eta, vtype=float, repair=RoundingRepair()),
    #                       mutation=PM(prob=prob, eta=eta, vtype=float, repair=RoundingRepair()),
    #                       eliminate_duplicates=True,
    #                       ref_dirs=ref_dirs),
    #                 ('n_eval', max_evals),
    #                 seed=1,
    #                 verbose=True,
    #                 save_history=False)

    X = res.X
    F = res.F

    print(f'Best X: ', X)
    print(f'Best F: ', F)

    # Extract the objective function values from each generation
    # obj_values = [gen.pop.get("F") for gen in res.history]

    # Calculate the minimum objective function value in each generation
    # min_obj_values = [np.min(val) for val in obj_values]

    plot = Scatter()
    plot.add(problem.pareto_front(), plot_type="line", color="black", alpha=0.7)
    # plt.scatter(F[:, 0], F[:, 1], s=30, facecolors='none', edgecolors='blue')
    plot.add(res.F, facecolor="none", edgecolor="red")
    # plot.add(_res.F, facecolor="none", edgecolor="blue")
    # plot.show()

    # ret = [np.min(e.pop.get("F")) for e in res.history]
    # _ret = [np.min(e.pop.get("F")) for e in _res.history]
    #
    # plt.plot(np.arange(len(ret)), ret, label="unsga3")
    # plt.plot(np.arange(len(_ret)), _ret, label="nsga3")
    # plt.title("Convergence")
    # plt.xlabel("Generation")
    # plt.ylabel("F")
    # plt.legend()
    # plt.show()

    return X, F
