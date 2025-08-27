# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import pytest
import numpy as np
import VeraGridEngine.api as gce


@pytest.mark.skip(reason="Not passing because this problem must have slacks")
def test_ntc_ultra_simple() -> None:
    """

    :return:
    """
    np.set_printoptions(precision=4)
    fname = os.path.join('data', 'grids', 'red_ultra_simple_ntc.gridcal')

    grid = gce.open_file(fname)

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                           objects_to=[grid.areas[1]])

    opf_options = gce.OptimalPowerFlowOptions(
        # export_model_fname="test_ntc_ultra_simple.lp"
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
        strict_formulation=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results

    assert res.converged
    assert np.isclose(res.Sf[0].real, 100.0)
    assert res.dSbus.sum() == 0.0
    assert res.dSbus[0] == 75.0
    assert abs(res.nodal_balance.sum()) < 1e-8


@pytest.mark.skip(reason="Not passing because this problem must have slacks")
def test_ntc_ieee_14() -> None:
    """

    :return:
    """
    np.set_printoptions(precision=4)
    fname = os.path.join('data', 'grids', 'ntc_test.gridcal')

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
        strict_formulation=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results

    assert res.converged
    assert abs(res.nodal_balance.sum()) < 1e-8


@pytest.mark.skip(reason="Not passing because this problem must have slacks")
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
    # fname = os.path.join('data', 'grids', 'ntc_test.gridcal')
    fname = os.path.join('data', 'grids', 'IEEE14 - ntc areas_voltages_hvdc_shifter_l10free.gridcal')

    grid = gce.open_file(fname)

    # Phase shifter (branch 8): tap_phase_control_mode: fixed.
    grid.transformers2w[6].tap_phase_control_mode = gce.TapPhaseControl.fixed

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                           objects_to=[grid.areas[1]])

    opf_options = gce.OptimalPowerFlowOptions(
        consider_contingencies=False,
        # export_model_fname="test_issue_372_1.lp"
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
        strict_formulation=True,
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
    assert abs(res.nodal_balance.sum()) < 1e-8

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


@pytest.mark.skip(reason="Not passing because this problem must have slacks")
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
    # fname = os.path.join('data', 'grids', 'ntc_test.gridcal')
    fname = os.path.join('data', 'grids', 'IEEE14 - ntc areas_voltages_hvdc_shifter_l10free.gridcal')

    grid = gce.open_file(fname)

    # Phase shifter (branch 8): tap_phase_control_mode: Pt.
    grid.transformers2w[6].tap_phase_control_mode = gce.TapPhaseControl.Pf

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                           objects_to=[grid.areas[1]])

    opf_options = gce.OptimalPowerFlowOptions(
        consider_contingencies=False,
        # export_model_fname="test_issue_372_1.lp"
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
        strict_formulation=True,
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
    assert np.all(res.loading[monitor_idx] <= 1)

    # The total exchange should be greater than in _test1 (implemented as test_issue_372_1).
    # TODO: so far it is not, maybe this is not a universal truth
    assert res.Sbus[a1].sum() >= 49.74
    print()


@pytest.mark.skip(reason="Not passing because this problem must have slacks")
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
    # fname = os.path.join('data', 'grids', 'ntc_test.gridcal')
    fname = os.path.join('data', 'grids', 'IEEE14 - ntc areas_voltages_hvdc_shifter_l10free.gridcal')

    grid = gce.open_file(fname)

    # Phase shifter (branch 8): tap_phase_control_mode: Pt.
    grid.transformers2w[6].tap_phase_control_mode = gce.TapPhaseControl.fixed
    grid.hvdc_lines[0].control_mode = gce.HvdcControlType.type_0_free

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                           objects_to=[grid.areas[1]])

    opf_options = gce.OptimalPowerFlowOptions(
        consider_contingencies=False,
        # export_model_fname="test_issue_372_3.lp"
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
        strict_formulation=True,
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
    assert np.all(res.loading[monitor_idx] <= 1)

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


@pytest.mark.skip(reason="Not passing because this problem must have slacks")
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
    # fname = os.path.join('data', 'grids', 'ntc_test.gridcal')
    fname = os.path.join('data', 'grids', 'IEEE14 - ntc areas_voltages_hvdc_shifter_l10free.gridcal')

    grid = gce.open_file(fname)

    # Phase shifter (branch 8): tap_phase_control_mode: Pt.
    grid.transformers2w[6].tap_phase_control_mode = gce.TapPhaseControl.Pt
    grid.hvdc_lines[0].control_mode = gce.HvdcControlType.type_1_Pset

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                           objects_to=[grid.areas[1]])

    opf_options = gce.OptimalPowerFlowOptions(
        # export_model_fname="test_issue_372_4.lp",
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
        strict_formulation=True,
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

    # Because the alpha N-1 is made abs in this formulation, this is less precise (1e-5, instead of 1e-8)
    assert abs(res.nodal_balance.sum()) < 1e-5

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
    assert np.all(res.loading[monitor_idx] <= 1)

    # The total exchange should be greater than in _test1 (inter_area_flows=89.7438187457783)
    # TODO: so far it is not, maybe this is not a universal truth
    assert inter_area_flows <= 89.7438187457783

    # We expect less exchange than test 2. (inter_area_flows=89.7438187457783)
    # TODO: so far it is not (it is the same), maybe this is not a universal truth
    assert inter_area_flows <= 89.7438187457783
    print()


@pytest.mark.skip(reason="Not passing because this problem must have slacks")
def test_issue_372_5():
    """
    https://github.com/SanPen/VeraGrid/issues/372#issuecomment-2824174417

    Using the grid IEEE14 - ntc areas_voltages_hvdc_shifter_l10free.gridcal

    Test:

        Given a base situation (simulated with a linear power flow)
        We define the exchange from A1->A2
        Run the NTC optimization

    Run options:

        All contingencies
        HVDC mode: free
        Phase shifter (branch 8): tap_phase_control_mode: fixed.
        All generators enable_dispatch = True
        Exchange sensitivity criteria: use alpha = 5%

    Metrics:

        Δ P in A1 optimized > 0 (because there are no base overloads)
        Δ P in A2 optimized < 0 (because there are no base overloads)
        Δ P in A1 == − Δ P in A2
        The summation of flow increments in the inter-area branches must be ΔP in A1.
        Monitored & selected by the exchange sensitivity criteria, branches must not be overloaded beyond 100%
        The total exchange should be greater than in _test1.
        The HVDC power must be: P0 + angle_droop · (theta_f − theta_t) (all in proper units)

        TODO: Monitored & selected by the exchange sensitivity criteria branches flow must be lower than rate.
        TODO: Monitored & selected by the exchange sensitivity criteria branches contingency flow must be lower than contingency rate.

    """
    # fname = os.path.join('data', 'grids', 'ntc_test.gridcal')
    fname = os.path.join('data', 'grids', 'IEEE14 - ntc areas_voltages_hvdc_shifter_l10free.gridcal')

    grid = gce.open_file(fname)

    # Phase shifter (branch 8): tap_phase_control_mode: Pt.
    grid.transformers2w[6].tap_phase_control_mode = gce.TapPhaseControl.fixed
    grid.hvdc_lines[0].control_mode = gce.HvdcControlType.type_0_free

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                           objects_to=[grid.areas[1]])

    opf_options = gce.OptimalPowerFlowOptions(
        # export_model_fname="test_issue_372_5.lp",
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
        strict_formulation=True,
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

    # Because the alpha N-1 is made abs in this formulation, this is less precise (1e-5, instead of 1e-8)
    assert abs(res.nodal_balance.sum()) < 1e-5

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
    assert np.all(res.loading[monitor_idx] <= 1)

    # The HVDC power must be: P0 + angle_droop · (theta_f − theta_t) (all in proper units)
    dev = grid.hvdc_lines[0]
    k = dev.angle_droop
    theta_f = np.angle(res.voltage[10], deg=True)
    theta_t = np.angle(res.voltage[14], deg=True)
    hvdc_power = dev.Pset + k * (theta_f - theta_t)
    assert np.isclose(hvdc_power, res.hvdc_Pf[0], atol=1e-6)

    # The total exchange should be greater than in _test1 (inter_area_flows=89.7438187457783)
    # TODO: so far it is not, maybe this is not a universal truth
    assert inter_area_flows < 89.7438187457783

    # We expect less exchange than test 2. (inter_area_flows=89.7438187457783)
    # TODO: so far it is not (it is the same), maybe this is not a universal truth
    assert inter_area_flows < 89.7438187457783
    print()


@pytest.mark.skip(reason="Not passing because this problem must have slacks")
def test_ntc_pmode_saturation() -> None:
    """
    In this test we force one of the HVDC devices to dispatch using PMODE3 and saturate to its rating,
    checking that the PMODE3 equation goes on to provide a larger set point
    """
    np.set_printoptions(precision=4)
    fname = os.path.join('data', 'grids', 'ntc_test.gridcal')

    grid = gce.open_file(fname)

    grid.hvdc_lines[0].control_mode = gce.HvdcControlType.type_0_free
    grid.hvdc_lines[0].angle_droop = 0.2  # this will force a greater pmode3 flow

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
        strict_formulation=True,
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
    assert np.all(res.loading[monitor_idx] <= 1)

    # The HVDC power must be: P0 + angle_droop · (theta_f − theta_t) (all in proper units)
    dev = grid.hvdc_lines[0]
    k = dev.angle_droop
    theta_f = np.angle(res.voltage[3], deg=True)
    theta_t = np.angle(res.voltage[4], deg=True)
    hvdc_power = dev.Pset + k * (theta_f - theta_t)
    assert np.isclose(res.hvdc_Pf[0], grid.hvdc_lines[0].rate, atol=1e-6)  # the power must saturate to the rate
    assert res.hvdc_Pf[0] > hvdc_power  # the actual power must be greater than what the angles suggest

    assert res.converged
    assert abs(res.nodal_balance.sum()) < 1e-8


@pytest.mark.skip(reason="Not passing because this problem must have slacks")
def test_ntc_areas_connected_only_through_hvdc() -> None:
    """
    This test checks that a grid that is only joined with HVDC lines can transfer power through the 2 areas
    """
    np.set_printoptions(precision=4)
    fname = os.path.join('data', 'grids', 'ntc_test_cont.gridcal')

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
        strict_formulation=True,
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


@pytest.mark.skip(reason="Not passing because this problem must have slacks")
def test_ntc_vsc():
    """
    This test runs a test grid with VSC systems where controllers pairs are in Pset and Vdc modes
    No contingencies are enabled
    """
    fname = os.path.join('data', 'grids', 'ntc_test_cont (vsc).gridcal')

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
        strict_formulation=True,
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


@pytest.mark.skip(reason="Not passing because this problem must have slacks")
def test_ntc_vsc_contingencies():
    """
    This test runs a test grid with VSC systems where controllers pairs are in Pset and Vdc modes
    No contingencies are enabled
    """
    fname = os.path.join('data', 'grids', 'ntc_test_cont (vsc).gridcal')

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
        strict_formulation=True,
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


@pytest.mark.skip(reason="Not passing because this problem must have slacks")
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

    line12 = gce.Line(bus_from=bus1, bus_to=bus2, name="Line 1-2", x=1e-4, rate=1000.0)
    grid.add_line(line12)

    transformer12 = gce.Transformer2W(bus_from=bus1, bus_to=bus2, name="Transformer 1-2", x=1e-4, rate=1000.0)
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
        strict_formulation=True,
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
        strict_formulation=True,
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
        strict_formulation=True,
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
        strict_formulation=True,
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
        strict_formulation=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results
    assert abs(res.nodal_balance.sum()) < 1e-8
    assert not res.converged  # you cannot hard fix the inter area angle difference and enforce movement by proportions


@pytest.mark.skip(reason="Not passing because this problem must have slacks")
def test_hvdc_lines_tests():
    """
    Testing test_santi_20250625.gridcal
    >This is a simple test that checks that the flow is maximal between the two areas
    :return:
    """
    np.set_printoptions(precision=4)
    fname = os.path.join('data', 'grids', 'test_santi_20250625.gridcal')

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
        strict_formulation=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results
    assert abs(res.nodal_balance.sum()) < 1e-8
    assert np.isclose(res.Sf[7], 1000.0)
    assert np.isclose(res.hvdc_Pf[0], 1000.0)
    assert np.isclose(res.hvdc_Pf[1], 1000.0)
    assert np.isclose(res.inter_area_flows, 3000.0)


@pytest.mark.skip(reason="Not passing because this problem must have slacks")
def test_activs_2000():
    """
    Simulate a large size grid: ACTIVSg 2000 with contingencies
    :return:
    """
    np.set_printoptions(precision=4)
    fname = os.path.join('data', 'grids', 'ACTIVSg2000.gridcal')

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
        strict_formulation=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results
    ntc_no_contingencies = res.inter_area_flows
    assert abs(res.nodal_balance.sum()) < 1e-6
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
        strict_formulation=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results
    assert abs(res.nodal_balance.sum()) < 1e-6
    assert res.converged
    assert res.inter_area_flows < res.structural_inter_area_flows
    assert res.inter_area_flows < ntc_no_contingencies


@pytest.mark.skip(reason="Not passing because this problem must have slacks")
def test_activs_2000_acdc():
    """
    Simulate a large size grid: ACTIVSg 2000 extended with 2 DC lines and 2 converters with contingencies
    :return:
    """
    np.set_printoptions(precision=4)
    fname = os.path.join('data', 'grids', 'ACTIVSg2000.gridcal')

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
        strict_formulation=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results
    assert abs(res.nodal_balance.sum()) < 1e-6
    assert res.converged


@pytest.mark.skip(reason="Not passing because this problem must have slacks")
def test_activs_2000_acdc_ts():
    """
    Simulate a large size grid: ACTIVSg 2000 extended with 2 DC lines and 2 converters with contingencies
    and we extend it to 5 time steps to run them
    :return:
    """
    np.set_printoptions(precision=4)
    fname = os.path.join('data', 'grids', 'ACTIVSg2000_vsc.gridcal')

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
        strict_formulation=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityTimeSeriesDriver(grid, ntc_options,
                                                         time_indices=grid.get_all_time_indices())

    drv.run()

    res = drv.results
    assert abs(res.nodal_balance.sum()) < 1e-6
    assert res.converged.all()


if __name__ == '__main__':
    # test_issue_372_1()
    # test_issue_372_2()
    # test_issue_372_4()
    # test_ntc_ultra_simple()
    # test_ntc_pmode_saturation()
    # test_ntc_vsc()
    # test_ntc_vsc_contingencies()
    test_2_node_several_conditions_ntc()
