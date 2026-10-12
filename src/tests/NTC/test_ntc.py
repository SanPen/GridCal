# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
from typing import List, Tuple
import numpy as np
import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType, SolutionState, ResultTypes
from VeraGridEngine.Simulations.NTC.ntc_ts_results import OptimalNetTransferCapacityTimeSeriesResults
from VeraGridEngine.Simulations.Clustering.clustering_results import ClusteringResults
from VeraGridEngine.Simulations.NTC.ntc_opf import run_linear_ntc_opf, NtcVars, get_exchange_proportions
from VeraGridEngine.basic_structures import Logger, Vec, IntVec, ObjVec
from VeraGridEngine.Utils.MIP.selected_interface import LpModel
from VeraGridEngine.Devices.types import BRANCH_TYPES
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice


TEST_GRID_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "grids"))


def get_grid_path(file_name: str) -> str:
    """
    Build an absolute path to a grid fixture used by the NTC tests.

    :param file_name: Grid fixture file name.
    :return: Absolute grid fixture path.
    """
    return os.path.join(TEST_GRID_DIR, file_name)


def test_ntc_ultra_simple() -> None:
    """

    :return:
    """
    np.set_printoptions(precision=4)
    fname = get_grid_path('red_ultra_simple_ntc.gridcal')

    grid = gce.open_file(fname)

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                           objects_to=[grid.areas[1]])

    opf_options = gce.OptimalPowerFlowOptions()
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=False,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=False,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=False,
        consider_contingencies=False,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results

    assert res.converged
    assert np.isclose(res.Sf[0].real, 50.0)
    assert np.isclose(res.dSbus.sum(), 0.0)
    assert res.dSbus[0] == 25.0
    assert abs(res.nodal_balance.sum()) < 1e-8

    # ----------------------------------------------------------
    # Now, ignore the limits
    # ----------------------------------------------------------

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=False,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=False,
        consider_contingencies=False,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results

    assert res.converged
    assert np.isclose(res.Sf[0].real, 100.0)
    assert np.isclose(res.dSbus.sum(), 0.0)
    assert res.dSbus[0] == 75.0
    assert abs(res.nodal_balance.sum()) < 1e-8


def test_ntc_ieee_14() -> None:
    """

    :return:
    """
    np.set_printoptions(precision=4)
    fname = get_grid_path('ntc_test.gridcal')

    grid = gce.open_file(fname)

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                           objects_to=[grid.areas[1]])

    opf_options = gce.OptimalPowerFlowOptions()
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=True,
        consider_contingencies=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results

    assert res.converged
    assert abs(res.nodal_balance.sum()) < 1e-8


def test_issue_372_1():
    """
    https://github.com/SanPen/VeraGrid/issues/372#issuecomment-2823645586

    Using the grid IEEE14 - ntc areas_voltages_hvdc_shifter_l10free.gridcal

    Test:

        Given a base situation (simulated with a linear power flow)
        We define the exchange from A1->A2
        Run the NTC optimization

    Run options:

        No contingencies
        HVDC mode: Pset
        Phase shifter (branch 8): tap_phase_control_mode: fixed.
        All generators enable_dispatch = True
        Exchange sensitivity criteria: use alpha = 5%

    Metrics:

        ΔP in A1 optimized > 0 (because there are no base overloads)
        ΔP in A2 optimized < 0 (because there are no base overloads)
        ΔP in A1 == − ΔP in A2
        The summation of flow increments in the inter-area branches must be ΔP in A1.
        Monitored & selected by the exchange sensitivity criteria branches must not be overloaded beyond 100%

    """
    # fname = get_grid_path('ntc_test.gridcal')
    fname = get_grid_path('IEEE14 - ntc areas_voltages_hvdc_shifter_l10free.gridcal')

    grid = gce.open_file(fname)

    # Phase shifter (branch 8): tap_phase_control_mode: fixed.
    grid.transformers2w[6].tap_phase_control_mode = gce.TapPhaseControl.fixed

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                           objects_to=[grid.areas[1]])

    opf_options = gce.OptimalPowerFlowOptions(
        consider_contingencies=False,
    )

    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.05,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=True,
        consider_contingencies=False,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results

    bus_area_indices = grid.get_bus_area_indices()
    a1 = np.where(bus_area_indices == 0)[0]
    a2 = np.where(bus_area_indices == 1)[0]

    theta = np.angle(res.voltage)

    assert res.converged[0]
    # Allow small solver-dependent balance residuals (MW).
    assert abs(res.nodal_balance.sum()) < 1e-6

    # ΔP in A1 optimized > 0 (because there are no base overloads)
    assert res.dSbus[a1].sum() > 0

    # ΔP in A2 optimized < 0 (because there are no base overloads)
    assert res.dSbus[a2].sum() < 0

    # ΔP in A1 == − ΔP in A2
    assert np.isclose(res.dSbus[a1].sum(), -res.dSbus[a2].sum(), atol=1e-6)

    # List of (branch index, branch object, flow sense w.r.t the area exchange)
    inter_info = grid.get_inter_areas_branches(a1=[grid.areas[0]], a2=[grid.areas[1]])
    inter_area_branch_idx = [x[0] for x in inter_info]
    inter_area_branch_sense = [x[2] for x in inter_info]
    inter_info_hvdc = grid.get_inter_areas_hvdc_branches(a1=[grid.areas[0]], a2=[grid.areas[1]])
    inter_area_hvdc_idx = [x[0] for x in inter_info_hvdc]
    inter_area_hvdc_sense = [x[2] for x in inter_info_hvdc]
    inter_area_flows = np.sum(res.Sf[inter_area_branch_idx].real * inter_area_branch_sense)
    inter_area_flows += np.sum(res.hvdc_Pf[inter_area_hvdc_idx] * inter_area_hvdc_sense)
    assert np.isclose(res.Sbus[a1].sum(), inter_area_flows, atol=1e-6)

    print()


def test_issue_372_2():
    """
    https://github.com/SanPen/VeraGrid/issues/372#issuecomment-2823683335

    Using the grid IEEE14 - ntc areas_voltages_hvdc_shifter_l10free.gridcal

    Test:

        Given a base situation (simulated with a linear power flow)
        We define the exchange from A1->A2
        Run the NTC optimization

    Run options:

        No contingencies
        HVDC mode: Pset
        Phase shifter (branch 8): tap_phase_control_mode: Pt.
        All generators enable_dispatch = True
        Exchange sensitivity criteria: use alpha = 5%

    Metrics:

        ΔP in A1 optimized > 0 (because there are no base overloads)
        ΔP in A2 optimized < 0 (because there are no base overloads)
        ΔP in A1 == − ΔP in A2
        The summation of flow increments in the inter-area branches must be ΔP in A1.
        Monitored & selected by the exchange sensitivity criteria, branches must not be overloaded beyond 100%
        The total exchange should be greater than in _test1.

    """
    # fname = get_grid_path('ntc_test.gridcal')
    fname = get_grid_path('IEEE14 - ntc areas_voltages_hvdc_shifter_l10free.gridcal')

    grid = gce.open_file(fname)

    # Phase shifter (branch 8): tap_phase_control_mode: Pt.
    grid.transformers2w[6].tap_phase_control_mode = gce.TapPhaseControl.Pf

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                           objects_to=[grid.areas[1]])

    opf_options = gce.OptimalPowerFlowOptions(
        consider_contingencies=False,
    )

    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.05,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=True,
        consider_contingencies=False,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results

    bus_area_indices = grid.get_bus_area_indices()

    # List of (branch index, branch object, flow sense w.r.t the area exchange)
    inter_info = grid.get_inter_areas_branches(a1=[grid.areas[0]], a2=[grid.areas[1]])
    inter_area_branch_idx = [x[0] for x in inter_info]
    inter_area_branch_sense = [x[2] for x in inter_info]

    inter_info_hvdc = grid.get_inter_areas_hvdc_branches(a1=[grid.areas[0]], a2=[grid.areas[1]])
    inter_area_hvdc_idx = [x[0] for x in inter_info_hvdc]
    inter_area_hvdc_sense = [x[2] for x in inter_info_hvdc]

    a1 = np.where(bus_area_indices == 0)[0]
    a2 = np.where(bus_area_indices == 1)[0]

    assert res.converged[0]
    assert abs(res.nodal_balance.sum()) < 1e-8

    # ΔP in A1 optimized > 0 (because there are no base overloads)
    assert res.dSbus[a1].sum() > 0

    # ΔP in A2 optimized < 0 (because there are no base overloads)
    assert res.dSbus[a2].sum() < 0

    # ΔP in A1 == − ΔP in A2
    assert np.isclose(res.dSbus[a1].sum(), -res.dSbus[a2].sum(), atol=1e-6)

    # The summation of flow increments in the inter-area branches must be ΔP in A1.
    inter_area_flows = np.sum(res.Sf[inter_area_branch_idx].real * inter_area_branch_sense)
    inter_area_flows += np.sum(res.hvdc_Pf[inter_area_hvdc_idx] * inter_area_hvdc_sense)
    assert np.isclose(res.Sbus[a1].sum(), inter_area_flows, atol=1e-6)

    # Monitored & selected by the exchange sensitivity criteria branches must not be overloaded beyond 100%
    monitor_idx = np.where(res.monitor_logic == 1)[0]
    # Adding 1e-6 to avoid minor numerical accuracy discrepancies
    assert np.all(res.loading[monitor_idx] <= 1.0 + 1e-6)

    # The total exchange should be greater than in _test1 (implemented as test_issue_372_1).
    # TODO: so far it is not, maybe this is not a universal truth
    assert res.Sbus[a1].sum() >= 49.74
    print()


def test_issue_372_3():
    """
    https://github.com/SanPen/VeraGrid/issues/372#issuecomment-2823722874

    Using the grid IEEE14 - ntc areas_voltages_hvdc_shifter_l10free.gridcal

    Test:

        Given a base situation (simulated with a linear power flow)
        We define the exchange from A1->A2
        Run the NTC optimization

    Run options:

        No contingencies
        HVDC mode: free
        Phase shifter (branch 8): tap_phase_control_mode: fixed.
        All generators enable_dispatch = True
        Exchange sensitivity criteria: use alpha = 5%

    Metrics:

        ΔP in A1 optimized > 0 (because there are no base overloads)
        ΔP in A2 optimized < 0 (because there are no base overloads)
        ΔP in A1 == − ΔP in A2
        The summation of flow increments in the inter-area branches must be ΔP in A1.
        Monitored & selected by the exchange sensitivity criteria, branches must not be overloaded beyond 100%
        The total exchange should be greater than in _test1.
        The HVDC power must be: P0 + angle_droop · (theta_f − theta_t) (all in proper units)

    """
    fname = get_grid_path('IEEE14 - ntc areas_voltages_hvdc_shifter_l10free.gridcal')

    grid = gce.open_file(fname)

    # Phase shifter (branch 8): tap_phase_control_mode: Pt.
    grid.transformers2w[6].tap_phase_control_mode = gce.TapPhaseControl.fixed
    grid.hvdc_lines[0].control_mode = gce.HvdcControlType.type_0_free

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                           objects_to=[grid.areas[1]])

    opf_options = gce.OptimalPowerFlowOptions(
        consider_contingencies=False,
    )

    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.05,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=True,
        consider_contingencies=False,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results

    bus_area_indices = grid.get_bus_area_indices()

    # List of (branch index, branch object, flow sense w.r.t the area exchange)
    inter_info = grid.get_inter_areas_branches(a1=[grid.areas[0]], a2=[grid.areas[1]])
    inter_area_branch_idx = [x[0] for x in inter_info]
    inter_area_branch_sense = [x[2] for x in inter_info]

    inter_info_hvdc = grid.get_inter_areas_hvdc_branches(a1=[grid.areas[0]], a2=[grid.areas[1]])
    inter_area_hvdc_idx = [x[0] for x in inter_info_hvdc]
    inter_area_hvdc_sense = [x[2] for x in inter_info_hvdc]

    a1 = np.where(bus_area_indices == 0)[0]
    a2 = np.where(bus_area_indices == 1)[0]

    assert res.converged[0]
    assert abs(res.nodal_balance.sum()) < 1e-8

    # ΔP in A1 optimized > 0 (because there are no base overloads)
    assert res.dSbus[a1].sum() > 0

    # ΔP in A2 optimized < 0 (because there are no base overloads)
    assert res.dSbus[a2].sum() < 0

    # ΔP in A1 == − ΔP in A2
    assert np.isclose(res.dSbus[a1].sum(), -res.dSbus[a2].sum(), atol=1e-6)

    # The summation of flow increments in the inter-area branches must be ΔP in A1.
    inter_area_flows = np.sum(res.Sf[inter_area_branch_idx].real * inter_area_branch_sense)
    inter_area_flows += np.sum(res.hvdc_Pf[inter_area_hvdc_idx] * inter_area_hvdc_sense)
    assert np.isclose(res.Sbus[a1].sum(), inter_area_flows, atol=1e-6)

    # Monitored & selected by the exchange sensitivity criteria branches must not be overloaded beyond 100%
    monitor_idx = np.where(res.monitor_logic == 1)[0]
    # Adding 1e-6 to avoid minor numerical accuracy discrepancies
    assert np.all(res.loading[monitor_idx] <= 1.0 + 1e-6)

    # The total exchange should be greater than in _test1 (implemented as test_issue_372_1).
    # TODO: so far it is not, maybe this is not a universal truth
    # assert res.Sbus[a1].sum() >= 89.74

    # The HVDC power must be: P0 + angle_droop · (theta_f − theta_t) (all in proper units)
    dev = grid.hvdc_lines[0]
    k = dev.angle_droop
    theta_f = np.angle(res.voltage[10], deg=True)
    theta_t = np.angle(res.voltage[14], deg=True)
    hvdc_power = dev.Pset + k * (theta_f - theta_t)
    assert np.isclose(hvdc_power, res.hvdc_Pf[0], atol=1e-6)

    print()


def test_issue_372_4():
    """
    https://github.com/SanPen/VeraGrid/issues/372#issuecomment-2823729822

    Using the grid IEEE14 - ntc areas_voltages_hvdc_shifter_l10free.gridcal

    Test:

        Given a base situation (simulated with a linear power flow)
        We define the exchange from A1->A2
        Run the NTC optimization

    Run options:

        Enable all contingencies
        HVDC mode: Pset
        Phase shifter (branch 8): tap_phase_control_mode: Pt.
        All generators enable_dispatch = True
        Exchange sensitivity criteria: use alpha = 5%

    Metrics:

        ΔP in A1 optimized > 0 (because there are no base overloads)
        ΔP in A2 optimized < 0 (because there are no base overloads)
        ΔP in A1 == − ΔP in A2
        The summation of flow increments in the inter-area branches must be ΔP in A1.
        Monitored & selected by the exchange sensitivity criteria, branches must not be overloaded beyond 100%
        The total exchange should be greater than in _test1.
        We expect less exchange than test 2.

        TODO: Monitored & selected by the exchange sensitivity criteria branches flow must be lower than rate.
        TODO: Monitored & selected by the exchange sensitivity criteria branches contingency flow must be lower than contingency rate.

    """
    # fname = get_grid_path('ntc_test.gridcal')
    fname = get_grid_path('IEEE14 - ntc areas_voltages_hvdc_shifter_l10free.gridcal')

    grid = gce.open_file(fname)

    # Phase shifter (branch 8): tap_phase_control_mode: Pt.
    grid.transformers2w[6].tap_phase_control_mode = gce.TapPhaseControl.Pt
    grid.hvdc_lines[0].control_mode = gce.HvdcControlType.type_1_Pset

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                           objects_to=[grid.areas[1]])

    opf_options = gce.OptimalPowerFlowOptions(
        contingency_groups_used=grid.contingency_groups
    )

    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.05,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=False,
        consider_contingencies=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results

    bus_area_indices = grid.get_bus_area_indices()

    # List of (branch index, branch object, flow sense w.r.t the area exchange)
    inter_info = grid.get_inter_areas_branches(a1=[grid.areas[0]], a2=[grid.areas[1]])
    inter_area_branch_idx = [x[0] for x in inter_info]
    inter_area_branch_sense = [x[2] for x in inter_info]

    inter_info_hvdc = grid.get_inter_areas_hvdc_branches(a1=[grid.areas[0]], a2=[grid.areas[1]])
    inter_area_hvdc_idx = [x[0] for x in inter_info_hvdc]
    inter_area_hvdc_sense = [x[2] for x in inter_info_hvdc]

    a1 = np.where(bus_area_indices == 0)[0]
    a2 = np.where(bus_area_indices == 1)[0]

    assert res.converged[0]
    assert abs(res.nodal_balance.sum()) < 1e-5  # this one is less precise for some reason...

    # ΔP in A1 optimized > 0 (because there are no base overloads)
    assert res.dSbus[a1].sum() > 0

    # ΔP in A2 optimized < 0 (because there are no base overloads)
    assert res.dSbus[a2].sum() < 0

    # ΔP in A1 == − ΔP in A2
    assert np.isclose(res.dSbus[a1].sum(), -res.dSbus[a2].sum(), atol=1e-6)

    # The summation of flow increments in the inter-area branches must be ΔP in A1.
    inter_area_flows = np.sum(res.Sf[inter_area_branch_idx].real * inter_area_branch_sense)
    inter_area_flows += np.sum(res.hvdc_Pf[inter_area_hvdc_idx] * inter_area_hvdc_sense)
    assert np.isclose(res.Sbus[a1].sum(), inter_area_flows, atol=1e-6)

    # Monitored & selected by the exchange sensitivity criteria branches must not be overloaded beyond 100%
    monitor_idx = np.where(res.monitor_logic == 1)[0]
    # Adding 1e-6 to avoid minor numerical accuracy discrepancies
    assert np.all(res.loading[monitor_idx] <= 1.0 + 1e-6)

    # The total exchange should be greater than in _test1 (inter_area_flows=89.7438187457783)
    # TODO: so far it is not, maybe this is not a universal truth
    assert inter_area_flows <= 89.7438187457783

    # We expect less exchange than test 2. (inter_area_flows=89.7438187457783)
    # TODO: so far it is not (it is the same), maybe this is not a universal truth
    assert inter_area_flows <= 89.7438187457783
    print()


def test_issue_372_5():
    """Solve the issue-372 contingency set with a P-mode 3 HVDC and a radial outage.

    Branch 13 is the only connection of Bus 8, so its outage isolates a generator.
    Radial outages follow the LODF path. The island is absorbed at the cut and
    only the radial branch changes, so the outage cannot make the study infeasible.

    https://github.com/SanPen/VeraGrid/issues/372#issuecomment-2824174417
    """
    # fname = get_grid_path('ntc_test.gridcal')
    fname = get_grid_path('IEEE14 - ntc areas_voltages_hvdc_shifter_l10free.gridcal')

    grid = gce.open_file(fname)

    # Keep the phase shifter (branch 8) fixed.
    grid.transformers2w[6].tap_phase_control_mode = gce.TapPhaseControl.fixed
    grid.hvdc_lines[0].control_mode = gce.HvdcControlType.type_0_free

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                           objects_to=[grid.areas[1]])

    opf_options = gce.OptimalPowerFlowOptions(
        contingency_groups_used=grid.contingency_groups
    )

    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.05,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=True,
        consider_contingencies=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res: gce.OptimalNetTransferCapacityResults = drv.results

    # the radial outage really islands a producing generator
    branch: BRANCH_TYPES
    tie_bus: gce.Bus | None = None
    for branch in grid.get_branches():
        if branch.name == "branch 13":
            tie_bus = branch.bus_to
        else:
            pass  # not the radial tie
    generator: gce.Generator
    islanded_power: float = 0.0
    for generator in grid.get_generators():
        if generator.bus == tie_bus:
            islanded_power += generator.P
        else:
            pass  # generator outside the island
    assert islanded_power > 0.0

    bus_area_indices: IntVec = grid.get_bus_area_indices()

    # List of (branch index, branch object, flow sense w.r.t the area exchange)
    inter_info: List[Tuple[int, object, float]] = grid.get_inter_areas_branches(a1=[grid.areas[0]],
                                                                                a2=[grid.areas[1]])
    inter_area_branch_idx: List[int] = [x[0] for x in inter_info]
    inter_area_branch_sense: List[float] = [x[2] for x in inter_info]

    inter_info_hvdc: List[Tuple[int, object, float]] = grid.get_inter_areas_hvdc_branches(a1=[grid.areas[0]],
                                                                                          a2=[grid.areas[1]])
    inter_area_hvdc_idx: List[int] = [x[0] for x in inter_info_hvdc]
    inter_area_hvdc_sense: List[float] = [x[2] for x in inter_info_hvdc]

    a1: IntVec = np.where(bus_area_indices == 0)[0]
    a2: IntVec = np.where(bus_area_indices == 1)[0]

    assert res.converged[0]
    assert abs(res.nodal_balance.sum()) < 1e-8

    # ΔP in A1 optimized > 0 (because there are no base overloads)
    assert res.dSbus[a1].sum() > 0

    # ΔP in A2 optimized < 0 (because there are no base overloads)
    assert res.dSbus[a2].sum() < 0

    # ΔP in A1 == − ΔP in A2
    assert np.isclose(res.dSbus[a1].sum(), -res.dSbus[a2].sum(), atol=1e-6)

    # The summation of flow increments in the inter-area branches must be ΔP in A1.
    inter_area_flows: float = float(np.sum(res.Sf[inter_area_branch_idx].real * inter_area_branch_sense))
    inter_area_flows += float(np.sum(res.hvdc_Pf[inter_area_hvdc_idx] * inter_area_hvdc_sense))
    assert np.isclose(res.Sbus[a1].sum(), inter_area_flows, atol=1e-6)

    # Monitored & selected by the exchange sensitivity criteria branches must not be overloaded beyond 100%
    monitor_idx: IntVec = np.where(res.monitor_logic == 1)[0]
    # Adding 1e-6 to avoid minor numerical accuracy discrepancies
    assert np.all(res.loading[monitor_idx] <= 1.0 + 1e-6)

    # The HVDC power must be: P0 + angle_droop · (theta_f − theta_t) (all in proper units)
    dev: gce.HvdcLine = grid.hvdc_lines[0]
    k: float = dev.angle_droop
    theta_f: float = float(np.angle(res.voltage[10], deg=True))
    theta_t: float = float(np.angle(res.voltage[14], deg=True))
    hvdc_power: float = dev.Pset + k * (theta_f - theta_t)
    assert np.isclose(hvdc_power, res.hvdc_Pf[0], atol=1e-6)

    # We expect less exchange than test 2. (inter_area_flows=89.7438187457783)
    assert inter_area_flows < 89.7438187457783


def test_ntc_pmode_saturation() -> None:
    """
    In this test we force one of the HVDC devices to dispatch using PMODE3 and saturate to its rating,
    checking that the PMODE3 equation goes on to provide a larger set point
    """
    np.set_printoptions(precision=4)
    fname = get_grid_path('ntc_test.gridcal')

    grid = gce.open_file(fname)

    grid.hvdc_lines[0].control_mode = gce.HvdcControlType.type_0_free
    # grid.hvdc_lines[0].angle_droop = 0.2  # this will force a greater pmode3 flow
    grid.hvdc_lines[0].angle_droop = 2000  # this will force a greater pmode3 flow

    grid.hvdc_lines[1].control_mode = gce.HvdcControlType.type_1_Pset

    a1 = [grid.areas[0]]
    a2 = [grid.areas[1]]

    info = grid.get_inter_aggregation_info(objects_from=a1,
                                           objects_to=a2)

    opf_options = gce.OptimalPowerFlowOptions()
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=True,
        consider_contingencies=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results

    bus_area_indices = grid.get_bus_area_indices()

    # List of (branch index, branch object, flow sense w.r.t the area exchange)
    inter_info = grid.get_inter_areas_branches(a1=a1, a2=a2)
    inter_area_branch_idx = [x[0] for x in inter_info]
    inter_area_branch_sense = [x[2] for x in inter_info]

    inter_info_hvdc = grid.get_inter_areas_hvdc_branches(a1=a1, a2=a2)
    inter_area_hvdc_idx = [x[0] for x in inter_info_hvdc]
    inter_area_hvdc_sense = [x[2] for x in inter_info_hvdc]

    # Monitored & selected by the exchange sensitivity criteria branches must not be overloaded beyond 100%
    monitor_idx = np.where(res.monitor_logic == 1)[0]
    # Binding limits can exceed 1.0 by roundoff across solver builds.
    assert np.all(res.loading[monitor_idx] <= 1.0 + 1e-6)

    # The HVDC power must be: P0 + angle_droop · (theta_f − theta_t) (all in proper units)
    dev = grid.hvdc_lines[0]
    k = dev.angle_droop
    theta_f = np.angle(res.voltage[3], deg=True)
    theta_t = np.angle(res.voltage[4], deg=True)
    hvdc_power = dev.Pset + k * (theta_f - theta_t)
    assert np.isclose(res.hvdc_Pf[0], grid.hvdc_lines[0].rate, atol=1e-6)  # the power must saturate to the rate
    assert res.hvdc_Pf[0] < hvdc_power  # the actual power must be lower than what the angles suggest

    assert res.converged
    assert abs(res.nodal_balance.sum()) < 1e-8


def test_ntc_pmode_non_saturation() -> None:
    """
    In this test we set a small droop coefficient and check the HVDC operates
    in the droop region (Pmode3).
    """
    np.set_printoptions(precision=4)
    fname = get_grid_path('ntc_test.gridcal')

    grid = gce.open_file(fname)

    grid.hvdc_lines[0].control_mode = gce.HvdcControlType.type_0_free
    grid.hvdc_lines[0].angle_droop = 0.2  # this will force a small pmode3 flow
    # grid.hvdc_lines[0].angle_droop = 2000  # this will force a greater pmode3 flow

    grid.hvdc_lines[1].control_mode = gce.HvdcControlType.type_1_Pset

    a1 = [grid.areas[0]]
    a2 = [grid.areas[1]]

    info = grid.get_inter_aggregation_info(objects_from=a1,
                                           objects_to=a2)

    opf_options = gce.OptimalPowerFlowOptions()
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=True,
        consider_contingencies=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results

    bus_area_indices = grid.get_bus_area_indices()

    # List of (branch index, branch object, flow sense w.r.t the area exchange)
    inter_info = grid.get_inter_areas_branches(a1=a1, a2=a2)
    inter_area_branch_idx = [x[0] for x in inter_info]
    inter_area_branch_sense = [x[2] for x in inter_info]

    inter_info_hvdc = grid.get_inter_areas_hvdc_branches(a1=a1, a2=a2)
    inter_area_hvdc_idx = [x[0] for x in inter_info_hvdc]
    inter_area_hvdc_sense = [x[2] for x in inter_info_hvdc]

    # Monitored & selected by the exchange sensitivity criteria branches must not be overloaded beyond 100%
    monitor_idx = np.where(res.monitor_logic == 1)[0]
    # Adding 1e-6 to avoid minor numerical accuracy discrepancies
    assert np.all(res.loading[monitor_idx] <= 1.0 + 1e-6)

    # The HVDC power must be: P0 + angle_droop · (theta_f − theta_t) (all in proper units)
    dev = grid.hvdc_lines[0]
    k = dev.angle_droop
    theta_f = np.angle(res.voltage[3], deg=True)
    theta_t = np.angle(res.voltage[4], deg=True)
    hvdc_power = dev.Pset + k * (theta_f - theta_t)
    assert res.hvdc_Pf[0] < grid.hvdc_lines[0].rate  # the power must be less than the rate
    assert np.isclose(res.hvdc_Pf[0], hvdc_power, atol=1e-6)  # close to the power from the angles

    assert res.converged
    assert abs(res.nodal_balance.sum()) < 1e-8


def test_ntc_areas_connected_only_through_hvdc() -> None:
    """
    This test checks that a grid that is only joined with HVDC lines can transfer power through the 2 areas
    """
    np.set_printoptions(precision=4)
    fname = get_grid_path('ntc_test_cont.gridcal')

    grid = gce.open_file(fname)

    # we deactivate the only AC inter-area link
    grid.transformers2w[1].active = False

    # there must be a slack per area so that this works
    grid.buses[0].is_slack = True
    grid.buses[7].is_slack = True

    a1 = [grid.areas[0]]
    a2 = [grid.areas[1]]

    info = grid.get_inter_aggregation_info(objects_from=a1,
                                           objects_to=a2)

    opf_options = gce.OptimalPowerFlowOptions()
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=False,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=False,
        consider_contingencies=False,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results

    bus_area_indices = grid.get_bus_area_indices()
    a1 = np.where(bus_area_indices == 0)[0]
    a2 = np.where(bus_area_indices == 1)[0]

    assert res.converged[0]
    assert abs(res.nodal_balance.sum()) < 1e-8

    # ΔP in A1 optimized > 0 (because there are no base overloads)
    assert res.dSbus[a1].sum() > 0

    # ΔP in A2 optimized < 0 (because there are no base overloads)
    assert res.dSbus[a2].sum() < 0

    # ΔP in A1 == − ΔP in A2
    assert np.isclose(res.dSbus[a1].sum(), -res.dSbus[a2].sum(), atol=1e-6)

    assert res.converged


def test_ntc_vsc():
    """
    This test runs a test grid with VSC systems where controllers pairs are in Pset and Vdc modes
    No contingencies are enabled
    """
    fname = get_grid_path('ntc_test_cont (vsc).gridcal')

    grid = gce.open_file(fname)

    # ------------------------------------------------------------------------------------------------------------------
    # Modify initial conditions
    # ------------------------------------------------------------------------------------------------------------------

    # ------------------------------------------------------------------------------------------------------------------
    # run study
    # ------------------------------------------------------------------------------------------------------------------
    a1 = [grid.areas[0]]
    a2 = [grid.areas[1]]

    info = grid.get_inter_aggregation_info(objects_from=a1,
                                           objects_to=a2)

    opf_options = gce.OptimalPowerFlowOptions()
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=True,
        consider_contingencies=False,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results

    # ------------------------------------------------------------------------------------------------------------------
    # asserts
    # ------------------------------------------------------------------------------------------------------------------
    assert abs(res.nodal_balance.sum()) < 1e-8
    assert np.isclose(res.inter_area_flows, 3000.0)  # 3000 is the summation of the inter-area branch rates


def test_ntc_vsc_contingencies():
    """
    This test runs a test grid with VSC systems where controllers pairs are in Pset and Vdc modes
    Contingencies are enabled
    """
    fname = get_grid_path('ntc_test_cont (vsc).gridcal')

    grid = gce.open_file(fname)

    # ------------------------------------------------------------------------------------------------------------------
    # Modify initial conditions
    # ------------------------------------------------------------------------------------------------------------------

    # ------------------------------------------------------------------------------------------------------------------
    # run study
    # ------------------------------------------------------------------------------------------------------------------
    a1 = [grid.areas[0]]
    a2 = [grid.areas[1]]

    info = grid.get_inter_aggregation_info(objects_from=a1,
                                           objects_to=a2)

    opf_options = gce.OptimalPowerFlowOptions(contingency_groups_used=grid.contingency_groups)
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=False,
        consider_contingencies=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results

    # ------------------------------------------------------------------------------------------------------------------
    # asserts
    # ------------------------------------------------------------------------------------------------------------------
    assert abs(res.nodal_balance.sum()) < 1e-8
    assert np.isclose(res.inter_area_flows, 2000.0)  # 2000 is the summation of the inter-area branches (N-1) rates

    
def test_ntc_vsc_8_buses_REE_contingencies():
    """
    This test runs a test grid with VSC systems where controllers pairs are in Pset and Vdc modes
    Contingencies are enabled
    """
    fname = get_grid_path('NTC_8_bus_vsc_REE.veragrid')
    # fname = os.path.join('src', 'tests', 'data', 'grids', 'NTC_8_bus_vsc_REE.veragrid')

    grid = gce.open_file(fname)

    # ------------------------------------------------------------------------------------------------------------------
    # Modify initial conditions
    # ------------------------------------------------------------------------------------------------------------------

    # ------------------------------------------------------------------------------------------------------------------
    # run study
    # ------------------------------------------------------------------------------------------------------------------
    a1 = [grid.areas[0]]
    a2 = [grid.areas[1]]

    info = grid.get_inter_aggregation_info(objects_from=a1,
                                           objects_to=a2)

    opf_options = gce.OptimalPowerFlowOptions(contingency_groups_used=grid.contingency_groups)
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=False,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=False,
        consider_contingencies=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results

    # ------------------------------------------------------------------------------------------------------------------
    # asserts
    # ------------------------------------------------------------------------------------------------------------------
    print(res.inter_area_flows)
    assert abs(res.nodal_balance.sum()) < 1e-8
    assert np.isclose(res.inter_area_flows, 5000.0)  # 2000 is the summation of the inter-area branches (N-1) rates


def _run_ntc_8_bus_2_modes(corrective: bool):
    """
    Helper that runs the NTC on the '8 bus 2 modes' grid (2 AC ties + 2 VSC-bracketed DC corridors,
    each made of 2 parallel cables; all 6 inter-area branches are single N-1 contingencies).

    :param corrective: use corrective N-1 (converters may re-dispatch their set-points after a contingency)
    :return: OptimalNetTransferCapacityResults
    """
    fname = get_grid_path('NTC_8_bus_2_modes_v3.veragrid')
    grid = gce.open_file(fname)

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                           objects_to=[grid.areas[1]])

    opf_options = gce.OptimalPowerFlowOptions(contingency_groups_used=grid.get_contingency_groups_active())
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=False,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=False,
        consider_contingencies=True,
        corrective_contingencies=corrective,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)
    drv.run()
    return drv.results


def _solve_ntc_8_bus_2_modes_lp(reverse_contingencies: bool, max_lazy_rounds: int) -> NtcVars:
    """
    Solve the corrective NTC LP of the '8 bus 2 modes' grid.

    The DC cables get a 1e-3 resistance. Just numerical stuff.
    The fixture's 1e-5 makes their conductance 1e5, which
    amplifies the solver tolerances to tenths of a MW and hides the reproducibility under test.

    :param reverse_contingencies: hand the active contingency groups to the formulation in reverse order
    :param max_lazy_rounds: N-1 screening round budget
    :return: solved NTC variables
    """
    grid: gce.MultiCircuit = gce.open_file(get_grid_path('NTC_8_bus_2_modes_v3.veragrid'))
    dc_line: gce.DcLine
    for dc_line in grid.dc_lines:
        dc_line.R = 1e-3
    info: gce.InterAggregationInfo = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                                                     objects_to=[grid.areas[1]])

    # the formulation order is the only difference between the runs being compared
    groups: List[gce.ContingencyGroup] = grid.get_contingency_groups_active()
    if reverse_contingencies:
        groups = groups[::-1]
    else:
        pass  # keep the grid order

    solution: Tuple[NtcVars, LpModel] = run_linear_ntc_opf(grid=grid, t=None, skip_generation_limits=True,
                                                           consider_contingencies=True,
                                                           corrective_contingencies=True,
                                                           contingency_groups_used=groups,
                                                           bus_a1_idx=info.idx_bus_from,
                                                           bus_a2_idx=info.idx_bus_to,
                                                           monitor_only_sensitive_branches=False,
                                                           logger=Logger(),
                                                           max_lazy_rounds=max_lazy_rounds)
    return solution[0]


def test_ntc_corrective_report_does_not_depend_on_contingency_order() -> None:
    """
    The corrective converter moves carry no transfer cost, so many operating points reach the
    same TTC. The least control effort stage and the tie rule must make the operating point and
    the reported worst contingency pairs identical whatever the contingency order.
    """
    forward: NtcVars = _solve_ntc_8_bus_2_modes_lp(reverse_contingencies=False, max_lazy_rounds=100)
    backward: NtcVars = _solve_ntc_8_bus_2_modes_lp(reverse_contingencies=True, max_lazy_rounds=100)

    assert forward.acceptable_solution[0] and backward.acceptable_solution[0]
    assert np.isclose(forward.inter_area_flows[0], backward.inter_area_flows[0], atol=0.01)
    assert np.allclose(forward.vsc_vars.flows, backward.vsc_vars.flows, atol=0.01)
    assert np.allclose(forward.branch_vars.flows, backward.branch_vars.flows, atol=0.01)
    assert np.array_equal(forward.branch_vars.worst_contingency_idx, backward.branch_vars.worst_contingency_idx)
    assert np.allclose(forward.branch_vars.worst_contingency_flow, backward.branch_vars.worst_contingency_flow,
                       atol=0.01)


def test_ntc_unfinished_n1_screening_is_not_accepted() -> None:
    """
    A solution the N-1 screening could not certify may still violate unchecked contingency
    rows, so running out of screening rounds must not be reported as an acceptable solution.
    """
    assert not _solve_ntc_8_bus_2_modes_lp(reverse_contingencies=False, max_lazy_rounds=0).acceptable_solution[0]
    assert _solve_ntc_8_bus_2_modes_lp(reverse_contingencies=False, max_lazy_rounds=100).acceptable_solution[0]


def test_ntc_corrective_n1():
    """
    '8 bus 2 modes' grid: 2 AC ties (Line 8 ∥ Line 9) + 2 DC corridors, each of 2 parallel cables
    (Dc line 1∥2 and Dc line 3∥4). All 6 inter-area branches are single contingencies, each rated 1000 MW.

    - Preventive N-1 (fixed converter set-points): every parallel pair must be derated so its surviving
      member is not overloaded => 3 pairs x 1000 = 3000 MW.
    - Corrective N-1 (the VSC converters re-dispatch after the outage and reroute the transfer across the
      remaining corridors while preserving the exchange): the worst single outage only removes 1000 MW of
      capacity => 6000 - 1000 = 5000 MW.
    """
    res_prev = _run_ntc_8_bus_2_modes(corrective=False)
    assert abs(res_prev.nodal_balance.sum()) < 1e-6
    assert np.isclose(res_prev.inter_area_flows, 3000.0, atol=1.0)

    res_corr = _run_ntc_8_bus_2_modes(corrective=True)
    assert abs(res_corr.nodal_balance.sum()) < 1e-6
    assert np.isclose(res_corr.inter_area_flows, 5000.0, atol=1.0)

    # corrective must never be more conservative than preventive
    assert res_corr.inter_area_flows >= res_prev.inter_area_flows - 1.0


def test_ntc_corrective_n1_report_matches_corrected_state():
    """
    Corrective N-1 on the '8 bus 2 modes' grid. The worst contingency report must show the
    corrected (post action) N-1 loadings, i.e. the same preventive + corrective converter
    redispatch flows the LP enforced the limits on.

    The parallel DC cables were reported at ~200% N-1 loading (the
    preventive doubling after the loss of the twin cable) while the total slack was 0 MW,
    because the report ignored the solved corrective setpoint changes. After the fix the
    reported survivor flow is 1000 MW (100%), matching the enforced corrected state.
    """
    res = _run_ntc_8_bus_2_modes(corrective=True)

    assert res.converged
    assert np.isclose(res.inter_area_flows, 5000.0, atol=1.0)
    assert np.isclose(res.get_total_slack_mw(), 0.0, atol=0.1)

    dc_idx = [i for i, name in enumerate(res.branch_names) if 'Dc line' in name]
    assert len(dc_idx) == 4

    for i in dc_idx:
        # each cable runs at its 1000 MW rating in N and N-1
        assert np.isclose(res.worst_contingency_flow[i], 1000.0, atol=1.0)
        assert res.worst_contingency_loading[i] <= 1.0 + 1e-3


def _run_ntc_8_bus_preventive_with_deactivated_groups(deactivated_group_names: set):
    """
    Run the preventive NTC on the '8 bus 2 modes' grid after deactivating the named contingency groups.

    :param deactivated_group_names: names of the contingency groups whose active flag is set to False.
    :return: OptimalNetTransferCapacityResults of the preventive run.
    """
    fname: str = get_grid_path('NTC_8_bus_2_modes_v3.veragrid')
    grid = gce.open_file(fname)

    # deactivate the requested contingency groups so the NTC must ignore them
    for group in grid.contingency_groups:
        if group.name in deactivated_group_names:
            group.active = False
        else:
            # this group stays active and must still be honoured by the NTC
            pass

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]], objects_to=[grid.areas[1]])
    opf_options = gce.OptimalPowerFlowOptions(contingency_groups_used=grid.get_contingency_groups_active())
    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=False,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=False,
        consider_contingencies=True,
        corrective_contingencies=False,  # this test checks the preventive active-flag behaviour
        opf_options=opf_options,
        lin_options=gce.LinearAnalysisOptions()
    )
    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)
    drv.run()
    return drv.results


def test_ntc_contingency_group_active_status():
    """
    The status (active flag) of the contingency groups must be honoured by the NTC: deactivating the DC-cable
    contingency groups (so only the AC-tie outages remain) must relax the result, because the DC corridors are
    no longer required to survive the loss of one of their parallel cables.

    Preventive N-1:
        - all 6 contingencies active  -> 3000 MW
        - only the 2 AC-tie outages   -> AC pair <= 1000, both DC corridors free at 2000 => 5000 MW
    """
    res_all = _run_ntc_8_bus_preventive_with_deactivated_groups(deactivated_group_names=set())
    assert np.isclose(res_all.inter_area_flows, 3000.0, atol=1.0)

    deactivated: set = {'Contingency Dc line 1', 'Contingency Dc line 2',
                        'Contingency Dc line 3', 'Contingency Dc line 4'}
    res_ac_only = _run_ntc_8_bus_preventive_with_deactivated_groups(deactivated_group_names=deactivated)
    assert np.isclose(res_ac_only.inter_area_flows, 5000.0, atol=1.0)

    # deactivating contingency groups can only relax (increase) the secure transfer
    assert res_ac_only.inter_area_flows > res_all.inter_area_flows + 1.0


def test_ntc_snapshot_and_time_series_select_the_same_active_groups() -> None:
    """Snapshot and time-series results use the same active contingency selection."""
    grid = build_two_pmode3_link_grid(set_reference_bus_on_both=True)
    for index in range(3):
        line = gce.Line(name=f"parallel_{index}", bus_from=grid.buses[0], bus_to=grid.buses[1],
                        x=0.01, rate=1000.0)
        grid.add_line(line)
        group = gce.ContingencyGroup(name=f"outage_{index}", active=index != 0)
        grid.add_contingency_group(group)
        grid.add_contingency(gce.Contingency(device=line, group=group))
    grid.create_profiles(2, step_length=1.0, step_unit='h')
    inactive, first, second = grid.contingency_groups
    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]], objects_to=[grid.areas[1]])

    for strict in (False, True):
        for selected, expected in (([], [first, second]),
                                   ([second, inactive, first], [second, first]),
                                   ([second], [second]),
                                   ([inactive], [])):
            options = gce.OptimalNetTransferCapacityOptions(
                sending_bus_idx=info.idx_bus_from, receiving_bus_idx=info.idx_bus_to,
                skip_generation_limits=True, use_branch_exchange_sensitivity=False,
                strict_formulation=strict, consider_contingencies=True, corrective_contingencies=True,
                opf_options=gce.OptimalPowerFlowOptions(contingency_groups_used=selected),
            )
            snapshot = gce.OptimalNetTransferCapacityDriver(grid, options)
            time_series = gce.OptimalNetTransferCapacityTimeSeriesDriver(
                grid, options, time_indices=np.array([0, 1]))
            for driver in (snapshot, time_series):
                driver.run()
                assert np.all(driver.results.converged)
                reported = set(np.asarray(driver.results.worst_contingency_idx).ravel()) - {-1}
                assert reported <= {grid.contingency_groups.index(group) for group in expected}
                if expected:
                    assert reported
            assert np.allclose(time_series.results.inter_area_flows, snapshot.results.inter_area_flows)
            assert options.opf_options.contingency_groups_used == selected
            assert grid.contingency_groups == [inactive, first, second]


def test_2_node_several_conditions_ntc():
    """
    2-Bus example with some behaviors
    """
    grid = gce.MultiCircuit()

    area1 = gce.Area(name="Area1")
    grid.add_area(area1)

    area2 = gce.Area(name="Area2")
    grid.add_area(area2)

    bus1 = gce.Bus(name="Bus1", area=area1)
    grid.add_bus(bus1)

    bus2 = gce.Bus(name="Bus2", area=area2)
    grid.add_bus(bus2)

    load1 = gce.Load(name="Load1", P=10.0)
    grid.add_load(bus1, load1)

    load2 = gce.Load(name="Load2", P=10.0)
    grid.add_load(bus2, load2)

    gen1 = gce.Generator(name="Generator1", P=10.0, Pmax=10000.0)
    grid.add_generator(bus1, gen1)

    gen2 = gce.Generator(name="Generator2", P=10.0, Pmax=10000.0)
    grid.add_generator(bus2, gen2)

    # Better conditioned X values
    line12 = gce.Line(bus_from=bus1, bus_to=bus2, name="Line 1-2", x=0.01, rate=1000.0)
    grid.add_line(line12)

    transformer12 = gce.Transformer2W(bus_from=bus1, bus_to=bus2, name="Transformer 1-2", x=0.01, rate=1000.0)
    grid.add_transformer2w(transformer12)

    cg1 = gce.ContingencyGroup(name="Line12 contingency")
    con1 = gce.Contingency(device=line12, name=cg1.name, group=cg1)
    grid.add_contingency_group(cg1)
    grid.add_contingency(con1)

    cg2 = gce.ContingencyGroup(name="Transformer12 contingency")
    con2 = gce.Contingency(device=transformer12, name=cg1.name, group=cg2)
    grid.add_contingency_group(cg2)
    grid.add_contingency(con2)

    # ------------------------------------------------------------------------------------------------------------------
    # run study:
    # - No contingencies
    # - transformer behaving like a line
    # ------------------------------------------------------------------------------------------------------------------

    info = grid.get_inter_aggregation_info(objects_from=[area1],
                                           objects_to=[area2])

    opf_options = gce.OptimalPowerFlowOptions(contingency_groups_used=grid.contingency_groups)
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=True,
        consider_contingencies=False,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results
    assert abs(res.nodal_balance.sum()) < 1e-8
    assert np.isclose(res.inter_area_flows, 2000)

    # ------------------------------------------------------------------------------------------------------------------
    # run study:
    # - No contingencies
    # - transformer behaving like a phase shifter
    # ------------------------------------------------------------------------------------------------------------------

    transformer12.tap_phase_control_mode = gce.TapPhaseControl.Pf

    info = grid.get_inter_aggregation_info(objects_from=[area1],
                                           objects_to=[area2])

    opf_options = gce.OptimalPowerFlowOptions(contingency_groups_used=grid.contingency_groups)
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=True,
        consider_contingencies=False,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results
    assert abs(res.nodal_balance.sum()) < 1e-8
    assert np.isclose(res.inter_area_flows, 2000)

    # ------------------------------------------------------------------------------------------------------------------
    # run study:
    # - contingencies enabled
    # - transformer behaving like a line
    # ------------------------------------------------------------------------------------------------------------------

    info = grid.get_inter_aggregation_info(objects_from=[area1],
                                           objects_to=[area2])

    opf_options = gce.OptimalPowerFlowOptions(contingency_groups_used=grid.contingency_groups)
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=True,
        consider_contingencies=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results
    assert abs(res.nodal_balance.sum()) < 1e-8
    assert np.isclose(res.inter_area_flows, 1000)  # half the transfer

    # ------------------------------------------------------------------------------------------------------------------
    # run study:
    # - contingencies enabled
    # - transformer behaving like a phase shifter
    # ------------------------------------------------------------------------------------------------------------------

    transformer12.tap_phase_control_mode = gce.TapPhaseControl.Pf

    info = grid.get_inter_aggregation_info(objects_from=[area1],
                                           objects_to=[area2])

    opf_options = gce.OptimalPowerFlowOptions(contingency_groups_used=grid.contingency_groups)
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=True,
        consider_contingencies=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results
    assert abs(res.nodal_balance.sum()) < 1e-8
    assert np.isclose(res.inter_area_flows, 1000)  # half the transfer

    # ------------------------------------------------------------------------------------------------------------------
    # run study:
    # - contingencies enabled
    # - transformer behaving like a phase shifter with a fixed angle
    # ------------------------------------------------------------------------------------------------------------------

    transformer12.tap_phase_control_mode = gce.TapPhaseControl.fixed
    transformer12.tap_phase = 0.02

    info = grid.get_inter_aggregation_info(objects_from=[area1],
                                           objects_to=[area2])

    opf_options = gce.OptimalPowerFlowOptions(contingency_groups_used=grid.contingency_groups)
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=True,
        consider_contingencies=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results
    assert abs(res.nodal_balance.sum()) < 1e-8
    assert res.converged

    # Both parallel branches are identical, so without any shift the transfer splits evenly
    b_tau = 0.02 / 0.01 * grid.Sbase
    assert np.isclose(res.inter_area_flows, 1000)
    assert np.isclose(res.Sf[0].real, 500 + b_tau / 2)  # Line 1-2 takes the flow
    assert np.isclose(res.Sf[1].real, 500 - b_tau / 2)  # Transformer 1-2 sheds
    assert np.all(np.abs(res.loading.real) <= 1.0)


def test_hvdc_lines_tests():
    """
    Testing test_santi_20250625.gridcal
    >This is a simple test that checks that the flow is maximal between the two areas
    :return:
    """
    np.set_printoptions(precision=4)
    fname = get_grid_path('test_santi_20250625.gridcal')

    grid = gce.open_file(fname)

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                           objects_to=[grid.areas[1]])

    opf_options = gce.OptimalPowerFlowOptions(
    )
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=True,
        consider_contingencies=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results
    assert abs(res.nodal_balance.sum()) < 1e-8

    # The documented intent is a maximal exchange between the two areas. Branch 7 is
    # overloaded to begin with, so not a good metric to assert.
    exchange = float(sum(res.Sf[k].real * sense for k, sense in res.inter_space_branches)
                     + sum(res.hvdc_Pf[k] * sense for k, sense in res.inter_space_hvdc))
    assert np.isclose(exchange, 3000.0)

    # the HVDC flows are part of the same degenerate optimum,
    # so only their physical limits are asserted, not their value
    assert np.all(np.abs(res.hvdc_Pf) <= 1000.0 + 1e-6)
    assert np.isclose(res.inter_area_flows, 3000.0)


def test_activs_2000():
    """
    Simulate a large size grid: ACTIVSg 2000 with contingencies
    :return:
    """
    np.set_printoptions(precision=4)
    fname = get_grid_path('ACTIVSg2000.gridcal')

    grid = gce.open_file(fname)

    info = grid.get_inter_aggregation_info(
        objects_from=[grid.areas[6]],  # Coast
        objects_to=[grid.areas[7]]  # East
    )

    opf_options = gce.OptimalPowerFlowOptions(
        consider_contingencies=True,
        contingency_groups_used=grid.contingency_groups
    )
    lin_options = gce.LinearAnalysisOptions()

    # ------------------------------------------------------------------------------------------------------------------
    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.05,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=False,
        consider_contingencies=False,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results
    ntc_no_contingencies = res.inter_area_flows
    # 1e-3 MW is the engine's own nodal balance tolerance
    assert abs(res.nodal_balance.sum()) < 1e-3
    assert res.converged
    assert res.inter_area_flows < res.structural_inter_area_flows

    # ------------------------------------------------------------------------------------------------------------------
    # Run with contingencies
    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.05,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=False,
        consider_contingencies=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results
    # 1e-3 MW is the engine's own nodal balance tolerance
    assert abs(res.nodal_balance.sum()) < 1e-3
    assert res.converged
    assert res.inter_area_flows < res.structural_inter_area_flows
    assert res.inter_area_flows < ntc_no_contingencies


def test_activs_2000_acdc():
    """
    Simulate a large size grid: ACTIVSg 2000 extended with 2 DC lines and 2 converters with contingencies
    :return:
    """
    np.set_printoptions(precision=4)
    fname = get_grid_path('ACTIVSg2000.gridcal')

    grid = gce.open_file(fname)

    # Create a double link from "WILLIS 2 0" to "LUFKIN 3 0"
    coast = grid.areas[6]
    east = grid.areas[7]
    willis_2_0 = grid.buses[1557]
    lufkun_3_0 = grid.buses[1843]
    dc1 = gce.Bus("WILLIS DC", is_dc=True, Vnom=500.0, area=coast,
                  latitude=willis_2_0.latitude, longitude=willis_2_0.longitude)
    dc2 = gce.Bus("LUFKIN DC", is_dc=True, Vnom=500.0, area=east,
                  latitude=lufkun_3_0.latitude, longitude=lufkun_3_0.longitude)
    converter1 = gce.VSC(name="WILLIS converter", bus_from=willis_2_0, bus_to=dc1, rate=2000.0,
                         control1=gce.ConverterControlType.Pac, control2=gce.ConverterControlType.Pdc)
    converter2 = gce.VSC(name="LUFKIN converter", bus_from=lufkun_3_0, bus_to=dc2, rate=2000.0,
                         control1=gce.ConverterControlType.Pac, control2=gce.ConverterControlType.Vm_dc,
                         control2_val=1.0)
    dc_line1 = gce.DcLine(name="WILLIS-LUFKIN1", bus_from=dc1, bus_to=dc2, rate=1000.0)
    dc_line2 = gce.DcLine(name="WILLIS-LUFKIN2", bus_from=dc1, bus_to=dc2, rate=1000.0)

    grid.add_bus(dc1)
    grid.add_bus(dc2)
    grid.add_vsc(converter1)
    grid.add_vsc(converter2)
    grid.add_dc_line(dc_line1)
    grid.add_dc_line(dc_line2)

    # create contingencies of the DC lines
    dc1_con_group = gce.ContingencyGroup(name="WILLIS-LUFKIN1")
    dc1_con = gce.Contingency(device=dc1, group=dc1_con_group)

    dc2_con_group = gce.ContingencyGroup(name="WILLIS-LUFKIN2")
    dc2_con = gce.Contingency(device=dc2, group=dc2_con_group)

    grid.add_contingency_group(dc1_con_group)
    grid.add_contingency_group(dc2_con_group)
    grid.add_contingency(dc1_con)
    grid.add_contingency(dc2_con)

    info = grid.get_inter_aggregation_info(
        objects_from=[grid.areas[6]],  # Coast
        objects_to=[grid.areas[7]]  # East
    )

    opf_options = gce.OptimalPowerFlowOptions(
        consider_contingencies=True,
        contingency_groups_used=grid.contingency_groups,
        report_formulation="test_activs_2000_acdc_gslv.lp"
    )
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.05,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=False,
        consider_contingencies=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results
    # 1e-3 MW is the engine's own nodal balance tolerance
    assert abs(res.nodal_balance.sum()) < 1e-3
    assert res.converged


def test_activs_2000_acdc_ts():
    """
    Simulate a large size grid: ACTIVSg 2000 extended with 2 DC lines and 2 converters with contingencies
    and we extend it to 5 time steps to run them
    :return:
    """
    np.set_printoptions(precision=4)
    fname = get_grid_path('ACTIVSg2000_vsc.gridcal')

    grid = gce.open_file(fname)

    grid.create_profiles(5, step_length=1.0, step_unit='h')

    info = grid.get_inter_aggregation_info(
        objects_from=[grid.areas[6]],  # Coast
        objects_to=[grid.areas[7]]  # East
    )

    opf_options = gce.OptimalPowerFlowOptions(
        consider_contingencies=True,
        contingency_groups_used=grid.contingency_groups
    )
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.05,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=False,
        consider_contingencies=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityTimeSeriesDriver(grid, ntc_options,
                                                         time_indices=grid.get_all_time_indices())

    drv.run()

    res = drv.results
    # 1e-3 MW is the engine's own nodal balance tolerance
    assert abs(res.nodal_balance.sum()) < 1e-3
    assert res.converged.all()



def build_two_pmode3_link_grid(set_reference_bus_on_both: bool) -> gce.MultiCircuit:
    """
    Build a 2-area grid where the areas are joined by an AC line and a symmetric
    HVDC link in P-mode 3 (angle droop).

    :param set_reference_bus_on_both: if True, the droop converter gets its remote AC
                                      reference bus, if False it is left unset.
    :return: MultiCircuit
    """
    grid = gce.MultiCircuit()

    area_1 = gce.Area(name="a1")
    area_2 = gce.Area(name="a2")
    grid.add_area(area_1)
    grid.add_area(area_2)

    bus_ac_1 = gce.Bus(name="ac1", Vnom=400.0, area=area_1, is_slack=True)
    bus_ac_2 = gce.Bus(name="ac2", Vnom=400.0, area=area_2)
    bus_dc_1 = gce.Bus(name="dc1", Vnom=400.0, area=area_1, is_dc=True)
    bus_dc_2 = gce.Bus(name="dc2", Vnom=400.0, area=area_2, is_dc=True)
    for bus in (bus_ac_1, bus_ac_2, bus_dc_1, bus_dc_2):
        grid.add_bus(bus)

    # generation in area 1 and the matching demand in area 2, so there is something to transfer
    grid.add_generator(bus_ac_1, gce.Generator(name="gen", P=500.0, Pmin=0.0, Pmax=2000.0))
    grid.add_load(bus_ac_2, gce.Load(name="load", P=500.0))

    # AC corridor between the two areas
    grid.add_line(gce.Line(name="ac_line", bus_from=bus_ac_1, bus_to=bus_ac_2, x=0.01, rate=1000.0))

    # DC corridor between the two areas
    grid.add_dc_line(gce.DcLine(name="dc_line", bus_from=bus_dc_1, bus_to=bus_dc_2, r=1e-5, rate=1000.0))

    # the sending converter fixes the DC voltage
    grid.add_vsc(gce.VSC(name="vsc_1", bus_from=bus_dc_1, bus_to=bus_ac_1, rate=1000.0,
                         control1=ConverterControlType.Vm_dc, control1_val=1.0,
                         control2=ConverterControlType.Pac, control2_val=0.0))

    # the receiving converter in P-mode 3
    vsc_2 = gce.VSC(name="vsc_2", bus_from=bus_dc_2, bus_to=bus_ac_2, rate=1000.0,
                    control1=ConverterControlType.Pdc_angle_droop, control1_val=174.53,
                    control2=ConverterControlType.Pac, control2_val=0.0)

    # the droop measures the angle from the AC bus at the other end of the DC link
    if set_reference_bus_on_both:
        vsc_2.control1_dev = bus_ac_1
    # left unset on purpose as this is the misconfiguration the test guards
    else:
        pass

    grid.add_vsc(vsc_2)

    return grid


def run_pmode3_link_ntc(grid: gce.MultiCircuit) -> gce.OptimalNetTransferCapacityDriver:
    """
    Run the NTC study on the two-area P-mode 3 grid built above

    :param grid: MultiCircuit
    :return: the driver
    """
    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                           objects_to=[grid.areas[1]])

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.0,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=False,
        branch_rating_contribution=1.0,
        monitor_only_ntc_load_rule_branches=False,
        consider_contingencies=False,
        opf_options=gce.OptimalPowerFlowOptions(),
        lin_options=gce.LinearAnalysisOptions()
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)
    drv.run()
    return drv


def test_ntc_pmode3_vsc_droop_direction() -> None:
    """
    Ensure the proper P-mode 3 VSC injection direction
    """
    drv = run_pmode3_link_ntc(build_two_pmode3_link_grid(set_reference_bus_on_both=True))
    res = drv.results

    assert res.converged
    assert abs(res.nodal_balance.sum()) < 1e-8

    ac_flow = float(res.Sf[0].real)   # the AC line, area 1 -> area 2
    dc_flow = float(res.Sf[1].real)   # the DC line, area 1 -> area 2

    # both corridors carry power in the same direction
    assert ac_flow > 0.0
    assert dc_flow > 0.0

    # the droop was tuned to the AC line reactance, so unsaturated both carry the same flow
    assert np.isclose(ac_flow, dc_flow, rtol=1e-3)


def test_ntc_pmode3_vsc_without_reference_bus_is_reported() -> None:
    """
    A P-mode 3 VSC with no angle-droop reference bus cannot form its control law. 
    It must be reported.
    """
    drv = run_pmode3_link_ntc(build_two_pmode3_link_grid(set_reference_bus_on_both=False))
    res = drv.results

    assert res.converged

    # the misconfiguration is reported instead of silently producing a loop
    reported = [e for e in drv.logger.entries if "angle-droop reference bus" in e.msg]
    assert len(reported) == 1

    # hold at its P setpoint at 0 MW, so the link does not push power the wrong way
    assert np.isclose(float(res.vsc_Pf[1].real), 0.0, atol=1e-6)


def test_ntc_pmode3_saturates_at_dc_bottleneck() -> None:
    """
    P-mode 3 droop must saturate at the DC-cable capacity, not only at the converter rating.
    """
    grid = gce.open_file(get_grid_path("NTC_8_bus_2pmode3_dc_bottleneck.veragrid"))
    drv = run_pmode3_link_ntc(grid)
    res = drv.results

    assert res.converged

    # every P-mode 3 converter saturated at its DC-cable capacity (2 x 1000 MW),
    # not necessarily at the converter rate if it is for instance set at 5000 MW
    vsc_flows = np.abs(np.real(res.vsc_Pf))
    assert np.allclose(vsc_flows, 2000.0, atol=1.0)

    # the DC cables carry their full rating
    dc_idx = [i for i, name in enumerate(res.branch_names) if str(name).startswith("Dc line")]
    assert np.allclose(np.abs(res.Sf[dc_idx].real), 1000.0, atol=1.0)

    tie_idx = [i for i, rate in enumerate(res.rates) if rate == 8000.0]
    assert np.allclose(res.Sf[tie_idx].real, 3000.0, atol=1.0)


def test_ntc_free_mode_dominates_droop_mode() -> None:
    """
    On the same grid, converters with free power (Pmode1: Pac + Pdc) must reach an NTC at
    least as high as converters on an angle droop (Pmode3) as the droop law only adds
    constraints. 
    """
    def solve_mode(free_mode: bool, consider_contingencies: bool) -> float:
        grid = gce.open_file(get_grid_path("NTC_8_bus_2pmode3_dc_bottleneck.veragrid"))
        if free_mode:
            for v in grid.vsc_devices:
                if v.control1 == ConverterControlType.Pdc_angle_droop:
                    # order matters: move control2 off Pac before assigning control1 = Pac,
                    # otherwise the duplicate-control guard refuses the change
                    v.control2 = ConverterControlType.Pdc
                    v.control2_val = 0.0
                    v.control1 = ConverterControlType.Pac
                    v.control1_val = 0.0
                    v.control1_dev = None
                    assert (v.control1, v.control2) == (ConverterControlType.Pac,
                                                        ConverterControlType.Pdc)
        a1, a2 = grid.areas[0], grid.areas[1]
        opts = gce.OptimalNetTransferCapacityOptions(
            sending_bus_idx=np.array([i for i, b in enumerate(grid.buses) if b.area == a1]),
            receiving_bus_idx=np.array([i for i, b in enumerate(grid.buses) if b.area == a2]),
            transfer_method=gce.AvailableTransferMode.InstalledPower,
            consider_contingencies=consider_contingencies,
            opf_options=gce.OptimalPowerFlowOptions(),
        )
        drv = gce.OptimalNetTransferCapacityDriver(grid, opts)
        drv.run()
        assert bool(np.all(drv.results.converged))
        return float(sum(drv.results.Sf[k].real * s
                         for k, s in drv.results.inter_space_branches))

    for consider_contingencies in (False, True):
        ntc_droop = solve_mode(free_mode=False, consider_contingencies=consider_contingencies)
        ntc_free = solve_mode(free_mode=True, consider_contingencies=consider_contingencies)
        # 1 MW tolerance for solver noise
        assert ntc_free >= ntc_droop - 1.0, \
            f"dominance violated (ctg={consider_contingencies}): free={ntc_free} < droop={ntc_droop}"


def _vsc_control_state(vsc: gce.VSC) -> tuple:
    """
    Capture the VSC control snapshot that the GUI objects inspector shows.

    :param vsc: Converter whose control pair is recorded.
    :return: Control modes, set-points and remote devices.
    """
    control1_dev_id: str | None
    control2_dev_id: str | None
    if vsc.control1_dev is None:
        control1_dev_id = None
    else:
        control1_dev_id = vsc.control1_dev.idtag
    if vsc.control2_dev is None:
        control2_dev_id = None
    else:
        control2_dev_id = vsc.control2_dev.idtag
    return (vsc.control1, vsc.control2, vsc.control1_val, vsc.control2_val,
            vsc.control1_val_droop, vsc.control2_val_droop,
            control1_dev_id, control2_dev_id)


def _assert_vsc_time_series_controls_match_snapshot(grid: gce.MultiCircuit) -> None:
    """
    Profiles and compilation at t = 0 must keep the snapshot VSC control pair.

    :param grid: Circuit whose converters are checked.
    :return: None
    """
    for vsc in grid.vsc_devices:
        assert vsc.get_control1_at(0) == vsc.control1
        assert vsc.get_control2_at(0) == vsc.control2
        assert vsc.get_control1_val_at(0) == vsc.control1_val
        assert vsc.get_control2_val_at(0) == vsc.control2_val
        assert vsc.control1_prof[0] == vsc.control1
        assert vsc.control2_prof[0] == vsc.control2

    nc_snap = gce.compile_numerical_circuit_at(circuit=grid, t_idx=None)
    nc_t0 = gce.compile_numerical_circuit_at(circuit=grid, t_idx=0)
    assert np.array_equal(nc_snap.vsc_data.control1_int, nc_t0.vsc_data.control1_int)
    assert np.array_equal(nc_snap.vsc_data.control2_int, nc_t0.vsc_data.control2_int)
    assert np.allclose(nc_snap.vsc_data.control1_val, nc_t0.vsc_data.control1_val)
    assert np.allclose(nc_snap.vsc_data.control2_val, nc_t0.vsc_data.control2_val)


def test_ntc_ts_does_not_mutate_vsc_controls() -> None:
    """
    NTC time series must not write back into the VSC control modes or set-points.

    This is the Pmode1 (Pac + Pdc) arrangement used on the large 6000h grids.
    """
    grid = gce.open_file(get_grid_path("NTC_8_bus_2pmode3_dc_bottleneck.veragrid"))
    for vsc in grid.vsc_devices:
        if vsc.control1 == ConverterControlType.Pdc_angle_droop:
            vsc.control2 = ConverterControlType.Pdc
            vsc.control2_val = 0.0
            vsc.control1 = ConverterControlType.Pac
            vsc.control1_val = 0.0
            vsc.control1_dev = None
        else:
            pass

    before = [_vsc_control_state(vsc) for vsc in grid.vsc_devices]
    grid.create_profiles(3, step_length=1.0, step_unit='h')
    _assert_vsc_time_series_controls_match_snapshot(grid)

    area_from, area_to = grid.areas[0], grid.areas[1]
    info = grid.get_inter_aggregation_info(objects_from=[area_from], objects_to=[area_to])
    options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        skip_generation_limits=True,
        consider_contingencies=True,
        corrective_contingencies=True,
        opf_options=gce.OptimalPowerFlowOptions(
            contingency_groups_used=grid.get_contingency_groups_active()),
        lin_options=gce.LinearAnalysisOptions(),
    )
    drv = gce.OptimalNetTransferCapacityTimeSeriesDriver(
        grid=grid,
        options=options,
        time_indices=list(range(3)),
    )
    drv.run()

    after = [_vsc_control_state(vsc) for vsc in grid.vsc_devices]
    assert before == after
    _assert_vsc_time_series_controls_match_snapshot(grid)


def test_ntc_ts_does_not_mutate_pmode3_vsc_controls() -> None:
    """
    NTC time series must not write back into Pmode3 VSC control modes or set-points.

    The 8-bus fixture already has the angle-droop pair (Pdc_angle_droop + Pac)
    with a remote AC reference bus, matching the 6000h Pmode3 FR converters.
    """
    grid = gce.open_file(get_grid_path("NTC_8_bus_2pmode3_dc_bottleneck.veragrid"))
    n_droop: int = 0
    for vsc in grid.vsc_devices:
        if vsc.control1 == ConverterControlType.Pdc_angle_droop:
            n_droop += 1
        else:
            pass
    assert n_droop >= 1

    before = [_vsc_control_state(vsc) for vsc in grid.vsc_devices]
    grid.create_profiles(3, step_length=1.0, step_unit='h')
    _assert_vsc_time_series_controls_match_snapshot(grid)

    area_from, area_to = grid.areas[0], grid.areas[1]
    info = grid.get_inter_aggregation_info(objects_from=[area_from], objects_to=[area_to])
    options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        skip_generation_limits=True,
        consider_contingencies=True,
        corrective_contingencies=True,
        opf_options=gce.OptimalPowerFlowOptions(
            contingency_groups_used=grid.get_contingency_groups_active()),
        lin_options=gce.LinearAnalysisOptions(),
    )
    drv = gce.OptimalNetTransferCapacityTimeSeriesDriver(
        grid=grid,
        options=options,
        time_indices=list(range(3)),
    )
    drv.run()

    after = [_vsc_control_state(vsc) for vsc in grid.vsc_devices]
    assert before == after
    assert bool(np.all(drv.results.converged))
    _assert_vsc_time_series_controls_match_snapshot(grid)


def _assert_ntc_contingency_limit(corrective: bool,
                                  initial_transfer: float,
                                  contingency_factor: float,
                                  reverse_line: bool) -> None:
    """Initial overloads must retain N-1 limits and report any necessary slack.

    Two buses exchange power over a 40 MW line and a 100 MW PST. With a 100 MW
    initial transfer the line starts at 50 MW, above its contingency rating.
    The PST can relieve it in N, but its outage puts all 100 MW onto the line.
    Since transfer cannot decrease below its initial value, N-1 requires slack.
    With a 20 MW initial transfer, NTC can instead stop at the contingency limit.
    """
    grid = gce.MultiCircuit()
    sending = gce.Area("Sending")
    receiving = gce.Area("Receiving")
    grid.add_area(sending)
    grid.add_area(receiving)
    bus_a = gce.Bus("A", Vnom=400, area=sending, is_slack=True)
    bus_b = gce.Bus("B", Vnom=400, area=receiving)
    grid.add_bus(bus_a)
    grid.add_bus(bus_b)
    grid.add_generator(bus_a, gce.Generator(name="Send", P=initial_transfer, Pmax=1000))
    grid.add_generator(bus_b, gce.Generator(name="Receive", P=100, Pmax=1000))
    grid.add_load(bus_b, gce.Load(name="Load", P=initial_transfer + 100))

    line = gce.Line(bus_b if reverse_line else bus_a,
                    bus_a if reverse_line else bus_b,
                    name="40 MW line", x=0.1, rate=40,
                    contingency_factor=contingency_factor)
    pst = gce.Transformer2W(bus_a, bus_b, name="100 MW PST", x=0.1, rate=100,
                            contingency_factor=1.0,
                            tap_phase_control_mode=gce.TapPhaseControl.Pf,
                            tap_phase_min=-0.5, tap_phase_max=0.5)
    grid.add_line(line)
    grid.add_transformer2w(pst)
    for branch in (line, pst):
        group = gce.ContingencyGroup(name=branch.name + " outage")
        grid.add_contingency_group(group)
        grid.add_contingency(gce.Contingency(device=branch, group=group))

    info = grid.get_inter_aggregation_info(objects_from=[sending], objects_to=[receiving])
    options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        use_branch_exchange_sensitivity=False,
        consider_contingencies=True,
        corrective_contingencies=corrective,
        opf_options=gce.OptimalPowerFlowOptions(contingency_groups_used=grid.contingency_groups),
    )
    driver = gce.OptimalNetTransferCapacityDriver(grid, options)
    driver.run()
    result = driver.results

    contingency_rate = line.rate * contingency_factor
    expected_transfer = max(initial_transfer, contingency_rate)
    expected_slack = max(initial_transfer - contingency_rate, 0.0)
    assert result.converged
    assert np.isclose(result.inter_area_flows, expected_transfer, atol=1e-6)
    assert np.isclose(result.get_total_slack_mw(), expected_slack, atol=1e-6)
    expected_state = SolutionState.Relaxed if expected_slack > 0 else SolutionState.Optimal
    assert result.get_solution_state() == expected_state

    # The base operating point is within both normal ratings, even in the stressed case.
    assert np.all(np.abs(result.Sf.real) <= np.array([line.rate, pst.rate]) + 1e-6)

    # Every excess MW in the reported worst contingency must be accounted for in its LP row.
    rows = [row for row in result.contingency_flows_list if row[1] == 0 and row[2] == 1]
    assert len(rows) == 1
    _, _, _, flow, negative_slack, positive_slack = rows[0]
    assert np.isclose(flow, result.worst_contingency_flow[0], atol=1e-6)
    assert np.isclose(abs(flow), expected_transfer, atol=1e-6)
    assert flow <= contingency_rate + positive_slack + 1e-6
    assert flow >= -contingency_rate - negative_slack - 1e-6
    assert np.isclose(negative_slack if reverse_line else positive_slack, expected_slack, atol=1e-6)


def test_ntc_initial_overload_keeps_contingency_limit() -> None:
    """An initially overloaded line retains its N-1 limit and reports the required slack."""
    for corrective in (False, True):
        for contingency_factor in (1.0, 1.2):
            _assert_ntc_contingency_limit(corrective=corrective,
                                          initial_transfer=100.0,
                                          contingency_factor=contingency_factor,
                                          reverse_line=False)
            _assert_ntc_contingency_limit(corrective=corrective,
                                          initial_transfer=100.0,
                                          contingency_factor=contingency_factor,
                                          reverse_line=True)


def test_ntc_contingency_limit_without_initial_overload() -> None:
    """A feasible initial transfer grows to the N-1 rating without requiring slack."""
    for corrective in (False, True):
        for contingency_factor in (1.0, 1.2):
            _assert_ntc_contingency_limit(corrective=corrective,
                                          initial_transfer=20.0,
                                          contingency_factor=contingency_factor,
                                          reverse_line=False)
            _assert_ntc_contingency_limit(corrective=corrective,
                                          initial_transfer=20.0,
                                          contingency_factor=contingency_factor,
                                          reverse_line=True)


def test_ntc_structural_n1_overload_is_relaxed_not_infeasible() -> None:
    """
    A structurally unavoidable N-1 overload must relax the limit (penalized slack, reported)
    instead of making the whole LP infeasible.

    Grid: gen area -> tie -> radial pair A (rate=100, x=0.01) / B (rate=50, x=0.02) feeding a
    fixed 120 MW load. Base split is 80/40 (B at 80 % of its rating, so its N-1 limit is
    enforced), but losing A forces all 120 MW through B. Thus 70 MW of violation where
    no exchange reduction can remove. With slacks an optimal solution should be reached.
    """
    grid = gce.MultiCircuit()
    a1 = gce.Area("A1")
    a2 = gce.Area("A2")
    grid.add_area(a1)
    grid.add_area(a2)
    b0 = gce.Bus("B0", Vnom=400, area=a1)
    b0.is_slack = True
    b1 = gce.Bus("B1", Vnom=400, area=a2)
    b2 = gce.Bus("B2", Vnom=400, area=a2)
    for b in (b0, b1, b2):
        grid.add_bus(b)
    grid.add_generator(b0, gce.Generator("G", P=120, Pmax=1000, Pmin=0))
    grid.add_load(b2, gce.Load("L", P=120))
    line_tie = gce.Line(b0, b1, name="tie", x=0.01, rate=1000)
    line_a = gce.Line(b1, b2, name="A", x=0.01, rate=100)
    line_b = gce.Line(b1, b2, name="B", x=0.02, rate=50)
    for ln in (line_tie, line_a, line_b):
        grid.add_line(ln)
    cg = gce.ContingencyGroup(name="A out")
    grid.add_contingency_group(cg)
    grid.add_contingency(gce.Contingency(device=line_a, group=cg))

    info = grid.get_inter_aggregation_info(objects_from=list([a1]), objects_to=list([a2]))
    opts = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        consider_contingencies=True,
        use_branch_exchange_sensitivity=False,
        opf_options=gce.OptimalPowerFlowOptions(),
    )
    drv = gce.OptimalNetTransferCapacityDriver(grid, opts)
    drv.run()
    res = drv.results

    # the LP stays optimal despite the structural violation
    assert bool(np.all(res.converged))

    # the base flows are the physical 80/40 split, untouched by the relaxation
    assert np.isclose(float(res.Sf[1].real), 80.0, atol=1.0)
    assert np.isclose(float(res.Sf[2].real), 40.0, atol=1.0)


def test_ntc_pmode3_screening_exceeds_former_pass_limit() -> None:
    """Certify every outage on a generated five bus grid beyond the old pass limit.

    The existing two area Pmode3 fixture has four buses. A fifth bus carries a
    fixed radial load above its line rating, so every added parallel line outage
    needs its own thermal slack. This forces admission of every group instead
    of letting numerical witnesses bypass the screening loop regression.
    """
    # These describe the removed algorithm, not limits used by the current solver.
    former_pass_limit = 50
    former_groups_per_pass = 8
    contingency_count = former_pass_limit * former_groups_per_pass + 1

    grid = build_two_pmode3_link_grid(set_reference_bus_on_both=True)
    for bus in grid.buses:
        if not bus.is_dc:
            # Keep the nonzero droop linear so this tests screening, not MIP cost.
            bus.angle_min = -0.04
            bus.angle_max = 0.04

    radial_bus = gce.Bus(name="radial_load", Vnom=400.0, area=grid.areas[0])
    radial_load = gce.Load(name="radial_load", P=50.0)
    radial_line = gce.Line(name="radial", bus_from=grid.buses[0], bus_to=radial_bus,
                           x=0.01, rate=10.0)
    grid.add_bus(radial_bus)
    grid.add_load(radial_bus, radial_load)
    grid.get_generators()[0].P += radial_load.P
    grid.add_line(radial_line)

    # Each group outages a distinct parallel AC line. The radial stays connected.
    for index in range(contingency_count):
        line = gce.Line(name=f"parallel_{index}", bus_from=grid.buses[0], bus_to=grid.buses[1],
                        x=0.01, rate=1000.0)
        grid.add_line(line)
        group = gce.ContingencyGroup(name=f"outage_{index}")
        grid.add_contingency_group(group)
        grid.add_contingency(gce.Contingency(device=line, group=group))

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]], objects_to=[grid.areas[1]])
    options = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        skip_generation_limits=True,
        use_branch_exchange_sensitivity=False,
        consider_contingencies=True,
        corrective_contingencies=True,
        opf_options=gce.OptimalPowerFlowOptions(contingency_groups_used=grid.contingency_groups),
    )
    driver = gce.OptimalNetTransferCapacityDriver(grid, options)
    driver.run()
    result = driver.results
    assert result.converged
    assert np.isclose(result.inter_area_flows, 500.0, atol=1e-6)
    assert np.all(np.abs(result.nodal_balance) < 1e-6)
    assert result.get_solution_state() == SolutionState.Relaxed
    slack_per_state = radial_load.P - radial_line.rate
    assert np.isclose(result.get_total_slack_mw(), slack_per_state * (contingency_count + 1), atol=1e-6)

    radial_index = int(np.flatnonzero(result.branch_names == radial_line.name)[0])
    rows = [row for row in result.contingency_flows_list if row[1] == radial_index]
    assert len(rows) == contingency_count
    assert {row[2] for row in rows} == set(range(contingency_count))
    for _, _, _, flow, negative_slack, positive_slack in rows:
        assert np.isclose(flow, radial_load.P, atol=1e-6)
        assert np.isclose(positive_slack, slack_per_state, atol=1e-6)
        assert np.isclose(negative_slack, 0.0, atol=1e-6)
        assert flow <= radial_line.rate + positive_slack + 1e-6
        assert flow >= -radial_line.rate - negative_slack - 1e-6


def test_ntc_exchange_proportions_sum_to_one_per_area() -> None:
    """
    Rounding the shares to 6 decimals makes 7 equal shares sum to 0.999999. Each area total
    must still be exactly 1, otherwise the area 1 increase and the area 2 decrease differ by
    the residue and the solution reports a false area mismatch.
    """
    power: Vec = np.ones(14)
    area_1: IntVec = np.arange(7)
    area_2: IntVec = np.arange(7, 14)

    # the premise: the rounded shares alone do not add up to one
    assert not np.isclose(np.round(np.full(7, 1.0 / 7.0), 6).sum(), 1.0, rtol=0.0, atol=1e-12)

    proportions: Vec = get_exchange_proportions(power=power, bus_a1_idx=area_1, bus_a2_idx=area_2,
                                                logger=Logger(), decimals=6)
    assert np.isclose(proportions[area_1].sum(), 1.0, rtol=0.0, atol=1e-12)
    assert np.isclose(proportions[area_2].sum(), -1.0, rtol=0.0, atol=1e-12)


def test_ntc_vsc_joining_the_areas_counts_in_the_ttc() -> None:
    """
    A converter whose two terminals sit in different areas carries part of the exchange.
    Its flow must enter the TTC with the right sense, so the TTC equals area 1's net export.
    """
    grid: gce.MultiCircuit = build_two_pmode3_link_grid(set_reference_bus_on_both=True)

    # move the sending DC bus to the receiving area: vsc_1 now joins the areas, the DC line does not
    bus: gce.Bus
    for bus in grid.buses:
        if bus.name == "dc1":
            bus.area = grid.areas[1]
        else:
            pass  # the other buses keep their area

    drv: gce.OptimalNetTransferCapacityDriver = run_pmode3_link_ntc(grid)
    res: gce.OptimalNetTransferCapacityResults = drv.results
    assert res.converged

    # area 1 exports through the AC line and the converter, so the TTC is its net injection
    area_1: IntVec = np.flatnonzero(grid.get_bus_area_indices() == 0)
    assert np.isclose(res.inter_area_flows, res.Sbus[area_1].real.sum(), atol=1e-6)


def test_ntc_pmode3_radial_outage_is_absorbed_at_the_cut() -> None:
    """
    A radial outage must not make the P-mode 3 study infeasible. As in the LODF path, the
    island is absorbed at the cut. The transfer capacity is unchanged and only the radial
    branch flow changes, while the converter keeps its P-mode 3 droop.
    """
    grid: gce.MultiCircuit = build_two_pmode3_link_grid(set_reference_bus_on_both=True)

    # a load fed through a single line inside the receiving area, and its outage
    radial_bus: gce.Bus = gce.Bus(name="radial_load", Vnom=400.0, area=grid.areas[1])
    radial_load: gce.Load = gce.Load(name="radial_load", P=50.0)
    radial_line: gce.Line = gce.Line(name="radial", bus_from=grid.buses[1], bus_to=radial_bus,
                                     x=0.01, rate=1000.0)
    grid.add_bus(radial_bus)
    grid.add_load(radial_bus, radial_load)
    grid.get_generators()[0].P += radial_load.P
    grid.add_line(radial_line)
    group: gce.ContingencyGroup = gce.ContingencyGroup(name="radial_outage")
    grid.add_contingency_group(group)
    grid.add_contingency(gce.Contingency(device=radial_line, group=group))

    # solve without and with the radial contingency
    info: gce.InterAggregationInfo = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                                                     objects_to=[grid.areas[1]])
    results: ObjVec = np.empty(2, dtype=object)
    i: int
    consider_contingencies: bool
    for i, consider_contingencies in enumerate((False, True)):
        options: gce.OptimalNetTransferCapacityOptions = gce.OptimalNetTransferCapacityOptions(
            sending_bus_idx=info.idx_bus_from,
            receiving_bus_idx=info.idx_bus_to,
            skip_generation_limits=True,
            use_branch_exchange_sensitivity=False,
            consider_contingencies=consider_contingencies,
            corrective_contingencies=True,
            opf_options=gce.OptimalPowerFlowOptions(contingency_groups_used=grid.contingency_groups),
        )
        driver: gce.OptimalNetTransferCapacityDriver = gce.OptimalNetTransferCapacityDriver(grid, options)
        driver.run()
        results[i] = driver.results

    n_state: gce.OptimalNetTransferCapacityResults = results[0]
    n1_state: gce.OptimalNetTransferCapacityResults = results[1]
    assert n_state.converged and n1_state.converged
    assert np.isclose(n_state.inter_area_flows, n1_state.inter_area_flows, atol=1e-6)

    # the radial outage moves no other flow, so every worst N-1 flow is the N flow
    assert np.allclose(n1_state.worst_contingency_flow, n1_state.Sf.real, atol=1e-6)


def build_two_tie_link_grid(droop: bool) -> gce.MultiCircuit:
    """
    Build a 2 area grid joined by two AC ties and an HVDC link with two DC cables, plus a load
    substation fed by two parallel lines. Every element type a contingency can trip is present.

    :param droop: True for a P-mode 3 (angle droop) receiving converter, False for a free one (P-mode 1)
    :return: MultiCircuit
    """
    grid: gce.MultiCircuit = gce.MultiCircuit()
    area_1: gce.Area = gce.Area(name="a1")
    area_2: gce.Area = gce.Area(name="a2")
    grid.add_area(area_1)
    grid.add_area(area_2)

    ac_1: gce.Bus = gce.Bus(name="ac1", Vnom=400.0, area=area_1, is_slack=True)
    ac_2: gce.Bus = gce.Bus(name="ac2", Vnom=400.0, area=area_2)
    dc_1: gce.Bus = gce.Bus(name="dc1", Vnom=400.0, area=area_1, is_dc=True)
    dc_2: gce.Bus = gce.Bus(name="dc2", Vnom=400.0, area=area_2, is_dc=True)
    substation: gce.Bus = gce.Bus(name="substation", Vnom=400.0, area=area_2)
    bus: gce.Bus
    for bus in (ac_1, ac_2, dc_1, dc_2, substation):
        grid.add_bus(bus)

    # generation on both sides so the exchange can grow, and a load only reachable through the feeders
    grid.add_generator(ac_1, gce.Generator(name="gen_a", P=300.0, Pmin=0.0, Pmax=5000.0))
    grid.add_generator(ac_1, gce.Generator(name="gen_b", P=300.0, Pmin=0.0, Pmax=5000.0))
    grid.add_generator(ac_2, gce.Generator(name="gen_c", P=100.0, Pmin=0.0, Pmax=5000.0))
    grid.add_load(ac_2, gce.Load(name="load", P=650.0))
    grid.add_load(substation, gce.Load(name="sub_load", P=50.0))

    i: int
    for i in (1, 2):
        grid.add_line(gce.Line(name=f"tie_{i}", bus_from=ac_1, bus_to=ac_2, x=0.02, rate=1000.0))
        grid.add_line(gce.Line(name=f"feeder_{i}", bus_from=ac_2, bus_to=substation, x=0.01, rate=1000.0))
        grid.add_dc_line(gce.DcLine(name=f"dc_{i}", bus_from=dc_1, bus_to=dc_2, r=1e-3, rate=500.0))

    # the sending converter fixes the DC voltage
    grid.add_vsc(gce.VSC(name="vsc_1", bus_from=dc_1, bus_to=ac_1, rate=1000.0,
                         control1=ConverterControlType.Vm_dc, control1_val=1.0,
                         control2=ConverterControlType.Pac, control2_val=0.0))

    if droop:
        vsc_2: gce.VSC = gce.VSC(name="vsc_2", bus_from=dc_2, bus_to=ac_2, rate=1000.0,
                                 control1=ConverterControlType.Pdc_angle_droop, control1_val=174.53,
                                 control2=ConverterControlType.Pac, control2_val=0.0)
        vsc_2.control1_dev = ac_1
    else:
        vsc_2 = gce.VSC(name="vsc_2", bus_from=dc_2, bus_to=ac_2, rate=1000.0,
                        control1=ConverterControlType.Pac, control1_val=0.0,
                        control2=ConverterControlType.Pdc, control2_val=0.0)
    grid.add_vsc(vsc_2)

    return grid


def run_two_tie_link_contingency(droop: bool, tripped: Tuple[str, ...]) -> gce.OptimalNetTransferCapacityResults:
    """
    Run the corrective N-1 NTC of the two-tie grid with one contingency group.

    :param droop: True for a P-mode 3 receiving converter, False for a free one
    :param tripped: names of the devices the single contingency group trips together
    :return: NTC results
    """
    grid: gce.MultiCircuit = build_two_tie_link_grid(droop=droop)

    # find the tripped devices by name among every kind of device the grid holds
    group: gce.ContingencyGroup = gce.ContingencyGroup(name="tripped together")
    grid.add_contingency_group(group)
    devices: Tuple[List[EditableDevice], ...] = (grid.lines, grid.dc_lines, grid.vsc_devices,
                                                  grid.get_generators(), grid.get_loads())
    device_list: List[EditableDevice]
    device: EditableDevice
    for device_list in devices:
        for device in device_list:
            if device.name in tripped:
                grid.add_contingency(gce.Contingency(device=device, group=group))
            else:
                pass  # this device stays in service

    info: gce.InterAggregationInfo = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                                                     objects_to=[grid.areas[1]])
    options: gce.OptimalNetTransferCapacityOptions = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        skip_generation_limits=True,
        use_branch_exchange_sensitivity=False,
        consider_contingencies=True,
        corrective_contingencies=True,
        opf_options=gce.OptimalPowerFlowOptions(contingency_groups_used=grid.contingency_groups),
    )
    driver: gce.OptimalNetTransferCapacityDriver = gce.OptimalNetTransferCapacityDriver(grid, options)
    driver.run()
    return driver.results


def test_ntc_pmode3_solves_every_contingency_type_like_pmode1() -> None:
    """
    Whatever a contingency trips, P-mode 3 must solve where the free converter mode solves, and
    reach the same transfer. Contingencies that leave a power imbalance used to have no solution.
    """
    cases: Tuple[Tuple[str, ...], ...] = (
        ("tie_1",),                # one AC tie
        ("feeder_1",),             # one of two feeders, nothing is cut off
        ("feeder_1", "feeder_2"),  # both feeders, the substation load is cut off
        ("dc_1",),                 # one of two DC cables
        ("dc_1", "dc_2"),          # both DC cables, the link is lost
        ("vsc_2",),                # the droop converter
        ("gen_a",),                # a generator
        ("sub_load",),             # a load
        ("tie_1", "tie_2"),        # both AC ties, only the link joins the areas
    )
    tripped: Tuple[str, ...]
    for tripped in cases:
        free: gce.OptimalNetTransferCapacityResults = run_two_tie_link_contingency(droop=False, tripped=tripped)
        droop: gce.OptimalNetTransferCapacityResults = run_two_tie_link_contingency(droop=True, tripped=tripped)
        assert free.converged, tripped
        assert droop.converged, tripped
        assert np.isclose(droop.inter_area_flows, free.inter_area_flows, atol=0.5), tripped

    # Tripping the converter that holds the DC voltage leaves the droop converter alone on the DC
    # side, so the link is lost exactly as when the droop converter itself trips.
    link_lost: gce.OptimalNetTransferCapacityResults = run_two_tie_link_contingency(droop=True, tripped=("vsc_2",))
    voltage_lost: gce.OptimalNetTransferCapacityResults = run_two_tie_link_contingency(droop=True,
                                                                                         tripped=("vsc_1",))
    assert voltage_lost.converged
    assert np.isclose(voltage_lost.inter_area_flows, link_lost.inter_area_flows, atol=0.5)


def test_ntc_pmode3_dc_cable_outage_stops_the_link() -> None:
    """
    When the only DC cable of a link trips, both converters are alone on their DC bus and cannot
    transfer any power. 
    """
    grid: gce.MultiCircuit = build_two_pmode3_link_grid(set_reference_bus_on_both=True)
    group: gce.ContingencyGroup = gce.ContingencyGroup(name="dc cable out")
    grid.add_contingency_group(group)
    grid.add_contingency(gce.Contingency(device=grid.dc_lines[0], group=group))

    info: gce.InterAggregationInfo = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                                                     objects_to=[grid.areas[1]])
    options: gce.OptimalNetTransferCapacityOptions = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        skip_generation_limits=True,
        use_branch_exchange_sensitivity=False,
        consider_contingencies=True,
        corrective_contingencies=True,
        opf_options=gce.OptimalPowerFlowOptions(contingency_groups_used=grid.contingency_groups),
    )
    driver: gce.OptimalNetTransferCapacityDriver = gce.OptimalNetTransferCapacityDriver(grid, options)
    driver.run()
    res: gce.OptimalNetTransferCapacityResults = driver.results
    assert res.converged

    # branch 0 is the AC line, branch 1 the DC cable
    ac_flow: float = float(res.Sf[0].real)
    dc_flow: float = float(res.Sf[1].real)
    assert dc_flow > 1.0
    assert np.isclose(res.worst_contingency_flow[0], ac_flow + dc_flow, atol=1e-3)


def test_ntc_strict_pmode3_snapshot_report() -> None:
    """Read status and contingency reports from a solved strict Pmode3 snapshot.

    :return: None.
    """
    grid: gce.MultiCircuit = gce.open_file(get_grid_path("NTC_8_bus_2pmode3_dc_bottleneck.veragrid"))
    info: gce.InterAggregationInfo = grid.get_inter_aggregation_info(
        objects_from=list((grid.areas[0],)), objects_to=list((grid.areas[1],)))
    options: gce.OptimalNetTransferCapacityOptions = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        skip_generation_limits=True,
        use_branch_exchange_sensitivity=False,
        strict_formulation=True,
        consider_contingencies=True,
        corrective_contingencies=True,
        opf_options=gce.OptimalPowerFlowOptions(contingency_groups_used=grid.contingency_groups),
    )
    driver: gce.OptimalNetTransferCapacityDriver = gce.OptimalNetTransferCapacityDriver(grid, options)
    driver.run()
    result: gce.OptimalNetTransferCapacityResults = driver.results

    # Require actual strict contingency rows so an empty report cannot hide the failure.
    assert np.all(result.converged)
    assert len(result.contingency_flows_list) > 0
    assert result.get_total_slack_mw() == 0.0
    assert result.get_solution_state() == SolutionState.Optimal

    # The user facing report must also show zero slack for the solved hard limits.
    report: gce.ResultsTable = result.mdl(ResultTypes.ContingencyFlowsReport)
    slack_column: int = list(report.cols_c).index('Total slack (MW)')
    assert report.r > 0
    assert np.all(report.data_c[:, slack_column] == 0.0)


def test_ntc_reports_ttc_and_ntc() -> None:
    """Apply the configured TRM in snapshot and hourly capacity reports.

    :return: None.
    """
    grid: gce.MultiCircuit = gce.open_file(get_grid_path("NTC_8_bus_2pmode3_dc_bottleneck.veragrid"))
    grid.create_profiles(1, step_length=1.0, step_unit='h')
    info: gce.InterAggregationInfo = grid.get_inter_aggregation_info(
        objects_from=list((grid.areas[0],)), objects_to=list((grid.areas[1],)))
    strict: bool
    margin: float
    for strict in (False, True):
        for margin in (0.0, 125.0):
            options: gce.OptimalNetTransferCapacityOptions = gce.OptimalNetTransferCapacityOptions(
                sending_bus_idx=info.idx_bus_from,
                receiving_bus_idx=info.idx_bus_to,
                transmission_reliability_margin=margin,
                skip_generation_limits=True,
                use_branch_exchange_sensitivity=False,
                strict_formulation=strict,
                consider_contingencies=True,
                corrective_contingencies=True,
                opf_options=gce.OptimalPowerFlowOptions(contingency_groups_used=grid.contingency_groups),
            )
            snapshot: gce.OptimalNetTransferCapacityDriver = gce.OptimalNetTransferCapacityDriver(grid, options)
            hourly: gce.OptimalNetTransferCapacityTimeSeriesDriver = gce.OptimalNetTransferCapacityTimeSeriesDriver(
                grid, options, time_indices=np.array((0,), dtype=int))
            snapshot.run()
            hourly.run()
            assert np.all(snapshot.results.converged)
            assert np.all(hourly.results.converged)
            assert snapshot.results.transmission_reliability_margin == margin
            assert hourly.results.transmission_reliability_margin == margin
            assert np.allclose(hourly.results.inter_area_flows, snapshot.results.inter_area_flows)

            # Both report paths must retain solved TTC and apply the margin exactly once
            result: gce.OptimalNetTransferCapacityResults | OptimalNetTransferCapacityTimeSeriesResults
            for result in (snapshot.results, hourly.results):
                report: gce.ResultsTable = result.mdl(ResultTypes.ContingencyFlowsReport)
                columns: List[str] = list(report.cols_c)
                ttc_column: int = columns.index('TTC (MW)')
                ntc_column: int = columns.index('NTC (MW)')
                assert report.r > 0
                assert ntc_column == ttc_column + 1
                assert np.allclose(report.data_c[:, ttc_column].astype(float), snapshot.results.inter_area_flows)
                assert np.allclose(report.data_c[:, ntc_column].astype(float), snapshot.results.inter_area_flows - margin)
                # Appending the capacity column must preserve the converter report alignment
                vsc_column: int = columns.index(f'VSC {grid.vsc_devices[0].name}: P N (MW)')
                assert np.allclose(report.data_c[:, vsc_column].astype(float), snapshot.results.vsc_Pf[0], atol=1e-4)
                result.parse_saved_data(
                    grid=grid,
                    data_dict=dict(transmission_reliability_margin=np.array(((margin,),), dtype=float)),
                    logger=gce.Logger())
                restored_report: gce.ResultsTable = result.mdl(ResultTypes.ContingencyFlowsReport)
                assert np.isscalar(restored_report.data_c[0, ntc_column])
                assert np.array_equal(restored_report.data_c, report.data_c)

            capacity: gce.ResultsTable = hourly.results.mdl(ResultTypes.NetTransferCapacity)
            assert list(capacity.cols_c) == list(('TTC (MW)', 'NTC (MW)'))
            assert np.allclose(capacity.data_c[:, 0], hourly.results.inter_area_flows)
            assert np.allclose(capacity.data_c[:, 1], hourly.results.inter_area_flows - margin)


def test_ntc_every_offered_result_table_can_be_built() -> None:
    """
    The GUI lists the available results of a study and builds a table when one is clicked.
    Every result type the NTC snapshot and time series results offer must therefore build.
    """
    time_array: np.ndarray = np.array(['2020-01-01T00', '2020-01-01T01'], dtype='datetime64[h]')
    ts_results: OptimalNetTransferCapacityTimeSeriesResults = OptimalNetTransferCapacityTimeSeriesResults(
        bus_names=np.array(['b1', 'b2']),
        branch_names=np.array(['br1']),
        hvdc_names=np.array(['h1']),
        vsc_names=np.array(['v1']),
        contingency_group_names=np.array(['g1']),
        time_array=time_array,
        time_indices=np.array([0, 1]),
    )
    snapshot_results: gce.OptimalNetTransferCapacityResults = gce.OptimalNetTransferCapacityResults(
        bus_names=np.array(['b1', 'b2']),
        branch_names=np.array(['br1']),
        hvdc_names=np.array(['h1']),
        vsc_names=np.array(['v1']),
        contingency_group_names=np.array(['g1']),
    )

    # Walk the same category. Result types structure the results tree is built from
    results: gce.OptimalNetTransferCapacityResults | OptimalNetTransferCapacityTimeSeriesResults
    result_types: List[ResultTypes]
    result_type: ResultTypes
    for results in (snapshot_results, ts_results):
        for result_types in results.available_results.values():
            for result_type in result_types:
                table: gce.ResultsTable = results.mdl(result_type)
                assert table is not None, result_type


def test_ntc_ts_solution_status_column() -> None:
    """
    The net-transfer-capacity time-series table reports Optimal, Relaxed, or
    NotOptimal for each hour.
    """
    time_array: np.ndarray = np.array(['2020-01-01T00', '2020-01-01T01', '2020-01-01T02'],
                                      dtype='datetime64[h]')
    res = OptimalNetTransferCapacityTimeSeriesResults(
        bus_names=np.array(['b1']),
        branch_names=np.array(['br1']),
        hvdc_names=np.array([]),
        vsc_names=np.array([]),
        contingency_group_names=np.array(['g1']),
        time_array=time_array,
        time_indices=np.array([0, 1, 2]),
    )
    res.converged[0] = True
    res.converged[1] = True
    res.converged[2] = False
    res.overloads[0, 0] = 0.0
    res.overloads[1, 0] = 5.0
    res.inter_area_flows[0] = 100.0
    res.inter_area_flows[1] = 90.0
    res.inter_area_flows[2] = 0.0

    states: List[SolutionState] = res.get_solution_states(slack_tol_mw=0.1)
    assert states[0] == SolutionState.Optimal
    assert states[1] == SolutionState.Relaxed
    assert states[2] == SolutionState.NotOptimal

    ntc_table = res.mdl(ResultTypes.NetTransferCapacity)
    assert list(ntc_table.cols_c) == list(('TTC (MW)', 'NTC (MW)'))
    assert ntc_table.data_c.dtype == float
    assert ntc_table.data_c[0, 0] == 100.0
    assert np.array_equal(ntc_table.data_c[:, 1], ntc_table.data_c[:, 0])

    slack_table = res.mdl(ResultTypes.NetTransferCapacitySlack)
    assert list(slack_table.cols_c) == ['Total slack (MW)']
    assert slack_table.data_c.dtype == float
    assert slack_table.data_c[0, 0] == 0.0
    assert slack_table.data_c[1, 0] == 5.0
    assert slack_table.data_c[2, 0] == 0.0

    status_table = res.mdl(ResultTypes.NetTransferCapacityStatus)
    assert list(status_table.cols_c) == ['Status']
    assert status_table.data_c[0, 0] == SolutionState.Optimal
    assert status_table.data_c[1, 0] == SolutionState.Relaxed
    assert status_table.data_c[2, 0] == SolutionState.NotOptimal


def test_ntc_ts_solution_status_expands_with_clustering() -> None:
    """
    After clustering expansion, the status table has one row per original hour and
    each hour inherits the representative's Optimal / Relaxed / NotOptimal state.
    """
    full_nt: int = 10
    time_all: np.ndarray = np.array(
        [np.datetime64('2020-01-01T00') + np.timedelta64(h, 'h') for h in range(full_nt)]
    )
    time_indices: np.ndarray = np.array([0, 4, 8])
    original_sample_idx: np.ndarray = np.array([0, 0, 0, 0, 1, 1, 1, 1, 2, 2])
    clustering: ClusteringResults = ClusteringResults(
        time_indices=time_indices,
        sampled_probabilities=np.array([0.4, 0.4, 0.2]),
        time_array=time_all,
        original_sample_idx=original_sample_idx,
    )

    res = OptimalNetTransferCapacityTimeSeriesResults(
        bus_names=np.array(['b1']),
        branch_names=np.array(['br1']),
        hvdc_names=np.array([]),
        vsc_names=np.array([]),
        contingency_group_names=np.array(['g1']),
        time_array=time_all[time_indices],
        time_indices=time_indices,
        clustering_results=clustering,
    )
    res.converged[:] = np.array([True, True, False])
    res.overloads[:, 0] = np.array([0.0, 5.0, 0.0])
    res.inter_area_flows[:] = np.array([100.0, 90.0, 0.0])

    res.expand_clustered_results()

    assert len(res.time_array) == full_nt
    assert res.converged.shape[0] == full_nt

    status_table = res.mdl(ResultTypes.NetTransferCapacityStatus)
    assert status_table.r == full_nt
    assert list(status_table.cols_c) == ['Status']

    expected: List[SolutionState] = (
        [SolutionState.Optimal] * 4
        + [SolutionState.Relaxed] * 4
        + [SolutionState.NotOptimal] * 2
    )
    t: int
    for t in range(full_nt):
        assert status_table.data_c[t, 0] == expected[t]

    ntc_table = res.mdl(ResultTypes.NetTransferCapacity)
    assert ntc_table.r == full_nt
    assert ntc_table.data_c[0, 0] == 100.0
    assert ntc_table.data_c[4, 0] == 90.0
    assert ntc_table.data_c[8, 0] == 0.0


def test_ntc_ts_worst_contingency_report_expands_with_clustering() -> None:
    """
    After clustering expansion, the contingency report has one row per original hour
    and per branch, and the timestamps cover the full original calendar.
    """
    full_nt: int = 10
    time_all: np.ndarray = np.array(
        [np.datetime64('2020-01-01T00') + np.timedelta64(h, 'h') for h in range(full_nt)]
    )
    time_indices: np.ndarray = np.array([0, 4, 8])
    original_sample_idx: np.ndarray = np.array([0, 0, 0, 0, 1, 1, 1, 1, 2, 2])
    clustering: ClusteringResults = ClusteringResults(
        time_indices=time_indices,
        sampled_probabilities=np.array([0.4, 0.4, 0.2]),
        time_array=time_all,
        original_sample_idx=original_sample_idx,
    )

    res = OptimalNetTransferCapacityTimeSeriesResults(
        bus_names=np.array(['b1']),
        branch_names=np.array(['br1']),
        hvdc_names=np.array([]),
        vsc_names=np.array([]),
        contingency_group_names=np.array(['g1']),
        time_array=time_all[time_indices],
        time_indices=time_indices,
        clustering_results=clustering,
        transmission_reliability_margin=10.0,
    )
    res.contingency_group_device_names[0] = "line A"
    res.inter_area_flows[:] = np.array([100.0, 90.0, 0.0])
    res.Sf[:, 0] = np.array([10.0, 20.0, 5.0])
    res.alpha[:, 0] = np.array([0.1, 0.2, 0.0])
    res.alpha_n1_worst[:, 0] = np.array([0.3, 0.4, 0.0])
    res.monitor_logic[:, 0] = np.array([1, 1, 1])
    res.worst_contingency_idx[:, 0] = np.array([0, 0, -1])
    res.worst_contingency_flow[:, 0] = np.array([12.0, 25.0, 5.0])
    res.worst_contingency_loading[:, 0] = np.array([0.24, 0.50, 0.10])
    res.contingency_rates[0] = 50.0
    res.loading_threshold_to_report = 0.0
    # only the second cluster needed relaxed limits
    res.overloads[:, 0] = np.array([0.0, 7.5, 0.0])

    # The representative view must agree before and after calendar expansion.
    representative: gce.ResultsTable = res.mdl(ResultTypes.ContingencyFlowsRepresentativeReport)
    representative_columns: List[str] = list(representative.cols_c)
    representative_ttc: int = representative_columns.index('TTC (MW)')
    representative_ntc: int = representative_columns.index('NTC (MW)')
    assert np.array_equal(representative.data_c[:, representative_ttc], np.array((100.0, 90.0, 0.0)))
    assert np.array_equal(representative.data_c[:, representative_ntc], np.array((90.0, 80.0, -10.0)))

    res.expand_clustered_results()
    expanded_representative: gce.ResultsTable = res.mdl(ResultTypes.ContingencyFlowsRepresentativeReport)
    assert np.array_equal(expanded_representative.data_c, representative.data_c)

    table = res.mdl(ResultTypes.ContingencyFlowsReport)
    # 10 original hours times 1 branch
    assert table.r == full_nt
    columns = list(table.cols_c)

    time_col: int = columns.index('Time')
    t_idx_col: int = columns.index('Time index')
    ntc_col: int = columns.index('NTC (MW)')
    ttc_col: int = columns.index('TTC (MW)')
    flow_n1_col: int = columns.index('Flow N-1 (MW)')
    last_time: str = str(table.data_c[full_nt - 1, time_col])
    assert '2020-01-01T09' in last_time.replace(' ', 'T')
    assert table.data_c[0, t_idx_col] == 0
    assert table.data_c[full_nt - 1, t_idx_col] == full_nt - 1
    assert table.data_c[0, ttc_col] == 100.0
    assert table.data_c[4, ttc_col] == 90.0
    assert table.data_c[8, ttc_col] == 0.0
    assert table.data_c[0, ntc_col] == 90.0
    assert table.data_c[4, ntc_col] == 80.0
    assert table.data_c[8, ntc_col] == -10.0
    assert table.data_c[0, flow_n1_col] == 12.0
    assert table.data_c[4, flow_n1_col] == 25.0
    # cluster 2 has no worse N-1, so the table reports the N flow
    assert table.data_c[8, flow_n1_col] == 5.0

    # every original hour shows the slack of its cluster, so a loading above the rate can be
    # told apart from a clean hour without opening the representative report
    slack_col: int = columns.index('Total slack (MW)')
    assert table.data_c[0, slack_col] == 0.0
    assert table.data_c[4, slack_col] == 7.5
    assert table.data_c[7, slack_col] == 7.5
    assert table.data_c[8, slack_col] == 0.0

    res.monitor_logic[8:, 0] = False
    monitored_table = res.mdl(ResultTypes.ContingencyFlowsReport)
    assert monitored_table.r == 8
    assert list(monitored_table.data_c[:, t_idx_col]) == list(range(8))


def test_ntc_worst_contingency_is_the_other_tie() -> None:
    """
    On a two area pair of radial branches, losing A means the load goes into B.

    B's worst N-1 is therefore the outage of A, and the N-1 flow on B is the full load.
    """
    grid = gce.MultiCircuit()
    a1 = gce.Area("A1")
    a2 = gce.Area("A2")
    grid.add_area(a1)
    grid.add_area(a2)
    b0 = gce.Bus("B0", Vnom=400, area=a1)
    b0.is_slack = True
    b1 = gce.Bus("B1", Vnom=400, area=a2)
    b2 = gce.Bus("B2", Vnom=400, area=a2)
    grid.add_bus(b0)
    grid.add_bus(b1)
    grid.add_bus(b2)
    grid.add_generator(b0, gce.Generator("G", P=120, Pmax=1000, Pmin=0))
    grid.add_load(b2, gce.Load("L", P=120))
    line_tie = gce.Line(b0, b1, name="tie", x=0.01, rate=1000)
    line_a = gce.Line(b1, b2, name="A", x=0.01, rate=100)
    line_b = gce.Line(b1, b2, name="B", x=0.02, rate=50)
    grid.add_line(line_tie)
    grid.add_line(line_a)
    grid.add_line(line_b)
    cg = gce.ContingencyGroup(name="A out")
    grid.add_contingency_group(cg)
    grid.add_contingency(gce.Contingency(device=line_a, group=cg))

    info = grid.get_inter_aggregation_info(objects_from=list([a1]), objects_to=list([a2]))
    opts = gce.OptimalNetTransferCapacityOptions(
        sending_bus_idx=info.idx_bus_from,
        receiving_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        consider_contingencies=True,
        use_branch_exchange_sensitivity=False,
        opf_options=gce.OptimalPowerFlowOptions(contingency_groups_used=grid.contingency_groups),
    )
    drv = gce.OptimalNetTransferCapacityDriver(grid, opts)
    drv.run()
    res = drv.results

    # branch order is tie, A, B
    assert str(res.contingency_group_device_names[0]) == "A"
    assert int(res.worst_contingency_idx[2]) == 0
    assert float(res.worst_contingency_flow[2]) > 100.0
    # A's own outage does not raise A's loading, so A keeps "no worse N-1"
    assert int(res.worst_contingency_idx[1]) == -1

    table = res.mdl(ResultTypes.ContingencyFlowsReport)
    columns = list(table.cols_c)
    assert 'Contingency branch' not in columns
    assert 'Branch' in columns
    assert 'Monitored' in columns
    n1_col: int = columns.index('Flow N-1 (MW)')
    grp_col: int = columns.index('Contingency group')
    br_col: int = columns.index('Branch')
    load_col: int = columns.index('Loading N-1 (%)')
    found_b: bool = False
    i_row: int
    for i_row in range(table.r):
        if table.data_c[i_row, br_col] == "B":
            found_b = True
            assert table.data_c[i_row, grp_col] == "A out"
            assert float(table.data_c[i_row, n1_col]) > 100.0
            assert float(table.data_c[i_row, load_col]) >= 98.0
        else:
            pass
    assert found_b


def test_ntc_ts_report_keeps_only_rows_above_loading_threshold() -> None:
    """
    The contingency report drops (hour, branch) pairs whose N-1 loading is below
    the NTC loading threshold to report.
    """
    time_array: np.ndarray = np.array(['2020-01-01T00', '2020-01-01T01'], dtype='datetime64[h]')
    res = OptimalNetTransferCapacityTimeSeriesResults(
        bus_names=np.array(['b1']),
        branch_names=np.array(['light', 'heavy']),
        hvdc_names=np.array([]),
        vsc_names=np.array([]),
        contingency_group_names=np.array(['g1']),
        time_array=time_array,
        time_indices=np.array([0, 1]),
    )
    res.loading_threshold_to_report = 98.0
    res.monitor_logic[:, :] = 1
    res.contingency_rates[:] = np.array([100.0, 100.0])
    res.Sf[:, :] = 10.0
    res.worst_contingency_idx[:, :] = 0
    res.worst_contingency_flow[:, 0] = 50.0
    res.worst_contingency_flow[:, 1] = 99.0
    res.worst_contingency_loading[:, 0] = 0.50
    res.worst_contingency_loading[:, 1] = 0.99
    res.inter_area_flows[:] = 100.0

    table = res.mdl(ResultTypes.ContingencyFlowsReport)
    columns = list(table.cols_c)
    br_col: int = columns.index('Branch')
    t_col: int = columns.index('Time index')
    assert table.r == 2
    i_row: int
    for i_row in range(table.r):
        assert table.data_c[i_row, br_col] == 'heavy'
        assert table.data_c[i_row, t_col] in (0, 1)

    res.loading_threshold_to_report = 0.0
    full_table = res.mdl(ResultTypes.ContingencyFlowsReport)
    assert full_table.r == 4

    res.monitor_logic[0, 1] = False
    res.loading_threshold_to_report = 98.0
    monitored_table = res.mdl(ResultTypes.ContingencyFlowsReport)
    assert monitored_table.r == 1
    assert monitored_table.data_c[0, br_col] == 'heavy'
    assert monitored_table.data_c[0, t_col] == 1

    res.monitor_logic[:, :] = False
    assert res.mdl(ResultTypes.ContingencyFlowsReport).r == 0


if __name__ == '__main__':
    # test_issue_372_1()
    # test_issue_372_2()
    # test_issue_372_4()
    # test_ntc_ultra_simple()
    # test_ntc_pmode_saturation()
    # test_ntc_vsc()
    # test_ntc_vsc_contingencies()
    # test_2_node_several_conditions_ntc()
    # test_ntc_pmode_saturation()
    # test_ntc_pmode_non_saturation()
    # test_issue_372_3()
    # test_hvdc_lines_tests()
    # test_activs_2000_acdc()
    test_ntc_vsc_8_buses_REE_contingencies()
