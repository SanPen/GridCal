# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import numpy as np
import pytest
import VeraGridEngine.api as vg
from VeraGridEngine.Compilers.Gslv.activation import pg
from VeraGridEngine.Compilers.Gslv.conversion import to_gslv
from VeraGridEngine.Compilers.Gslv.Simulations.opf import gslv_opf
from tests.LinearOPF.test_battery_facility_dispatch import make_facility_grid
from VeraGridEngine.enumerations import BatteryDispatchMode, RemedialActionPropertyEnum
from VeraGridEngine.Devices.Aggregation.investment import Investment
from VeraGridEngine.Devices.Aggregation.investments_group import InvestmentsGroup
from VeraGridEngine.Devices.Events.remedial_action import RemedialAction
from VeraGridEngine.Devices.Events.remedial_action_group import RemedialActionGroup


@pytest.mark.skipif(pg is None, reason="pygslv is not installed")
@pytest.mark.parametrize("sliced", (False, True))
@pytest.mark.parametrize("sparse", (False, True))
def test_battery_dispatch_profiles(sliced: bool, sparse: bool) -> None:
    """
    Preserve dispatch policies in snapshots and full or sliced time series.

    :param sliced: Whether to select only part of the source profile.
    :param sparse: Whether the profile uses sparse storage.
    :return: None.
    """
    grid: vg.MultiCircuit = vg.MultiCircuit()
    bus: vg.Bus = vg.Bus()
    grid.add_bus(bus)
    battery: vg.Battery = vg.Battery(dispatch_mode=BatteryDispatchMode.PlantChargeGridDischarge)
    grid.add_battery(bus=bus, api_obj=battery)
    grid.create_profiles(steps=10 if sparse else 3, step_length=2, step_unit='h')
    modes: np.ndarray = np.array(tuple(BatteryDispatchMode), dtype=object)
    if sparse:
        modes = np.full(10, BatteryDispatchMode.Grid, dtype=object)
        modes[2] = BatteryDispatchMode.PlantChargeAndDisCharge
    else:
        pass
    battery.dispatch_mode_prof.set(modes)
    assert battery.dispatch_mode_prof.is_sparse == sparse
    selected: np.ndarray | None = np.array([2, 0]) if sliced else None
    converted, _ = to_gslv(grid, use_time_series=True, time_indices=selected)
    expected: np.ndarray = modes if selected is None else modes[selected]
    for index, mode in enumerate(expected):
        assert converted.batteries[0].get_dispatch_mode_at(index) == pg.BatteryDispatchMode.__members__[mode.name]
    snapshot, _ = to_gslv(grid, use_time_series=False)
    assert snapshot.batteries[0].get_dispatch_mode_at(0) == pg.BatteryDispatchMode.PlantChargeGridDischarge


@pytest.mark.skipif(pg is None, reason="pygslv is not installed")
def test_event_targets_and_remedial_second_pass() -> None:
    """
    Preserve event target identity, forward predecessors and monitored limits.

    :return: None.
    """
    grid: vg.MultiCircuit = vg.MultiCircuit()
    bus: vg.Bus = vg.Bus()
    grid.add_bus(bus)
    battery: vg.Battery = vg.Battery()
    grid.add_battery(bus=bus, api_obj=battery)
    contingency_group: vg.ContingencyGroup = vg.ContingencyGroup()
    grid.add_contingency_group(contingency_group)
    grid.add_contingency(vg.Contingency(device=battery, group=contingency_group))
    investment_group: InvestmentsGroup = InvestmentsGroup()
    grid.add_investments_group(investment_group)
    grid.add_investment(Investment(device=battery, group=investment_group, CAPEX=10.0))
    substation: vg.Substation = vg.Substation()
    grid.add_substation(substation)
    grid.add_investment(Investment(device=substation, group=None))
    predecessor: RemedialActionGroup = RemedialActionGroup(name='predecessor')
    group: RemedialActionGroup = RemedialActionGroup(name='dependent')
    group.conn_group = contingency_group
    group.prev_ra = predecessor
    group.monitored_device = bus
    group.property_type = RemedialActionPropertyEnum.Vmin
    grid.add_remedial_action_group(group)
    grid.add_remedial_action_group(predecessor)
    grid.add_remedial_action(RemedialAction(device=battery, group=group, value=0.0))
    converted, _ = to_gslv(grid, use_time_series=False)
    assert converted.contingencies[0].device is converted.batteries[0]
    assert converted.contingencies[0].tpe == pg.DeviceType.BatteryDevice
    assert converted.investments[0].device is converted.batteries[0]
    assert converted.investments[0].CAPEX == 10.0
    assert converted.investments[1].device is converted.substations[0]
    assert converted.investments[1].group is None
    assert converted.remedial_actions[0].device is converted.batteries[0]
    assert converted.remedial_actions[0].group is converted.remedial_action_groups[0]
    assert converted.remedial_action_groups[0].prev_ra is converted.remedial_action_groups[1]
    assert converted.remedial_action_groups[0].conn_group is converted.contingency_groups[0]
    assert converted.remedial_action_groups[0].monitored_device is converted.buses[0]
    assert converted.remedial_action_groups[0].property_type == pg.RemedialActionPropertyEnum.Vmin


@pytest.mark.skipif(pg is None, reason="pygslv is not installed")
def test_static_generator_constructor() -> None:
    """
    Export fixed P/Q injections using the pygslv 1.0 constructor.

    :return: None.
    """
    grid: vg.MultiCircuit = vg.MultiCircuit()
    bus: vg.Bus = vg.Bus()
    grid.add_bus(bus)
    generator: vg.StaticGenerator = vg.StaticGenerator(P=12.0, Q=3.0)
    generator.build_status = vg.BuildStatus.Planned
    grid.add_static_generator(bus=bus, api_obj=generator)
    converted, _ = to_gslv(grid, use_time_series=False)
    assert converted.static_generators[0].P.to_list() == [12.0]
    assert converted.static_generators[0].Q.to_list() == [3.0]
    assert converted.static_generators[0].build_status == pg.BuildStatus.Planned


@pytest.mark.skipif(pg is None or not pg.isLicensed(), reason="A pygslv license is required")
@pytest.mark.parametrize("mode", tuple(BatteryDispatchMode))
@pytest.mark.parametrize("charging", (False, True))
def test_converted_battery_facility_dispatch(mode: BatteryDispatchMode, charging: bool) -> None:
    """
    Exercise each converted plant policy through the installed OPF solver.

    :param mode: Battery exchange policy.
    :param charging: Whether prices encourage battery charging.
    :return: None.
    """
    grid: vg.MultiCircuit = make_facility_grid(mode=mode, charging=charging)
    result: pg.OptimalPowerFlowResults = gslv_opf(
        circuit=grid, opf_options=vg.OptimalPowerFlowOptions(), time_series=True,
        time_indices=np.array([0], dtype=int))
    expected: float = -10.0 if charging else 10.0
    if charging and mode != BatteryDispatchMode.Grid:
        expected = -3.0
    elif not charging and mode == BatteryDispatchMode.PlantChargeAndDisCharge:
        expected = 4.0
    else:
        pass
    assert np.all(result.converged)
    assert np.isclose(result.battery_power[0, 0], expected)
