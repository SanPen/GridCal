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
#PYMOO:
from pymoo.core.problem import ElementwiseProblem
from pymoo.util.ref_dirs import get_reference_directions
from pymoo.optimize import minimize
from pymoo.algorithms.moo.nsga3 import NSGA3
from pymoo.operators.crossover.sbx import SBX as SBX_pymoo
from pymoo.operators.repair.rounding import RoundingRepair
# from pymoo.operators.mutation.bitflip import BitflipMutation
from pymoo.core.sampling import Sampling
from pymoo.core.mutation import Mutation as Mutation_pymoo
#PLATYPUS:
from platypus.algorithms import NSGAII, NSGAIII
#from platypus.core import Mutation as MutationPtp
from platypus.problems import Problem
from platypus.types import Real, Integer
import matplotlib.pyplot as plt
from platypus import *
from platypus.indicators import Hypervolume


class UniformBinarySampling(Sampling):
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


class BitflipMutation(Mutation_pymoo):

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

        :param obj_func: bound method InvestmentsEvaluationDriver.objective_function of <GridCalEngine.Simulations.InvestmentsEvaluation.investments_evaluation_driver.IndestmentsEvaluationDriver object
        :param n_var: int
        :param n_obj: int
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

        :param x: [0 0 0 .....0] ndarray with len=390=pop_size
        :param out:
        :param args:
        :param kwargs:
        :return:
        """
        out["F"] = self.obj_func(x) # F is array of 2 values (ndarray)


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
                      sampling=UniformBinarySampling(),  #UniformBinarySampling() for ideal grid #SkewedBinarySampling
                      crossover=SBX_pymoo(prob=crossover_prob, eta=eta, vtype=float, repair=RoundingRepair()),
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
    dff.to_excel('nsga_PYMOO.xlsx')
    import matplotlib.pyplot as plt
    # import matplotlib
    # matplotlib.use("Qt5Agg")
    #
    # plt.scatter(res.F)
    # plt.show()
    return res.X, res.F

# class TestProblem_platypus(Problem):
#     def __init__(self, n_var, n_obj,n_const):
#         super().__init__(n_var, n_obj, n_const)           # decision variable,objective,constraints respectively
#         # self.types[:]=[Real(-2,2),Integer(-4,4)]              # fill variable type for every variable "[:]". If all are the same: self.types[:]=Real(0,100)
#         self.types[0] = Real(-2, 2)                    # first variable is Real number, bounds (-2,+2)
#         self.types[1] = Integer(-4, 4)                 # second variable is an Integer, bounds (-4,+4)
#         self.constraints[:] = '<=0'                             # applied to all constraints [:]. Also can do constraint[0]='>=0'. Also included: '==',"<", ">" "!=". See platypus library
#         self.directions[:] = Problem.MINIMIZE                   # or MAXIMIZE - optional parameter. NSGA3 not implemented maximization in platypus at the moment (june 2024)
#
#     def evaluate(self, solution):
#         x1 = solution.variables[0]
#         x2 = solution.variables[1]
#         f1 = x1 + x2
#         f2 = x1 ** 2 + x2 ** 2
#         solution.objectives[:] = [f1, f2]                       #objective functions
#         g1 = (x1 - 2) ** 2 + (x2 - 2) ** 2 - 36
#         solution.constraints[:] = [g1]                          #constraint
#         print(solution.objectives)
# class GridNsga_platypus(Problem):
#     def __init__(self, n_var, n_obj,n_const): #obj_func,
#         super().__init__(n_var, n_obj, n_const)           # decision variable,objective,constraints respectively
#         # self.types[:]=[Real(-2,2),Integer(-4,4)]              # fill variable type for every variable "[:]". If all are the same: self.types[:]=Real(0,100)
#         self.types[:] = Integer(0,1)                    #Binary variable is True or Flase not [1,0]
#         #self.constraints[:] = '<=0'                             # applied to all constraints [:]. Also can do constraint[0]='>=0'. Also included: '==',"<", ">" "!=". See platypus library
#         self.directions[:] = Problem.MINIMIZE                   # or MAXIMIZE - optional parameter. NSGA3 not implemented maximization in platypus at the moment (june 2024)
#         #self.obj_func=obj_func                              #same que pymoo
#         #print(obj_func)
#     def evaluate(self, solution):
#         x = solution.variables[:] #x = solution.variables[0]
#         #solution.objectives[:]=self.obj_func
#         #solution.objectives[0]=self.obj_func[0]
#         #solution.objectives[1] = self.obj_func[1]
#         print("")

def NSGA_3_platypus(obj_func,
           n_partitions: int = 100,
           n_var: int = 1,
           n_obj: int = 2,
           n_const: int = 0, # 1 for platypus test problem, 0 for PF problem
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

    #platypus:
    #problem_ptp=TestProblem_platypus(n_var, n_obj,n_const)
    # Powerflow problem:
    #problem_ptp=GridNsga_platypus(n_var, n_obj,n_const) #obj_func,
    problem_ptp=Problem(n_var, n_obj,n_const)
    problem_ptp.types[:]=Integer(0,1)
    problem_ptp.function=obj_func
    #print(problem_ptp)
    #calling NSGA3 algorithm from Platypus library:
    algorithm = NSGAIII(
                        problem_ptp,
                        divisions_outer=n_partitions,           # outer divisions for reference points
                        divisions_inner=0,                      # optional, used for reference points too
                        generator=RandomGenerator(),           #generates initial population
                        #selector=TournamentSelector(2),        # selects parents during recombination
                        variator=CompoundOperator(SBX(probability=crossover_prob, distribution_index=eta),
                                                  BitFlip(probability=mutation_probability)) # for Powerflow objective function

                        #variator=CompoundOperator(SBX(), PMX(), PM(), UM())    # CompoundOperator for mixed variables
                        #variator = CompoundOperator(SBX(), HUX(), PM(), BitFlip())
                        )
    # running algorithm:
    algorithm.population_size=pop_size           #optional - fixing population size, if not specified, it estimates it from "divisions_outer".
    #algorithm.reference_points=[[1,1],[..],...] #optional - specific reference points specified by user (list of lists)
    algorithm.run(max_evals)                     # number of evaluations = Termination condition

    #results:for platypus test problem:
    res_objective = []
    res_norm_objective=[] #normalised objective
    res_variables = []
    res_variables_decoded=[]
    for solution in unique(nondominated(algorithm.result)):
        res_objective.append([solution.objectives[0], solution.objectives[1]])
        res_norm_objective.append([solution.normalized_objectives[0], solution.normalized_objectives[1]])
        res_variables = solution.variables[:]                       # integer variables, returns true false (not decoded)
        variables_decoded = []
        #option1:
        variables_decoded2 = [problem_ptp.types[i].decode(res_variables[i]) for i in range(len(solution.variables))]

        #option 2:
        # for i in range(len(solution.variables)):
        #     #variable_to_decode = var
        #     decoded=problem_ptp.types[i].decode(res_variables[i])
        #     variables_decoded.append(decoded)                       # for 1 solution only, stores all the values of the investments (0,1) decoded

        res_variables_decoded.append(variables_decoded2)             #for each solution, stores all the values of the investments decoded (0,1)
        # res_variables=solution.variables[:] #integer variables, returns true false
        # problem_ptp.types[0].decode(res_variables[0])

    res_objective_all=[]
    for solution in algorithm.result:
        res_objective_all.append(solution.objectives)

    # #results:for platypus test problem:
    # res_objective = []
    # res_variables = []
    # for solution in unique(nondominated(algorithm.result)):
    #     res_objective.append([solution.objectives[0], solution.objectives[1]])
    #     variable_to_decode = solution.variables[1]  # x2 in this problem
    #     x1 = solution.variables[0]
    #     x2 = problem_ptp.types[1].decode(variable_to_decode)
    #     res_variables.append([x1, x2])  # decode integer variable (from binary representation to number)
    #     plt.scatter(solution.objectives[0],
    #                 solution.objectives[1],
    #                 color="r")
    #     plt.title("{}".format(type(algorithm)))

    import pandas as pd
    dff = pd.DataFrame(res_objective)       #only non-dominated solutions
    dff.to_excel('nsga_platypus.xlsx')      #only non-dominated solutions
    df=pd.DataFrame(res_objective_all)      # save all the solutions
    dff.to_excel('nsga_platypus_all.xlsx')  # Save all the solutions

    #hyp2=Hypervolume.calculate(algorithm.result)
    hyp = Hypervolume(minimum=[0, 0], maximum=[1, 1])
    print("Hypervolume: {}".format(hyp(algorithm.result)))

    print("pop_size: {}, pop_size internal: {}".format(algorithm.population_size,len(algorithm.population)))
    print("max_evals: {}".format(max_evals))
    print("divisions_outer: {}".format(n_partitions))
    print("obj_function: {}".format(obj_func))
    print("n_vars: {}".format(n_var))
    print("n_const: {}".format(n_const))
    print("n_obj: {}".format(n_obj))
    print("Num de soluciones variables nondominated:{}".format(len(res_variables)))
    print("Num de soluciones objetivo nondominated:{}".format(len(res_objective)))
    print("Num total de soluciones {}".format(len(algorithm.result)))

    return res_variables_decoded, res_objective #res.X, res.F

