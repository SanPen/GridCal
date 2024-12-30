import os
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_options import SolverType
import GridCalEngine.api as gce
import faulthandler
import numpy as np
import os
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_generalized_formulation import PfGeneralizedFormulation
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx
from GridCalEngine.basic_structures import Logger
import faulthandler

faulthandler.enable()  # start @ the beginning

"""
Check that a transformer can regulate the voltage at a bus
"""
# fname = os.path.join("..", "..", "..", "tests", 'data', 'grids', 'Lynn 5 Bus (pq).gridcal')
fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", 'Lynn 5 Bus (pq).gridcal')
grid = gce.open_file(fname)

# run power flow
main_nc = gce.compile_numerical_circuit_at(grid)

islands = main_nc.split_into_islands(
    consider_hvdc_as_island_links=True,
)
print(f"Base: nbus {main_nc.nbus}, nbr: {main_nc.nbr}, nvsc: {main_nc.nvsc}, nhvdc: {main_nc.nhvdc}")

options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, tolerance=1e-11, verbose=2)
logger = Logger()

island = islands[0]

problem = PfGeneralizedFormulation(V0=island.Vbus,
                                   S0=island.Sbus,
                                   I0=island.Ibus,
                                   Y0=island.YLoadBus,
                                   Qmin=island.Qmin_bus,
                                   Qmax=island.Qmax_bus,
                                   nc=island,
                                   options=options,
                                   logger=logger)

print()

solution = newton_raphson_fx(problem=problem,
                             tol=options.tolerance,
                             max_iter=options.max_iter,
                             trust=options.trust_radius,
                             verbose=options.verbose,
                             logger=logger)

print(solution.V)
print(solution.converged)
print(solution.iterations)

