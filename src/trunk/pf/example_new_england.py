import os
import GridCalEngine as gce
import pandas as pd
import numpy as np

# folder_path = r"/home/santi/Descargas/New England_Base_case.gridcal"
# file_name = "/home/santi/Descargas/New England_Base_case.gridcal"
file_path = "/home/santi/Descargas/New England_Base_case.gridcal"

# Load a grid
main_circuit = gce.open_file(file_path)

options = gce.PowerFlowOptions(
    solver_type= gce.SolverType.NR,
    retry_with_other_methods = False,
    verbose = 0,
    initialize_with_existing_solution = False,
    tolerance = 1e-7,
    max_iter = 40,
    control_q = False,
    control_taps_modules = False,
    control_taps_phase = False,
    control_remote_voltage = False,
    orthogonalize_controls = False,
    apply_temperature_correction = False,
    branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
    distributed_slack = False,
    ignore_single_node_islands = False,
    trust_radius = 1.0,
    backtracking_parameter = 0.05,
    use_stored_guess = False,
    initialize_angles = False,
    generate_report = False
 )

res = gce.power_flow(grid=main_circuit, options=options)
bus_df = res.get_bus_df()
branch_df = res.get_branch_df()
print(bus_df)
print(branch_df)

