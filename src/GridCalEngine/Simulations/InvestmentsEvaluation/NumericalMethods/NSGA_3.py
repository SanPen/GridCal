import numpy as np
import pandas as pd
from pymoo.core.problem import ElementwiseProblem
from pymoo.util.ref_dirs import get_reference_directions
from pymoo.optimize import minimize
from pymoo.algorithms.moo.nsga3 import NSGA3
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.repair.rounding import RoundingRepair
from pymoo.operators.sampling.rnd import IntegerRandomSampling
from pymoo.operators.sampling.rnd import FloatRandomSampling
from pymoo.operators.sampling.rnd import BinaryRandomSampling
# from pymoo.operators.sampling.rnd import UniformBinarySampling
from pymoo.operators.crossover.pntx import PointCrossover
from pymoo.operators.crossover.expx import ExponentialCrossover
from pymoo.operators.crossover.ux import UniformCrossover
from pymoo.operators.crossover.hux import HalfUniformCrossover
from pymoo.operators.sampling.lhs import LHS
from pymoo.visualization.scatter import Scatter
from pymoo.algorithms.moo.unsga3 import UNSGA3
from pymoo.operators.mutation.bitflip import BitflipMutation
import matplotlib.pyplot as plt
from pymoo.operators.selection.rnd import RandomSelection
from pymoo.operators.selection.tournament import TournamentSelection
import scipy
from inspect import signature
from pymoo.core.sampling import Sampling


class UniformBinarySampling(Sampling):
    def __init__(self, num_ones):
        super().__init__()
        self.num_ones = num_ones

    def _do(self, problem, n_samples, **kwargs):
        num_ones = np.linspace(self.num_ones, problem.n_var, n_samples, dtype=int)
        ones_into_array = np.zeros((n_samples + 1, problem.n_var), dtype=int)

        # Fill ones into array randomly
        for i, num in enumerate(num_ones):
            ones_into_array[i, :num] = 1
            np.random.shuffle(ones_into_array[i])

        return ones_into_array


# class UniformBinarySampling(Sampling):
#     def _do(self, problem, n_samples, **kwargs):
#         num_ones = np.linspace(20, problem.n_var, n_samples, dtype=int)
#         ones_into_array = np.zeros((n_samples + 1, problem.n_var), dtype=int)
#
#         # Fill ones into array randomly
#         for i, num in enumerate(num_ones):
#             ones_into_array[i, :num] = 1
#             np.random.shuffle(ones_into_array[i])
#
#         return ones_into_array


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
                         xl=np.array([0] * n_var),
                         xu=np.array([1] * n_var),
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
           prob: float = 0.5,
           crossover_prob: float = 0.5,
           mutation_probability: float = 0.1,
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

    # ref_dirs = get_reference_directions(
    #     "multi-layer",
    #     get_reference_directions("uniform", n_obj, n_partitions=12, scaling=1.0))
    # ref_dirs = get_reference_directions(
    #     "multi-layer",
    # ref_dirs = get_reference_directions("energy", n_obj, n_partitions, seed=1)
    ref_dirs = get_reference_directions("reduction", n_obj, n_partitions, seed=1)
    # ref_dirs = get_reference_directions("energy", n_obj, n_partitions, seed=1)
    # ref_dirs = get_reference_directions("das-dennis", n_obj,
    #                                     n_partitions=n_partitions)  # Try different methods or adjust n_partitions

    num_ones = 20
    algorithm = NSGA3(pop_size=pop_size,
                      sampling=UniformBinarySampling(num_ones=num_ones),
                      # crossover=ExponentialCrossover(prob=0.5, prob_exp=0.4),
                      # crossover=HalfUniformCrossover(prob=1.0),
                      # crossover=UniformCrossover(prob=1.0, repair=RoundingRepair()),
                      crossover=SBX(prob=prob, eta=eta, vtype=float, repair=RoundingRepair()),
                      # mutation=PM(prob=mutation_probability, eta=eta, vtype=float, repair=RoundingRepair()),
                      # mutation=BitflipMutation(prob=0.2, prob_var=0.2, repair=RoundingRepair()),
                      # sampling=IntegerRandomSampling(),
                      # crossover=SBX(prob=0.1, eta=1.0, vtype=float, repair=RoundingRepair()),
                      # mutation=PM(prob=0.5, eta=1.0, vtype=float, repair=RoundingRepair()),
                      # mutation=PM(prob=0.5, eta=5, repair=RoundingRepair()),
                      mutation=BitflipMutation(prob=0.5, prob_var=0.4),
                      # selection=TournamentSelection(pressure=2),
                      eliminate_duplicates=True,
                      ref_dirs=ref_dirs)

    res = minimize(problem=problem,
                   algorithm=algorithm,
                   termination=('n_eval', max_evals),
                   seed=1,
                   verbose=True,
                   save_history=False)

    # X_swapped = res.F[:, 1]
    # Y_swapped = res.F[:, 0]
    #
    # # Now, create the scatter plot with swapped axes
    # plt.scatter(X_swapped, Y_swapped, color="red", label='NSGA3')
    #
    # # csv_data = np.loadtxt('src/GridCalEngine/Simulations/InvestmentsEvaluation/table.csv', delimiter=',')
    # data = pd.read_csv("/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations"
    #                    "/InvestmentsEvaluation/table.csv")
    #
    # Extract the investment cost and technical cost columns
    # investment_cost = data["Investment cost (M€)"]
    # technical_cost = data["Technical cost (M€)"]

    # # Plot the data
    # plt.scatter(investment_cost, technical_cost, color="blue", label="MVRSM")
    # plt.xlabel("Investment cost (M€)")
    # plt.ylabel("Technical cost (M€)")
    # plt.title("Pareto Front")
    # plt.show()
    #
    # # Your existing code to generate the first scatter plot
    X_swapped = res.F[:, 1]
    Y_swapped = res.F[:, 0]
    combined_cost_nsga3 = X_swapped + Y_swapped  # Calculate combined cost for NSGA3
    #
    # Plot the first scatter plot with color based on combined cost


    # data = pd.read_csv("/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations"
    #                    "/InvestmentsEvaluation/10_gen.csv")
    #
    # investment_cost = data["Investment cost (M€)"]
    # technical_cost = data["Technical cost (M€)"]
    #
    # combined_cost_mvrsm = investment_cost + technical_cost

    # plt.scatter(investment_cost, technical_cost, c=combined_cost_mvrsm, cmap='viridis', label="MVRSM")
    # plt.colorbar(label='Objective function (MVRSM)')

    # # Activate/deactivate plot below
    # plt.scatter(X_swapped, Y_swapped, c=combined_cost_nsga3, cmap='cividis', label='NSGA3')
    # plt.colorbar(label='Objective function (NSGA3)')
    #
    # plt.xlabel("Investment cost (M€)")
    # plt.ylabel("Technical cost (M€)")
    # plt.title("Pareto Front")
    # plt.legend()
    # plt.show()

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
    algorithm = NSGA3(pop_size=pop_size,
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
