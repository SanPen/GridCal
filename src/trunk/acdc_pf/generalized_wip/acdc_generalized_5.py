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
    print(
        "##########################################################################################################################")
    return results.iterations, results.error, results.elapsed


def run_cases():
    iterations = []
    errors = []
    elapseds = []
    # results1_abs = [1.0234, 1.1234, 1.02343826, 1.0222, 1.0111]
    # results1_angle = [-0.00171021, -0.0012147, -0.00171077, 0, 0]
    # iteration, error, elapsed = run_pf("5bus_HVDC_v6.gridcal", results1_abs, results1_angle)
    # iterations.append(iteration)
    # errors.append(error)
    # elapseds.append(elapsed)
    #
    # results1_abs = [1.0234, 1.1234, 1.02343826, 1.0222, 1.0111]
    # results1_angle = [-0.00171021, -0.0012147, -0.00171077, 0, 0]
    # iteration, error, elapsed = run_pf("5bus_HVDC_v6.gridcal", results1_abs, results1_angle)
    # iterations.append(iteration)
    # errors.append(error)
    # elapseds.append(elapsed)
    #
    #
    # results2_abs = [1.01, 1.0333, 1.04608061, 1.05, 1.02521801, 1.02]
    # results2_angle = [0, -0.00476848, 0, 0, -0.02481211, -0.02380485]
    # iteration, error, elapsed = run_pf("fubm_caseHVDC_vt_mod6.gridcal", results2_abs, results2_angle)
    # iterations.append(iteration)
    # errors.append(error)
    # elapseds.append(elapsed)
    #
    # results3_abs = [1.01, 1.0333, 1.05390476, 1.05, 1.07016516, 1.02]
    # results3_angle = [0, -0.00795171, 0, 0, -0.16700929, -0.16562434]
    # iteration, error, elapsed = run_pf("fubm_caseHVDC_vt_mod6_diffcontrols.gridcal", results3_abs, results3_angle)
    # iterations.append(iteration)
    # errors.append(error)
    # elapseds.append(elapsed)
    #
    # # LTC test case: tap_module_control_mode = Vm, tap_phase_control_mode = Fixed
    # results4_abs_old = [1.06, 1.0, 0.96728881, 1.0, 0.96584775, 0.96711307]
    # results4_angle_old = [0.0, -0.07753742, -0.09242494, -0.03761135, -0.104008, -0.09123176]
    # results4_abs = [1.06, 1.0, 0.96788061, 1.0, 0.96604488, 0.96756809]
    # results4_angle = [0.0, -0.07728802, -0.09302293, -0.03767614, -0.10423513, -0.09069765]
    # iteration, error, elapsed = run_pf("transformerSimpleRaiyan.gridcal", results4_abs, results4_angle)
    # iterations.append(iteration)
    # errors.append(error)
    # elapseds.append(elapsed)
    #
    # # LTC test case: tap_module_control_mode = Fixed, tap_phase_control_mode = Pf
    # results5_abs = [1.06, 0.98968571, 0.9801954, 1.0, 0.96997036, 0.98149764]
    # results5_angle = [0., -0.06216552, -0.11737288, -0.04102584, -0.11426947, -0.11781403]
    # iteration, error, elapsed = run_pf("transformerSimpleRaiyan_2.gridcal", results5_abs, results5_angle)
    # iterations.append(iteration)
    # errors.append(error)
    # elapseds.append(elapsed)
    #
    # # LTC test case: tap_module_control_mode = Vm, tap_phase_control_mode = Pf
    # results6_abs = [1.06, 1., 0.96816084, 1., 0.96588642, 0.96798615]
    # results6_angle = [0., -0.0649926, -0.11397142, -0.04094719, -0.11328811, -0.1139095 ]
    # iteration, error, elapsed = run_pf("transformerSimpleRaiyan_3.gridcal", results6_abs, results6_angle)
    # iterations.append(iteration)
    # errors.append(error)
    # elapseds.append(elapsed)

    # VSC + Trafo test case
    results7_abs = [1.01, 1.0333, 1.04608061, 1.05, 1.02521801, 1.02]
    #symbolic = [1.01       1.0333     1.04608061 1.05       1.02521803 1.02      ]
    results7_angle = [0, -0.00476848, 0, 0, -0.02481211, -0.02380485]
    #symbolic =  [ 0.         -0.00476847  0.          0.         -0.02481183 -0.02380457]
    # iteration, error, elapsed = run_pf("fubm_caseHVDC_vt_wTrafo.gridcal", results7_abs, results7_angle)
    iteration, error, elapsed = run_pf("fubm_caseHVDC_vt_wTrafo.gridcal")
    iterations.append(iteration)
    errors.append(error)
    elapseds.append(elapsed)

    # Out-of-order indexing test case
    results8_abs = [1., 1., 0.9991856, 0.99962511, 1.00001694, 1.00001048, 1., 1.00000484, 0.99991987, 0.99983983, 1., 1.]
    results8_angle = [ 0., 0.00064356, 0.00001842, 0.00008691, 0., 0., 0., 0., -0.00043535, -0.00037459, 0., 0.00031276]
    iteration, error, elapsed = run_pf("ACDC_Josep.gridcal", results8_abs, results8_angle)
    iterations.append(iteration)
    errors.append(error)
    elapseds.append(elapsed)

    # joseps test case without hvdc
    # results9_abs = [1., 1., 0.99987995, 0.99985992, 0.99998306, 0.99998952, 1., 0.99999516, 0.99922554, 0.99960503, 1., 1., 0.99997714, 1.]
    # results9_angle = [ 0., 0.00065027, 0.0000522, 0.00010047, 0., 0., 0., 0., -0.00050546, -0.00046048, 0., 0.00012553, -0.00007508, 0.00028869]
    # iteration, error, elapsed = run_pf("12Bus AC-DC Josep v4noHVDC.gridcal", results9_abs, results9_angle)
    # iterations.append(iteration)
    # errors.append(error)
    # elapseds.append(elapsed)

    print("All test cases passed")
    print("iterations", iterations)
    print("errors", errors)
    print("elapseds", elapseds)




def check_timing():
    import time
    import timeit
    from GridCalEngine.Topology.generalized_simulation_indices import GeneralizedSimulationIndices
    from GridCalEngine.Simulations.PowerFlow.Formulations.pf_generalized_formulation import PfGeneralizedFormulation
    from GridCalEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx
    from GridCalEngine.basic_structures import Logger



    fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids",
                         "fubm_caseHVDC_vt_wTrafo.gridcal")

    grid = gce.open_file(fname)
    main_nc = gce.compile_numerical_circuit_at(grid)

    islands = main_nc.split_into_islands(
        consider_hvdc_as_island_links=True,
    )

    print(f"Base: nbus {main_nc.nbus}, nbr: {main_nc.nbr}, nvsc: {main_nc.nvsc}, nhvdc: {main_nc.nhvdc}")

    options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, tolerance=1e-11)
    logger = Logger()

    island = islands[0]

    problem = PfGeneralizedFormulation(V0=island.Vbus,
                                       S0=island.Sbus,
                                       I0=island.Ibus,
                                       Y0=island.YLoadBus,
                                       Qmin=island.Qmin_bus,
                                       Qmax=island.Qmax_bus,
                                       nc=island,
                                       options=options,
                                       logger=logger)
    print("problem.cg_pttr")
    print(problem.cg_pttr)
    start = time.perf_counter()
    solution = newton_raphson_fx(problem=problem,
                                 tol=options.tolerance,
                                 max_iter=options.max_iter,
                                 trust=options.trust_radius,
                                 verbose=options.verbose,
                                 logger=logger)

    end = time.perf_counter()
    execution_time = end - start
    print(f"Execution Time: {execution_time} seconds")

    print(solution.V)
    print(solution.converged)
    print(solution.iterations)
    print(solution.elapsed)

# run_cases()
check_timing()
check_timing()
# check_timing()

