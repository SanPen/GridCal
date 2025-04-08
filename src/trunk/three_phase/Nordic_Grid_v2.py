import GridCalEngine.api as gce

my_grid = gce.open_file("Nordic_Grid_v2.gridcal")

for trafo in my_grid.transformers2w:
    trafo.rate = trafo.nominal_power

gce.save_file(my_grid,"Nordic_Grid_v2.gridcal")