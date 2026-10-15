# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Build a modified IEEE 13-bus feeder manually, then compare it with its DGS
exported from the same system in PowerFactory.

This is the network in ieee13_bus_test_feeder.dgs, not the standard IEEE reference case:
the three supply transformers have fixed unity taps, and five intermediate buses carry
distributed loads.

Unused catalogue entries, drawing objects and the Summary Grid are omitted.

Run this file in the VeraGrid IDE configuration, with src marked as a Sources
Root. No PowerFactory installation is needed. The DGS is read only AFTER the
independent manual network is built.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure

import VeraGridEngine.api as vg
from VeraGridEngine.Devices.admittance_matrix import AdmittanceMatrix
from VeraGridEngine.enumerations import ShuntConnectionType, SolverType, WindingType
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_results_3ph import PowerFlowResults3Ph


def build_overhead_templates(grid: vg.MultiCircuit) -> dict[str, vg.OverheadLineType]:
    """Calculate the five overhead arrangements actually used by the feeder.

    :param grid: Circuit receiving the wire and tower catalogue entries.
    :return: Tower lookup by name for connecting the line sections later.
    """
    # Wire resistance is in ohm/km, diameter in mm and rated current in kA.
    # These are solid equivalent conductors, so internal diameter is unused.
    wire_556: vg.Wire = vg.Wire(name='556.5 ACSR', r=0.115512, diameter=23.5458,
                               diameter_internal=16.0, max_current=0.73, material='Al')
    wire_n1: vg.Wire = vg.Wire(name='n1 ACSR', r=0.695935, diameter=10.1092,
                              diameter_internal=16.0, max_current=0.23, material='As')
    wire_n4: vg.Wire = vg.Wire(name='n4 ACSR', r=0.367851, diameter=14.3002,
                              diameter_internal=16.0, max_current=0.34, material='Al')
    wire: vg.Wire
    for wire in (wire_556, wire_n1, wire_n4):
        grid.add_wire(wire)

    # Coordinates are (horizontal position, height) in metres; 1/2/3 mean A/B/C.
    # The same two-wire geometry needs separate CB and AC phase assignments.
    # In particular, the single wire to bus 611 is phase C, not phase A.
    arrangements: tuple[tuple[str, vg.Wire, tuple[tuple[float, float, int], ...]], ...] = (
        ('LineConfig601', wire_556, ((-0.3048, 8.5344, 1), (-1.0668, 8.5344, 2), (1.0668, 8.5344, 3))),
        ('LineConfig602', wire_n4, ((-0.3048, 8.5344, 1), (1.0668, 8.5344, 2), (-1.0668, 8.5344, 3))),
        ('LineConfig603-604_CB', wire_n1, ((-1.0668, 8.5344, 3), (1.0668, 8.5344, 2))),
        ('LineConfig603-604_AC', wire_n1, ((-1.0668, 8.5344, 1), (1.0668, 8.5344, 3))),
        ('LineConfig605', wire_n1, ((0.0, 8.8392, 3),)),
    )
    towers: dict[str, vg.OverheadLineType] = dict()
    name: str
    positions: tuple[tuple[float, float, int], ...]
    xpos: float
    ypos: float
    phase: int
    tower: vg.OverheadLineType
    for name, wire, positions in arrangements:
        tower = vg.OverheadLineType(name=name, Vnom=4.16, frequency=60.0, earth_resistivity=100.0)
        for xpos, ypos, phase in positions:
            tower.add_wire_relationship(wire=wire, xpos=xpos, ypos=ypos, phase=phase)
        # Reuse the engine's geometry calculation, rather than entering a Z matrix.
        tower.compute()
        assert tower.is_computed(), f'Could not calculate {name}'
        grid.add_overhead_line(tower)
        towers[name] = tower
    return towers


def build_underground_templates(grid: vg.MultiCircuit) -> dict[str, vg.UndergroundLineType]:
    """Calculate the two cable systems from their construction and burial data.

    :param grid: Circuit receiving the cable and underground-line catalogue entries.
    :return: Underground-line lookup by name.
    """
    # A cable type describes ONE core and its metallic sheath. All dimensions
    # below are mm; resistivities are micro-ohm cm, and filling factors are %.
    # The 15 kV cable rating is distinct from the feeder operating at 4.16 kV.
    cable_250: vg.UndergroundCableType = vg.UndergroundCableType(
        name='250 AA CN', nominal_voltage=15.0, core_dc_resistance=0.222551,
        core_diameter=12.71618, core_internal_diameter=0.0, cable_diameter=30.54451,
        sheath_thickness=0.159258, main_insulation_thickness=7.103906,
        core_resistivity=2.8264, sheath_resistivity=1.7241,
        core_filling_factor=100.0, sheath_filling_factor=99.44012,
        main_insulation_permittivity=2.3, outer_insulation_permittivity=2.5,
        main_insulation_loss_tangent=0.0, outer_insulation_loss_tangent=0.0,
        core_relative_permeability=1.0, sheath_relative_permeability=0.999993,
        skin_effect_factor=1.0, proximity_effect_factor=1.0,
    )
    cable_1_0: vg.UndergroundCableType = vg.UndergroundCableType(
        name='1/0 AA TS', nominal_voltage=15.0, core_dc_resistance=0.528299,
        core_diameter=8.253382, core_internal_diameter=0.0, cable_diameter=26.924,
        sheath_thickness=0.762, main_insulation_thickness=6.287309,
        core_resistivity=2.8264, sheath_resistivity=2.84,
        core_filling_factor=100.0, sheath_filling_factor=100.0,
        main_insulation_permittivity=2.3, outer_insulation_permittivity=8.0,
        main_insulation_loss_tangent=0.0, outer_insulation_loss_tangent=0.1,
        core_relative_permeability=1.0, sheath_relative_permeability=1.0,
        skin_effect_factor=1.0, proximity_effect_factor=1.0,
    )
    grid.add_underground_cable(cable_250)
    grid.add_underground_cable(cable_1_0)

    # An underground line type places the cables in soil. Depth is POSITIVE,
    # in metres. Use the exported depth without shortening its precision.
    system_606: vg.UndergroundLineType = vg.UndergroundLineType(
        name='606', Vnom=15.0, Imax=0.26, freq=60.0, earth_resistivity=100.0,
    )
    phase: int
    xpos: float
    for phase, xpos in enumerate((-0.1524, 0.0, 0.1524), start=1):
        system_606.add_cable_relationship(cable=cable_250, xpos=xpos,
                                          ypos=0.60959998049280, phase=phase)
    system_607: vg.UndergroundLineType = vg.UndergroundLineType(
        name='607 A', Vnom=15.0, Imax=0.165, freq=60.0, earth_resistivity=100.0,
    )
    system_607.add_cable_relationship(cable=cable_1_0, xpos=0.0,
                                      ypos=0.60959998049280, phase=1)

    # The engine calculates primitive matrices and eliminates grounded sheaths.
    systems: dict[str, vg.UndergroundLineType] = dict()
    system: vg.UndergroundLineType
    for system in (system_606, system_607):
        system.compute()
        assert system.is_computed(), f'Could not calculate {system.name}'
        grid.add_underground_line(system)
        systems[system.name] = system
    return systems


def add_lines(grid: vg.MultiCircuit, buses: dict[str, vg.Bus],
              towers: dict[str, vg.OverheadLineType],
              cables: dict[str, vg.UndergroundLineType]) -> None:
    """Connect the fifteen line sections using the physical templates.

    :param grid: Circuit receiving the lines.
    :param buses: Bus lookup by name.
    :param towers: Calculated overhead arrangements.
    :param cables: Calculated underground arrangements.
    :return: None.
    """
    # Every row contains name, sending bus, receiving bus, length in km, template.
    # Do not collapse the six 632--671 sections: their five junctions carry loads.
    sections: tuple[tuple[str, str, str, float, vg.OverheadLineType | vg.UndergroundLineType], ...] = (
        ('LC684-652', '684', '652', 0.2438, cables['607 A']),
        ('LC692-675', '692', '675', 0.1524, cables['606']),
        ('LOHL632-633', '632', '633', 0.1524, towers['LineConfig602']),
        ('LOHL632-645', '632', '645', 0.1524, towers['LineConfig603-604_CB']),
        ('LOHL632-671', '632', 'Terminal', 0.1016, towers['LineConfig601']),
        ('LOHL632-671_a', 'Terminal', 'Terminal(1)', 0.1016, towers['LineConfig601']),
        ('LOHL632-671_b', 'Terminal(1)', 'Terminal(2)', 0.1016, towers['LineConfig601']),
        ('LOHL632-671_c', 'Terminal(2)', 'Terminal(3)', 0.1016, towers['LineConfig601']),
        ('LOHL632-671_d', 'Terminal(3)', 'Terminal(4)', 0.1016, towers['LineConfig601']),
        ('LOHL632-671_e', 'Terminal(4)', '671', 0.1016, towers['LineConfig601']),
        ('LOHL645-646', '645', '646', 0.0914, towers['LineConfig603-604_CB']),
        ('LOHL650-632', 'RG60', '632', 0.6096, towers['LineConfig601']),
        ('LOHL671-680', '671', '680', 0.3048, towers['LineConfig601']),
        ('LOHL671-684', '671', '684', 0.0914, towers['LineConfig603-604_AC']),
        ('LOHL684-611', '684', '611', 0.0914, towers['LineConfig605']),
    )
    name: str
    from_name: str
    to_name: str
    length: float
    template: vg.OverheadLineType | vg.UndergroundLineType
    line: vg.Line
    admittance: AdmittanceMatrix
    for name, from_name, to_name, length, template in sections:
        line = vg.Line(name=name, bus_from=buses[from_name], bus_to=buses[to_name], length=length)
        # apply_template handles length and bus-voltage bases: ys is stored in
        # pu, ysh in micro-pu. It also retains the template reference.
        line.apply_template(obj=template, Sbase=grid.Sbase, freq=grid.fBase)
        # Mark only the conductors present in this template. This matters for
        # the single-phase cable: unused B/C slots must not energize extra phases.
        for admittance in (line.ys, line.ysh):
            admittance.phN = False
            admittance.phA = 1 in template.z_phases_nabc
            admittance.phB = 2 in template.z_phases_nabc
            admittance.phC = 3 in template.z_phases_nabc
        grid.add_line(line)

    # A closed switch is a topological connection, not a short artificial line.
    # Keep both original buses: the solver must return the same voltage for them.
    grid.add_switch(vg.Switch(name='Switch', bus_from=buses['671'], bus_to=buses['692'], active=True))


def add_transformers(grid: vg.MultiCircuit, buses: dict[str, vg.Bus]) -> None:
    """Add the fixed-tap supply bank and the 4.16/0.48 kV transformer.

    :param grid: Circuit receiving the transformer types and branches.
    :param buses: Bus lookup by name.
    :return: None.
    """
    # Nameplate inputs: voltage in kV, power in MVA, copper losses in kW,
    # short-circuit voltage in %. The engine converts these to system-base pu.
    supply_type: vg.TransformerType = vg.TransformerType(
        name='AutoTRF1ph', hv_nominal_voltage=2.401777, lv_nominal_voltage=2.401777,
        nominal_power=1.667, copper_losses=6.0, short_circuit_voltage=3.0,
    )
    distribution_type: vg.TransformerType = vg.TransformerType(
        name='XFM-1Typ', hv_nominal_voltage=4.16, lv_nominal_voltage=0.48,
        nominal_power=0.5, copper_losses=5.5, short_circuit_voltage=2.282542,
    )
    transformer_type: vg.TransformerType
    for transformer_type in (supply_type, distribution_type):
        transformer_type.conn_hv = WindingType.GroundedStar
        transformer_type.conn_lv = WindingType.GroundedStar
        grid.add_transformer_type(transformer_type)

    # These are three SINGLE-PHASE branches, not three three-phase transformers.
    # Phase 0 denotes their grounded return. Keep the rounded exported phase
    # voltage (2.401777 kV), rather than replacing it with 4.16/sqrt(3).
    phase: int
    phase_name: str
    transformer: vg.Transformer2W
    for phase, phase_name in enumerate(('A', 'B', 'C'), start=1):
        transformer = vg.Transformer2W(name=f'Ureg{phase_name}',
                                       bus_from=buses['650'], bus_to=buses['RG60'])
        transformer.apply_template(obj=supply_type, Sbase=grid.Sbase)
        transformer.phases = np.array((0, phase), dtype=int)
        transformer.conn_f = WindingType.GroundedStar
        transformer.conn_t = WindingType.GroundedStar
        # Exported zero-sequence data: uk0=3%, ur0=0%; negative equals positive.
        transformer.R0 = 0.0
        transformer.X0 = 0.03 * grid.Sbase / supply_type.Sn
        transformer.R2 = transformer.R
        transformer.X2 = transformer.X
        grid.add_transformer2w(transformer)

    # The secondary bus uses line-to-line voltage, as do the other Bus objects.
    distribution: vg.Transformer2W = vg.Transformer2W(
        name='XFM-1', bus_from=buses['633'], bus_to=buses['634'],
    )
    distribution.apply_template(obj=distribution_type, Sbase=grid.Sbase)
    distribution.phases = np.array((0, 1, 2, 3), dtype=int)
    distribution.conn_f = WindingType.GroundedStar
    distribution.conn_t = WindingType.GroundedStar
    distribution.R0 = distribution.R2 = distribution.R
    distribution.X0 = distribution.X2 = distribution.X
    grid.add_transformer2w(distribution)


def add_loads_and_capacitors(grid: vg.MultiCircuit, buses: dict[str, vg.Bus]) -> None:
    """Enter the feeder's unbalanced PQ, current and impedance loads.

    :param grid: Circuit receiving the injections.
    :param buses: Bus lookup by name.
    :return: None.
    """
    # Grounded-star slots 1/2/3 mean A/B/C; delta slots mean AB/BC/CA.
    # P/Q are MW/MVAr. Ir/Ii and G/B are also POWER-EQUIVALENT coefficients
    # at nominal voltage, not amperes or siemens. Inductive Ii and B are negative.
    # Aggregate inputs retain the equivalent balanced model alongside phase data.
    injections: tuple[tuple[str, vg.Load, ShuntConnectionType], ...] = (
        ('611', vg.Load(name='L611-YcI', Ir=0.17, Ii=-0.08,
                        Ir3=0.17, Ii3=-0.08), ShuntConnectionType.GroundedStar),
        ('634', vg.Load(name='L634-YcPQ', P=0.4, Q=0.29,
                        P1=0.16, P2=0.12, P3=0.12, Q1=0.11, Q2=0.09, Q3=0.09),
         ShuntConnectionType.GroundedStar),
        ('645', vg.Load(name='L645-YcPQ', P=0.17, Q=0.125,
                        P2=0.17, Q2=0.125), ShuntConnectionType.GroundedStar),
        ('646', vg.Load(name='L646-DcZ', G=0.23, B=-0.132,
                        G2=0.23, B2=-0.132), ShuntConnectionType.Delta),
        ('652', vg.Load(name='L652-YcZ', G=0.128, B=-0.086,
                        G1=0.128, B1=-0.086), ShuntConnectionType.GroundedStar),
        ('671', vg.Load(name='L671-DcPQ', P=1.155, Q=0.66,
                        P1=0.385, P2=0.385, P3=0.385, Q1=0.22, Q2=0.22, Q3=0.22),
         ShuntConnectionType.Delta),
        ('675', vg.Load(name='L675-YcPQ', P=0.843, Q=0.462,
                        P1=0.485, P2=0.068, P3=0.29, Q1=0.19, Q2=0.06, Q3=0.212),
         ShuntConnectionType.GroundedStar),
        ('692', vg.Load(name='L692-Dcl', Ir=0.17, Ii=-0.151,
                        Ir3=0.17, Ii3=-0.151), ShuntConnectionType.Delta),
    )
    bus_name: str
    load: vg.Load
    connection: ShuntConnectionType
    for bus_name, load, connection in injections:
        load.conn = connection
        grid.add_load(bus=buses[bus_name], api_obj=load)

    # Five identical loads are spread along the six sections from 632 to 671.
    index: int
    for index, bus_name in enumerate(('Terminal', 'Terminal(1)', 'Terminal(2)', 'Terminal(3)', 'Terminal(4)'), start=1):
        load = vg.Load(name=f'Distributed Load {index}', P=0.04, Q=0.0232,
                       P1=0.0034, P2=0.0132, P3=0.0234, Q1=0.002, Q2=0.0076, Q3=0.0136)
        load.conn = ShuntConnectionType.GroundedStar
        grid.add_load(bus=buses[bus_name], api_obj=load)

    # Shunt B is positive for capacitors and is expressed in MVAr at 1 pu.
    # Bus 611 has only phase C; bus 675 has a balanced three-phase capacitor bank.
    capacitor_611: vg.Shunt = vg.Shunt(name='C611', B=0.1, B3=0.1)
    capacitor_675: vg.Shunt = vg.Shunt(name='C675', B=0.6, B1=0.2, B2=0.2, B3=0.2)
    capacitor_611.conn = ShuntConnectionType.GroundedStar
    capacitor_675.conn = ShuntConnectionType.GroundedStar
    grid.add_shunt(bus=buses['611'], api_obj=capacitor_611)
    grid.add_shunt(bus=buses['675'], api_obj=capacitor_675)


def build_ieee13_feeder() -> vg.MultiCircuit:
    """Build the complete manual feeder without reading any reference file.

    :return: Independent circuit containing only the used network elements.
    """
    grid: vg.MultiCircuit = vg.MultiCircuit(name='IEEE 13-bus feeder with underground cables', Sbase=100.0, fbase=60.0)

    # Keep the original bus names. The first group follows the main feeder;
    # the remaining buses belong to its laterals. There are 19 buses in this variant.
    bus_names: tuple[str, ...] = (
        '650', 'RG60', '632', 'Terminal', 'Terminal(1)', 'Terminal(2)',
        'Terminal(3)', 'Terminal(4)', '671', '692', '675',
        '633', '634', '645', '646', '680', '684', '652', '611',
    )
    buses: dict[str, vg.Bus] = dict()
    name: str
    for name in bus_names:
        buses[name] = grid.add_bus(vg.Bus(name=name, Vnom=0.48 if name == '634' else 4.16,
                                          is_slack=name == '650'))

    # A voltage-controlled generator at the slack bus represents the external
    # supply in the power flow. The balanced source fixes 1 pu and phase A at 0 deg.
    grid.add_generator(bus=buses['650'], api_obj=vg.Generator(name='External Grid', vset=1.0))
    towers: dict[str, vg.OverheadLineType] = build_overhead_templates(grid)
    cables: dict[str, vg.UndergroundLineType] = build_underground_templates(grid)
    add_lines(grid=grid, buses=buses, towers=towers, cables=cables)
    add_transformers(grid=grid, buses=buses)
    add_loads_and_capacitors(grid=grid, buses=buses)
    return grid


def compare_power_flows(manual: vg.MultiCircuit, imported: vg.MultiCircuit) -> tuple[np.ndarray, np.ndarray]:
    """Assert electrical equivalence and compare both three-phase solutions.

    :param manual: Independently constructed feeder.
    :param imported: Feeder read from the reference DGS.
    :return: Manual and imported complex ABC voltages, in manual bus order;
        absent phases are replaced with NaN for plotting.
    """
    # Check the network inventory before comparing numerical results. Catalogue
    # counts differ intentionally: the DGS contains unused types, the builder does not.
    grid: vg.MultiCircuit
    for grid in (manual, imported):
        assert len(grid.buses) == 19
        assert len(grid.lines) == 15
        assert len(grid.transformers2w) == 4
        assert len(grid.switch_devices) == 1
        assert len(grid.get_loads()) == 13
        assert len(grid.get_shunts()) == 2
        assert len(grid.get_generators()) == 1
        # Nominal ZIP demand is 3.466 MW + j2.102 MVAr, before capacitor support.
        # Actual demand differs at solved voltages because I and Z are not PQ.
        load: vg.Load
        np.testing.assert_allclose(
            (sum(load.P + load.Ir + load.G for load in grid.get_loads()),
             sum(load.Q - load.Ii - load.B for load in grid.get_loads())),
            (3.466, 2.102), rtol=0.0, atol=1e-12,
        )

    # Check every line's connectivity and full phase matrices, not just a few
    # sequence parameters. This also verifies both underground cable calculations.
    line: vg.Line
    reference_lines: dict[str, vg.Line] = dict((line.name, line) for line in imported.lines)
    assert len(reference_lines) == len(imported.lines)
    assert set(reference_lines) == set(line.name for line in manual.lines)
    reference_line: vg.Line
    for line in manual.lines:
        reference_line = reference_lines[line.name]
        assert (line.bus_from.name, line.bus_to.name) == (reference_line.bus_from.name, reference_line.bus_to.name)
        np.testing.assert_allclose(line.ys.values, reference_line.ys.values, rtol=0.0, atol=1e-12,
                                   err_msg=f'Series matrix: {line.name}')
        np.testing.assert_allclose(line.ysh.values, reference_line.ysh.values, rtol=0.0, atol=1e-12,
                                   err_msg=f'Shunt matrix: {line.name}')

    # Run the same solver with the same options; no imported parameter is copied
    # into the manual model. Tight solver tolerance makes this a numerical check.
    options: vg.PowerFlowOptions = vg.PowerFlowOptions(
        solver_type=SolverType.NR, tolerance=1e-10, max_iter=1000,
    )
    manual_result: PowerFlowResults3Ph = vg.power_flow3ph(grid=manual, options=options)
    imported_result: PowerFlowResults3Ph = vg.power_flow3ph(grid=imported, options=options)
    assert len(manual_result.convergence_reports) > 0 and manual_result.converged
    assert len(imported_result.convergence_reports) > 0 and imported_result.converged

    # Match by unique names, never by importer-dependent array order.
    name: str
    index: int
    manual_indices: dict[str, int] = dict((name, index) for index, name in enumerate(manual_result.bus_names))
    imported_indices: dict[str, int] = dict((name, index) for index, name in enumerate(imported_result.bus_names))
    assert len(manual_indices) == len(imported_indices) == 19
    assert set(manual_indices) == set(imported_indices)
    bus: vg.Bus
    assert tuple(manual_result.bus_names) == tuple(bus.name for bus in manual.buses)
    order: np.ndarray = np.array(tuple(imported_indices[name] for name in manual_result.bus_names), dtype=int)
    voltage_manual: np.ndarray = np.column_stack((manual_result.voltage_A, manual_result.voltage_B, manual_result.voltage_C))
    voltage_imported: np.ndarray = np.column_stack((imported_result.voltage_A, imported_result.voltage_B, imported_result.voltage_C))[order]

    # Check all 57 slots, including zero voltage in the seven absent phases.
    # A complex comparison detects both magnitude errors and phase-angle errors.
    voltage_tolerance: float = 1e-8
    assert np.all(np.isfinite(voltage_manual)) and np.all(np.isfinite(voltage_imported))
    np.testing.assert_allclose(voltage_manual, voltage_imported, rtol=0.0, atol=voltage_tolerance,
                               err_msg='Manual and DGS complex bus voltages differ')
    voltage: np.ndarray
    for voltage in (voltage_manual, voltage_imported):
        np.testing.assert_allclose(voltage[manual_indices['671']], voltage[manual_indices['692']],
                                   rtol=0.0, atol=1e-12, err_msg='Closed-switch voltages differ')

    # Also compare complex power at both ends of every line and transformer.
    # The ideal switch is reduced topologically and has no independent flow here.
    branch_indices: dict[str, int] = dict((name, index) for index, name in enumerate(imported_result.branch_names))
    assert len(branch_indices) == len(imported_result.branch_names)
    assert set(branch_indices) == set(manual_result.branch_names)
    branch_order: np.ndarray = np.array(tuple(branch_indices[name] for name in manual_result.branch_names), dtype=int)
    powers_manual: np.ndarray = np.column_stack((manual_result.Sf_A, manual_result.Sf_B, manual_result.Sf_C,
                                                manual_result.St_A, manual_result.St_B, manual_result.St_C))
    powers_imported: np.ndarray = np.column_stack((imported_result.Sf_A, imported_result.Sf_B, imported_result.Sf_C,
                                                  imported_result.St_A, imported_result.St_B, imported_result.St_C))[branch_order]
    np.testing.assert_allclose(powers_manual, powers_imported, rtol=0.0, atol=1e-8,
                               err_msg='Branch complex powers differ (MVA)')

    # The mask is specified from the physical feeder, not inferred from a result
    # that could itself be wrong. Only the five reduced-phase buses need entries.
    reduced_phases: dict[str, tuple[bool, bool, bool]] = dict((
        ('611', (False, False, True)), ('652', (True, False, False)),
        ('645', (False, True, True)), ('646', (False, True, True)),
        ('684', (True, False, True)),
    ))
    present: np.ndarray = np.array(tuple(reduced_phases.get(name, (True, True, True))
                                         for name in manual_result.bus_names), dtype=bool)
    assert np.count_nonzero(present) == 50
    np.testing.assert_array_equal(np.abs(voltage_manual) > 0.0, present)
    np.testing.assert_array_equal(np.abs(voltage_imported) > 0.0, present)
    print('Both power flows converged: 19 buses, 50 physical phases.')
    print(f'Maximum complex voltage difference: {np.max(np.abs(voltage_manual - voltage_imported)):.3e} pu')
    print(f'Maximum branch complex-power difference: {np.max(np.abs(powers_manual - powers_imported)):.3e} MVA')
    print(f'PASS: absolute voltage tolerance = {voltage_tolerance:.0e} pu; closed switch 671--692 checked.')
    voltage_manual[~present] = np.nan
    voltage_imported[~present] = np.nan
    print('\nBus             Manual |V| A/B/C [pu]               DGS |V| A/B/C [pu]')
    for index, name in enumerate(manual_result.bus_names):
        print(f'{name:<12} {np.abs(voltage_manual[index])}   {np.abs(voltage_imported[index])}')
    return voltage_manual, voltage_imported


def plot_voltages(bus_names: tuple[str, ...], voltage_manual: np.ndarray,
                  voltage_imported: np.ndarray, show_plots: bool) -> None:
    """Plot all bus phases and the voltage profile along the main feeder.

    :param bus_names: Names in the same order as the voltage rows.
    :param voltage_manual: Manual complex voltages; absent phases are NaN.
    :param voltage_imported: DGS complex voltages in the same order.
    :param show_plots: Display the figures interactively when True.
    :return: None. Figures are saved beside this script.
    """
    # A categorical bus axis covers ALL buses without implying that separate
    # laterals form one continuous electrical path. Matching markers should overlap.
    figure: Figure
    axes: np.ndarray
    figure, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True, layout='constrained')
    phase: int
    label: str
    color: str
    phase_styles: tuple[tuple[str, str], ...] = (('A', 'tab:red'), ('B', 'tab:green'), ('C', 'tab:blue'))
    for phase, (label, color) in enumerate(phase_styles):
        axes[0].plot(bus_names, np.abs(voltage_manual[:, phase]), 'o', color=color, label=f'{label}: manual')
        axes[0].plot(bus_names, np.abs(voltage_imported[:, phase]), 'x', color=color, label=f'{label}: DGS')
        axes[1].plot(bus_names, np.abs(voltage_manual[:, phase] - voltage_imported[:, phase]),
                     'o', color=color, label=f'Phase {label}')
    axes[0].set_title('Modified IEEE 13-bus feeder: manual construction vs DGS import')
    axes[0].set_ylabel('Phase-to-ground voltage [pu]')
    axes[0].legend(ncol=3)
    axes[1].set_ylabel('Absolute complex-voltage difference [pu]')
    axes[1].set_xlabel('Bus (categorical order; laterals are not connected in series)')
    axes[1].tick_params(axis='x', labelrotation=60)
    axes[1].ticklabel_format(axis='y', style='sci', scilimits=(0, 0))
    axes[1].legend(ncol=3)
    axis: Axes
    for axis in axes:
        axis.grid(True, alpha=0.3)

    # This second plot follows one REAL path: supply, distributed-load section,
    # closed switch, and 1 km underground cable. Show the bus at each distance.
    path_names: tuple[str, ...] = ('650', 'RG60', '632', 'Terminal', 'Terminal(1)',
                                  'Terminal(2)', 'Terminal(3)', 'Terminal(4)', '671', '692', '675')
    name: str
    index: int
    bus_indices: dict[str, int] = dict((name, index) for index, name in enumerate(bus_names))
    path_indices: np.ndarray = np.array(tuple(bus_indices[name] for name in path_names), dtype=int)
    distance_km: np.ndarray = np.cumsum(np.array((0.0, 0.0, 0.6096, 0.1016, 0.1016, 0.1016,
                                                0.1016, 0.1016, 0.1016, 0.0, 0.1524)))
    profile_figure: Figure
    profile_axis: Axes
    profile_figure, profile_axis = plt.subplots(figsize=(12, 5), layout='constrained')
    for phase, (label, color) in enumerate(phase_styles):
        profile_axis.plot(distance_km, np.abs(voltage_manual[path_indices, phase]),
                          '-o', color=color, label=f'Phase {label}')
    profile_axis.axvspan(distance_km[-2], distance_km[-1], color='tab:orange', alpha=0.12,
                         label='Underground 606: 692--675')
    profile_axis.set_title('Voltage profile along the main feeder (manual model)')
    profile_axis.set_ylabel('Phase-to-ground voltage [pu]')
    profile_axis.set_xlabel('Cumulative line length from bus 650 [km]; transformers and switch have zero length')
    profile_axis.set_xticks(distance_km[[0, 2, 3, 4, 5, 6, 7, 8, 10]],
                            ('650 / RG60', '632', 'Terminal', 'Terminal(1)', 'Terminal(2)',
                             'Terminal(3)', 'Terminal(4)', '671 / 692', '675'), rotation=60)
    profile_axis.legend(ncol=4)
    profile_axis.grid(True, alpha=0.3)

    # Save before showing, so closing an interactive window cannot discard output.
    output_directory: Path = Path(__file__).resolve().parent / 'ieee13_results'
    output_directory.mkdir(exist_ok=True)
    figure.savefig(output_directory / 'bus_voltage_comparison.png', dpi=150)
    profile_figure.savefig(output_directory / 'main_feeder_voltage_profile.png', dpi=150)
    print(f'\nPlots saved to: {output_directory}')
    if show_plots:
        plt.show()
    else:
        pass
    plt.close(figure)
    plt.close(profile_figure)


def main(show_plots: bool = True) -> None:
    """Build, solve, verify and plot the two independently obtained networks.

    :param show_plots: Set False for a non-interactive benchmark run.
    :return: None.
    """
    # This tracked fixture is byte-for-byte identical to the supplied ieee13_bus_test_feeder.dgs
    # (SHA256: d68b27e4e30e9f066a9bc4e9939e2b626b178850735a3dec1fd278162807b5d6).
    # Reuse it rather than requiring a Desktop path or storing another copy.
    dgs_path: Path = (Path(__file__).resolve().parents[2] / 'src' / 'tests' / 'data' / 'grids'
                      / 'DGS' / 'ieee13_bus_test_feeder.dgs')
    manual: vg.MultiCircuit = build_ieee13_feeder()
    imported: vg.MultiCircuit = vg.open_file(filename=str(dgs_path))
    print(f'Reference DGS: {dgs_path}')
    # The importer currently leaves fBase at 50 Hz, but every used physical
    # template is calculated at its exported 60 Hz. No rescaling or correction
    # is made here: compare against the imported circuit exactly as returned.
    print(f'Grid frequency metadata: manual={manual.fBase:g} Hz, imported={imported.fBase:g} Hz; physical templates=60 Hz')
    voltage_manual: np.ndarray
    voltage_imported: np.ndarray
    voltage_manual, voltage_imported = compare_power_flows(manual=manual, imported=imported)
    bus: vg.Bus
    plot_voltages(bus_names=tuple(bus.name for bus in manual.buses), voltage_manual=voltage_manual,
                  voltage_imported=voltage_imported, show_plots=show_plots)


if __name__ == '__main__':
    main()
else:
    pass
