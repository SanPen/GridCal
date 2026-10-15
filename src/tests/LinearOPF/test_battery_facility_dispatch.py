"""Small-grid evidence for facility battery dispatch in the linear OPF.

Positive battery power means discharge; negative power means charging. Power
is checked in MW and stored energy in MWh. Hourly intervals and unit battery
efficiencies keep most expected results directly calculable; the final energy
test deliberately uses non-unit efficiencies.

The one-bus cases isolate individual rules. The three-bus cases combine two
plants, mixed modes, unrelated demand, network capacity, and time profiles.
Plant allowances use gross actual generation and served demand. They express
eligible source/sink accounting, not a trace of which physical electrons reach
an individual battery or a requirement to serve plant loads before charging.

Each test documents its setup, expected result, and the specific regression it
would catch. Parameterization repeats the same reasoning across the stated
modes, operating directions, dispatch formulations, or selected time windows.
"""

from typing import Dict, List, Tuple

import numpy as np
import pytest

import VeraGridEngine.api as vg
from VeraGridEngine.enumerations import BatteryDispatchMode, OpfDispatchMode, DeviceType
from VeraGridEngine.Devices.multi_circuit import FacilityDispatchGroup
from VeraGridEngine.Simulations.OPF.Formulations.linear_opf_ts import run_linear_opf_ts


def make_facility_grid(mode: BatteryDispatchMode, charging: bool, count: int = 1) -> vg.MultiCircuit:
    """Build the shared one-bus circuit used by the focused tests.

    Setup: The single 10 kV bus has one facility containing a 3 MW static
    generator, a 4 MW load, and the requested number of batteries. Another
    30 MW load and a 100 MW dispatchable generator have no facility. Thus
    every device is electrically connected, but only the assigned solar
    and load contribute to the plant's charging and discharge allowances.

    Each battery has a 100 MWh capacity, starts at 50 MWh, can exchange
    10 MW in either direction, and has unit charge/discharge efficiency.
    Two hourly profile entries are available; most tests solve the first.
    Energy availability therefore does not limit those basic mode tests.

    The grid generator costs -100 when charging is requested and +100
    when discharge is requested. Those prices encourage the optimizer to
    reach the allowed battery limit. Load shedding costs 10000, making
    serving demand preferable. Individual tests explicitly change these
    defaults when testing shedding, energy limits, or device availability.

    This helper constructs the input only. The tests below establish
    which dispatch results are expected from each policy.

    :param mode: Battery operating policy.
    :param charging: Whether grid prices encourage charging rather than discharge.
    :param count: Number of batteries sharing the facility budget.
    :return: One-bus circuit with two hourly profile entries.
    """
    grid: vg.MultiCircuit = vg.MultiCircuit()
    grid.create_profiles(steps=2, step_length=1, step_unit="h")
    bus: vg.Bus = grid.add_bus(vg.Bus(name="Bus", Vnom=10.0))
    facility: vg.Facility = vg.Facility(name="Plant")
    grid.add_facility(facility)
    local_load: vg.Load = grid.add_load(bus=bus, api_obj=vg.Load(P=4.0, Cost=10000.0))
    local_load.facility = facility
    grid.add_load(bus=bus, api_obj=vg.Load(P=30.0, Cost=10000.0))
    grid.add_generator(bus=bus, api_obj=vg.Generator(Pmin=0.0, Pmax=100.0,
                                                   Cost=-100.0 if charging else 100.0))
    solar: vg.StaticGenerator = grid.add_static_generator(bus=bus,
                                                          api_obj=vg.StaticGenerator(P=3.0))
    solar.facility = facility
    for k in range(count):
        battery: vg.Battery = grid.add_battery(bus=bus, api_obj=vg.Battery(
            name=f"Battery {k}", Pmin=-10.0, Pmax=10.0, Enom=100.0, soc=0.5,
            min_soc=0.0, max_soc=1.0, charge_efficiency=1.0, discharge_efficiency=1.0,
            Cost=1.0, dispatch_mode=mode))
        battery.facility = facility
    return grid


@pytest.mark.parametrize("mode", tuple(BatteryDispatchMode))
@pytest.mark.parametrize("charging", (True, False))
@pytest.mark.parametrize("dispatch", (OpfDispatchMode.Normal, OpfDispatchMode.UnitCommitment))
def test_facility_battery_modes(mode: BatteryDispatchMode, charging: bool, dispatch: OpfDispatchMode) -> None:
    """Check the complete operating-policy table on the shared one-bus grid.

    Setup: One assigned 10 MW battery shares a facility with 3 MW solar
    and 4 MW demand. An unassigned generator and 30 MW external demand
    make grid exchange available in both directions. Each of the three
    battery modes is tested with prices encouraging charging and prices
    encouraging discharge, under both Normal and UnitCommitment dispatch.

    Expected: Grid mode charges at 10 MW or discharges at 10 MW. Both
    plant-charging modes charge at only 3 MW. PlantChargeGridDischarge
    can still discharge at 10 MW, whereas PlantChargeAndDisCharge can
    discharge at only 4 MW to match the facility's own demand.

    This proves that each enum selects its specified directional limits
    in both formulations. The unrelated generator and load cannot enlarge
    a restricted plant allowance, despite sharing the same bus. These
    expectations use gross plant production and demand; they do not
    impose a local-load-first charging priority.

    :param mode: Battery operating policy.
    :param charging: Direction encouraged by the grid price.
    :param dispatch: Normal dispatch or unit commitment formulation.
    :return: None.
    """
    grid: vg.MultiCircuit = make_facility_grid(mode=mode, charging=charging)
    result, _model = run_linear_opf_ts(grid=grid, time_indices=np.array((0,), dtype=int), dispatch_mode=dispatch)
    expected: float = -10.0 if charging else 10.0
    if charging and mode != BatteryDispatchMode.Grid:
        expected = -3.0
    elif not charging and mode == BatteryDispatchMode.PlantChargeAndDisCharge:
        expected = 4.0
    else:
        pass
    assert result.acceptable_solution
    assert np.isclose(result.batt_vars.p[0, 0], expected)


@pytest.mark.parametrize("charging", (True, False))
def test_facility_budget_is_shared(charging: bool) -> None:
    """Check that two batteries share one production and demand allowance.

    Setup: Two identical 10 MW batteries use PlantChargeAndDisCharge and
    belong to the same facility. Its total solar output is still 3 MW
    and its total load is still 4 MW. Prices separately encourage maximum
    charging and maximum discharge.

    Expected: The sum of the two battery powers is -3 MW when charging
    and +4 MW when discharging. Giving each battery its own copy of the
    allowance would incorrectly permit -6 MW or +8 MW.

    This proves that the limit applies to the facility total. The test
    deliberately does not require a particular split between identical
    batteries: either allocation is valid provided the shared total is
    correct.

    :param charging: Direction encouraged by the grid price.
    :return: None.
    """
    grid: vg.MultiCircuit = make_facility_grid(BatteryDispatchMode.PlantChargeAndDisCharge,
                                              charging=charging, count=2)
    result, _model = run_linear_opf_ts(grid=grid, time_indices=np.array((0,), dtype=int))
    assert result.acceptable_solution
    assert np.isclose(np.sum(result.batt_vars.p[0]), -3.0 if charging else 4.0)


@pytest.mark.parametrize("charging", (True, False))
@pytest.mark.parametrize("mode", tuple(BatteryDispatchMode))
def test_missing_facility_opts_out(charging: bool, mode: BatteryDispatchMode) -> None:
    """Check that an unassigned battery opts out of every plant policy.

    Setup: Start with the one-bus circuit, then set the battery's facility
    to None while leaving the solar and local load assigned. Repeat for
    all three battery modes and for both charging and discharge prices.
    The battery retains its 10 MW power limit and sufficient stored energy.

    Expected: The battery charges at 10 MW or discharges at 10 MW in
    every mode, rather than inheriting the nearby plant's 3 MW or 4 MW
    limits. The logger must not report a missing-facility warning.

    This proves that None is an intentional opt-out, not an invalid
    configuration or an implicit shared plant. The battery remains subject
    to its ordinary device and network constraints.

    :param charging: Direction encouraged by the grid price.
    :param mode: Policy ignored when the battery has no facility.
    :return: None.
    """
    grid: vg.MultiCircuit = make_facility_grid(mode,
                                              charging=charging)
    grid.get_batteries()[0].facility = None
    logger: vg.Logger = vg.Logger()
    result, _model = run_linear_opf_ts(grid=grid, time_indices=np.array((0,), dtype=int), logger=logger)
    assert result.acceptable_solution
    assert np.isclose(result.batt_vars.p[0, 0], -10.0 if charging else 10.0)
    assert not any(entry.msg == "Plant battery dispatch requires a facility" for entry in logger.entries)


@pytest.mark.parametrize("selected", (True, False))
def test_facility_dispatch_uses_global_profile_index(selected: bool) -> None:
    """Check mode changes and the distinction between local and global time indices.

    Setup: Negative grid prices encourage charging. The battery's snapshot
    mode is Grid, but its two profile entries are Grid followed by
    PlantChargeGridDischarge. The plant produces 3 MW at both times.
    Solve either both hours or only global time index one.

    Expected: The full run charges at 10 MW in the first hour and 3 MW
    in the second. The selected-hour run charges at 3 MW even though
    that hour occupies local result row zero.

    This proves that the formulation reads the mode profile at the global
    simulation index, rather than using the snapshot mode, the first
    profile entry, or a grouping decision frozen at the start of dispatch.

    :param selected: Whether to solve only the second step or the complete profile.
    :return: None.
    """
    grid: vg.MultiCircuit = make_facility_grid(BatteryDispatchMode.Grid, charging=True)
    grid.get_batteries()[0].dispatch_mode_prof = np.array(
        (BatteryDispatchMode.Grid, BatteryDispatchMode.PlantChargeGridDischarge), dtype=object)
    indices: np.ndarray = np.array((1,) if selected else (0, 1), dtype=int)
    result, _model = run_linear_opf_ts(grid=grid, time_indices=indices)
    assert result.acceptable_solution
    assert np.allclose(result.batt_vars.p[:, 0], (-3.0,) if selected else (-10.0, -3.0))


@pytest.mark.parametrize("reversible", (True, False))
@pytest.mark.parametrize("charging", (True, False))
def test_facility_uses_dispatched_generator_power(reversible: bool, charging: bool) -> None:
    """Check actual generator output and the sign of reversible operation.

    Setup: Disable the plant's solar and add a dispatchable plant generator
    with a 10 MW maximum and a marginal cost of 200. The grid generator
    is cheaper, so ordinary local generation remains at zero. In the
    reversible variant the local minimum is -3 MW: consuming 3 MW gives
    a negative generation-cost contribution and is selected by the model.
    The battery is local-only and the original plant load remains 4 MW.

    Expected: The local generator is at zero in the ordinary variant
    and -3 MW in the reversible variant. Neither can fund battery charging,
    so battery power is zero in the charging-price run. In discharge runs
    the battery supplies 4 MW of local load, or 7 MW when the reversible
    generator adds 3 MW of plant consumption.

    This proves that unused nameplate capacity is not counted as charging
    supply. Negative generator output is treated as demand rather than
    invented production, and the test verifies the generator's solved
    output as well as the battery result.

    :param reversible: Whether the generator can consume power.
    :param charging: Direction encouraged by the grid price.
    :return: None.
    """
    grid: vg.MultiCircuit = make_facility_grid(BatteryDispatchMode.PlantChargeAndDisCharge,
                                              charging=charging)
    grid.get_static_generators()[0].active = False
    grid.get_static_generators()[0].active_prof = np.zeros(2, dtype=bool)
    generator: vg.Generator = grid.add_generator(bus=grid.buses[0], api_obj=vg.Generator(
        Pmin=-3.0 if reversible else 0.0, Pmax=10.0, Cost=200.0))
    generator.facility = grid.get_batteries()[0].facility
    result, _model = run_linear_opf_ts(grid=grid, time_indices=np.array((0,), dtype=int))
    expected: float = 0.0 if charging else (7.0 if reversible else 4.0)
    assert result.acceptable_solution
    assert np.isclose(result.batt_vars.p[0, 0], expected)
    assert np.isclose(result.gen_vars.p[0, 1], -3.0 if reversible else 0.0)


def test_grid_discharge_remains_allowed_without_facility() -> None:
    """Check the None opt-out through the snapshot execution path.

    Setup: Give the battery PlantChargeGridDischarge mode, remove its
    facility association, and use positive grid-generation costs so that
    battery discharge is useful. Call run_linear_opf_ts with time_indices
    set to None instead of selecting profile indices.

    Expected: The solver finds an acceptable solution with 10 MW battery
    discharge, equal to the device's own power limit.

    This proves that unassigned batteries can operate normally in snapshot
    studies as well as the time-series cases tested elsewhere. This case
    specifically exercises discharge; charging opt-out is covered by the
    parameterized test_missing_facility_opts_out test.

    :return: None.
    """
    grid: vg.MultiCircuit = make_facility_grid(BatteryDispatchMode.PlantChargeGridDischarge,
                                              charging=False)
    grid.get_batteries()[0].facility = None
    result, _model = run_linear_opf_ts(grid=grid, time_indices=None)
    assert result.acceptable_solution
    assert np.isclose(result.batt_vars.p[0, 0], 10.0)


def test_facilities_do_not_share_budgets() -> None:
    """Check facility isolation even when both plants share the same bus.

    Setup: Create two plant-charging, grid-discharging batteries. Keep the
    first battery with the original 3 MW solar generator, then move the
    second battery to a newly created facility with no generation. Both
    batteries remain on the same electrical bus. Negative prices encourage
    both batteries to charge as much as their policies permit.

    Expected: The first battery charges at 3 MW and the second remains
    at zero. The unassigned grid generator cannot fund the second plant.

    This proves that facility identity, rather than bus connectivity or
    proximity to generation, determines which source allowance a battery
    can use.

    :return: None.
    """
    grid: vg.MultiCircuit = make_facility_grid(BatteryDispatchMode.PlantChargeGridDischarge,
                                              charging=True, count=2)
    second: vg.Facility = vg.Facility(name="Second plant")
    grid.add_facility(second)
    grid.get_batteries()[1].facility = second
    result, _model = run_linear_opf_ts(grid=grid, time_indices=np.array((0,), dtype=int))
    assert result.acceptable_solution
    assert np.allclose(result.batt_vars.p[0], (-3.0, 0.0))


@pytest.mark.parametrize("charging", (True, False))
def test_fixed_power_battery_obeys_facility_budget(charging: bool) -> None:
    """Check that fixed battery profiles cannot bypass plant limits.

    Setup: The battery uses PlantChargeAndDisCharge, but dispatchability
    is disabled in both its snapshot setting and profile. Request a fixed
    10 MW charge or discharge. The plant still has only 3 MW generation
    and 4 MW demand. The existing battery-schedule shedding variables
    allow the optimizer to reduce an unsupported request.

    Expected: Charging is reduced to 3 MW with 7 MW of schedule shedding.
    Discharge is reduced to 4 MW with 6 MW of schedule shedding. The
    resulting optimization must remain feasible.

    This proves that the facility constraints apply to fixed schedules as
    well as freely dispatched batteries, and that excess requests are
    accounted for through the existing shedding mechanism.

    :param charging: Direction of the fixed battery schedule.
    :return: None.
    """
    grid: vg.MultiCircuit = make_facility_grid(BatteryDispatchMode.PlantChargeAndDisCharge,
                                              charging=charging)
    battery: vg.Battery = grid.get_batteries()[0]
    battery.enabled_dispatch = False
    battery.enabled_dispatch_prof = np.zeros(2, dtype=bool)
    battery.P = -10.0 if charging else 10.0
    battery.P_prof = np.full(2, battery.P)
    result, _model = run_linear_opf_ts(grid=grid, time_indices=np.array((0,), dtype=int))
    assert result.acceptable_solution
    assert np.isclose(result.batt_vars.p[0, 0], -3.0 if charging else 4.0)
    assert np.isclose(result.batt_vars.shedding[0, 0], 7.0 if charging else 6.0)


def test_shed_demand_cannot_fund_battery_discharge() -> None:
    """Check that only served plant load permits local-only discharge.

    Setup: Use the local-only battery and positive grid-generation costs,
    but change the 4 MW plant load's shedding cost to -1000. This deliberate
    synthetic incentive makes shedding all of that load optimal. The
    unrelated 30 MW load retains its high shedding cost, so there is
    still external demand that would otherwise benefit from discharge.

    Expected: Exactly 4 MW of local demand is shed and battery discharge
    is zero, although the original local load profile still says 4 MW.

    This proves that the discharge allowance follows solved, served load
    after shedding. Using the input demand directly would incorrectly let
    the battery export power against a plant load that is no longer served.

    :return: None.
    """
    grid: vg.MultiCircuit = make_facility_grid(BatteryDispatchMode.PlantChargeAndDisCharge,
                                              charging=False)
    grid.get_loads()[0].Cost = -1000.0
    grid.get_loads()[0].Cost_prof = np.full(2, -1000.0)
    result, _model = run_linear_opf_ts(grid=grid, time_indices=np.array((0,), dtype=int))
    assert result.acceptable_solution
    assert np.isclose(result.load_vars.shedding[0, 0], 4.0)
    assert np.isclose(result.batt_vars.p[0, 0], 0.0)


def test_facility_groups_preserve_objects_and_compiled_indices() -> None:
    """Check the grouping data structure without solving an optimization.

    Setup: Create two assigned batteries and append a local generator
    after the unassigned grid generator. The load-like compilation order
    is local load, unrelated load, then static generator. Build the
    facility dictionary through MultiCircuit.

    Expected: There is one group. Its battery dictionary contains the
    original objects at indices zero and one. Its generator dictionary
    contains only the added local generator at index one. Its load-like
    dictionary contains the local load at index zero and solar at index
    two. Unassigned devices are absent.

    This proves that grouping preserves both object references and original
    compiled-array indices. In particular, filtering devices must not
    renumber the local generator to zero or the solar to one.

    :return: None.
    """
    grid: vg.MultiCircuit = make_facility_grid(BatteryDispatchMode.Grid, charging=True, count=2)
    generator: vg.Generator = grid.add_generator(bus=grid.buses[0], api_obj=vg.Generator())
    generator.facility = grid.get_batteries()[0].facility
    groups: Dict[vg.Facility, FacilityDispatchGroup] = grid.build_facility_dispatch_groups()
    assert len(groups) == 1
    assert groups[grid.get_batteries()[0].facility].batteries == dict(((grid.get_batteries()[0], 0), (grid.get_batteries()[1], 1)))
    assert groups[grid.get_batteries()[0].facility].generators == dict(((generator, 1),))
    # Static generators follow all ordinary loads in the compiled load array.
    assert groups[grid.get_batteries()[0].facility].loads == dict(((grid.get_loads()[0], 0), (grid.get_static_generators()[0], 2)))


def test_facility_groups_keep_unassigned_batteries_without_resources() -> None:
    """Check that None never becomes a facility dictionary key.

    Setup: Create two batteries in the shared one-bus fixture, then set
    both facility references to None. Keep the original assigned solar
    and load in the circuit and build the dispatch groups directly.

    Expected: The resulting facility dictionary is empty, because there
    are no assigned batteries requiring a plant dispatch group.

    This proves that unassigned batteries are excluded rather than pooled
    into an artificial None facility. It checks membership construction;
    their unrestricted operation is checked separately by the opt-out
    dispatch tests.

    :return: None.
    """
    grid: vg.MultiCircuit = make_facility_grid(BatteryDispatchMode.Grid, charging=True, count=2)
    for battery in grid.get_batteries():
        battery.facility = None
    groups: Dict[vg.Facility, FacilityDispatchGroup] = grid.build_facility_dispatch_groups()
    assert groups == dict()


def test_facility_groups_are_keyed_by_facility_not_battery_order() -> None:
    """Check lookup by facility identity when battery ordering differs.

    Setup: Start with two batteries in the first facility. Add a second
    facility, then move battery zero into it while battery one stays in
    the first. The solar and local load remain in the first facility.
    Therefore the first battery encountered belongs to the second facility.

    Expected: Looking up the second facility returns battery zero and
    no loads. Looking up the first returns battery one plus the original
    local load and static generator at their unchanged compilation indices.

    This proves that callers can use the actual Facility objects as keys.
    Neither battery order nor dictionary insertion order is interpreted
    as the index of a facility.

    :return: None.
    """
    grid: vg.MultiCircuit = make_facility_grid(BatteryDispatchMode.Grid, charging=True, count=2)
    first: vg.Facility = grid.get_facilities()[0]
    second: vg.Facility = vg.Facility(name="Second plant")
    grid.add_facility(second)
    grid.get_batteries()[0].facility = second
    groups: Dict[vg.Facility, FacilityDispatchGroup] = grid.build_facility_dispatch_groups()
    assert groups[second].batteries == dict(((grid.get_batteries()[0], 0),))
    assert groups[first].batteries == dict(((grid.get_batteries()[1], 1),))
    assert groups[second].loads == dict()
    assert groups[first].loads == dict(((grid.get_loads()[0], 0), (grid.get_static_generators()[0], 2)))


def make_two_plant_grid(charging: bool) -> vg.MultiCircuit:
    """Build the shared three-bus circuit for combined plant and network tests.

    Setup: A grid bus connects to separate A and B buses through lossless
    lines with reactance 0.1 and 200 MW ratings. Plant A has 2 MW fixed
    generation, 3 MW solar, and 4 MW demand. Plant B has 7 MW solar and
    6 MW demand. The grid bus has 80 MW unrelated demand and an unassigned
    200 MW generator with a cost of -100 for charging or +100 for discharge.
    Local loads cost 10000 to shed; A's fixed generation costs 1000 to
    curtail, so the basic cases retain that source.

    Six batteries are deliberately interleaved in compilation order:
    index zero is A local-only; one is B local-only; two is A plant-charge,
    grid-discharge; three is B Grid; four is unassigned local-only; five
    is A Grid. Each has a 10 MW limit, 100 MWh capacity, 50 MWh initial
    energy, and unit efficiencies. The registered facility order is B
    then A, unlike the first appearance of batteries in the device list.

    Three hourly profile entries are available. Basic combined tests solve
    the first; profile tests change individual sources, loads, modes, and
    active states. The mixture lets assertions distinguish shared plant
    budgets from physical bus balance, grid permissions, and the None
    opt-out without relying on a particular allocation between equivalent
    restricted batteries.

    :param charging: Whether negative grid prices encourage charging.
    :return: Three-hour circuit with all three modes and an unassigned battery.
    """
    grid: vg.MultiCircuit = vg.MultiCircuit()
    grid.create_profiles(steps=3, step_length=1, step_unit="h")
    grid_bus: vg.Bus = grid.add_bus(vg.Bus(name="Grid", Vnom=10.0))
    bus_a: vg.Bus = grid.add_bus(vg.Bus(name="Plant A bus", Vnom=10.0))
    bus_b: vg.Bus = grid.add_bus(vg.Bus(name="Plant B bus", Vnom=10.0))
    grid.add_line(vg.Line(bus_from=grid_bus, bus_to=bus_a, name="Grid to A", x=0.1, rate=200.0))
    grid.add_line(vg.Line(bus_from=grid_bus, bus_to=bus_b, name="Grid to B", x=0.1, rate=200.0))
    plant_a: vg.Facility = vg.Facility(name="Plant A")
    plant_b: vg.Facility = vg.Facility(name="Plant B")
    # Facility order deliberately differs from first appearance in the battery list.
    grid.add_facility(plant_b)
    grid.add_facility(plant_a)
    grid.add_generator(bus=grid_bus, api_obj=vg.Generator(
        name="Grid generator", Pmin=0.0, Pmax=200.0, Cost=-100.0 if charging else 100.0))
    local_generator: vg.Generator = grid.add_generator(bus=bus_a, api_obj=vg.Generator(
        name="A fixed generation", enabled_dispatch=False, P=2.0, Pmin=0.0, Pmax=2.0, Cost=1000.0))
    local_generator.facility = plant_a
    solar_a: vg.StaticGenerator = grid.add_static_generator(bus=bus_a, api_obj=vg.StaticGenerator(P=3.0))
    solar_a.facility = plant_a
    solar_b: vg.StaticGenerator = grid.add_static_generator(bus=bus_b, api_obj=vg.StaticGenerator(P=7.0))
    solar_b.facility = plant_b
    load_a: vg.Load = grid.add_load(bus=bus_a, api_obj=vg.Load(P=4.0, Cost=10000.0))
    load_a.facility = plant_a
    load_b: vg.Load = grid.add_load(bus=bus_b, api_obj=vg.Load(P=6.0, Cost=10000.0))
    load_b.facility = plant_b
    grid.add_load(bus=grid_bus, api_obj=vg.Load(P=80.0, Cost=10000.0))
    # Same plant, different modes; same bus, different memberships; unrelated indices.
    specifications: List[Tuple[vg.Bus, vg.Facility | None, BatteryDispatchMode]] = list((
        (bus_a, plant_a, BatteryDispatchMode.PlantChargeAndDisCharge),
        (bus_b, plant_b, BatteryDispatchMode.PlantChargeAndDisCharge),
        (bus_a, plant_a, BatteryDispatchMode.PlantChargeGridDischarge),
        (bus_b, plant_b, BatteryDispatchMode.Grid),
        (grid_bus, None, BatteryDispatchMode.PlantChargeAndDisCharge),
        (bus_a, plant_a, BatteryDispatchMode.Grid),
    ))
    for k, (bus, facility, mode) in enumerate(specifications):
        battery: vg.Battery = grid.add_battery(bus=bus, api_obj=vg.Battery(
            name=f"Battery {k}", Pmin=-10.0, Pmax=10.0, Enom=100.0, soc=0.5,
            min_soc=0.0, max_soc=1.0, charge_efficiency=1.0, discharge_efficiency=1.0,
            Cost=1.0, dispatch_mode=mode))
        battery.facility = facility
    return grid


@pytest.mark.parametrize("charging", (True, False))
@pytest.mark.parametrize("dispatch", (OpfDispatchMode.Normal, OpfDispatchMode.UnitCommitment))
def test_two_plants_with_mixed_battery_modes(charging: bool, dispatch: OpfDispatchMode) -> None:
    """Check both plants, all modes, and network balance in one solved grid.

    Setup: Use the three-bus fixture with six interleaved batteries and
    two independent plants. Run the first hour with prices encouraging
    either charging or discharge, under Normal and UnitCommitment dispatch.
    A has 5 MW total generation and 4 MW demand; B has 7 MW generation
    and 6 MW demand. Batteries three and five are Grid mode; battery four
    has None as its facility and therefore opts out.

    Expected when charging: A's restricted batteries zero and two share
    5 MW, B's local-only battery charges at 7 MW, and the three unrestricted
    batteries charge at 10 MW each. Total battery charging is 42 MW.
    Total demand is 90 MW and local generation is 12 MW, so the grid
    generator supplies 90 + 42 - 12 = 120 MW.

    Expected when discharging: A's local-only battery supplies 4 MW and
    its export-capable battery supplies 10 MW. B's local-only battery
    supplies 6 MW. The unrestricted batteries supply 10 MW each, giving
    50 MW total battery discharge and 90 - 12 - 50 = 28 MW grid generation.

    The assertions also check zero load shedding, battery energy equal
    to 50 MWh minus the one-hour discharge, each plant bus's line-flow
    balance, and whole-grid power balance. Together these establish that
    separate plant budgets, mixed permissions, the None opt-out, compiled
    indices, energy accounting, and the physical network work together.
    A's individual charging split is intentionally left unspecified.

    :param charging: Direction encouraged by the grid price.
    :param dispatch: Normal dispatch or unit commitment.
    :return: None.
    """
    grid: vg.MultiCircuit = make_two_plant_grid(charging)
    result, _model = run_linear_opf_ts(grid, np.array((0,), dtype=int), dispatch_mode=dispatch)
    power: np.ndarray = result.batt_vars.p[0]
    assert result.acceptable_solution
    assert np.allclose(result.load_vars.shedding, 0.0)
    assert np.allclose(result.gen_vars.p[0], (120.0, 2.0) if charging else (28.0, 2.0))
    assert np.isclose(power[0] + power[2], -5.0 if charging else 14.0)
    assert np.isclose(power[1], -7.0 if charging else 6.0)
    assert np.allclose(power[np.array((3, 4, 5))], -10.0 if charging else 10.0)
    if charging:
        assert np.all(power[np.array((0, 2))] <= 1e-6)
    else:
        assert np.isclose(power[0], 4.0)
        assert np.isclose(power[2], 10.0)
    # With unit efficiencies and a one-hour interval, energy changes by minus power.
    assert np.allclose(result.batt_vars.e[0], 50.0 - power)
    # Independent bus balances verify that plant budgets coexist with network flows.
    assert np.isclose(result.branch_vars.flows[0, 0], 4.0 - 5.0 - np.sum(power[np.array((0, 2, 5))]))
    assert np.isclose(result.branch_vars.flows[0, 1], 6.0 - 7.0 - np.sum(power[np.array((1, 3))]))
    assert np.isclose(np.sum(result.gen_vars.p[0]) + 10.0 + np.sum(power), 90.0)


@pytest.mark.parametrize("charging", (True, False))
def test_network_limits_still_apply_to_plant_dispatch(charging: bool) -> None:
    """Check a binding network constraint alongside plant dispatch limits.

    Setup: Use the three-bus fixture but reduce only B's grid connection
    to 4 MW. Set its overload cost to 10000 so violating that soft limit
    is more expensive than the gain from battery arbitrage. B still has
    7 MW generation, 6 MW demand, one local-only battery, and one Grid
    battery. Run once with charging prices and once with discharge prices.

    Expected: B has a baseline 1 MW surplus. With at most 4 MW import,
    its two batteries can charge at only 1 + 4 = 5 MW combined. With at
    most 4 MW export, they can discharge at only 4 - 1 = 3 MW combined.
    The line flow must be +4 MW for charging and -4 MW for discharge.

    Zero load shedding and zero positive/negative flow slacks establish
    that these results respect the line rating without buying an overload
    or dropping demand. This proves that a plant allowance is an upper
    bound on eligible battery operation, not permission to bypass network
    capacity. The split between B's batteries need not be unique.

    :param charging: Direction encouraged by the grid price.
    :return: None.
    """
    grid: vg.MultiCircuit = make_two_plant_grid(charging)
    grid.get_lines()[1].rate = 4.0
    grid.get_lines()[1].rate_prof = np.full(3, 4.0)
    # Overloads are soft constraints: make violations more expensive than arbitrage.
    grid.get_lines()[1].Cost = 10000.0
    grid.get_lines()[1].Cost_prof = np.full(3, 10000.0)
    result, _model = run_linear_opf_ts(grid, np.array((0,), dtype=int))
    assert result.acceptable_solution
    assert np.allclose(result.load_vars.shedding, 0.0)
    assert np.isclose(result.batt_vars.p[0, 1] + result.batt_vars.p[0, 3], -5.0 if charging else 3.0)
    assert np.isclose(result.branch_vars.flows[0, 1], 4.0 if charging else -4.0)
    assert np.allclose(result.branch_vars.flow_slacks_pos, 0.0)
    assert np.allclose(result.branch_vars.flow_slacks_neg, 0.0)


@pytest.mark.parametrize("charging", (True, False))
@pytest.mark.parametrize("selected", (True, False))
def test_two_plant_profiles_update_every_step(charging: bool, selected: bool) -> None:
    """Check changing allowances and mode profiles across several hours.

    Setup: Modify the three-bus fixture so A's production is [5, 0, 2]
    MW and demand is [4, 1, 0] MW. Its export-capable battery switches
    through plant-charge/grid-discharge, Grid, then local-only modes.
    B's production is [7, 1, 0] MW and demand [6, 2, 0] MW; its local-only
    battery is inactive in the middle hour. Run either all three hours
    or only global indices one and two, with charging or discharge prices.

    Expected when charging: A's two nonpermanent-Grid batteries have
    combined powers [-5, -10, -2] MW. The middle -10 MW comes entirely
    from the battery temporarily in Grid mode. B's local-only battery
    has powers [-7, 0, 0] MW. Grid generation is [120, 122, 110] MW.

    Expected when discharging: The corresponding A totals are [14, 11, 0]
    MW and B's local-only powers are [6, 0, 0] MW. Grid generation is
    [28, 41, 48] MW. The permanently Grid-mode and unassigned batteries
    exchange 10 MW each in the encouraged direction throughout both runs.

    This proves that cached membership does not freeze production, demand,
    active states, or operating policies. Selecting a later time window
    must use the matching global profile entries. Stored energy is checked
    by cumulative battery power for batteries active throughout the window.
    The selected-window run deliberately starts from the configured initial
    energy; this test does not simulate carrying energy from a prior run.

    :param charging: Direction encouraged by the grid price.
    :param selected: Whether the solve starts at global index one.
    :return: None.
    """
    grid: vg.MultiCircuit = make_two_plant_grid(charging)
    grid.get_generators()[1].active_prof = np.array((True, False, True))
    grid.get_static_generators()[0].active_prof = np.array((True, True, False))
    grid.get_static_generators()[0].P_prof = np.array((3.0, 0.0, 3.0))
    grid.get_static_generators()[1].P_prof = np.array((7.0, 1.0, 0.0))
    grid.get_loads()[0].P_prof = np.array((4.0, 1.0, 0.0))
    grid.get_loads()[1].P_prof = np.array((6.0, 2.0, 0.0))
    grid.get_batteries()[1].active_prof = np.array((True, False, True))
    grid.get_batteries()[2].dispatch_mode_prof = np.array((
        BatteryDispatchMode.PlantChargeGridDischarge,
        BatteryDispatchMode.Grid,
        BatteryDispatchMode.PlantChargeAndDisCharge,
    ), dtype=object)
    indices: np.ndarray = np.array((1, 2) if selected else (0, 1, 2), dtype=int)
    result, _model = run_linear_opf_ts(grid, indices)
    power: np.ndarray = result.batt_vars.p
    expected_a: np.ndarray = np.array((-5.0, -10.0, -2.0) if charging else (14.0, 11.0, 0.0))
    expected_b: np.ndarray = np.array((-7.0, 0.0, 0.0) if charging else (6.0, 0.0, 0.0))
    expected_grid: np.ndarray = np.array((120.0, 122.0, 110.0) if charging else (28.0, 41.0, 48.0))
    assert result.acceptable_solution
    assert np.allclose(result.load_vars.shedding, 0.0)
    assert np.allclose(power[:, 0] + power[:, 2], expected_a[indices])
    assert np.allclose(power[:, 1], expected_b[indices])
    assert np.allclose(result.gen_vars.p[:, 0], expected_grid[indices])
    assert np.allclose(power[:, np.array((3, 4, 5))], -10.0 if charging else 10.0)
    # Check energy continuity for the batteries active throughout the modeled window.
    assert np.allclose(result.batt_vars.e[:, np.array((0, 2, 3, 4, 5))],
                       50.0 - np.cumsum(power[:, np.array((0, 2, 3, 4, 5))], axis=0))


@pytest.mark.parametrize("device_type", (DeviceType.GeneratorDevice, DeviceType.StaticGeneratorDevice,
                                          DeviceType.LoadDevice))
@pytest.mark.parametrize("charging", (True, False))
@pytest.mark.parametrize("unassigned", (True, False))
def test_opted_out_and_inactive_devices_do_not_fund_plant_batteries(
        device_type: DeviceType, charging: bool, unassigned: bool) -> None:
    """Check removing one resource from A without changing B's permissions.

    Setup: Use the three-bus fixture and select A's 2 MW fixed generator,
    its 3 MW solar generator, or its 4 MW load. Remove the selected device
    from plant accounting either by setting facility=None, which leaves
    it electrically connected, or by setting its active state false in
    both the snapshot and profile. Repeat with charging and discharge prices.

    Expected: Removing the 2 MW generator reduces A's restricted charging
    total from 5 MW to 3 MW. Removing the 3 MW solar reduces it to 2 MW.
    Neither change reduces A's 14 MW permitted discharge total, because
    its 4 MW local load and 10 MW export-capable battery remain available.
    Removing A's load leaves its 5 MW charging allowance intact but reduces
    discharge to 10 MW, supplied entirely by the export-capable battery.

    In every variant B's local-only battery still charges at 7 MW or
    discharges at 6 MW; the three unrestricted batteries still exchange
    10 MW each, and no load is shed. This proves that resource membership
    and availability are evaluated independently, that None opts a resource
    out of the allowance without disconnecting it, and that A's changes
    cannot alter B's eligible production or demand.

    :param device_type: Resource to remove from A's allowance.
    :param charging: Direction encouraged by the grid price.
    :param unassigned: Whether to opt out with None or deactivate the resource.
    :return: None.
    """
    grid: vg.MultiCircuit = make_two_plant_grid(charging)
    device: vg.Generator | vg.StaticGenerator | vg.Load
    expected_charge: float = -5.0
    expected_discharge: float = 14.0
    if device_type == DeviceType.GeneratorDevice:
        device = grid.get_generators()[1]
        expected_charge = -3.0
    elif device_type == DeviceType.StaticGeneratorDevice:
        device = grid.get_static_generators()[0]
        expected_charge = -2.0
    else:
        device = grid.get_loads()[0]
        expected_discharge = 10.0
    if unassigned:
        device.facility = None
    else:
        device.active = False
        device.active_prof = np.zeros(3, dtype=bool)
    result, _model = run_linear_opf_ts(grid, np.array((0,), dtype=int))
    assert result.acceptable_solution
    assert np.allclose(result.load_vars.shedding, 0.0)
    assert np.isclose(result.batt_vars.p[0, 0] + result.batt_vars.p[0, 2],
                      expected_charge if charging else expected_discharge)
    assert np.isclose(result.batt_vars.p[0, 1], -7.0 if charging else 6.0)
    assert np.allclose(result.batt_vars.p[0, np.array((3, 4, 5))], -10.0 if charging else 10.0)


@pytest.mark.parametrize("mode", tuple(BatteryDispatchMode))
@pytest.mark.parametrize("charging", (True, False))
def test_assigned_battery_without_plant_resources(mode: BatteryDispatchMode, charging: bool) -> None:
    """Distinguish an empty plant from a battery with no assigned plant.

    Setup: Keep the battery assigned to its facility, but set the 3 MW
    solar generator and 4 MW load facilities to None. They remain connected
    at the same bus, alongside the unassigned grid generator and external
    demand. Repeat for all battery modes and both encouraged directions.

    Expected: Grid mode still exchanges 10 MW in either direction.
    PlantChargeGridDischarge cannot charge but can discharge at 10 MW.
    PlantChargeAndDisCharge cannot charge or discharge because its plant
    now has neither an eligible source nor an eligible sink. No load sheds.

    This proves that opting out a source or load does not opt out an
    assigned battery. Physical connectivity and nearby unassigned devices
    cannot supply missing plant allowances; the allowed grid-export
    direction remains available where the battery mode explicitly permits it.

    :param mode: Battery operating policy.
    :param charging: Direction encouraged by the grid price.
    :return: None.
    """
    grid: vg.MultiCircuit = make_facility_grid(mode, charging)
    grid.get_static_generators()[0].facility = None
    grid.get_loads()[0].facility = None
    result, _model = run_linear_opf_ts(grid, np.array((0,), dtype=int))
    expected: float = 0.0
    if mode == BatteryDispatchMode.Grid:
        expected = -10.0 if charging else 10.0
    elif mode == BatteryDispatchMode.PlantChargeGridDischarge and not charging:
        expected = 10.0
    else:
        pass
    assert result.acceptable_solution
    assert np.isclose(result.batt_vars.p[0, 0], expected)
    assert np.allclose(result.load_vars.shedding, 0.0)


@pytest.mark.parametrize("charging", (True, False))
def test_plant_limits_preserve_soc_and_efficiencies(charging: bool) -> None:
    """Check device energy limits when they are tighter than plant allowances.

    Setup: Use a local-only battery with a fixed 10 MW charge or discharge
    request, disabling free dispatch in its snapshot and profile. Set
    charge efficiency to 0.8 and discharge efficiency to 0.9. The plant
    retains its 3 MW generation and 4 MW load. The one-hour charging run
    starts at 98 MWh; the discharge run starts at 2 MWh.

    Expected when charging: Only 2 MWh of storage headroom remains, so
    grid-side charging is limited to 2 / 0.8 = 2.5 MW, below the 3 MW
    plant allowance. Stored energy ends at 100 MWh and 7.5 MW of the
    original 10 MW charging request is shed.

    Expected when discharging: At most 2 * 0.9 = 1.8 MW can reach the
    plant before the battery empties, below its 4 MW demand allowance.
    Stored energy ends at zero and 8.2 MW of the request is shed.

    This proves that facility permissions supplement the existing energy
    constraints rather than overriding them, that efficiency is applied
    in the correct direction, and that unsupported fixed power is recorded
    as schedule shedding. Fixed schedules select one physical direction
    here; this test does not establish charge/discharge exclusivity for
    freely dispatched batteries.

    :param charging: Direction of the fixed 10 MW request.
    :return: None.
    """
    grid: vg.MultiCircuit = make_facility_grid(BatteryDispatchMode.PlantChargeAndDisCharge, charging)
    battery: vg.Battery = grid.get_batteries()[0]
    battery.soc_0 = 0.98 if charging else 0.02
    battery.charge_efficiency = 0.8
    battery.discharge_efficiency = 0.9
    battery.enabled_dispatch = False
    battery.enabled_dispatch_prof = np.zeros(2, dtype=bool)
    battery.P = -10.0 if charging else 10.0
    battery.P_prof = np.full(2, battery.P)
    result, _model = run_linear_opf_ts(grid, np.array((0,), dtype=int))
    assert result.acceptable_solution
    assert np.isclose(result.batt_vars.p[0, 0], -2.5 if charging else 1.8)
    assert np.isclose(result.batt_vars.e[0, 0], 100.0 if charging else 0.0)
    assert np.isclose(result.batt_vars.shedding[0, 0], 7.5 if charging else 8.2)
