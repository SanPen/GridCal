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
from VeraGridEngine.Simulations.ShortCircuitStudies.short_circuit_results import ShortCircuitResults
from VeraGridEngine.enumerations import FaultType, MethodShortCircuit, PhasesShortCircuit


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

def short_circuit_3ph(grid, fault_type, method, phases) -> ShortCircuitResults:
    """
    Short Circuit
    :param grid:
    :return:
    """
    nc = gce.compile_numerical_circuit_at(circuit=grid, fill_three_phase=True, t_idx=None)

    V0 = expandVoltage3ph(nc.bus_data.Vbus)
    V0[0] = 1.0210 * np.exp(1j * (-2.49 * np.pi / 180))
    V0[1] = 1.0420 * np.exp(1j * (-121.72 * np.pi / 180))
    V0[2] = 1.0174 * np.exp(1j * (117.83 * np.pi / 180))

    res_3ph = power_flow_3ph(grid, V0_3ph=V0)

    pf_res = gce.PowerFlowResults(
        n=grid.get_bus_number() * 3,
        m=grid.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True) * 3,
        n_hvdc=grid.get_hvdc_number(),
        n_vsc=grid.get_vsc_number(),
        n_gen=grid.get_generators_number(),
        n_batt=grid.get_batteries_number(),
        n_sh=grid.get_shunt_like_device_number(),
        bus_names=grid.get_bus_names(),
        branch_names=grid.get_branch_names(),
        hvdc_names=grid.get_hvdc_names(),
        vsc_names=grid.get_vsc_names(),
        gen_names=grid.get_generator_names(),
        batt_names=grid.get_battery_names(),
        sh_names=grid.get_shunt_like_devices_names(),
        bus_types=np.ones(grid.get_bus_number())
    )

    pf_res.voltage = res_3ph.V
    pf_res.Sbus = res_3ph.Scalc

    sc_options = gce.ShortCircuitOptions(bus_index=4,
                                         fault_type=fault_type,
                                         mid_line_fault=False,
                                         branch_index=0,
                                         branch_fault_locations=0.5,
                                         verbose=0,
                                         method=method,
                                         phases=phases)

    sc_driver = gce.ShortCircuitDriver(grid=grid,
                                       options=sc_options,
                                       pf_options=gce.PowerFlowOptions(three_phase_unbalanced=True),
                                       pf_results=pf_res)
    sc_driver.run()

    return sc_driver.results


def test_three_phase_to_ground_fault():
    """
    This test builds the IEEE 13-Bus Test Feeder and simulates a Three-Phase-to-Ground Fault (LLLG).
    The results have been validated using OpenDSS and Matlab.
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
    gen = gce.Generator(vset=1.0, r1=1e-10, x1=1e-10, r2=1e-10, x2=1e-10, r0=1e-10, x0=1e-10)
    grid.add_generator(bus=bus_632, api_obj=gen)

    bus_645 = gce.Bus(name='645', Vnom=4.16, xpos=-100 * 5, ypos=0)
    grid.add_bus(obj=bus_645)

    bus_646 = gce.Bus(name='646', Vnom=4.16, xpos=-200 * 5, ypos=0)
    grid.add_bus(obj=bus_646)

    bus_633 = gce.Bus(name='633', Vnom=4.16, xpos=100 * 5, ypos=0)
    grid.add_bus(obj=bus_633)

    bus_634 = gce.Bus(name='634', Vnom=0.48, xpos=200 * 5, ypos=0, r_fault=0.1)
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
    load_634 = gce.Load(P1=0.160,
                        Q1=0.110,
                        P2=0.120,
                        Q2=0.090,
                        P3=0.120,
                        Q3=0.090)
    load_634.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_634, api_obj=load_634)

    load_645 = gce.Load(P1=0.0,
                        Q1=0.0,
                        P2=0.170,
                        Q2=0.125,
                        P3=0.0,
                        Q3=0.0)
    load_645.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_645, api_obj=load_645)

    load_646 = gce.Load(G1=0.0,
                        B1=0.0,
                        G2=0.230,
                        B2=-0.132,
                        G3=0.0,
                        B3=0.0)
    load_646.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_646, api_obj=load_646)

    load_652 = gce.Load(G1=0.128,
                        B1=-0.086,
                        G2=0.0,
                        B2=0.0,
                        G3=0.0,
                        B3=0.0)
    load_652.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_652, api_obj=load_652)

    load_671 = gce.Load(P1=0.385,
                        Q1=0.220,
                        P2=0.385,
                        Q2=0.220,
                        P3=0.385,
                        Q3=0.220)
    load_671.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_671, api_obj=load_671)

    load_675 = gce.Load(P1=0.485,
                        Q1=0.190,
                        P2=0.068,
                        Q2=0.060,
                        P3=0.290,
                        Q3=0.212)
    load_675.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_675, api_obj=load_675)

    load_671_692 = gce.Load(Ir1=0.0,
                            Ii1=0.0,
                            Ir2=0.0,
                            Ii2=0.0,
                            Ir3=0.170,
                            Ii3=0.151)
    load_671_692.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_671, api_obj=load_671_692)

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

    res_SC = short_circuit_3ph(grid=grid,
                               fault_type=FaultType.ph3,
                               method=MethodShortCircuit.phases,
                               phases=PhasesShortCircuit.abc)

    Ua_obtained = res_SC.voltageA
    Ub_obtained = res_SC.voltageB
    Uc_obtained = res_SC.voltageC

    Ua_reference = np.array([
        1.02003599 - 0.04435737j, 0.0 + 0.0j, 0.0 + 0.0j, 0.92335156 - 0.02851233j, 0.00944052 - 0.01764448j,
        0.99070338 - 0.09384913j, 0.99074583 - 0.09695726j, 0.0 + 0.0j, 0.9829495 - 0.09564841j,
        0.99070346 - 0.09384917j, 0.98695215 - 0.10131184j
    ])

    Ub_reference = np.array([
        -0.54785089 - 0.88635399j, -0.54875124 - 0.87899878j, -0.55077001 - 0.87808189j, -0.4840374 - 0.79790671j,
        -0.02021348 + 0.00046903j, -0.55189152 - 0.8872176j, 0.0 + 0.0j, 0.0+0.0j, -0.55368371 - 0.88728923j,
        -0.55189159 - 0.88721765j, 0.0 + 0.0j
    ])

    Uc_reference = np.array([
        -0.47497293 + 0.89972411j, -0.4715181 + 0.89990176j, -0.46948981 + 0.89899954j, -0.44277556 + 0.79498421j,
        0.01014477 + 0.01690382j, -0.42294709 + 0.86234229j, -0.42040954 + 0.85919862j, -0.41792198 + 0.85681249j,
        -0.42283749 + 0.85856126j, -0.4229471 + 0.86234236j, 0.0 + 0.0j
    ])

    assert np.allclose(Ua_obtained, Ua_reference, atol=1e-4)
    assert np.allclose(Ub_obtained, Ub_reference, atol=1e-4)
    assert np.allclose(Uc_obtained, Uc_reference, atol=1e-4)

def test_single_line_to_ground_fault():
    """
    This test builds the IEEE 13-Bus Test Feeder and simulates a Single Line-to-Ground Fault (SLG).
    The results have been validated using OpenDSS and Matlab.
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
    gen = gce.Generator(vset=1.0, r1=1e-10, x1=1e-10, r2=1e-10, x2=1e-10, r0=1e-10, x0=1e-10)
    grid.add_generator(bus=bus_632, api_obj=gen)

    bus_645 = gce.Bus(name='645', Vnom=4.16, xpos=-100 * 5, ypos=0)
    grid.add_bus(obj=bus_645)

    bus_646 = gce.Bus(name='646', Vnom=4.16, xpos=-200 * 5, ypos=0)
    grid.add_bus(obj=bus_646)

    bus_633 = gce.Bus(name='633', Vnom=4.16, xpos=100 * 5, ypos=0)
    grid.add_bus(obj=bus_633)

    bus_634 = gce.Bus(name='634', Vnom=0.48, xpos=200 * 5, ypos=0, r_fault=0.1)
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
    load_634 = gce.Load(P1=0.160,
                        Q1=0.110,
                        P2=0.120,
                        Q2=0.090,
                        P3=0.120,
                        Q3=0.090)
    load_634.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_634, api_obj=load_634)

    load_645 = gce.Load(P1=0.0,
                        Q1=0.0,
                        P2=0.170,
                        Q2=0.125,
                        P3=0.0,
                        Q3=0.0)
    load_645.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_645, api_obj=load_645)

    load_646 = gce.Load(G1=0.0,
                        B1=0.0,
                        G2=0.230,
                        B2=-0.132,
                        G3=0.0,
                        B3=0.0)
    load_646.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_646, api_obj=load_646)

    load_652 = gce.Load(G1=0.128,
                        B1=-0.086,
                        G2=0.0,
                        B2=0.0,
                        G3=0.0,
                        B3=0.0)
    load_652.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_652, api_obj=load_652)

    load_671 = gce.Load(P1=0.385,
                        Q1=0.220,
                        P2=0.385,
                        Q2=0.220,
                        P3=0.385,
                        Q3=0.220)
    load_671.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_671, api_obj=load_671)

    load_675 = gce.Load(P1=0.485,
                        Q1=0.190,
                        P2=0.068,
                        Q2=0.060,
                        P3=0.290,
                        Q3=0.212)
    load_675.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_675, api_obj=load_675)

    load_671_692 = gce.Load(Ir1=0.0,
                            Ii1=0.0,
                            Ir2=0.0,
                            Ii2=0.0,
                            Ir3=0.170,
                            Ii3=0.151)
    load_671_692.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_671, api_obj=load_671_692)

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

    res_SC = short_circuit_3ph(grid=grid,
                               fault_type=FaultType.LG,
                               method=MethodShortCircuit.phases,
                               phases=PhasesShortCircuit.a)

    Ua_obtained = res_SC.voltageA
    Ub_obtained = res_SC.voltageB
    Uc_obtained = res_SC.voltageC

    Ua_reference = np.array([
        1.02003599 - 0.04435737j, 0.0 + 0.j, 0.0 + 0.j, 0.87612024 - 0.03188121j, 0.00886699 - 0.01679408j,
        0.99070338 - 0.09384913j, 0.99074583 - 0.09695726j, 0.0 + 0.0j, 0.9829495 - 0.09564841j,
        0.99070346 - 0.09384917j, 0.98695215 - 0.10131184j
    ])

    Ub_reference = np.array([
        -0.54785089 - 0.88635399j, -0.54875124 - 0.87899878j, -0.55077001 - 0.87808189j, -0.59276898 - 0.88946302j,
        -0.58924585 - 0.86910368j, -0.55189152 - 0.8872176j, 0.0 + 0.0j, 0.0 + 0.0j, -0.55368371 - 0.88728923j,
        -0.55189159 - 0.88721765j, 0.0 + 0.0j
    ])

    Uc_reference = np.array([
        -0.47497293 + 0.89972411j, -0.4715181 + 0.89990176j, -0.46948981 + 0.89899954j, -0.5258212 + 0.88854078j,
        -0.50874582 + 0.8763412j, -0.42294709 + 0.86234229j, -0.42040954 + 0.85919862j, -0.41792198 + 0.85681249j,
        -0.42283749 + 0.85856126j, -0.4229471 + 0.86234236j,
        0. + 0.j
    ])

    assert np.allclose(Ua_obtained, Ua_reference, atol=1e-4)
    assert np.allclose(Ub_obtained, Ub_reference, atol=1e-4)
    assert np.allclose(Uc_obtained, Uc_reference, atol=1e-4)


def test_double_line_to_ground_fault():
    """
    This test builds the IEEE 13-Bus Test Feeder and simulates a Double Line-to-Ground Fault (DLG).
    The results have been validated using OpenDSS and Matlab.
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
    gen = gce.Generator(vset=1.0, r1=1e-10, x1=1e-10, r2=1e-10, x2=1e-10, r0=1e-10, x0=1e-10)
    grid.add_generator(bus=bus_632, api_obj=gen)

    bus_645 = gce.Bus(name='645', Vnom=4.16, xpos=-100 * 5, ypos=0)
    grid.add_bus(obj=bus_645)

    bus_646 = gce.Bus(name='646', Vnom=4.16, xpos=-200 * 5, ypos=0)
    grid.add_bus(obj=bus_646)

    bus_633 = gce.Bus(name='633', Vnom=4.16, xpos=100 * 5, ypos=0)
    grid.add_bus(obj=bus_633)

    bus_634 = gce.Bus(name='634', Vnom=0.48, xpos=200 * 5, ypos=0, r_fault=0.1)
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
    load_634 = gce.Load(P1=0.160,
                        Q1=0.110,
                        P2=0.120,
                        Q2=0.090,
                        P3=0.120,
                        Q3=0.090)
    load_634.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_634, api_obj=load_634)

    load_645 = gce.Load(P1=0.0,
                        Q1=0.0,
                        P2=0.170,
                        Q2=0.125,
                        P3=0.0,
                        Q3=0.0)
    load_645.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_645, api_obj=load_645)

    load_646 = gce.Load(G1=0.0,
                        B1=0.0,
                        G2=0.230,
                        B2=-0.132,
                        G3=0.0,
                        B3=0.0)
    load_646.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_646, api_obj=load_646)

    load_652 = gce.Load(G1=0.128,
                        B1=-0.086,
                        G2=0.0,
                        B2=0.0,
                        G3=0.0,
                        B3=0.0)
    load_652.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_652, api_obj=load_652)

    load_671 = gce.Load(P1=0.385,
                        Q1=0.220,
                        P2=0.385,
                        Q2=0.220,
                        P3=0.385,
                        Q3=0.220)
    load_671.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_671, api_obj=load_671)

    load_675 = gce.Load(P1=0.485,
                        Q1=0.190,
                        P2=0.068,
                        Q2=0.060,
                        P3=0.290,
                        Q3=0.212)
    load_675.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_675, api_obj=load_675)

    load_671_692 = gce.Load(Ir1=0.0,
                            Ii1=0.0,
                            Ir2=0.0,
                            Ii2=0.0,
                            Ir3=0.170,
                            Ii3=0.151)
    load_671_692.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_671, api_obj=load_671_692)

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

    res_SC = short_circuit_3ph(grid=grid,
                               fault_type=FaultType.LLG,
                               method=MethodShortCircuit.phases,
                               phases=PhasesShortCircuit.ca)

    Ua_obtained = res_SC.voltageA
    Ub_obtained = res_SC.voltageB
    Uc_obtained = res_SC.voltageC

    Ua_reference = np.array([
        1.02003599 - 0.04435737j, 0.0 + 0.0j, 0.0 + 0.0j, 0.908033 - 0.06558249j, 0.00857901 - 0.01775737j,
        0.99070338 - 0.09384913j, 0.99074583 - 0.09695726j, 0.0 + 0.0j, 0.9829495 - 0.09564841j,
        0.99070346 - 0.09384917j, 0.98695215 - 0.10131184j
    ])

    Ub_reference = np.array([
        -0.54785089 - 0.88635399j, -0.54875124 - 0.87899878j, - 0.55077001 - 0.87808189j, - 0.56820752 - 0.92126371j,
        - 0.56536727 - 0.90053428j, -0.55189152 - 0.8872176j, 0.0 + 0.0j, 0.0 + 0.0j, -0.55368371 - 0.88728923j,
        -0.55189159 - 0.88721765j, 0.0 + 0.0j
    ])

    Uc_reference = np.array([
        -0.47497293 + 0.89972411j, -0.4715181 + 0.89990176j, -0.46948981 + 0.89899954j, -0.45765194 + 0.76181308j,
        0.00936114 + 0.01682478j, -0.42294709 + 0.86234229j, -0.42040954 + 0.85919862j, -0.41792198 + 0.85681249j,
        -0.42283749 + 0.85856126j, -0.4229471 + 0.86234236j, 0.0 + 0.0j
    ])

    assert np.allclose(Ua_obtained, Ua_reference, atol=1e-4)
    assert np.allclose(Ub_obtained, Ub_reference, atol=1e-4)
    assert np.allclose(Uc_obtained, Uc_reference, atol=1e-4)


def test_line_to_line_fault():
    """
    This test builds the IEEE 13-Bus Test Feeder and simulates a Line-to-Line Fault (LL).
    The results have been validated using OpenDSS and Matlab.
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
    gen = gce.Generator(vset=1.0, r1=1e-10, x1=1e-10, r2=1e-10, x2=1e-10, r0=1e-10, x0=1e-10)
    grid.add_generator(bus=bus_632, api_obj=gen)

    bus_645 = gce.Bus(name='645', Vnom=4.16, xpos=-100 * 5, ypos=0)
    grid.add_bus(obj=bus_645)

    bus_646 = gce.Bus(name='646', Vnom=4.16, xpos=-200 * 5, ypos=0)
    grid.add_bus(obj=bus_646)

    bus_633 = gce.Bus(name='633', Vnom=4.16, xpos=100 * 5, ypos=0)
    grid.add_bus(obj=bus_633)

    bus_634 = gce.Bus(name='634', Vnom=0.48, xpos=200 * 5, ypos=0, r_fault=0.1)
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
    load_634 = gce.Load(P1=0.160,
                        Q1=0.110,
                        P2=0.120,
                        Q2=0.090,
                        P3=0.120,
                        Q3=0.090)
    load_634.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_634, api_obj=load_634)

    load_645 = gce.Load(P1=0.0,
                        Q1=0.0,
                        P2=0.170,
                        Q2=0.125,
                        P3=0.0,
                        Q3=0.0)
    load_645.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_645, api_obj=load_645)

    load_646 = gce.Load(G1=0.0,
                        B1=0.0,
                        G2=0.230,
                        B2=-0.132,
                        G3=0.0,
                        B3=0.0)
    load_646.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_646, api_obj=load_646)

    load_652 = gce.Load(G1=0.128,
                        B1=-0.086,
                        G2=0.0,
                        B2=0.0,
                        G3=0.0,
                        B3=0.0)
    load_652.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_652, api_obj=load_652)

    load_671 = gce.Load(P1=0.385,
                        Q1=0.220,
                        P2=0.385,
                        Q2=0.220,
                        P3=0.385,
                        Q3=0.220)
    load_671.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_671, api_obj=load_671)

    load_675 = gce.Load(P1=0.485,
                        Q1=0.190,
                        P2=0.068,
                        Q2=0.060,
                        P3=0.290,
                        Q3=0.212)
    load_675.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_675, api_obj=load_675)

    load_671_692 = gce.Load(Ir1=0.0,
                            Ii1=0.0,
                            Ir2=0.0,
                            Ii2=0.0,
                            Ir3=0.170,
                            Ii3=0.151)
    load_671_692.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_671, api_obj=load_671_692)

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

    res_SC = short_circuit_3ph(grid=grid,
                               fault_type=FaultType.LL,
                               method=MethodShortCircuit.phases,
                               phases=PhasesShortCircuit.ab)

    Ua_obtained = res_SC.voltageA
    Ub_obtained = res_SC.voltageB
    Uc_obtained = res_SC.voltageC

    Ua_reference = np.array([
        1.02003599 - 0.04435737j, 0.0 + 0.0j, 0.0 + 0.0j, 0.9331353 - 0.07515303j, 0.23329598 - 0.46068763j,
        0.99070338 - 0.09384913j, 0.99074583 - 0.09695726j, 0.0 + 0.0j, 0.9829495 - 0.09564841j,
        0.99070346 - 0.09384917j, 0.98695215 - 0.10131184j
    ])

    Ub_reference = np.array([
        -0.54785089 - 0.88635399j, -0.54875124 - 0.87899878j, -0.55077001 - 0.87808189j, -0.46261692 - 0.85174847j,
        0.21846762 - 0.45162668j, -0.55189152 - 0.8872176j, 0.0 + 0.0j, 0.0 + 0.0j, -0.55368371 - 0.88728923j,
        -0.55189159 - 0.88721765j,  0. + 0.j
    ])

    Uc_reference = np.array([
        -0.47497293 + 0.89972411j, -0.4715181 + 0.89990176j, -0.46948981 + 0.89899954j, -0.47951579 + 0.888732j,
        -0.46329973 + 0.87614846j, -0.42294709 + 0.86234229j, -0.42040954 + 0.85919862j, -0.41792198 + 0.85681249j,
        -0.42283749 + 0.85856126j, -0.4229471 + 0.86234236j, 0.0 + 0.0j
    ])

    assert np.allclose(Ua_obtained, Ua_reference, atol=1e-4)
    assert np.allclose(Ub_obtained, Ub_reference, atol=1e-4)
    assert np.allclose(Uc_obtained, Uc_reference, atol=1e-4)


def test_three_phase_fault():
    """
    This test builds the IEEE 13-Bus Test Feeder and simulates a Three-Phase Fault (LLL).
    The results have been validated using OpenDSS and Matlab.
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
    gen = gce.Generator(vset=1.0, r1=1e-10, x1=1e-10, r2=1e-10, x2=1e-10, r0=1e-10, x0=1e-10)
    grid.add_generator(bus=bus_632, api_obj=gen)

    bus_645 = gce.Bus(name='645', Vnom=4.16, xpos=-100 * 5, ypos=0)
    grid.add_bus(obj=bus_645)

    bus_646 = gce.Bus(name='646', Vnom=4.16, xpos=-200 * 5, ypos=0)
    grid.add_bus(obj=bus_646)

    bus_633 = gce.Bus(name='633', Vnom=4.16, xpos=100 * 5, ypos=0)
    grid.add_bus(obj=bus_633)

    bus_634 = gce.Bus(name='634', Vnom=0.48, xpos=200 * 5, ypos=0, r_fault=0.1)
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
    load_634 = gce.Load(P1=0.160,
                        Q1=0.110,
                        P2=0.120,
                        Q2=0.090,
                        P3=0.120,
                        Q3=0.090)
    load_634.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_634, api_obj=load_634)

    load_645 = gce.Load(P1=0.0,
                        Q1=0.0,
                        P2=0.170,
                        Q2=0.125,
                        P3=0.0,
                        Q3=0.0)
    load_645.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_645, api_obj=load_645)

    load_646 = gce.Load(G1=0.0,
                        B1=0.0,
                        G2=0.230,
                        B2=-0.132,
                        G3=0.0,
                        B3=0.0)
    load_646.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_646, api_obj=load_646)

    load_652 = gce.Load(G1=0.128,
                        B1=-0.086,
                        G2=0.0,
                        B2=0.0,
                        G3=0.0,
                        B3=0.0)
    load_652.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_652, api_obj=load_652)

    load_671 = gce.Load(P1=0.385,
                        Q1=0.220,
                        P2=0.385,
                        Q2=0.220,
                        P3=0.385,
                        Q3=0.220)
    load_671.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_671, api_obj=load_671)

    load_675 = gce.Load(P1=0.485,
                        Q1=0.190,
                        P2=0.068,
                        Q2=0.060,
                        P3=0.290,
                        Q3=0.212)
    load_675.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_675, api_obj=load_675)

    load_671_692 = gce.Load(Ir1=0.0,
                            Ii1=0.0,
                            Ir2=0.0,
                            Ii2=0.0,
                            Ir3=0.170,
                            Ii3=0.151)
    load_671_692.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_671, api_obj=load_671_692)

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

    res_SC = short_circuit_3ph(grid=grid,
                               fault_type=FaultType.LLL,
                               method=MethodShortCircuit.phases,
                               phases=PhasesShortCircuit.abc)

    Ua_obtained = res_SC.voltageA
    Ub_obtained = res_SC.voltageB
    Uc_obtained = res_SC.voltageC

    Ua_reference = np.array([
        1.02003599 - 0.04435737j, 0.0 + 0.0j, 0.0 + 0.0j, 0.92266007 - 0.03018665j, 0.00166156 - 0.0189617j,
        0.99070338 - 0.09384913j, 0.99074583 - 0.09695726j, 0.0 + 0.0j, 0.9829495 - 0.09564841j,
        0.99070346 - 0.09384917j, 0.98695215 - 0.10131184j
    ])

    Ub_reference = np.array([
        -0.54785089 - 0.88635399j, -0.54875124 - 0.87899878j, -0.55077001 - 0.87808189j, -0.48289818 - 0.80083292j,
        -0.00821963 - 0.01276833j, -0.55189152 - 0.8872176j, 0.0 + 0.0j, 0.0 + 0.0j, -0.55368371 - 0.88728923j,
        -0.55189159 - 0.88721765j, 0.0 + 0.0j
    ])

    Uc_reference = np.array([
        -0.47497293 + 0.89972411j, -0.4715181 + 0.89990176j, -0.46948981 + 0.89899954j, -0.44396357 + 0.79106747j,
        0.00203004 - 0.00736884j, -0.42294709 + 0.86234229j, -0.42040954 + 0.85919862j, -0.41792198 + 0.85681249j,
        -0.42283749 + 0.85856126j, -0.4229471 + 0.86234236j, 0.0 + 0.0j
    ])

    assert np.allclose(Ua_obtained, Ua_reference, atol=1e-4)
    assert np.allclose(Ub_obtained, Ub_reference, atol=1e-4)
    assert np.allclose(Uc_obtained, Uc_reference, atol=1e-4)