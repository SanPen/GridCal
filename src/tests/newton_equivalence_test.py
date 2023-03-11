import os
import numpy as np
import pandas as pd
import newtonpa as npa
import GridCal.Engine as gce
from GridCal.Engine.Core.Compilers.circuit_to_newton_pa import to_newton_pa
npa.findAndActivateLicense()
from tests.newton_equivalence_utils import compare_inputs, compare_inputs_at

gridcal_file_name = '/Users/santi/Git/Elewit/newton-solver/newton/research/data/gridcal/Spain_France_portugal.gridcal'
# gridcal_file_name = '/Users/santi/Git/GitHub/GridCal/src/tests/data/grids/IEEE39_1W.gridcal'

grid_gc = gce.FileOpen(gridcal_file_name).open()

# use the GridCal converter to get the Newton Grid
grid_newton, _ = to_newton_pa(grid_gc, time_series=True, tidx=list(range(grid_gc.get_time_number())))


t = 100
err_count = compare_inputs_at(grid_newton=grid_newton, grid_gc=grid_gc, tol=1e-6, t=t)

print(err_count, "errors")
