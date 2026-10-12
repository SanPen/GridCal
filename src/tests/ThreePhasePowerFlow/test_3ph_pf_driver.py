# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from pathlib import Path
from typing import Any

import VeraGridEngine.api as gce
from VeraGridEngine import WindingType, ShuntConnectionType
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Simulations.PowerFlow3ph.Formulations.pf_basic_formulation_3ph import expandVoltage3ph
import numpy as np
import pytest


def test_expand_voltage_3ph_initializes_neutrals_uniformly():
    voltage = np.array([1.0, 0.95 * np.exp(0.1j)])
    expanded = expandVoltage3ph(voltage)

    assert np.allclose(expanded[0::4], 1e-4 * np.exp(1j * np.angle(voltage)))


def test_three_phase_power_flow_propagates_reduced_bus_voltages() -> None:
    """Return the representative voltage at every bus joined by an ideal switch.

    :return: None.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit()
    bus_from: gce.Bus = grid.add_bus(gce.Bus(name="From", is_slack=True))
    bus_to: gce.Bus = grid.add_bus(gce.Bus(name="To"))
    generator: gce.Generator = gce.Generator(vset=1.0)
    switch: gce.Switch = gce.Switch(name="Switch", bus_from=bus_from, bus_to=bus_to)
    grid.add_generator(bus=bus_from, api_obj=generator)
    grid.add_switch(switch)

    results: Any = gce.power_flow3ph(grid=grid)

    assert np.isclose(results.voltage_N[1], results.voltage_N[0])
    assert np.isclose(results.voltage_A[1], results.voltage_A[0])
    assert np.isclose(results.voltage_B[1], results.voltage_B[0])
    assert np.isclose(results.voltage_C[1], results.voltage_C[0])


@pytest.mark.parametrize("disabled_lines,max_iter", (((3, 5), 25), ((3,), 0), ((), 0)))
def test_three_phase_nonconvergence_preserves_branch_results(disabled_lines: tuple[int, ...],
                                                            max_iter: int) -> None:
    """Preserve branch result dimensions and failure diagnostics after solver rejection.

    :param disabled_lines: IEEE 9 bus lines to disconnect before solving.
    :param max_iter: Solver iteration limit; zero forces rejection in connected cases.
    :return: None.
    """
    # Cover the reported island split and connected grids with different branch counts.
    grid_path: Path = Path(__file__).resolve().parents[3] / "Grids_and_profiles" / "grids" / "IEEE 9 Bus.gridcal"
    grid: gce.MultiCircuit = gce.open_file(str(grid_path))
    # Complete the old balanced fixture's missing sequence data before testing rejection.
    generator: gce.Generator
    for generator in grid.generators:
        generator.R0, generator.X0 = 0.01, 0.08
        generator.R2, generator.X2 = 0.02, 0.10
    line_idx: int
    for line_idx in disabled_lines:
        grid.lines[line_idx].active = False

    options: gce.PowerFlowOptions = gce.PowerFlowOptions(max_iter=max_iter)
    driver: PowerFlowDriver3Ph = PowerFlowDriver3Ph(grid=grid, options=options)
    driver.run()
    results: PowerFlowResults3Ph = driver.results

    # Returning correctly sized fallback arrays must not hide the solver failure.
    assert not results.converged
    assert results.error > options.tolerance
    assert "Tried solution is garbage" in str(driver.logger)
    assert "Did not converge, even after retry!" in str(driver.logger)

    branch_count: int = grid.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True)
    branch_values: np.ndarray
    for branch_values in (results.Sf_A, results.Sf_B, results.Sf_C,
                          results.St_A, results.St_B, results.St_C,
                          results.If_N, results.If_A, results.If_B, results.If_C,
                          results.It_N, results.It_A, results.It_B, results.It_C,
                          results.loading_A, results.loading_B, results.loading_C,
                          results.losses_A, results.losses_B, results.losses_C):
        assert branch_values.shape == (branch_count,)
        assert np.all(branch_values == 0.0)


def test_ieee_13_bus_feeder_driver():
    """
    This test builds the IEEE 13-Bus Test Feeder and compares the obtained results with the reference values.
    Uses power_flow_driver.py
    """

    logger = gce.Logger()
    grid = gce.MultiCircuit()
    grid.fBase = 60

    # ----------------------------------------------------------------------------------------------------------------------
    # Buses
    # ----------------------------------------------------------------------------------------------------------------------
    bus_632 = gce.Bus(name='632', Vnom=4.16, xpos=0, ypos=0)
    bus_632.is_slack = True
    grid.add_bus(obj=bus_632)
    gen = gce.Generator(vset=1.0)
    grid.add_generator(bus=bus_632, api_obj=gen)

    bus_645 = gce.Bus(name='645', Vnom=4.16, xpos=-100 * 5, ypos=0)
    grid.add_bus(obj=bus_645)

    bus_646 = gce.Bus(name='646', Vnom=4.16, xpos=-200 * 5, ypos=0)
    grid.add_bus(obj=bus_646)

    bus_633 = gce.Bus(name='633', Vnom=4.16, xpos=100 * 5, ypos=0)
    grid.add_bus(obj=bus_633)

    bus_634 = gce.Bus(name='634', Vnom=0.48, xpos=200 * 5, ypos=0)
    grid.add_bus(obj=bus_634)

    bus_671 = gce.Bus(name='671', Vnom=4.16, xpos=0, ypos=100 * 5)
    grid.add_bus(obj=bus_671)

    bus_684 = gce.Bus(name='684', Vnom=4.16, xpos=-100 * 5, ypos=100 * 5)
    grid.add_bus(obj=bus_684)

    bus_611 = gce.Bus(name='611', Vnom=4.16, xpos=-200 * 5, ypos=100 * 5)
    grid.add_bus(obj=bus_611)

    bus_675 = gce.Bus(name='675', Vnom=4.16, xpos=200 * 5, ypos=100 * 5)
    grid.add_bus(obj=bus_675)

    bus_680 = gce.Bus(name='680', Vnom=4.16, xpos=0, ypos=200 * 5)
    grid.add_bus(obj=bus_680)

    bus_652 = gce.Bus(name='652', Vnom=4.16, xpos=-100 * 5, ypos=200 * 5)
    grid.add_bus(obj=bus_652)

    # ----------------------------------------------------------------------------------------------------------------------
    # Impedances [Ohm/km]
    # ----------------------------------------------------------------------------------------------------------------------
    z_601 = np.array([
        [0.3465 + 1j * 1.0179, 0.1560 + 1j * 0.5017, 0.1580 + 1j * 0.4236],
        [0.1560 + 1j * 0.5017, 0.3375 + 1j * 1.0478, 0.1535 + 1j * 0.3849],
        [0.1580 + 1j * 0.4236, 0.1535 + 1j * 0.3849, 0.3414 + 1j * 1.0348]
    ], dtype=complex) / 1.60934

    z_602 = np.array([
        [0.7526 + 1j * 1.1814, 0.1580 + 1j * 0.4236, 0.1560 + 1j * 0.5017],
        [0.1580 + 1j * 0.4236, 0.7475 + 1j * 1.1983, 0.1535 + 1j * 0.3849],
        [0.1560 + 1j * 0.5017, 0.1535 + 1j * 0.3849, 0.7436 + 1j * 1.2112]
    ], dtype=complex) / 1.60934

    z_603 = np.array([
        [1.3294 + 1j * 1.3471, 0.2066 + 1j * 0.4591],
        [0.2066 + 1j * 0.4591, 1.3238 + 1j * 1.3569]
    ], dtype=complex) / 1.60934

    z_604 = np.array([
        [1.3238 + 1j * 1.3569, 0.2066 + 1j * 0.4591],
        [0.2066 + 1j * 0.4591, 1.3294 + 1j * 1.3471]
    ], dtype=complex) / 1.60934

    z_605 = np.array([
        [1.3292 + 1j * 1.3475]
    ], dtype=complex) / 1.60934

    z_606 = np.array([
        [0.7982 + 1j * 0.4463, 0.3192 + 1j * 0.0328, 0.2849 + 1j * -0.0143],
        [0.3192 + 1j * 0.0328, 0.7891 + 1j * 0.4041, 0.3192 + 1j * 0.0328],
        [0.2849 + 1j * -0.0143, 0.3192 + 1j * 0.0328, 0.7982 + 1j * 0.4463]
    ], dtype=complex) / 1.60934

    z_607 = np.array([
        [1.3425 + 1j * 0.5124]
    ], dtype=complex) / 1.60934

    # ----------------------------------------------------------------------------------------------------------------------
    # Admittances [S/km]
    # ----------------------------------------------------------------------------------------------------------------------
    y_601 = np.array([
        [1j * 6.2998, 1j * -1.9958, 1j * -1.2595],
        [1j * -1.9958, 1j * 5.9597, 1j * -0.7417],
        [1j * -1.2595, 1j * -0.7417, 1j * 5.6386]
    ], dtype=complex) / 10 ** 6 / 1.60934

    y_602 = np.array([
        [1j * 5.6990, 1j * -1.0817, 1j * -1.6905],
        [1j * -1.0817, 1j * 5.1795, 1j * -0.6588],
        [1j * -1.6905, 1j * -0.6588, 1j * 5.4246]
    ], dtype=complex) / 10 ** 6 / 1.60934

    y_603 = np.array([
        [1j * 4.7097, 1j * -0.8999],
        [1j * -0.8999, 1j * 4.6658]
    ], dtype=complex) / 10 ** 6 / 1.60934

    y_604 = np.array([
        [1j * 4.6658, 1j * -0.8999],
        [1j * -0.8999, 1j * 4.7097]
    ], dtype=complex) / 10 ** 6 / 1.60934

    y_605 = np.array([
        [1j * 4.5193]
    ], dtype=complex) / 10 ** 6 / 1.60934

    y_606 = np.array([
        [1j * 96.8897, 1j * 0.0000, 1j * 0.0000],
        [1j * 0.0000, 1j * 96.8897, 1j * 0.0000],
        [1j * 0.0000, 1j * 0.0000, 1j * 96.8897]
    ], dtype=complex) / 10 ** 6 / 1.60934

    y_607 = np.array([
        [1j * 88.9912]
    ], dtype=complex) / 10 ** 6 / 1.60934

    # ----------------------------------------------------------------------------------------------------------------------
    # Loads
    # ----------------------------------------------------------------------------------------------------------------------
    # Three-phase power load
    load_634 = gce.Load(P1=0.160,
                        Q1=0.110,
                        P2=0.120,
                        Q2=0.090,
                        P3=0.120,
                        Q3=0.090)
    load_634.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_634, api_obj=load_634)

    # Single-phase power load
    load_645 = gce.Load(P1=0.0,
                        Q1=0.0,
                        P2=0.170,
                        Q2=0.125,
                        P3=0.0,
                        Q3=0.0)
    load_645.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_645, api_obj=load_645)

    # Two-phase impedance load
    load_646 = gce.Load(G2=0.230,
                        B2=-0.132)
    load_646.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_646, api_obj=load_646)

    # Single-phase impedance load
    load_652 = gce.Load(G1=0.128,
                        B1=-0.086)
    load_652.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_652, api_obj=load_652)

    # Three-phase delta power load
    load_671 = gce.Load(P1=0.385,
                        Q1=0.220,
                        P2=0.385,
                        Q2=0.220,
                        P3=0.385,
                        Q3=0.220)
    load_671.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_671, api_obj=load_671)

    # Three-phase star power load
    load_675 = gce.Load(P1=0.485,
                        Q1=0.190,
                        P2=0.068,
                        Q2=0.060,
                        P3=0.290,
                        Q3=0.212)
    load_675.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_675, api_obj=load_675)

    # Two-phase current load
    load_671_692 = gce.Load(Ir3=0.170,
                            Ii3=-0.151)
    load_671_692.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_671, api_obj=load_671_692)

    # Single-phase current load
    load_611 = gce.Load(Ir3=0.170,
                        Ii3=-0.080)
    load_611.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_611, api_obj=load_611)

    load_632_distrib = gce.Load(P1=0.017 / 2,
                                Q1=0.010 / 2,
                                P2=0.066 / 2,
                                Q2=0.038 / 2,
                                P3=0.117 / 2,
                                Q3=0.068 / 2)
    load_632_distrib.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_632, api_obj=load_632_distrib)

    load_671_distrib = gce.Load(P1=0.017 / 2,
                                Q1=0.010 / 2,
                                P2=0.066 / 2,
                                Q2=0.038 / 2,
                                P3=0.117 / 2,
                                Q3=0.068 / 2)
    load_671_distrib.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_671, api_obj=load_671_distrib)

    # ----------------------------------------------------------------------------------------------------------------------
    # Capacitors
    # ----------------------------------------------------------------------------------------------------------------------
    cap_675 = gce.Shunt(B1=0.2,
                        B2=0.2,
                        B3=0.2)
    cap_675.conn = ShuntConnectionType.GroundedStar
    grid.add_shunt(bus=bus_675, api_obj=cap_675)

    cap_611 = gce.Shunt(B3=0.1)
    cap_611.conn = ShuntConnectionType.GroundedStar
    grid.add_shunt(bus=bus_611, api_obj=cap_611)

    # ----------------------------------------------------------------------------------------------------------------------
    # Line Configurations
    # ----------------------------------------------------------------------------------------------------------------------
    config_601 = gce.create_known_abc_overhead_template(name='Config. 601',
                                                        z_nabc=z_601,
                                                        ysh_nabc=y_601,
                                                        phases=np.array([1, 2, 3]),
                                                        Vnom=4.16,
                                                        frequency=60)
    grid.add_overhead_line(config_601)

    config_602 = gce.create_known_abc_overhead_template(name='Config. 602',
                                                        z_nabc=z_602,
                                                        ysh_nabc=y_602,
                                                        phases=np.array([1, 2, 3]),
                                                        Vnom=4.16,
                                                        frequency=60)

    grid.add_overhead_line(config_602)

    config_603 = gce.create_known_abc_overhead_template(name='Config. 603',
                                                        z_nabc=z_603,
                                                        ysh_nabc=y_603,
                                                        phases=np.array([2, 3]),
                                                        Vnom=4.16,
                                                        frequency=60)

    grid.add_overhead_line(config_603)

    config_604 = gce.create_known_abc_overhead_template(name='Config. 604',
                                                        z_nabc=z_604,
                                                        ysh_nabc=y_604,
                                                        phases=np.array([1, 3]),
                                                        Vnom=4.16,
                                                        frequency=60)

    grid.add_overhead_line(config_604)

    config_605 = gce.create_known_abc_overhead_template(name='Config. 605',
                                                        z_nabc=z_605,
                                                        ysh_nabc=y_605,
                                                        phases=np.array([3]),
                                                        Vnom=4.16,
                                                        frequency=60)

    grid.add_overhead_line(config_605)

    config_606 = gce.create_known_abc_overhead_template(name='Config. 606',
                                                        z_nabc=z_606,
                                                        ysh_nabc=y_606,
                                                        phases=np.array([1, 2, 3]),
                                                        Vnom=4.16,
                                                        frequency=60)

    grid.add_overhead_line(config_606)

    config_607 = gce.create_known_abc_overhead_template(name='Config. 607',
                                                        z_nabc=z_607,
                                                        ysh_nabc=y_607,
                                                        phases=np.array([1]),
                                                        Vnom=4.16,
                                                        frequency=60)

    grid.add_overhead_line(config_607)

    # ----------------------------------------------------------------------------------------------------------------------
    # Lines
    # ----------------------------------------------------------------------------------------------------------------------
    line_632_645 = gce.Line(bus_from=bus_632,
                            bus_to=bus_645,
                            length=500 * 0.0003048)
    line_632_645.apply_template(config_603, grid.Sbase, grid.fBase, logger)
    grid.add_line(obj=line_632_645)

    line_645_646 = gce.Line(bus_from=bus_645,
                            bus_to=bus_646,
                            length=300 * 0.0003048)
    line_645_646.apply_template(config_603, grid.Sbase, grid.fBase, logger)
    grid.add_line(obj=line_645_646)

    line_632_633 = gce.Line(bus_from=bus_632,
                            bus_to=bus_633,
                            length=500 * 0.0003048)
    line_632_633.apply_template(config_602, grid.Sbase, grid.fBase, logger)
    grid.add_line(obj=line_632_633)

    line_632_671 = gce.Line(bus_from=bus_632,
                            bus_to=bus_671,
                            length=2000 * 0.0003048)
    line_632_671.apply_template(config_601, grid.Sbase, grid.fBase, logger)
    grid.add_line(obj=line_632_671)

    line_671_684 = gce.Line(bus_from=bus_671,
                            bus_to=bus_684,
                            length=300 * 0.0003048)
    line_671_684.apply_template(config_604, grid.Sbase, grid.fBase, logger)
    grid.add_line(obj=line_671_684)

    line_684_611 = gce.Line(bus_from=bus_684,
                            bus_to=bus_611,
                            length=300 * 0.0003048)
    line_684_611.apply_template(config_605, grid.Sbase, grid.fBase, logger)
    grid.add_line(obj=line_684_611)

    line_671_675 = gce.Line(bus_from=bus_671,
                            bus_to=bus_675,
                            length=500 * 0.0003048)
    line_671_675.apply_template(config_606, grid.Sbase, grid.fBase, logger)
    grid.add_line(obj=line_671_675)

    line_684_652 = gce.Line(bus_from=bus_684,
                            bus_to=bus_652,
                            length=800 * 0.0003048)
    line_684_652.apply_template(config_607, grid.Sbase, grid.fBase, logger)
    grid.add_line(obj=line_684_652)

    line_671_680 = gce.Line(bus_from=bus_671,
                            bus_to=bus_680,
                            length=1000 * 0.0003048)
    line_671_680.apply_template(config_601, grid.Sbase, grid.fBase, logger)
    grid.add_line(obj=line_671_680)

    # ----------------------------------------------------------------------------------------------------------------------
    # Transformer
    # ----------------------------------------------------------------------------------------------------------------------
    XFM_1 = gce.Transformer2W(name='XFM-1',
                              bus_from=bus_633,
                              bus_to=bus_634,
                              HV=4.16,
                              LV=0.48,
                              nominal_power=0.5,
                              rate=0.5,
                              r=1.1 * 2,
                              x=2 * 2)
    XFM_1.conn_f = WindingType.GroundedStar
    XFM_1.conn_t = WindingType.GroundedStar
    XFM_1.phases = np.array([1, 2, 3])
    grid.add_transformer2w(XFM_1)

    # ------------------------------------------------------------------------------------------------------------------
    # Run power flow
    # ------------------------------------------------------------------------------------------------------------------
    res = gce.power_flow3ph(grid=grid, options=gce.PowerFlowOptions())

    # ----------------------------------------------------------------------------------------------------------------------
    # Results
    # ----------------------------------------------------------------------------------------------------------------------
    Ua_reference = np.array(
        [1. + 0.j, 0. + 0.j, 0. + 0.j, 0.99690934 - 0.00115138j, 0.97231175 - 0.01309998j,
         0.96701492 - 0.04891478j, 0.96511924 - 0.04921662j, 0. + 0.j, 0.96012162 - 0.05287428j, 0.967015 - 0.04891481j,
         0.95973949 - 0.04769043j]
    )

    Ub_reference = np.array(
        [-0.5 - 0.8660254j, - 0.49814148 - 0.85632681j, - 0.49845802 - 0.85421114j, - 0.49973493 - 0.86386177j,
        - 0.49745893 - 0.84299841j, - 0.51502594 - 0.86901544j,
        0. + 0.j, 0. + 0.j, - 0.51893699 - 0.8694148j, - 0.515026 - 0.8690155j, 0. + 0.j]
    )

    Uc_reference = np.array(
        [-0.5 + 0.8660254j, - 0.49942153 + 0.86425949j, - 0.49908814 + 0.8621438j, - 0.49859895 + 0.86377297j,
        - 0.48164799 + 0.85137466j, - 0.4521935 + 0.84581621j, - 0.44971761 + 0.84482343j,
        - 0.44659921 + 0.84418802j,
        - 0.45148771 + 0.84389416j, - 0.45219352 + 0.84581629j,
        0. + 0.j]
    )

    Ua_comp = np.array([abs(res.voltage_A), abs(Ua_reference)])
    # Ub_comp = np.array([res.voltage_B, Ub_reference])

    assert np.allclose(res.voltage_A, Ua_reference, atol=1e-4)
    assert np.allclose(res.voltage_B, Ub_reference, atol=1e-4)
    assert np.allclose(res.voltage_C, Uc_reference, atol=1e-4)
