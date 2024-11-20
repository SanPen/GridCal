import os
import GridCalEngine as gce
from GridCalEngine.Topology.generalized_simulation_indices import GeneralizedSimulationIndices

# fname = os.path.join("Grids_and_profiles", "grids", "fubm_caseHVDC_vt.gridcal")
fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "fubm_caseHVDC_vt.gridcal")
grid = gce.open_file(fname)
#run power flow
main_nc = gce.compile_numerical_circuit_at(grid)

islands = main_nc.split_into_islands(
    consider_hvdc_as_island_links=True,
)

print(f"Base: nbus {main_nc.nbus}, nbr: {main_nc.nbr}, nvsc: {main_nc.nvsc}, nhvdc: {main_nc.nhvdc}")

for i, island in enumerate(islands):
    _, is_dc_str = island.is_dc()
    print(f"island {i} is {is_dc_str}: nbus {island.nbus}, nbr: {island.nbr}, nvsc: {island.nvsc}, nhvdc: {island.nhvdc}")

    indices = GeneralizedSimulationIndices(island)

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


print()
options = gce.PowerFlowOptions(solver_type= gce.SolverType.GENERALISED)
results = gce.power_flow(grid, options)
print(f"Power flow converged: {results.converged}")