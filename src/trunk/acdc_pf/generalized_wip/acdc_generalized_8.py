import os
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_options import SolverType
import GridCalEngine.api as gce
import faulthandler
import numpy as np

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



# run_voltage_control_with_ltc() # passes
run_qf_control_with_ltc()  # fails:             results.Sf[7].imag 10.03461107847338    grid.transformers2w[0].Qset 10.0
# run_qt_control_with_ltc()   # fails:                results.St[7].imag 10.134990502497686      grid.transformers2w[0].Qset 10.0
# run_power_flow_control_with_pst_pf() #fails:         results.Sf[7].real -19.770663505442016       grid.transformers2w[0].Pset 40.0
# run_power_flow_control_with_pst_pt() # fails:        results.St[7].real 19.770663505442016    grid.transformers2w[0].Pset 40.0