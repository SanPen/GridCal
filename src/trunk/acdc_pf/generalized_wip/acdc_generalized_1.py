import os
import GridCalEngine as gce
# from GridCalEngine.Simulations.PowerFlow.Formulations.pf_advanced_formulation import PfAdvancedFormulation
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_generalized_formulation import PfGeneralizedFormulation
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx
from GridCalEngine.basic_structures import Logger

# fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "fubm_caseHVDC_vt.gridcal")
fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "fubm_caseHVDC_vt_josep.gridcal")
grid = gce.open_file(fname)
# run power flow
main_nc = gce.compile_numerical_circuit_at(grid)

islands = main_nc.split_into_islands(
    consider_hvdc_as_island_links=True,
)

"""
for test case fubm_caseHVDC_vt.gridcal, we have the following setpoints (perhaps not real ones but just for testing):
Name	control1	control2	control1_val	control2_val	control1_dev	control2_dev
0:VSC1	Vm_dc	    P_ac	    1	            0	            None	        None
1:VSC2	Vm_dc	    P_ac	    1	            0	            None	        None

expecting the following indices:
cx_va: [1, 4, 5]
cx_vm: [2, 4]
cx_tau: []
cx_m: []
cx_pzip: [0]
cx_qzip: [0, 5]
cx_pfa: [5]
cx_qfa: []
cx_pta: [4]
cx_qta: [4, 5]
"""

print(f"Base: nbus {main_nc.nbus}, nbr: {main_nc.nbr}, nvsc: {main_nc.nvsc}, nhvdc: {main_nc.nhvdc}")

options = gce.PowerFlowOptions(solver_type= gce.SolverType.GENERALISED)
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
