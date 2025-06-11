import GridCalEngine.api as gce
from GridCalEngine import WindingType, ShuntConnectionType, AdmittanceMatrix
import numpy as np
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation_3ph import PfBasicFormulation3Ph
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx

logger = gce.Logger()

grid = gce.MultiCircuit()
grid.fBase = 60

"""
13 Buses
"""
bus_650 = gce.Bus(name='650', Vnom=4.16, xpos=0, ypos=30)
bus_650.is_slack = True
grid.add_bus(obj=bus_650)
gen = gce.Generator(vset = 1.0625)
grid.add_generator(bus = bus_650, api_obj = gen)

bus_632 = gce.Bus(name='632', Vnom=4.16, xpos=0, ypos=20)
grid.add_bus(obj=bus_632)

bus_645 = gce.Bus(name='645', Vnom=4.16, xpos=-10, ypos=20)
grid.add_bus(obj=bus_645)

bus_646 = gce.Bus(name='646', Vnom=4.16, xpos=-20, ypos=20)
grid.add_bus(obj=bus_646)

bus_633 = gce.Bus(name='633', Vnom=4.16, xpos=10, ypos=20)
grid.add_bus(obj=bus_633)

bus_634 = gce.Bus(name='634', Vnom=0.48, xpos=20, ypos=20)
grid.add_bus(obj=bus_634)

bus_671 = gce.Bus(name='671', Vnom=4.16, xpos=0, ypos=10)
grid.add_bus(obj=bus_671)

bus_684 = gce.Bus(name='684', Vnom=4.16, xpos=-10, ypos=10)
grid.add_bus(obj=bus_684)

bus_611 = gce.Bus(name='611', Vnom=4.16, xpos=-20, ypos=10)
grid.add_bus(obj=bus_611)

bus_692 = gce.Bus(name='692', Vnom=4.16, xpos=10, ypos=10)
grid.add_bus(obj=bus_692)

bus_675 = gce.Bus(name='675', Vnom=4.16, xpos=20, ypos=10)
grid.add_bus(obj=bus_675)

bus_680 = gce.Bus(name='680', Vnom=4.16, xpos=0, ypos=0)
grid.add_bus(obj=bus_680)

bus_652 = gce.Bus(name='652', Vnom=4.16, xpos=-10, ypos=0)
grid.add_bus(obj=bus_652)

"""
Tap Changer between 650 - 632 ?
"""

"""
Impedances [Ohm/mile]
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
Admittances [uS/mile]
"""
y_601 = np.array([
    [1j * 6.2998, 1j * -1.9958, 1j * -1.2595],
    [1j * -1.9958, 1j * 5.9597, 1j * -0.7417],
    [1j * -1.2595, 1j * -0.7417, 1j * 5.6386]
], dtype=complex) / 10**6 / 1.60934

y_602 = np.array([
    [1j * 5.6990, 1j * -1.0817, 1j * -1.6905],
    [1j * -1.0817, 1j * 5.1795, 1j * -0.6588],
    [1j * -1.6905, 1j * -0.6588, 1j * 5.4246]
], dtype=complex) / 10**6 / 1.60934

y_603 = np.array([
    [1j * 4.7097, 1j * -0.8999],
    [1j * -0.8999, 1j * 4.6658]
], dtype=complex) / 10**6 / 1.60934

y_604 = np.array([
    [1j * 4.6658, 1j * -0.8999],
    [1j * -0.8999, 1j * 4.7097]
], dtype=complex) / 10**6 / 1.60934

y_605 = np.array([
    [1j * 4.5193]
], dtype=complex) / 10**6 / 1.60934

y_606 = np.array([
    [1j * 96.8897, 1j * 0.0000, 1j * 0.0000],
    [1j * 0.0000, 1j * 96.8897, 1j * 0.0000],
    [1j * 0.0000, 1j * 0.0000, 1j * 96.8897]
], dtype=complex) / 10**6 / 1.60934

y_607 = np.array([
    [1j * 88.9912]
], dtype=complex) / 10**6 / 1.60934

"""
Loads
"""
load_634 = gce.Load(P1=0.16,
                    Q1=0.11,
                    P2=0.12,
                    Q2=0.09,
                    P3=0.12,
                    Q3=0.09)
load_634.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus_634, api_obj=load_634)

load_645 = gce.Load(P1=0.0,
                    Q1=0.0,
                    P2=0.17,
                    Q2=0.125,
                    P3=0.0,
                    Q3=0.0)
load_645.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus_645, api_obj=load_645)

load_646 = gce.Load(G1=0.0,
                    B1=0.0,
                    G2=0.23,
                    B2=0.132,
                    G3=0.0,
                    B3=0.0)
load_646.conn = ShuntConnectionType.Delta
grid.add_load(bus=bus_646, api_obj=load_646)

load_652 = gce.Load(G1=0.128,
                    B1=0.086,
                    G2=0.0,
                    B2=0.0,
                    G3=0.0,
                    B3=0.0)
load_652.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus_652, api_obj=load_652)

load_671 = gce.Load(P1=0.385,
                    Q1=0.22,
                    P2=0.385,
                    Q2=0.22,
                    P3=0.385,
                    Q3=0.22)
load_671.conn = ShuntConnectionType.Delta
grid.add_load(bus=bus_671, api_obj=load_671)

load_675 = gce.Load(P1=0.485,
                    Q1=0.190,
                    P2=0.068,
                    Q2=0.06,
                    P3=0.29,
                    Q3=0.212)
load_675.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus_675, api_obj=load_675)

load_692 = gce.Load(Ir1=0.0,
                    Ii1=0.0,
                    Ir2=0.0,
                    Ii2=0.0,
                    Ir3=0.17,
                    Ii3=0.151)
load_692.conn = ShuntConnectionType.Delta
grid.add_load(bus=bus_692, api_obj=load_692)

load_611 = gce.Load(Ir1=0.0,
                    Ii1=0.0,
                    Ir2=0.0,
                    Ii2=0.0,
                    Ir3=0.17,
                    Ii3=0.08)
load_611.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus_611, api_obj=load_611)

load_632_671_distrib = gce.Load(P1=0.017/2,
                            Q1=0.010/2,
                            P2=0.066/2,
                            Q2=0.038/2,
                            P3=0.117/2,
                            Q3=0.068/2)
load_632_671_distrib.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus_632, api_obj=load_632_671_distrib)
grid.add_load(bus=bus_671, api_obj=load_632_671_distrib)

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
Transformer between 633 and 634
"""
XFM_1 = gce.Transformer2W(name='XFM-1',
                          bus_from=bus_633,
                          bus_to=bus_634,
                          HV=4.16,
                          LV=0.48,
                          nominal_power=0.5,
                          rate=0.5,
                          r=1.1*2,
                          x=2*2)
XFM_1.conn_f = WindingType.GroundedStar
XFM_1.conn_t = WindingType.GroundedStar
grid.add_transformer2w(XFM_1)

"""
Line Configurations
"""
config_601 = gce.OverheadLineType(name='Config. 601',
                                  Vnom=4.16,
                                  frequency=60)
config_601.z_abc = z_601
config_601.y_abc = y_601
config_601.y_phases_abc = np.array([1,2,3])
grid.add_overhead_line(config_601)

config_602 = gce.OverheadLineType(name='Config. 602',
                                  Vnom=4.16,
                                  frequency=60)
config_602.z_abc = z_602
config_602.y_abc = y_602
config_602.y_phases_abc = np.array([1,2,3])
grid.add_overhead_line(config_602)

config_603 = gce.OverheadLineType(name='Config. 603',
                                  Vnom=4.16,
                                  frequency=60)
config_603.z_abc = z_603
config_603.y_abc = y_603
config_603.y_phases_abc = np.array([2,3])
grid.add_overhead_line(config_603)

config_604 = gce.OverheadLineType(name='Config. 604',
                                  Vnom=4.16,
                                  frequency=60)
config_604.z_abc = z_604
config_604.y_abc = y_604
config_604.y_phases_abc = np.array([1,3])
grid.add_overhead_line(config_604)

config_605 = gce.OverheadLineType(name='Config. 605',
                                  Vnom=4.16,
                                  frequency=60)
config_605.z_abc = z_605
config_605.y_abc = y_605
config_605.y_phases_abc = np.array([3])
grid.add_overhead_line(config_605)

config_606 = gce.OverheadLineType(name='Config. 606',
                                  Vnom=4.16,
                                  frequency=60)
config_606.z_abc = z_606
config_606.y_abc = y_606
config_606.y_phases_abc = np.array([1,2,3])
grid.add_overhead_line(config_606)

config_607 = gce.OverheadLineType(name='Config. 607',
                                  Vnom=4.16,
                                  frequency=60)
config_607.z_abc = z_607
config_607.y_abc = y_607
config_607.y_phases_abc = np.array([1])
grid.add_overhead_line(config_607)

"""
Lines
"""
line_632_645 = gce.Line(bus_from=bus_632,
                        bus_to=bus_645,
                        length=500 * 0.0003048)
line_632_645.apply_template(config_603, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_632_645)

line_632_633 = gce.Line(bus_from=bus_632,
                        bus_to=bus_633,
                        length=500 * 0.0003048)
line_632_633.apply_template(config_602, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_632_633)

line_645_646 = gce.Line(bus_from=bus_645,
                        bus_to=bus_646,
                        length=300 * 0.0003048)
line_645_646.apply_template(config_603, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_645_646)

line_650_632 = gce.Line(bus_from=bus_650,
                        bus_to=bus_632,
                        length= 2000 * 0.0003048)
line_650_632.apply_template(config_601, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_650_632)

line_684_652 = gce.Line(bus_from=bus_684,
                        bus_to=bus_652,
                        length= 800 * 0.0003048)
line_684_652.apply_template(config_607, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_684_652)

line_632_671 = gce.Line(bus_from=bus_632,
                        bus_to=bus_671,
                        length= 2000 * 0.0003048)
line_632_671.apply_template(config_601, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_632_671)

line_671_684 = gce.Line(bus_from=bus_671,
                        bus_to=bus_684,
                        length= 300 * 0.0003048)
line_671_684.apply_template(config_604, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_671_684)

line_671_680 = gce.Line(bus_from=bus_671,
                        bus_to=bus_680,
                        length= 1000 * 0.0003048)
line_671_680.apply_template(config_601, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_671_680)

line_684_611 = gce.Line(bus_from=bus_684,
                        bus_to=bus_611,
                        length= 300 * 0.0003048)
line_684_611.apply_template(config_605, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_684_611)

line_692_675 = gce.Line(bus_from=bus_692,
                        bus_to=bus_675,
                        length= 500 * 0.0003048)
line_692_675.apply_template(config_606, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_692_675)

"""
Switch between 671 and 692
"""
switch = gce.Switch(name='Switch',
                    bus_from=bus_671,
                    bus_to=bus_692)
grid.add_switch(obj=switch)


"""
Power Flow
"""
def power_flow_3ph(grid, t_idx=None):
    nc = gce.compile_numerical_circuit_at(circuit=grid, fill_three_phase=True, t_idx = t_idx)

    V0 = nc.bus_data.Vbus
    S0 = nc.get_power_injections_pu()
    Qmax, Qmin = nc.get_reactive_power_limits()

    options = gce.PowerFlowOptions(tolerance=1e-10, max_iter=1000)

    problem = PfBasicFormulation3Ph(V0=V0, S0=S0, Qmin=Qmin*100, Qmax=Qmax*100, nc=nc, options=options)

    print('Ybus = \n', problem.Ybus.toarray())
    print('S0 = \n', problem.S0)
    print('I0 = \n', problem.I0)
    print('V0 = \n', problem.V)

    res = newton_raphson_fx(problem=problem, verbose=1)

    Ibus = problem.Ybus.dot(res.V)
    print('Ibus = \n', Ibus)

    Sbus = res.V * np.conj(Ibus)
    print('Sbus = \n', Sbus)

    return res

res_3ph = power_flow_3ph(grid)