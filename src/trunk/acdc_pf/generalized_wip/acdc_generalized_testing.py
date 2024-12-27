# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import os
import pandas as pd
import numpy as np
from GridCalEngine.basic_structures import Logger
from GridCalEngine.IO.file_handler import FileOpen
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_options import SolverType
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
import GridCalEngine.api as gce
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_generalized_formulation2 import PfGeneralizedFormulation
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx

TEST_FOLDER = os.path.join("..", "..", "..", "tests")


def solve_generalized(grid: gce.MultiCircuit, options: PowerFlowOptions) -> NumericPowerFlowResults:
    """

    :param grid:
    :param options:
    :return:
    """
    nc = gce.compile_numerical_circuit_at(grid)
    islands = nc.split_into_islands(consider_hvdc_as_island_links=True, )
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

    solution = newton_raphson_fx(problem=problem,
                                 tol=options.tolerance,
                                 max_iter=options.max_iter,
                                 trust=options.trust_radius,
                                 verbose=options.verbose,
                                 logger=logger)

    return solution


def test_ieee_grids():
    """
    Checks the .RAW files of IEEE grids against the PSS/e results
    This test checks 2 things:
    - PSS/e import fidelity
    - PSS/e vs GridCal results
    :return: Nothing if ok, fails if not
    """

    files = [
        ('IEEE 14 bus.raw', 'IEEE 14 bus.sav.xlsx'),
        ('IEEE 30 bus.raw', 'IEEE 30 bus.sav.xlsx'),
        ('IEEE 118 Bus v2.raw', 'IEEE 118 Bus.sav.xlsx'),
    ]

    options = PowerFlowOptions(gce.SolverType.NR,
                               verbose=0,
                               control_q=False,
                               retry_with_other_methods=False)

    for f1, f2 in files:

        fname = os.path.join(TEST_FOLDER, 'data', 'grids', 'RAW', f1)
        grid = FileOpen(fname).open()

        solution = solve_generalized(grid=grid, options=options)

        # load the associated results file
        df_v = pd.read_excel(os.path.join(TEST_FOLDER, 'data', 'results', f2), sheet_name='Vabs', index_col=0)
        df_p = pd.read_excel(os.path.join(TEST_FOLDER, 'data', 'results', f2), sheet_name='Pbranch', index_col=0)

        v_gc = np.abs(solution.V)
        v_psse = df_v.values[:, 0]
        p_gc = solution.Sf.real
        p_psse = df_p.values[:, 0]

        # br_codes = [e.code for e in main_circuit.get_branches_wo_hvdc()]
        # p_gc_df = pd.DataFrame(data=p_gc, columns=[0], index=br_codes)
        # pf_diff_df = p_gc_df - df_p

        v_ok = np.allclose(v_gc, v_psse, atol=1e-2)
        flow_ok = np.allclose(p_gc, p_psse, atol=1e-0)
        # flow_ok = (np.abs(pf_diff_df.values) < 1e-3).all()

        if not v_ok:
            print('power flow voltages test for {} failed'.format(fname))
        if not flow_ok:
            print('power flow flows test for {} failed'.format(fname))

        assert v_ok
        assert flow_ok


def test_zip() -> None:
    """
    Test the power flow with ZIP loads compared to PSSe
    """

    fname = os.path.join(TEST_FOLDER, 'data', 'grids', 'ZIP_load_example.raw')
    grid = FileOpen(fname).open()

    options = PowerFlowOptions(tolerance=1e-6)
    solution = solve_generalized(grid=grid, options=options)

    Vm_psse = np.array([1.00000, 0.98933, 0.98560, 0.98579])
    Va_psse = np.deg2rad(np.array([0.00000, -5.1287, -9.1535, -11.4464]))

    Vm = np.abs(solution.V)
    Va = np.angle(solution.V, deg=False)

    assert np.allclose(Vm_psse, Vm, atol=1e-3)
    assert np.allclose(Va_psse, Va, atol=1e-3)


def test_controllable_shunt() -> None:
    """
    This tests that the controllable shunt is indeed controlling voltage at 1.02 at the third bus
    """

    fname = os.path.join(TEST_FOLDER, 'data', 'grids', 'Controllable_shunt_example.gridcal')
    grid = FileOpen(fname).open()
    options = PowerFlowOptions(control_q=False)
    solution = solve_generalized(grid=grid, options=options)

    Vm = np.abs(solution.V)
    Vm_test = np.array([[1., 1.0164564, 1.02]])

    assert np.allclose(Vm_test, Vm, atol=1e-3)


def test_voltage_local_control_with_generation() -> None:
    """
    Check that a generator can perform remote voltage regulation
    """
    fname = os.path.join(TEST_FOLDER, 'data', 'grids', 'RAW', 'IEEE 14 bus.raw')

    grid = gce.open_file(fname)

    # control local bus with generator 4
    gen = grid.generators[4]
    gen.is_controlled = True
    bus_dict = grid.get_bus_index_dict()
    bus_i = bus_dict[gen.bus]

    # run power flow with the local voltage control enabled
    options = PowerFlowOptions(gce.SolverType.NR,
                               verbose=0,
                               control_q=False,
                               retry_with_other_methods=False)

    solution = solve_generalized(grid=grid, options=options)

    vm = np.abs(solution.V)

    assert solution.converged
    assert np.isclose(vm[bus_i], gen.Vset, atol=options.tolerance)

    # run power flow with the local voltage control disabled
    gen.is_controlled = False

    options = PowerFlowOptions(gce.SolverType.NR,
                               verbose=0,
                               control_q=False,
                               retry_with_other_methods=False)

    solution = solve_generalized(grid=grid, options=options)

    results = gce.power_flow(grid, options)
    vm = np.abs(solution.V)

    assert results.converged
    assert not np.isclose(vm[bus_i], gen.Vset, atol=options.tolerance)


def test_voltage_remote_control_with_generation() -> None:
    """
    Check that a generator can perform remote voltage regulation
    """
    fname = os.path.join(TEST_FOLDER, 'data', 'grids', 'RAW', 'IEEE 14 bus.raw')

    grid = gce.open_file(fname)

    # control bus 6 with generator 4
    grid.generators[4].control_bus = grid.buses[6]

    for control_remote_voltage in [True, False]:

        options = PowerFlowOptions(solver_type=SolverType.NR,
                                   verbose=0,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_remote_voltage=control_remote_voltage)

        solution = solve_generalized(grid=grid, options=options)

        vm = np.abs(solution.V)

        assert solution.converged

        # is the control voltage equal to the desired set point?
        ok = np.isclose(vm[6], grid.generators[4].Vset, atol=options.tolerance)

        if control_remote_voltage:
            assert ok
        else:
            assert not ok


def test_voltage_control_with_ltc() -> None:
    """
    Check that a transformer can regulate the voltage at a bus
    """
    fname = os.path.join(TEST_FOLDER, 'data', 'grids', '5Bus_LTC_FACTS_Fig4.7.gridcal')

    grid = gce.open_file(fname)
    bus_dict = grid.get_bus_index_dict()
    ctrl_idx = bus_dict[grid.transformers2w[0].regulation_bus]

    for control_taps_modules in [True, False]:
        options = PowerFlowOptions(gce.SolverType.NR,
                                   verbose=0,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_modules=control_taps_modules,
                                   control_taps_phase=False,
                                   control_remote_voltage=False,
                                   apply_temperature_correction=False)

        solution = solve_generalized(grid=grid, options=options)

        vm = np.abs(solution.V)

        assert solution.converged

        # check that the bus voltage module is the transformer voltage set point
        ok = np.isclose(vm[ctrl_idx], grid.transformers2w[0].vset, atol=options.tolerance)

        if control_taps_modules:
            assert ok
        else:
            assert not ok


def test_qf_control_with_ltc() -> None:
    """
    Check that a transformer can regulate the voltage at a bus
    """
    fname = os.path.join(TEST_FOLDER, 'data', 'grids', '5Bus_PST_FACTS_Fig4.10(Qf).gridcal')

    grid = gce.open_file(fname)

    for control_taps_modules in [True, False]:

        options = PowerFlowOptions(gce.SolverType.NR,
                                   verbose=0,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_modules=control_taps_modules)


        solution = solve_generalized(grid=grid, options=options)

        assert solution.converged

        # check that the bus voltage module is the transformer voltage set point
        ok = np.isclose(solution.Sf[7].imag, grid.transformers2w[0].Qset, atol=options.tolerance)

        if control_taps_modules:
            assert ok
        else:
            assert not ok


def test_qt_control_with_ltc() -> None:
    """
    Check that a transformer can regulate the voltage at a bus
    """
    fname = os.path.join(TEST_FOLDER, 'data', 'grids', '5Bus_PST_FACTS_Fig4.10(Qf).gridcal')

    grid = gce.open_file(fname)
    grid.transformers2w[0].tap_module_control_mode = gce.TapModuleControl.Qt

    for control_taps_modules in [True, False]:
        options = PowerFlowOptions(gce.SolverType.NR,
                                   verbose=0,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_modules=control_taps_modules)

        solution = solve_generalized(grid=grid, options=options)

        assert solution.converged

        # check that the bus voltage module is the transformer voltage set point
        ok = np.isclose(solution.St[7].imag, grid.transformers2w[0].Qset, atol=options.tolerance)

        if control_taps_modules:
            assert ok
        else:
            assert not ok


def test_power_flow_control_with_pst_pf() -> None:
    """
    Check that a transformer can regulate the voltage at a bus
    """
    fname = os.path.join(TEST_FOLDER, 'data', 'grids', '5Bus_PST_FACTS_Fig4.10.gridcal')

    grid = gce.open_file(fname)

    for control_taps_phase in [True, False]:
        options = PowerFlowOptions(gce.SolverType.NR,
                                   verbose=0,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_phase=control_taps_phase)

        solution = solve_generalized(grid=grid, options=options)

        assert solution.converged

        # check that the bus voltage module is the transformer voltage set point
        ok = np.isclose(solution.Sf[7].real, grid.transformers2w[0].Pset, atol=options.tolerance)

        if control_taps_phase:
            assert ok
        else:
            assert not ok


def test_power_flow_control_with_pst_pt() -> None:
    """
    Check that a transformer can regulate the voltage at a bus
    """
    fname = os.path.join(TEST_FOLDER, 'data', 'grids', '5Bus_PST_FACTS_Fig4.10(Pt).gridcal')

    grid = gce.open_file(fname)

    for control_taps_phase in [True, False]:
        options = PowerFlowOptions(gce.SolverType.NR,
                                   verbose=0,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_phase=control_taps_phase,
                                   max_iter=80)

        solution = solve_generalized(grid=grid, options=options)

        assert solution.converged

        # check that the bus voltage module is the transformer voltage set point
        ok = np.isclose(solution.St[7].real, grid.transformers2w[0].Pset, atol=options.tolerance)

        if control_taps_phase:
            assert ok
        else:
            assert not ok


def test_fubm() -> None:
    """

    :return:
    """
    fname = os.path.join(TEST_FOLDER, 'data', 'grids', 'fubm_caseHVDC_vt.m')
    grid = gce.open_file(fname)

    options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_modules=True,
                                   control_taps_phase=True,
                                   control_remote_voltage=True,
                                   verbose=0)
    solution = solve_generalized(grid=grid, options=options)

    vm = np.abs(solution.V)
    expected_vm = np.array([1.1000, 1.0960, 1.0975, 1.1040, 1.1119, 1.1200])
    ok = np.allclose(vm, expected_vm, rtol=1e-4)
    assert ok


def test_power_flow_12bus_acdc() -> None:
    """
    Check that a transformer can regulate the voltage at a bus
    """
    fname = os.path.join(TEST_FOLDER, 'data', 'grids', 'AC-DC with all and DCload.gridcal')

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
    # for solver_type in [SolverType.NR, SolverType.LM, SolverType.PowellDogLeg]:
    # run power flow


    options = PowerFlowOptions(solver_type=gce.SolverType.NR,
                               verbose=0,
                               control_q=False,
                               retry_with_other_methods=False,
                               control_taps_phase=True,
                               max_iter=80)

    solution = solve_generalized(grid=grid, options=options)

    assert np.allclose(expected_v, solution.V, atol=1e-6)

    assert solution.converged
