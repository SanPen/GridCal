import os
import GridCalEngine as gce

fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "fubm_caseHVDC_vt.gridcal")
grid = gce.open_file(fname)


main_nc = gce.compile_numerical_circuit_at(grid)

islands = main_nc.split_into_islands()

print()
