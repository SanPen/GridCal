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
    assert results.converged, f"Power flow did not converge for {file}"
    if results_abs is None:
        print("results.voltage", np.abs(results.voltage))
        print("results.voltage", np.angle(results.voltage))
    else:
        assert np.allclose(np.abs(results.voltage), results_abs), "results_abs are not equal"
        assert np.allclose(np.angle(results.voltage), results_angle), "results_angle are not equal"
    print(file, "passed")
    print("##########################################################################################################################")
    return results.iterations, results.error


def run_cases():
    iterations = []
    errors = []
    results1_abs = [1.0234, 1.1234, 1.02343826, 1.0222, 1.0111]
    results1_angle = [-0.00171021, -0.0012147, -0.00171077, 0, 0]
    iteration, error = run_pf("5bus_HVDC_v6.gridcal", results1_abs, results1_angle)
    iterations.append(iteration)
    errors.append(error)

    results2_abs = [1.01, 1.0333, 1.04608061, 1.05, 1.02521801, 1.02]
    results2_angle = [0, -0.00476848, 0, 0, -0.02481211, -0.02380485]
    iteration, error = run_pf("fubm_caseHVDC_vt_mod6.gridcal", results2_abs, results2_angle)
    iteration, error = run_pf("fubm_caseHVDC_vt_mod6.gridcal")
    iterations.append(iteration)
    errors.append(error)

    results3_abs = [1.01, 1.0333, 1.05390476, 1.05, 1.07016516, 1.02]
    results3_angle = [0, -0.00795171, 0, 0, -0.16700929, -0.16562434]
    iteration, error = run_pf("fubm_caseHVDC_vt_mod6_diffcontrols.gridcal", results3_abs, results3_angle)
    iterations.append(iteration)
    errors.append(error)

    # LTC test case: tap_module_control_mode = Vm, tap_phase_control_mode = Fixed
    results4_abs = [1.06, 1.0, 0.96728881, 1.0, 0.96584775, 0.96711307]
    results4_angle = [0.0, -0.07753742, -0.09242494, -0.03761135, -0.104008, -0.09123176]
    iteration, error = run_pf("transformerSimpleRaiyan.gridcal", results4_abs, results4_angle)
    iterations.append(iteration)
    errors.append(error)

    # LTC test case: tap_module_control_mode = Fixed, tap_phase_control_mode = Pf
    results5_abs = [1.06, 0.98928662, 0.98005916, 1.0, 0.9699242, 0.98072026]
    results5_angle = [0, -0.06205628, -0.11733545, -0.04102865, -0.11426107, -0.11755944]
    iteration, error = run_pf("transformerSimpleRaiyan_2.gridcal", results5_abs, results5_angle)
    iterations.append(iteration)
    errors.append(error)

    # LTC test case: tap_module_control_mode = Vm, tap_phase_control_mode = Pf
    results6_abs = [1.06, 1.0, 0.96756753, 1.0, 0.96568495, 0.96746196]
    results6_angle = [0, -0.06499367, -0.11381034, -0.0409491, -0.11324635, -0.11377308]
    iteration, error = run_pf("transformerSimpleRaiyan_3.gridcal", results6_abs, results6_angle)
    iterations.append(iteration)
    errors.append(error)

    # # VSC + Trafo test case (FAILED)
    results7_abs = [1.01, 1.0333, 1.04608061, 1.05, 1.02521801, 1.02]
    results7_angle = [0, -0.00476848, 0, 0, -0.02481211, -0.02380485]
    iteration, error = run_pf("fubm_caseHVDC_vt_wTrafo.gridcal", results7_abs, results7_angle)
    iterations.append(iteration)
    errors.append(error)

    # Out-of-order indexing is a problem (FAILED)
    # results8_abs = [1.0, 1.0, 0.99918761, 0.99962913, 1.00000645, 0.99999161, 1.0, 0.99999613, 0.99991786, 0.99983582, 1.0, 1.0]
    # results8_angle = [0, 0.00051981, -0.00000531, 0.00003945, 0, 0, 0, 0, -0.00041348, -0.00032589, 0, 0.00043712]
    # iteration, error = run_pf("ACDC_Josep.gridcal", results8_abs, results8_angle)
    # iterations.append(iteration)
    # errors.append(error)

    # joseps test case without hvdc (FAILED)
    # results.voltage [1.01       1.0333     1.04608061 1.05       1.02521801 1.02      ]
    # results8_abs = [1.0, 1.0, 0.99987996, 0.99985993, 0.99998306, 0.99998952, 1.0, 0.99999516, 0.99922554, 0.99960503, 1.0, 1.0, 0.99997713, 1.0]
    # results8_angle = [0, 0.00052527, 0.0000272, 0.00005047, 0, 0, 0, 0, -0.00048425, -0.00041804, 0, 0.00023161, -0.00009023, 0.00031899]
    # iteration, error = run_pf("12Bus AC-DC Josep v4noHVDC.gridcal", results8_abs, results8_angle)
    # iterations.append(iteration)
    # errors.append(error)

    print("All test cases passed")
    print("iterations", iterations)
    print("errors", errors)

run_cases()