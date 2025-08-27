# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import VeraGridEngine.api as gce
from VeraGridEngine import WindingType, ShuntConnectionType
import numpy as np
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation_3ph import (PfBasicFormulation3Ph, expand3ph,
                                                                                        expandVoltage3ph)


def power_flow_3ph(grid: gce.MultiCircuit, V0_3ph: Vec):
    """

    :param grid:
    :param V0_3ph: Voltage vector expanded for 3N (no need for masks to be applied)
    :return:
    """
    nc = gce.compile_numerical_circuit_at(circuit=grid, fill_three_phase=True, t_idx=None)

    S0 = nc.get_power_injections_pu()
    Qmax, Qmin = nc.get_reactive_power_limits()

    options = gce.PowerFlowOptions(tolerance=1e-10, max_iter=1000)

    problem = PfBasicFormulation3Ph(
        V0=V0_3ph,
        S0=expand3ph(S0),
        Qmin=Qmin * 100.0,
        Qmax=Qmax * 100.0,
        nc=nc,
        options=options,
        logger=gce.Logger()
    )

    res = newton_raphson_fx(problem=problem, verbose=1, max_iter=1000)

    return res


def test_ieee_13_bus_feeder():
    """
    This test builds the IEEE 13-Bus Test Feeder and compares the obtained results with the reference values.
    :return:
    """
    logger = gce.Logger()

    grid = gce.MultiCircuit()
    grid.fBase = 60

    """
    13 Buses
    """
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

    """
    Impedances [Ohm/km]
    """
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

    """
    Admittances [S/km]
    """
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

    """
    Loads
    """
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
    load_646 = gce.Load(G1=0.0,
                        B1=0.0,
                        G2=0.230,
                        B2=0.132,
                        G3=0.0,
                        B3=0.0)
    load_646.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_646, api_obj=load_646)

    # Single-phase impedance load
    load_652 = gce.Load(G1=0.128,
                        B1=0.086,
                        G2=0.0,
                        B2=0.0,
                        G3=0.0,
                        B3=0.0)
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
    load_671_692 = gce.Load(Ir1=0.0,
                            Ii1=0.0,
                            Ir2=0.0,
                            Ii2=0.0,
                            Ir3=0.170,
                            Ii3=0.151)
    load_671_692.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_671, api_obj=load_671_692)

    # Single-phase current load
    load_611 = gce.Load(Ir1=0.0,
                        Ii1=0.0,
                        Ir2=0.0,
                        Ii2=0.0,
                        Ir3=0.170,
                        Ii3=0.080)
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

    """
    Capacitors
    """
    cap_675 = gce.Shunt(B1=0.2,
                        B2=0.2,
                        B3=0.2)
    cap_675.conn = ShuntConnectionType.GroundedStar
    grid.add_shunt(bus=bus_675, api_obj=cap_675)

    cap_611 = gce.Shunt(B1=0.0,
                        B2=0.0,
                        B3=0.1)
    cap_611.conn = ShuntConnectionType.GroundedStar
    grid.add_shunt(bus=bus_611, api_obj=cap_611)

    """
    Line Configurations
    """
    config_601 = gce.create_known_abc_overhead_template(name='Config. 601',
                                                        z_abc=z_601,
                                                        ysh_abc=y_601,
                                                        phases=np.array([1, 2, 3]),
                                                        Vnom=4.16,
                                                        frequency=60)
    grid.add_overhead_line(config_601)

    config_602 = gce.create_known_abc_overhead_template(name='Config. 602',
                                                        z_abc=z_602,
                                                        ysh_abc=y_602,
                                                        phases=np.array([1, 2, 3]),
                                                        Vnom=4.16,
                                                        frequency=60)

    grid.add_overhead_line(config_602)

    config_603 = gce.create_known_abc_overhead_template(name='Config. 603',
                                                        z_abc=z_603,
                                                        ysh_abc=y_603,
                                                        phases=np.array([2, 3]),
                                                        Vnom=4.16,
                                                        frequency=60)

    grid.add_overhead_line(config_603)

    config_604 = gce.create_known_abc_overhead_template(name='Config. 604',
                                                        z_abc=z_604,
                                                        ysh_abc=y_604,
                                                        phases=np.array([1, 3]),
                                                        Vnom=4.16,
                                                        frequency=60)

    grid.add_overhead_line(config_604)

    config_605 = gce.create_known_abc_overhead_template(name='Config. 605',
                                                        z_abc=z_605,
                                                        ysh_abc=y_605,
                                                        phases=np.array([3]),
                                                        Vnom=4.16,
                                                        frequency=60)

    grid.add_overhead_line(config_605)

    config_606 = gce.create_known_abc_overhead_template(name='Config. 606',
                                                        z_abc=z_606,
                                                        ysh_abc=y_606,
                                                        phases=np.array([1, 2, 3]),
                                                        Vnom=4.16,
                                                        frequency=60)

    grid.add_overhead_line(config_606)

    config_607 = gce.create_known_abc_overhead_template(name='Config. 607',
                                                        z_abc=z_607,
                                                        ysh_abc=y_607,
                                                        phases=np.array([1]),
                                                        Vnom=4.16,
                                                        frequency=60)

    grid.add_overhead_line(config_607)

    """
    Lines
    """
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

    """
    Transformer between 633 and 634
    """
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
    grid.add_transformer2w(XFM_1)

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

    # ------------------------------------------------------------------------------------------------------------------
    # Run power flow
    # ------------------------------------------------------------------------------------------------------------------
    nc = gce.compile_numerical_circuit_at(circuit=grid, fill_three_phase=True, t_idx=None)

    V0 = expandVoltage3ph(nc.bus_data.Vbus)
    V0[0] = 1.0210 * np.exp(1j * (-2.49 * np.pi / 180))
    V0[1] = 1.0420 * np.exp(1j * (-121.72 * np.pi / 180))
    V0[2] = 1.0174 * np.exp(1j * (117.83 * np.pi / 180))

    res_3ph = power_flow_3ph(grid, V0_3ph=V0)

    U_obtained = abs(res_3ph.V)
    angle_obtained = np.degrees(np.angle((res_3ph.V)))

    U_reference = np.array(
        [1.021, 1.042, 1.0174, 0.0, 1.0328, 1.0154, 0.0, 1.0311, 1.0134, 1.018, 1.0401, 1.0148, 0.994, 1.0218, 0.996,
         0.99, 1.0529, 0.9777, 0.9881, 0.0, 0.9757, 0.0, 0.0, 0.9737, 0.9835, 1.0553, 0.9758, 0.99, 1.0529, 0.9777,
         0.9825, 0.0, 0.0])
    angle_reference = np.array(
        [-2.49, -121.72, 117.83, 0.0, -121.9, 117.86, 0.0, -121.98, 117.9, -2.55, -121.77, 117.83, -3.23, -122.22,
         117.35, -5.3, -122.34, 116.03, -5.32, 0.0, 115.93, 0.0, 0.0, 115.78, -5.55, -122.52, 116.04, -5.3, -122.34,
         116.03, -5.25, 0.0, 0.0])

    assert np.allclose(U_obtained, U_reference, atol=1e-4)
    assert np.allclose(angle_obtained, angle_reference, atol=1e-2)


def test_ieee_13_bus_feeder_modified():
    """
    This test builds a modified version of the IEEE 13-Bus Test Feeder and compares the obtained results with the
    reference values. In this case, it includes only the load types that doesn't appear in the original test case:

    - Three-phase Star Impedance Load
    - Three-phase Star Current Load
    - Three-phase Delta Impedance Load
    - Three-phase Delta Current Load
    - Two-phase Delta Power Load

    The results have been validated using the software OpenDSS.

    :return:
    """
    logger = gce.Logger()

    grid = gce.MultiCircuit()
    grid.fBase = 60

    """
    13 Buses
    """
    bus_632 = gce.Bus(name='632', Vnom=4.16, xpos=0, ypos=0)
    bus_632.is_slack = True
    grid.add_bus(obj=bus_632)
    gen = gce.Generator(vset=1.0)
    grid.add_generator(bus=bus_632, api_obj=gen)

    bus_633 = gce.Bus(name='633', Vnom=4.16, xpos=100 * 5, ypos=0)
    grid.add_bus(obj=bus_633)

    bus_634 = gce.Bus(name='634', Vnom=0.48, xpos=200 * 5, ypos=0)
    grid.add_bus(obj=bus_634)

    bus_645 = gce.Bus(name='645', Vnom=4.16, xpos=-100 * 5, ypos=0)
    grid.add_bus(obj=bus_645)

    bus_646 = gce.Bus(name='646', Vnom=4.16, xpos=-200 * 5, ypos=0)
    grid.add_bus(obj=bus_646)

    bus_652 = gce.Bus(name='652', Vnom=4.16, xpos=-100 * 5, ypos=200 * 5)
    grid.add_bus(obj=bus_652)

    bus_671 = gce.Bus(name='671', Vnom=4.16, xpos=0, ypos=100 * 5)
    grid.add_bus(obj=bus_671)

    bus_675 = gce.Bus(name='675', Vnom=4.16, xpos=200 * 5, ypos=100 * 5)
    grid.add_bus(obj=bus_675)

    bus_611 = gce.Bus(name='611', Vnom=4.16, xpos=-200 * 5, ypos=100 * 5)
    grid.add_bus(obj=bus_611)

    bus_680 = gce.Bus(name='680', Vnom=4.16, xpos=0, ypos=200 * 5)
    grid.add_bus(obj=bus_680)

    bus_684 = gce.Bus(name='684', Vnom=4.16, xpos=-100 * 5, ypos=100 * 5)
    grid.add_bus(obj=bus_684)

    """
    Impedances [Ohm/km]
    """
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

    """
    Admittances [S/km]
    """
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

    """
    Loads
    """
    # Three-phase Star Impedance Load (Validated with OpenDSS)
    load_634 = gce.Load(G1=0.160,
                        B1=0.110,
                        G2=0.120,
                        B2=0.090,
                        G3=0.120,
                        B3=0.090)
    load_634.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_634, api_obj=load_634)

    # Three-phase Star Current Load (Validated with OpenDSS)
    load_633 = gce.Load(Ir1=0.160,
                        Ii1=0.110,
                        Ir2=0.120,
                        Ii2=0.090,
                        Ir3=0.120,
                        Ii3=0.090)
    load_633.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_633, api_obj=load_633)

    # Three-phase Delta Impedance Load (Validated with OpenDSS)
    load_675 = gce.Load(G1=0.160,
                        B1=0.110,
                        G2=0.120,
                        B2=0.090,
                        G3=0.120,
                        B3=0.090)
    load_675.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_675, api_obj=load_675)

    # Three-phase Delta Current Load (Validated with OpenDSS)
    load_680 = gce.Load(Ir1=0.160,
                        Ii1=0.110,
                        Ir2=0.120,
                        Ii2=0.090,
                        Ir3=0.120,
                        Ii3=0.090)
    load_680.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_680, api_obj=load_680)

    # Two-phase Delta Power Load (Validated with OpenDSS)
    load_684 = gce.Load(P1=0.0,
                        Q1=0.0,
                        P2=0.0,
                        Q2=0.0,
                        P3=0.160,
                        Q3=0.110)
    load_684.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_684, api_obj=load_684)

    """
    Capacitors
    """
    # Three-phase Delta (Validated with OpenDSS)
    cap_671 = gce.Shunt(B1=0.2,
                        B2=0.2,
                        B3=0.2)
    cap_671.conn = ShuntConnectionType.Delta
    grid.add_shunt(bus=bus_671, api_obj=cap_671)

    # Two-phase Delta (Validated with OpenDSS)
    cap_646 = gce.Shunt(B1=0.0,
                        B2=0.2,
                        B3=0.0)
    cap_646.conn = ShuntConnectionType.Delta
    grid.add_shunt(bus=bus_646, api_obj=cap_646)

    """
    Line Configurations
    """
    config_601 = gce.create_known_abc_overhead_template(name='Config. 601',
                                                        z_abc=z_601,
                                                        ysh_abc=y_601,
                                                        phases=np.array([1, 2, 3]),
                                                        Vnom=4.16,
                                                        frequency=60)
    grid.add_overhead_line(config_601)

    config_602 = gce.create_known_abc_overhead_template(name='Config. 602',
                                                        z_abc=z_602,
                                                        ysh_abc=y_602,
                                                        phases=np.array([1, 2, 3]),
                                                        Vnom=4.16,
                                                        frequency=60)

    grid.add_overhead_line(config_602)

    config_603 = gce.create_known_abc_overhead_template(name='Config. 603',
                                                        z_abc=z_603,
                                                        ysh_abc=y_603,
                                                        phases=np.array([2, 3]),
                                                        Vnom=4.16,
                                                        frequency=60)

    grid.add_overhead_line(config_603)

    config_604 = gce.create_known_abc_overhead_template(name='Config. 604',
                                                        z_abc=z_604,
                                                        ysh_abc=y_604,
                                                        phases=np.array([1, 3]),
                                                        Vnom=4.16,
                                                        frequency=60)

    grid.add_overhead_line(config_604)

    config_605 = gce.create_known_abc_overhead_template(name='Config. 605',
                                                        z_abc=z_605,
                                                        ysh_abc=y_605,
                                                        phases=np.array([3]),
                                                        Vnom=4.16,
                                                        frequency=60)

    grid.add_overhead_line(config_605)

    config_606 = gce.create_known_abc_overhead_template(name='Config. 606',
                                                        z_abc=z_606,
                                                        ysh_abc=y_606,
                                                        phases=np.array([1, 2, 3]),
                                                        Vnom=4.16,
                                                        frequency=60)

    grid.add_overhead_line(config_606)

    config_607 = gce.create_known_abc_overhead_template(name='Config. 607',
                                                        z_abc=z_607,
                                                        ysh_abc=y_607,
                                                        phases=np.array([1]),
                                                        Vnom=4.16,
                                                        frequency=60)

    grid.add_overhead_line(config_607)

    """
    Lines
    """
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

    """
    Transformer between 633 and 634
    """
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
    grid.add_transformer2w(XFM_1)

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

    # ------------------------------------------------------------------------------------------------------------------
    # Run power flow
    # ------------------------------------------------------------------------------------------------------------------
    nc = gce.compile_numerical_circuit_at(circuit=grid, fill_three_phase=True, t_idx=None)

    V0 = expandVoltage3ph(nc.bus_data.Vbus)
    V0[0] = 1.0210 * np.exp(1j * (-2.49 * np.pi / 180))
    V0[1] = 1.0420 * np.exp(1j * (-121.72 * np.pi / 180))
    V0[2] = 1.0174 * np.exp(1j * (117.83 * np.pi / 180))

    res_3ph = power_flow_3ph(grid, V0_3ph=V0)

    U_obtained = abs(res_3ph.V)
    angle_obtained = np.degrees(np.angle((res_3ph.V)))

    print(U_obtained)

    U_reference = np.array(
        [1.021, 1.042, 1.0174, 1.015, 1.038, 1.0123, 0.9914, 1.0189, 0.9936, 0.0, 1.0446, 1.0178, 0.0, 1.0462, 1.0181,
         1.0113, 0.0, 0.0, 1.0127, 1.0403, 1.0129, 1.0109, 1.0385, 1.0113, 0.0, 0.0, 1.0116, 1.01, 1.0376, 1.0101,
         1.0113, 0.0, 1.0116])
    angle_reference = np.array(
        [-2.49, -121.72, 117.83, -2.62, -121.82, 117.82, -3.28, -122.29, 117.34, 0.0, -121.78, 117.67, 0.0, -121.81,
         117.58, -3.1, 0.0, 0.0, -3.14, -122.32, 117.01, -3.16, -122.31, 117.0, 0.0, 0.0, 116.96, -3.25, -122.44,
         116.91, -3.1, 0.0, 116.96])

    assert np.allclose(U_obtained, U_reference, atol=1e-4)
    assert np.allclose(angle_obtained, angle_reference, atol=1e-2)