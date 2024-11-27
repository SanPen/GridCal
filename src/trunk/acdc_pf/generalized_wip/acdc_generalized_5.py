import os
import pandas as pd
import numpy as np

from GridCalEngine.IO.file_handler import FileOpen
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_options import SolverType
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
import GridCalEngine.api as gce

"""
Check that a transformer can regulate the voltage at a bus
"""

def run_pf(file, results_abs=None, results_angle=None):
    print("Running", file)
    fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", file)

    grid = gce.open_file(fname)
    options = PowerFlowOptions(SolverType.NR, verbose=1, control_q=False, retry_with_other_methods=False,
                               control_taps_modules=True, control_taps_phase=True,
                               control_remote_voltage=False, apply_temperature_correction=False)
    results = gce.power_flow(grid, options)
    assert results.converged
    if results_abs is None:
        print("results.voltage", np.abs(results.voltage))
        print("results.voltage", np.angle(results.voltage))
    else:
        assert np.allclose(np.abs(results.voltage), results_abs), "results_abs are not equal"
        assert np.allclose(np.angle(results.voltage), results_angle), "results_angle are not equal"
    print(file, "passed")
    print("##########################################################################################################################")

results1_abs = [1.0234, 1.1234, 1.02343826, 1.0222, 1.0111]
results1_angle = [-0.00171021, -0.0012147, -0.00171077, 0, 0]
run_pf("5bus_HVDC_v6.gridcal", results1_abs, results1_angle)
run_pf("fubm_caseHVDC_vt_mod6.gridcal")
run_pf("fubm_caseHVDC_vt_mod6_diffcontrols.gridcal")
run_pf("transformerSimpleRaiyan.gridcal")

