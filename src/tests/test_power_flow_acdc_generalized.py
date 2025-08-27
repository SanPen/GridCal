# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from typing import Tuple
import os
import pandas as pd
import numpy as np
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.file_handler import FileOpen
from VeraGridEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_generalized_formulation import PfGeneralizedFormulation
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx

TEST_FOLDER = os.path.join("")


def solve_generalized(grid: gce.MultiCircuit,
                      options: PowerFlowOptions) -> Tuple[PfGeneralizedFormulation, NumericPowerFlowResults]:
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


def test_ieee_grids():
    """
    Checks the .RAW files of IEEE grids against the PSS/e results
    This test checks 2 things:
    - PSS/e import fidelity
    - PSS/e vs VeraGrid results
    :return: Nothing if ok, fails if not
    """

    files = [
        ('IEEE 14 bus.raw', 'IEEE 14 bus.sav.xlsx'),
        ('IEEE 30 bus.raw', 'IEEE 30 bus.sav.xlsx'),
        ('IEEE 118 Bus v2.raw', 'IEEE 118 Bus.sav.xlsx'),
    ]

    options = PowerFlowOptions(gce.SolverType.NR,
                               verbose=1,
                               control_q=False,
                               retry_with_other_methods=False)

    for f1, f2 in files:

        fname = os.path.join('data', 'grids', 'RAW', f1)
        grid = FileOpen(fname).open()

        problem, solution = solve_generalized(grid=grid, options=options)

        # load the associated results file
        df_v = pd.read_excel(os.path.join('data', 'results', f2), sheet_name='Vabs', index_col=0)
        df_p = pd.read_excel(os.path.join('data', 'results', f2), sheet_name='Pbranch', index_col=0)

        v_gc = np.abs(solution.V)
        v_psse = df_v.values[:, 0]
        p_gc = solution.Sf.real
        p_psse = df_p.values[:, 0]

        v_ok = np.allclose(v_gc, v_psse, atol=1e-2)
        flow_ok = np.allclose(p_gc, p_psse, atol=1e-0)

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

    fname = os.path.join('data', 'grids', 'ZIP_load_example.gridcal')
    grid = FileOpen(fname).open()

    options = PowerFlowOptions(tolerance=1e-6)
    problem, solution = solve_generalized(grid=grid, options=options)

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

    fname = os.path.join('data', 'grids', 'Controllable_shunt_example.gridcal')
    grid = FileOpen(fname).open()
    options = PowerFlowOptions(control_q=False)
    problem, solution = solve_generalized(grid=grid, options=options)

    Vm = np.abs(solution.V)
    Vm_test = np.array([[1., 1.0164564, 1.02]])

    assert np.allclose(Vm_test, Vm, atol=1e-3)


def test_voltage_local_control_with_generation() -> None:
    """
    Check that a generator can perform remote voltage regulation
    """
    fname = os.path.join('data', 'grids', 'RAW', 'IEEE 14 bus.raw')

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

    problem, solution = solve_generalized(grid=grid, options=options)

    vm = np.abs(solution.V)

    assert solution.converged
    assert np.isclose(vm[bus_i], gen.Vset, atol=options.tolerance)

    # run power flow with the local voltage control disabled
    gen.is_controlled = False

    options = PowerFlowOptions(gce.SolverType.NR,
                               verbose=0,
                               control_q=False,
                               retry_with_other_methods=False)

    problem, solution = solve_generalized(grid=grid, options=options)

    results = gce.power_flow(grid, options)
    vm = np.abs(solution.V)

    assert results.converged
    assert not np.isclose(vm[bus_i], gen.Vset, atol=options.tolerance)


def test_voltage_remote_control_with_generation() -> None:
    """
    Check that a generator can perform remote voltage regulation
    """
    fname = os.path.join('data', 'grids', 'RAW', 'IEEE 14 bus.raw')

    grid = gce.open_file(fname)

    # control bus 6 with generator 4
    grid.generators[4].control_bus = grid.buses[6]

    for control_remote_voltage in [True, False]:

        options = PowerFlowOptions(solver_type=SolverType.NR,
                                   verbose=0,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_remote_voltage=control_remote_voltage)

        problem, solution = solve_generalized(grid=grid, options=options)

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
    fname = os.path.join('data', 'grids', '5Bus_LTC_FACTS_Fig4.7.gridcal')

    grid = gce.open_file(fname)
    bus_dict = grid.get_bus_index_dict()
    ctrl_idx = bus_dict[grid.transformers2w[0].regulation_bus]

    for control_taps_modules in [True, False]:
        options = PowerFlowOptions(gce.SolverType.NR,
                                   verbose=1,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_modules=control_taps_modules,
                                   control_taps_phase=False,
                                   control_remote_voltage=False,
                                   apply_temperature_correction=False)

        problem, solution = solve_generalized(grid=grid, options=options)

        vm = np.abs(solution.V)

        print('LTC test case iterations: ', solution.iterations)

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
    fname = os.path.join('data', 'grids', '5Bus_PST_FACTS_Fig4.10(Qf).gridcal')

    grid = gce.open_file(fname)

    for control_taps_modules in [True, False]:

        options = PowerFlowOptions(gce.SolverType.NR,
                                   verbose=1,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_modules=control_taps_modules,
                                   control_taps_phase=False,
                                   orthogonalize_controls=False)

        problem, solution = solve_generalized(grid=grid, options=options)

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
    fname = os.path.join('data', 'grids', '5Bus_PST_FACTS_Fig4.10(Qf).gridcal')

    grid = gce.open_file(fname)
    grid.transformers2w[0].tap_module_control_mode = gce.TapModuleControl.Qt

    for control_taps_modules in [True, False]:
        options = PowerFlowOptions(gce.SolverType.NR,
                                   verbose=1,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_modules=control_taps_modules,
                                   orthogonalize_controls=False)

        problem, solution = solve_generalized(grid=grid, options=options)

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
    fname = os.path.join('data', 'grids', '5Bus_PST_FACTS_Fig4.10.gridcal')

    grid = gce.open_file(fname)

    for control_taps_phase in [True, False]:
        options = PowerFlowOptions(gce.SolverType.NR,
                                   verbose=0,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_phase=control_taps_phase,
                                   orthogonalize_controls=False)

        problem, solution = solve_generalized(grid=grid, options=options)

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
    fname = os.path.join('data', 'grids', '5Bus_PST_FACTS_Fig4.10(Pt).gridcal')

    grid = gce.open_file(fname)

    for control_taps_phase in [True, False]:
        options = PowerFlowOptions(gce.SolverType.NR,
                                   verbose=0,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_phase=control_taps_phase,
                                   orthogonalize_controls=False,
                                   max_iter=80)

        problem, solution = solve_generalized(grid=grid, options=options)

        assert solution.converged

        # check that the bus voltage module is the transformer voltage set point
        ok = np.isclose(solution.St[7].real, grid.transformers2w[0].Pset, atol=options.tolerance)

        if control_taps_phase:
            assert ok
        else:
            assert not ok


# def test_fubm() -> None:  # This test needs to adust the matpower-fubm reading...
#     """
#
#     :return:
#     """
#     fname = os.path.join('data', 'grids', 'fubm_caseHVDC_vt.m')
#     grid = gce.open_file(fname)
#
#     options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
#                                    control_q=False,
#                                    retry_with_other_methods=False,
#                                    control_taps_modules=True,
#                                    control_taps_phase=True,
#                                    control_remote_voltage=True,
#                                    verbose=0)
#     problem, solution = solve_generalized(grid=grid, options=options)
#
#     vm = np.abs(solution.V)
#     expected_vm = np.array([1.1000, 1.0960, 1.0975, 1.1040, 1.1119, 1.1200])
#     ok = np.allclose(vm, expected_vm, rtol=1e-4)
#     assert ok


def test_fubm_new() -> None:
    """

    :return:
    """
    fname = os.path.join('data', 'grids', 'fubm_caseHVDC_vt_josep.gridcal')
    grid = gce.open_file(fname)

    options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_modules=True,
                                   control_taps_phase=True,
                                   control_remote_voltage=True,
                                   verbose=1)
    problem, solution = solve_generalized(grid=grid, options=options)

    vm = np.abs(solution.V)
    expected_vm = np.abs(np.array([1.01 + 0j,
                                   1.0120148113290914 - 0.00414941372825624j,
                                   1.01116 + 0j,
                                   1.0111600156849796 + 0j,
                                   1.0117031232472475 - 0.03475745116898685j,
                                   1.0194294344036188 - 0.03411199600606859j]))

    ok = np.allclose(vm, expected_vm, rtol=1e-4)
    assert ok


def test_hvdc_new() -> None:
    """

    :return:
    """
    fname = os.path.join('data', 'grids', '5bus_HVDC_simple.gridcal')
    grid = gce.open_file(fname)

    options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_modules=True,
                                   control_taps_phase=True,
                                   control_remote_voltage=True,
                                   verbose=1)
    problem, solution = solve_generalized(grid=grid, options=options)

    expected_vm = np.array([1.0233985 - 0.00175023j,
                            1.12339917 - 0.00136459j,
                            1.02343677 - 0.00175086j,
                            1.0222 + 0.j,
                            1.0111 + 0.j])

    ok = np.allclose(solution.V, expected_vm, rtol=1e-4)
    assert ok


def test_power_flow_12bus_acdc() -> None:
    """
    Check that a transformer can regulate the voltage at a bus
    """
    fname = os.path.join('data', 'grids', 'AC-DC with all and DCload.gridcal')

    grid = gce.open_file(fname)

    expected_v = np.array([1. + 0.j,
                           0.99993477 - 0.01142182j,
                           0.981475 - 0.02798462j,
                           0.99961098 - 0.02789078j,
                           0.9970314 + 0.j,
                           0.9921219 + 0.j,
                           1. + 0.j,
                           0.9967762 + 0.j,
                           0.99174229 - 0.02349737j,
                           0.99263056 - 0.02449658j,
                           1. + 0.j,
                           0.99972273 - 0.0235469j,
                           0.99752297 - 0.01554718j,
                           0.99999114 - 0.00421027j,
                           0.99937536 - 0.03533967j,
                           0.99964957 - 0.02647153j,
                           0.99799207 + 0.j])

    # ------------------------------------------------------------------------------------------------------------------
    # for solver_type in [SolverType.NR, SolverType.LM, SolverType.PowellDogLeg]:
    # run power flow

    options = PowerFlowOptions(solver_type=gce.SolverType.NR,
                               verbose=1,
                               control_q=False,
                               retry_with_other_methods=False,
                               control_taps_phase=True,
                               max_iter=80)

    problem, solution = solve_generalized(grid=grid, options=options)

    assert np.allclose(expected_v, solution.V, atol=1e-6)

    assert grid.vsc_devices[0].control1_val == solution.Pf_vsc[0]
    assert grid.vsc_devices[0].control2_val == solution.St_vsc[0].imag

    assert grid.vsc_devices[1].control1_val == abs(solution.V[3])
    assert grid.vsc_devices[1].control2_val == solution.St_vsc[1].real

    assert grid.vsc_devices[2].control1_val == abs(solution.V[6])
    assert grid.vsc_devices[2].control2_val == solution.St_vsc[2].imag

    assert grid.vsc_devices[3].control1_val == solution.Pf_vsc[3]
    assert grid.vsc_devices[3].control2_val == solution.St_vsc[3].imag

    assert grid.transformers2w[2].vset == abs(solution.V[13])

    assert grid.hvdc_lines[0].Pset == solution.Sf_hvdc[0].real

    assert solution.converged


def test_generator_Q_lims() -> None:
    """
    Check that we can shift the controls well when hitting Q limits
    """
    fname = os.path.join('data', 'grids', '5Bus_LTC_FACTS_Fig4.7_Qlim.gridcal')

    grid = gce.open_file(fname)

    for control_q in [True, False]:
        options = PowerFlowOptions(gce.SolverType.NR,
                                   verbose=1,
                                   control_q=control_q,
                                   retry_with_other_methods=False,
                                   control_taps_modules=False,
                                   control_taps_phase=False,
                                   control_remote_voltage=False,
                                   apply_temperature_correction=False,
                                   distributed_slack=False)

        problem, solution = solve_generalized(grid=grid, options=options)

        # check that the bus Q is at the limit
        qbus = solution.Scalc[3].imag
        ok = np.isclose(qbus, grid.generators[1].Qmin, atol=options.tolerance)

        if control_q:
            assert ok
        else:
            assert not ok

        assert solution.converged


def test_transformer_m_lims() -> None:
    """
    Check that we can shift the controls well when dealing with continuous m
    """
    fname = os.path.join('data', 'grids', '5Bus_LTC_FACTS_Fig4.7_mlim.gridcal')

    grid = gce.open_file(fname)

    for control_tap_modules in [True, False]:
        options = PowerFlowOptions(gce.SolverType.NR,
                                   verbose=1,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_modules=control_tap_modules,
                                   control_taps_phase=False,
                                   control_remote_voltage=False,
                                   apply_temperature_correction=False,
                                   distributed_slack=False,
                                   orthogonalize_controls=True,)

        problem, solution = solve_generalized(grid=grid, options=options)

        # check that the transformer m hits a limit
        mtrafo = solution.tap_module[7]
        ok = np.isclose(mtrafo, grid.transformers2w[0].tap_module_max, atol=options.tolerance)

        if control_tap_modules:
            assert ok
        else:
            assert not ok

        assert solution.converged


def test_transformer_tau_lims() -> None:
    """
    Check that we can shift the controls well when dealing with continuous tau
    """
    fname = os.path.join('data', 'grids', '5Bus_LTC_FACTS_Fig4.7_tlim.gridcal')

    grid = gce.open_file(fname)

    for control_tap_phase in [True, False]:
        options = PowerFlowOptions(gce.SolverType.NR,
                                   verbose=1,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_modules=False,
                                   control_taps_phase=control_tap_phase,
                                   control_remote_voltage=False,
                                   apply_temperature_correction=False,
                                   distributed_slack=False)

        problem, solution = solve_generalized(grid=grid, options=options)

        # check that the transformer m hits a limit
        mtrafo = solution.tap_angle[7]
        ok = np.isclose(mtrafo, grid.transformers2w[0].tap_phase_max, atol=options.tolerance)

        if control_tap_phase:
            assert ok
        else:
            assert not ok

        assert solution.converged


if __name__ == "__main__":
    # test_ieee_grids()
    # test_zip()
    # test_controllable_shunt()
    # test_voltage_local_control_with_generation()
    # test_voltage_remote_control_with_generation()
    # test_voltage_control_with_ltc()
    # test_qf_control_with_ltc()
    # test_qt_control_with_ltc()
    # test_power_flow_control_with_pst_pf()
    # test_power_flow_control_with_pst_pt()
    # test_fubm()
    # test_fubm_new()
    # test_hvdc_new()
    # test_power_flow_12bus_acdc()
    # test_generator_Q_lims()
    # test_transformer_m_lims()
    # test_transformer_tau_lims()
    test_power_flow_12bus_acdc()
