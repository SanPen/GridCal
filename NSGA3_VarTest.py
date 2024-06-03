"""
This is a script to test NSGA III algorithm performance with different types of variables (integer, continuous)

MILP problem: mixed-integer problem (integer and continuous decision variables)
"""

from pymoo.algorithms.moo.nsga3 import NSGA3
from pymoo.optimize import minimize
from pymoo.problems import get_problem
from pymoo.util.ref_dirs import get_reference_directions
from pymoo.visualization.scatter import Scatter
#from pymoo.core.problem import ElementwiseProblem
from pymoo.core.problem import Problem
import numpy as np

#Define MILP Problem:
class EnergyDispatchProblem(Problem):
    def __init__(self,N,CE_f,CE_v,CO2,D,Cap,low_bounds,up_bounds):       #super is to access parent atribute "__init__". Parent class is "Problem" from pymoo library
        super().__init__(n_var=2*N,
                         n_obj=2,
                         n_constr=2*N+1,
                         xl=low_bounds,                     #lower bounds, array
                         xu=up_bounds,                      #upper bounds, array
                         )
        self.N=N
        self.CE_f=CE_f                                      #fixed cost of operation generation unit i (if off = 0 €)
        self.CE_v=CE_v                                      # variable cost of operation generation unit i (€/MWh)
        self.CO2=CO2                                        #emissions CO2 per generation unit i operating (CO2/MWh)
        self.D=D                                            #total demand (MWh)
        self.Cap=Cap                                        # total capacity per generation unit i (MW)

        def _evaluate(self, x, out, *args, **kwargs):
            x_bin=x[:,:self.N]                              # binary variables (on/off)
            y=x[:,self.N:]                                  # continuous variables (Energy produced per generating unit i - MWh)

            #objective function 1
            total_cost=np.sum(self.CE_f*x_bin,axis=1) + np.sum (self.CE_v*y,axis=1)         # €
            #objective funcion 2
            total_emissions=np.sum(self.CO2*y, axis=1)                                      # CO2

            out["F"]=np.column_stack([total_cost,total_emissions])                          # concatenates vectors by columns

            #constraints:
            g1=np.sum(y)-self.D                          #demand balance
            g2=y-self.Cap*x_bin                          #for each generator, capacity constraint

            out["G"]=np.column_stack([g1,g2])

#PARAMETERS OF THE PROBLEM (INPUTS)
N=3
CE_f=np.array([1000,1200,1500])
CE_v=np.array([50,60,70])
CO2=np.array([0.5,0.4,0.3])
D=300
Cap=np.array([150,200,250])
low_bounds=np.array([0]*N*2)
up_bounds=np.array([1]*N+Cap.tolist())
problem=EnergyDispatchProblem(N,CE_f,CE_v,CO2,D,Cap,low_bounds,up_bounds) #instance

#generate reference directions:
#ref_dirs = get_reference_directions("reduction", n_obj, n_partitions, seed=1)

ref_dirs=get_reference_directions("reduction",n_objective=2,n_partitions=12) #das-dennis #reduction
#define algorithm
algorithm=NSGA3(pop_size=40,ref_dirs=ref_dirs)

#optimization
results=minimize(problem=problem,
                 algorithm=algorithm,
                 termination=('n_gen',100), #n_eval, max_evals
                 seed=1,
                 save_history=True, #false
                 verbose=True)
#plotting
plot = Scatter()
plot.add(results.F, facecolor="none", edgecolor="red")
plot.show()

