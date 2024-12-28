import os
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_options import SolverType
import GridCalEngine.api as gce
import faulthandler
import numpy as np
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_generalized_formulation2 import PfGeneralizedFormulation
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx
faulthandler.enable()  # start @ the beginning

"""
Check that a transformer can regulate the voltage at a bus
"""
def run_fubm() -> None:
    """

    :return:
    """
    # fname = os.path.join("..", "..", "..", "tests", 'data', 'grids', 'fubm_caseHVDC_vt.m')
    fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids",
                         "fubm_caseHVDC_vt_copy.gridcal")  # copy of the above
    # fname = os.path.join('data', 'grids', 'fubm_caseHVDC_vt.m')
    grid = gce.open_file(fname)

    for solver_type in [SolverType.NR, SolverType.LM, SolverType.PowellDogLeg]:
        opt = gce.PowerFlowOptions(solver_type=solver_type,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_modules=True,
                                   control_taps_phase=True,
                                   control_remote_voltage=True,
                                   verbose=2)
        driver = gce.PowerFlowDriver(grid=grid, options=opt)
        driver.run()
        results = driver.results
        vm = np.abs(results.voltage)
        expected_vm = np.array([1.1000, 1.0960, 1.0975, 1.1040, 1.1119, 1.1200])
        print("results converge?", results.converged)
        print("results.voltage absolute", np.abs(results.voltage))
        print("results.voltage angle", np.angle(results.voltage))
        ok = np.allclose(vm, expected_vm, rtol=1e-4)
        assert ok



def run_voltage_control_with_ltc() -> None:
    """
    Check that a transformer can regulate the voltage at a bus
    """
    fname = os.path.join("..", "..", "..", "tests", 'data', 'grids', '5Bus_LTC_FACTS_Fig4.7.gridcal')
    grid = gce.open_file(fname)
    bus_dict = grid.get_bus_index_dict()
    ctrl_idx = bus_dict[grid.transformers2w[0].regulation_bus]

    for control_taps_modules in [True, False]:
        for solver_type in [SolverType.NR, SolverType.LM, SolverType.PowellDogLeg]:
            options = PowerFlowOptions(solver_type,
                                       verbose=2,
                                       control_q=False,
                                       retry_with_other_methods=False,
                                       control_taps_modules=control_taps_modules,
                                       control_taps_phase=False,
                                       control_remote_voltage=False,
                                       apply_temperature_correction=False)

            results = gce.power_flow(grid, options)

            vm = np.abs(results.voltage)

            assert results.converged

            # check that the bus voltage module is the the transformer voltage set point
            ok = np.isclose(vm[ctrl_idx], grid.transformers2w[0].vset, atol=options.tolerance)

            if control_taps_modules:
                assert ok
            else:
                assert not ok


def run_qf_control_with_ltc() -> None:
    """
    Check that a transformer can regulate the voltage at a bus
    """
    fname = os.path.join("..", "..", "..", "tests", 'data', 'grids', '5Bus_PST_FACTS_Fig4.10(Qf).gridcal')
    grid = gce.open_file(fname)

    for control_taps_modules in [True, False]:
        for solver_type in [SolverType.NR, SolverType.LM, SolverType.PowellDogLeg]:
            options = PowerFlowOptions(solver_type,
                                       verbose=2,
                                       control_q=False,
                                       retry_with_other_methods=False,
                                       control_taps_modules=control_taps_modules)

            results = gce.power_flow(grid, options)
            print("results converged?", results.converged)
            assert results.converged

            # check that the bus voltage module is the transformer voltage set point
            print("results.Sf[7].imag", results.Sf[7].imag)
            print("grid.transformers2w[0].Qset", grid.transformers2w[0].Qset)
            ok = np.isclose(results.Sf[7].imag, grid.transformers2w[0].Qset, atol=options.tolerance)

            if control_taps_modules:
                assert ok
            else:
                assert not ok

def run_qt_control_with_ltc() -> None:
    """
    Check that a transformer can regulate the voltage at a bus
    """
    fname = os.path.join("..", "..", "..", "tests", 'data', 'grids', '5Bus_PST_FACTS_Fig4.10(Qf).gridcal')

    grid = gce.open_file(fname)
    grid.transformers2w[0].tap_module_control_mode = gce.TapModuleControl.Qt

    for control_taps_modules in [True, False]:
        for solver_type in [SolverType.NR, SolverType.LM, SolverType.PowellDogLeg]:
            options = PowerFlowOptions(solver_type,
                                       verbose=2,
                                       control_q=False,
                                       retry_with_other_methods=False,
                                       control_taps_modules=control_taps_modules)

            results = gce.power_flow(grid, options)

            assert results.converged

            # check that the bus voltage module is the the transformer voltage set point
            print("results.St[7].imag", results.St[7].imag)
            print("grid.transformers2w[0].Qset", grid.transformers2w[0].Qset)
            ok = np.isclose(results.St[7].imag, grid.transformers2w[0].Qset, atol=options.tolerance)

            if control_taps_modules:
                assert ok
            else:
                assert not ok


def run_power_flow_control_with_pst_pf() -> None:
    """
    Check that a transformer can regulate the voltage at a bus
    """
    fname = os.path.join("..", "..", "..", "tests", 'data', 'grids', '5Bus_PST_FACTS_Fig4.10.gridcal')
    grid = gce.open_file(fname)

    for control_taps_phase in [True, False]:
        for solver_type in [SolverType.NR, SolverType.LM, SolverType.PowellDogLeg]:
            options = PowerFlowOptions(solver_type,
                                       verbose=0,
                                       control_q=False,
                                       retry_with_other_methods=False,
                                       control_taps_phase=control_taps_phase)

            results = gce.power_flow(grid, options)

            assert results.converged

            # check that the bus voltage module is the the transformer voltage set point
            print("results.Sf[7].real", results.Sf[7].real)
            print("grid.transformers2w[0].Pset", grid.transformers2w[0].Pset)
            ok = np.isclose(results.Sf[7].real, grid.transformers2w[0].Pset, atol=options.tolerance)

            if control_taps_phase:
                assert ok
            else:
                assert not ok


def run_power_flow_control_with_pst_pt() -> None:
    """
    Check that a transformer can regulate the voltage at a bus
    """
    fname = os.path.join("..", "..", "..", "tests", 'data', 'grids', '5Bus_PST_FACTS_Fig4.10.gridcal')

    grid = gce.open_file(fname)

    for control_taps_phase in [True, False]:
        for solver_type in [SolverType.NR, SolverType.LM, SolverType.PowellDogLeg]:
            options = PowerFlowOptions(solver_type,
                                       verbose=0,
                                       control_q=False,
                                       retry_with_other_methods=False,
                                       control_taps_phase=control_taps_phase,
                                       max_iter=80)

            results = gce.power_flow(grid, options)

            assert results.converged

            # check that the bus voltage module is the transformer voltage set point
            print("results.St[7].real", results.St[7].real)
            print("grid.transformers2w[0].Pset", grid.transformers2w[0].Pset)
            ok = np.isclose(results.St[7].real, grid.transformers2w[0].Pset, atol=options.tolerance)

            if control_taps_phase:
                assert ok
            else:
                assert not ok

def run_power_flow_12bus_acdc() -> None:
    """
    Check that a transformer can regulate the voltage at a bus
    """
    fname = os.path.join("..", "..", "..", "tests", 'data', 'grids', 'AC-DC with all and DCload.gridcal')

    grid = gce.open_file(fname)

    expected_v = np.array(
        [1. + 0.j,
         0.99992855 - 0.01195389j,
         0.98147048 - 0.02808957j,
         0.99960499 - 0.02810458j,
         0.9970312 + 0.j,
         0.99212134 + 0.j,
         1. + 0.j,
         0.99677598 + 0.j,
         0.99172174 - 0.02331925j,
         0.99262885 - 0.02434865j,
         1. + 0.j,
         0.99972904 - 0.0232776j,
         0.99751785 - 0.01550583j,
         0.99999118 - 0.00419999j,
         0.99938143 - 0.03516744j,
         0.99965346 - 0.02632404j,
         0.99799193 + 0.j]
    )

    # ------------------------------------------------------------------------------------------------------------------
    for solver_type in [SolverType.NR, SolverType.LM, SolverType.PowellDogLeg]:

        options = PowerFlowOptions(solver_type=solver_type,
                                   verbose=2,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_phase=True,
                                   max_iter=80)

        results = gce.power_flow(grid, options)
        print("results converged?", results.converged)
        print("results.iterations", results.iterations)
        print("results.voltage", results.get_bus_df())

        assert np.allclose(expected_v, results.voltage, atol=1e-6)

        assert results.converged

def solve_generalized(grid: gce.MultiCircuit, options: PowerFlowOptions) -> NumericPowerFlowResults:
    """

    :param grid:
    :param options:
    :return:
    """
    nc = gce.compile_numerical_circuit_at(
        grid,
        t_idx=None,
        apply_temperature=False,
        branch_tolerance_mode=gce.BranchImpedanceMode.Specified,
        opf_results=None,
        use_stored_guess=False,
        bus_dict=None,
        areas_dict=None,
        control_taps_modules=options.control_taps_modules,
        control_taps_phase=options.control_taps_phase,
        control_remote_voltage=options.control_remote_voltage,
    )

    islands = nc.split_into_islands(consider_hvdc_as_island_links=True)
    logger = Logger()

    island = islands[0]

    Vbus = island.bus_data.Vbus
    S0 = island.get_power_injections_pu()
    I0 = island.get_current_injections_pu()
    Y0 = island.get_admittance_injections_pu()
    Qmax_bus, Qmin_bus = island.get_reactive_power_limits()
    problem = PfGeneralizedFormulation(V0=Vbus,
                                       S0=S0,
                                       I0=I0,
                                       Y0=Y0,
                                       Qmin=Qmin_bus,
                                       Qmax=Qmax_bus,
                                       nc=island,
                                       options=options,
                                       logger=logger)

    solution = newton_raphson_fx(problem=problem,
                                 tol=options.tolerance,
                                 max_iter=options.max_iter,
                                 trust=options.trust_radius,
                                 verbose=options.verbose,
                                 logger=logger)

    logger.print("Logger")

    return problem, solution

def run_fubm() -> None:
    """

    :return:
    """
    fname = os.path.join("..", "..", "..", "..", "Grids_and_profiles", "grids", "fubm_caseHVDC_vt_mod6.gridcal")
    # fname = os.path.join(TEST_FOLDER, 'data', 'grids', 'fubm_caseHVDC_vt.m')
    grid = gce.open_file(fname)

    options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_modules=True,
                                   control_taps_phase=True,
                                   control_remote_voltage=True,
                                   verbose=2)
    problem, solution = solve_generalized(grid=grid, options=options)

    vm = np.abs(solution.V)


# run_voltage_control_with_ltc() # passes
# run_qf_control_with_ltc()  # passes
# run_qt_control_with_ltc()   # passes
# run_power_flow_control_with_pst_pf() # passes
# run_power_flow_control_with_pst_pt() # passes
# run_power_flow_12bus_acdc()
run_fubm()