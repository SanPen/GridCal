import os
import numpy as np
import pandas as pd
try:
    import newtonpa as npa
    import GridCalEngine.api as gce
    from GridCalEngine.Compilers.circuit_to_newton_pa import to_newton_pa
    npa.findAndActivateLicense()
    from tests.newton_equivalence_utils import compare_inputs, compare_inputs_at

    # gridcal_file_name = '/Users/santi/Git/Elewit/newton-solver/newton/research/data/gridcal/Spain_France_portugal.gridcal'
    gridcal_file_name = '/home/santi/Escritorio/Redes/Spain_France_portugal.gridcal'
    # gridcal_file_name = '/Users/santi/Git/GitHub/GridCal/src/tests/data/grids/IEEE39_1W.gridcal'

    if os.path.exists(gridcal_file_name):
        grid_gc = gce.FileOpen(gridcal_file_name).open()

        # use the GridCal converter to get the Newton Grid
        grid_newton, _ = to_newton_pa(grid_gc, use_time_series=True, time_indices=list(range(grid_gc.get_time_number())))


        t = 100
        err_count = compare_inputs_at(grid_newton=grid_newton, grid_gc=grid_gc, tol=1e-6, t=t)

        print(err_count, "errors")
except ImportError:
    print('intall newtonpa to perform this test')
