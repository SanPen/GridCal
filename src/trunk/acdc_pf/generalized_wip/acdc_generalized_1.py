import os
import GridCalEngine as gce
from GridCalEngine.Topology.generalized_simulation_indices import GeneralizedSimulationIndices


fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "fubm_caseHVDC_vt.gridcal")
grid = gce.open_file(fname)

main_nc = gce.compile_numerical_circuit_at(grid, consider_vsc_as_island_links=False)

islands = main_nc.split_into_islands(
    ignore_single_node_islands=False,
    consider_hvdc_as_island_links=False,
    consider_vsc_as_island_links=True
)

print(f"Base: nbus {main_nc.nbus}, nbr: {main_nc.nbr}, nvsc: {main_nc.nvsc}, nhvdc: {main_nc.nhvdc}")

for i, island in enumerate(islands):
    _, is_dc_str = island.is_dc()
    print(f"island {i} is {is_dc_str}: nbus {island.nbus}, nbr: {island.nbr}, nvsc: {island.nvsc}, nhvdc: {island.nhvdc}")

    indices = GeneralizedSimulationIndices(island)

print()
