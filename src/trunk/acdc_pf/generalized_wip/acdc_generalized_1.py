import sys
import os
import GridCalEngine as gce

fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "fubm_caseHVDC_vt.gridcal")
# fname = os.path.join("Grids_and_profiles", "grids", "fubm_caseHVDC_vt.gridcal")
grid = gce.open_file(fname)

main_nc = gce.compile_numerical_circuit_at(grid, consider_vsc_as_island_links = False)

islands = main_nc.split_into_islands(
    ignore_single_node_islands=False,
    consider_hvdc_as_island_links=False,
    consider_vsc_as_island_links=False,
)

print()
