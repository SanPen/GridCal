import os
import numpy as np
import GridCalEngine.api as gce
from GridCalEngine.api import *
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import multi_island_pf_nc


# Load basic grid

def numerical_cicuit_branch_contingencies():
    """
    Check whether the branch contingency present on the gridcal file is applied correctly
    This test compares the number of contingencies with the number of deactivated branches.
    :return: Nothing if ok, fails if not
    """
    # fname = os.path.join('src', 'trunk', 'scopf', '3bus_cont1.gridcal')
    fname = os.path.join('src', 'trunk', 'scopf', '3bus_cont_line_only.gridcal')
    grid = gce.FileOpen(fname).open()
    nc = compile_numerical_circuit_at(grid, t_idx=None)

    cnt = grid.contingencies
    nc.set_con_or_ra_status(event_list=cnt)

    # 3. Define Power Flow Options
    pf_options = PowerFlowOptions(
        solver_type=GridCalEngine.enumerations.SolverType.NR, # Newton-Raphson is common
        tolerance=1e-8,
        max_iter=20,
        control_q=True # Or False, depending on desired controls
        # Add other options as needed
    )

    # 4. Run Power Flow using the NumericalCircuit
    print("Running power flow on NumericalCircuit...")
    pf_results = multi_island_pf_nc(nc=nc, options=pf_options)
    print(f"Error: {pf_results.error}")

    print('Done')


if __name__ == '__main__':
    numerical_cicuit_branch_contingencies()