import os
import GridCalEngine as gce
# from GridCalEngine.Simulations.PowerFlow.Formulations.pf_generalized_formulation import PfGeneralizedFormulation
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_generalized_formulation2 import PfGeneralizedFormulation
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx
from GridCalEngine.basic_structures import Logger
import faulthandler
faulthandler.enable() #start @ the beginning

# fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "fubm_caseHVDC_vt.gridcal")
# fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "fubm_caseHVDC_vt_raiyan.gridcal")
# fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "fubm_caseHVDC_vt_raiyan_signs.gridcal")
# fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "fubm_caseHVDC_vt_josep.gridcal")
# fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "fubm_caseHVDC_vt_mod6.gridcal") #this one works with symbolic
fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "fubm_caseHVDC_vt_wTrafo.gridcal") #this one works with symbolic
# fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "fubm_caseHVDC_vt_mod6_diffcontrols.gridcal") #this one works with symbolic
# fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "fubm_case_57_14_2MTDC_ctrls_raiyan.gridcal") #does not work, even with with autodiff

# fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "5bus_HVDC_v2.gridcal")
# fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "5bus_HVDC_v4.gridcal")
# fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "5bus_HVDC_v5.gridcal")
# fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "5bus_HVDC_v3.gridcal")
# fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "5bus_HVDC_v6.gridcal") #this one works with symbolic

grid = gce.open_file(fname)
# run power flow
main_nc = gce.compile_numerical_circuit_at(grid)

islands = main_nc.split_into_islands(
    consider_hvdc_as_island_links=True,
)
print(f"Base: nbus {main_nc.nbus}, nbr: {main_nc.nbr}, nvsc: {main_nc.nvsc}, nhvdc: {main_nc.nhvdc}")

options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, tolerance=1e-11)
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

solution = newton_raphson_fx(problem=problem,
                             tol=options.tolerance,
                             max_iter=options.max_iter,
                             trust=options.trust_radius,
                             verbose=options.verbose,
                             logger=logger)


print(solution.V)
print(solution.converged)
print(solution.iterations)