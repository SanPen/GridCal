import numpy as np
import matplotlib.pyplot as plt
from pymoo.core.problem import ElementwiseProblem
from pymoo.util.ref_dirs import get_reference_directions
from pymoo.optimize import minimize
from pymoo.algorithms.moo.nsga3 import NSGA3
from pymoo.visualization.scatter import Scatter

from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.repair.rounding import RoundingRepair
from pymoo.operators.sampling.rnd import IntegerRandomSampling


class GridNsga(ElementwiseProblem):

    def __init__(self, obj_func, n_var, n_obj):
        super().__init__(n_var=n_var,
                         n_obj=n_obj,
                         n_ieq_constr=0,
                         xl=np.zeros(n_var),
                         xu=np.ones(n_var),
                         vtype=int,
                         )
        self.obj_func = obj_func

    def _evaluate(self, x, out, *args, **kwargs):
        out["F"] = self.obj_func(x)


def NSGA_3(obj_func,
           n_partitions: int = 10,
           n_var: int = 1,
           n_obj: int = 1,
           max_evals: int = 30,
           pop_size: int = 1,
           prob: float = 1.0,
           eta: float = 3.0):

    problem = GridNsga(obj_func, n_var, n_obj)
    # ref_dirs = get_reference_directions("das-dennis", n_obj, n_partitions=n_partitions)
    ref_dirs = get_reference_directions("energy", n_obj, n_partitions, seed=1)
    algorithm = NSGA3(pop_size=pop_size,
                      sampling=IntegerRandomSampling(),
                      crossover=SBX(prob=prob, eta=eta, vtype=float, repair=RoundingRepair()),
                      mutation=PM(prob=prob, eta=eta, vtype=float, repair=RoundingRepair()),
                      eliminate_duplicates=True,
                      ref_dirs=ref_dirs)

    res = minimize(problem,
                   algorithm,
                   ('n_gen', max_evals),
                   seed=1,
                   verbose=True,
                   save_history=True)

    X = res.X
    F = res.F

    print(f'Best X: ', X)
    print(f'Best F: ', F)

    # Extract the objective function values from each generation
    obj_values = [gen.pop.get("F") for gen in res.history]

    # Calculate the minimum objective function value in each generation
    min_obj_values = [np.min(val) for val in obj_values]

    return X, obj_values
