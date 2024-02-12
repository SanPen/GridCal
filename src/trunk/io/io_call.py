import os
import GridCalEngine.api as gce

fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', "IEEE39_1W.gridcal")
grid_ = gce.open_file(fname)

fname2 = "IEEE39_1W_new.gridcal"

gce.save_file(grid=grid_, filename=fname2)

grid2_ = gce.open_file(fname2)

print()

