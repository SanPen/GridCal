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


class UniformBinarySampling(Sampling): #pymoo library
    def _do(self, problem, n_samples, **kwargs):

        num_ones = np.linspace(0, problem.n_var, n_samples, dtype=int)
        num_ones[-1] = problem.n_var
        ones_into_array = np.zeros((n_samples, problem.n_var), dtype=int)
        # Fill ones_into_array randomly
        for i, num in enumerate(num_ones):
            ones_into_array[i, :num] = 1
            np.random.shuffle(ones_into_array[i])
        print("testing")
        return ones_into_array

def UniformBinaryPopulation(problem_ptp,pop_size):
        """
        BASED ON PLATYPUS LIBRARY ONLY
        Defines the initial population matrix as an array and then transforms into platypus solution object
        to be used for InjectedPopulation Generator method. It is based on UniformBinarySampling method for pymoo

        """
        #inputs:
        n_samples=pop_size #78
        #creating an array with the number of ones we want in each individual:
        num_ones = np.linspace(0, problem_ptp.nvars, n_samples, dtype=int)
        num_ones[-1] = problem_ptp.nvars
        # creating an array for each individual, with the number of ones defined in "num_ones"
        ones_into_array = np.zeros((n_samples, problem_ptp.nvars), dtype=int)
        # Fill ones_into_array randomly
        ones_into_array_bin=[]
        for i, num in enumerate(num_ones):
            ones_into_array[i, :num] = 1
            np.random.shuffle(ones_into_array[i])
            #changing into platypus format:
            aux=[]
            for j in range(problem_ptp.nvars):
                aux.append([bool(ones_into_array[i,j])])
            ones_into_array_bin.append(aux)

        predefined_population =np.array(ones_into_array_bin) #array instead of list
        # #to check number of ones per individual:
        # for i in range(78):
        #     unos = 0
        #     suma=0
        #     #print(i)
        #     for j in range(390):
        #         #print(j)
        #         if ones_into_array_bin[i][j][0] == True: unos = unos + 1
        #     suma=np.sum(ones_into_array[i])
        #     print("individuo {} unos: {}".format(i, suma))
        #         #print(unos)
        #     print("individuo {} trues: {}".format(i, unos))

        #defining the initial population as a solution object
        ind=0
        initial_population=[]
        for individual in predefined_population:
            solution=Solution(problem_ptp)
            solution.variables=individual.tolist()
            #problem_ptp.evaluate(solution)
            initial_population.append(solution)
            ind=ind+1
            #print('individual: {}'.format(ind))

        return initial_population

class UniformBinaryGenerator(Generator): #platypus library, not used now, see UniformBinaryGenerator function above
    def __init__(self):
        super().__init__()

    def generate(self, problem_ptp):
        solution = Solution(problem_ptp)
        random_population=np.random.randint(0, 2, size=problem_ptp.nvars, dtype=int) #return random integers from the discrte uniform distribution (numpy array)
        random_population2=np.random.choice([0,1], p=[0.7,0.3],size=390)
        random_population=np.zeros(390) #initialize vector to zeros
        initial_population=[]
        for i in range(390):
            boolean_random_population=bool(random_population[i])
            initial_population.append([boolean_random_population])
        solution.variables = initial_population
        return solution

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

    return res.X, res.F

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

    # Powerflow problem:
    #problem_ptp=GridNsga_platypus(n_var, n_obj,n_const) #obj_func
    problem_ptp=Problem(n_var, n_obj,n_const)
    problem_ptp.types[:]=Integer(0,1)
    problem_ptp.function=obj_func

    init_pop_obj=UniformBinaryPopulation(problem_ptp,pop_size) #initialising population matrix

    #calling NSGA3 algorithm from Platypus library:
    algorithm = NSGAIII(
                        problem_ptp,
                        divisions_outer=n_partitions,                   # outer divisions for reference points
                        divisions_inner=0,                              # optional, used for reference points too
                        generator=InjectedPopulation(init_pop_obj),     # init_pop_obj is the initial population as solution object from platypus
                        #generator=RandomGenerator(),                   #generates initial population
                        #generator=UniformBinaryGenerator(),            # generator class not good distribution of initial population
                        #selector=TournamentSelector(2),                # selects parents during recombination
                        variator=CompoundOperator(SBX(probability=crossover_prob, distribution_index=eta),
                                                  BitFlip(probability=mutation_probability)) # for Powerflow objective function

                        #variator=CompoundOperator(SBX(), PMX(), PM(), UM())    # CompoundOperator for mixed variables: int and float
                        )
    # running algorithm:
    algorithm.population_size=pop_size              #optional - fixing population size, if not specified, it estimates it from "divisions_outer".
    #algorithm.population = initial_population      # n/a
    #algorithm.reference_points=[[1,1],[..],...]    #optional - specific reference points specified by user (list of lists)

    #=======================================STEP METHOD (EXECUTE + SAVE RESULTS)=========================================
    output_per_iteration=[]
    iterations=int(max_evals/pop_size)
    all_solutions = []
    all_variables=[]
    all_objectives=[]
    all_variables_decoded = []

    for it in range(iterations):
        algorithm.step()
        outputs=[solution.variables[:] for solution in algorithm.result]

        for s in range(len(algorithm.result)):
            all_solutions.append(algorithm.result[s])
            all_variables.append(algorithm.result[s].variables)
            all_variables_to_decode=algorithm.result[s].variables
            all_objectives.append(algorithm.result[s].objectives)
            #all_variables_decoded = []
            variables_decoded2 = [problem_ptp.types[i].decode(all_variables_to_decode[i]) for i in range(len(algorithm.result[s].variables))]
            all_variables_decoded.append(variables_decoded2)              #for each solution, stores all the values o
        output_per_iteration.append(outputs)
    res_objective_all=np.array(all_objectives[:])


    #=================================================RUN METHOD=========================================================
    #this method does not store all the solutions evaluated. It stores non-
    #dominated solutions and all the solutions evaluated in the last generation

    #algorithm.run(max_evals)                     # number of evaluations = Termination condition

    #=======================================STORING RESULTS FOR RUN METHOD===============================================
    # #platypus returns Integer(0,1) variables as True/false --> decode method to get 0/1
    # res_objective_nd = []
    # #res_norm_objective=[]                                          #normalised objective --> only for method algorithm.run()
    # res_variables = []
    # res_variables_decoded_nd=[]
    # for solution in unique(nondominated(algorithm.result)):
    #     res_objective_nd.append([solution.objectives[0], solution.objectives[1]])
    #     #res_norm_objective.append([solution.normalized_objectives[0], solution.normalized_objectives[1]])      #only for method algorithm.run()
    #     res_variables = solution.variables[:]                       # integer variables, returns true false (not decoded)
    #     variables_decoded = []
    #     variables_decoded2 = [problem_ptp.types[i].decode(res_variables[i]) for i in range(len(solution.variables))]
    #     res_variables_decoded_nd.append(variables_decoded2)              #for each solution, stores all the values of the investments decoded (0,1)

    #store last generation evaluation results --> N/A
    # res_objective_lastgen=[]
    # for solution in algorithm.result:
    #     res_objective_lastgen.append(solution.objectives)

    #=======================================EXPORT TO EXCEL SOLUTIONS OBJ VALUES========================================
    # import pandas as pd
    # df_nd = pd.DataFrame(res_objective_nd)              #only non-dominated solutions
    # df_nd.to_excel('nsga_ptp_uf_nd.xlsx')               #only non-dominated solutions, UF= uniform sampling, ptp=platypus
    # df_lasteval=pd.DataFrame(res_objective_lastgen)     # save all the solutions in last generation
    # df_lasteval.to_excel('nsga_ptp_uf_lastgen.xlsx')    # Save all the solutions in last generation ,   UF= uniform sampling
    # df_all = pd.DataFrame(res_objective_all)            # save all the solutions
    # df_all.to_excel('nsga_ptp_uf_all.xlsx')             # Save all the solutions,  UF= uniform sampling

    hyp = Hypervolume(minimum=[0, 0], maximum=[1, 1])
    print("Hypervolume: {}".format(hyp(algorithm.result)))

    print("pop_size: {}, pop_size internal: {}".format(algorithm.population_size,len(algorithm.population)))
    print("max_evals: {}".format(max_evals))
    print("divisions_outer: {}".format(n_partitions))
    print("n_vars: {}".format(n_var))
    print("n_const: {}".format(n_const))
    print("n_obj: {}".format(n_obj))
    #print("Num de soluciones variables nondominated:{}".format(len(res_variables)))
    #print("Num de soluciones objetivo nondominated:{}".format(len(res_objective_nd)))
    #print("Num de soluciones objetivo last gen:{}".format(len(res_objective_lastgen)))
    #print("Num de soluciones objetivo (all):{}".format(len(res_objective_all)))
    #print("Num total de soluciones {}".format(len(algorithm.result)))

    """
    outputs:
    res_objective_all: result values of the objective functions (f1, f2) all solutions (non dominated and dominated) from method algorithm.step
    res_objective_nd: result values of the objective functions (f1, f2) non-dominated solutions
    res_objective_lastgen: algorithm.run() method gives all the solutions only from last generation
    res_variables_decoded_nd: includes all the non dominated solutions
    all_variables_decoded: includes all the solutions (all solutions, non dominated and dominated) from method algorithm.step
    
    """
    return all_variables_decoded, res_objective_all #res_objective_nd, res_objective_lastgen, #res_variables_decoded_nd


