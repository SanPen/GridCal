import VeraGridEngine.api as gce
from VeraGridEngine import WindingType, ShuntConnectionType, AdmittanceMatrix
import numpy as np
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation_3ph import PfBasicFormulation3Ph
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx
import pandas as pd

logger = gce.Logger()

grid = gce.MultiCircuit()
grid.fBase = 60

"""
13 Buses
"""
bus_632 = gce.Bus(name='632', Vnom=4.16, xpos=0, ypos=0)
bus_632.is_slack = True
grid.add_bus(obj=bus_632)
gen = gce.Generator()
grid.add_generator(bus = bus_632, api_obj = gen)

bus_633 = gce.Bus(name='633', Vnom=4.16, xpos=100*5, ypos=0)
grid.add_bus(obj=bus_633)

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
# load_634 = gce.Load(G1=0.160*10,
#                     B1=0.110*10,
#                     G2=0.0,
#                     B2=0.0,
#                     G3=0.0,
#                     B3=0.0)
# load_634.conn = ShuntConnectionType.GroundedStar
# grid.add_load(bus=bus_633, api_obj=load_634)

load_634 = gce.Load(Ir1=0.160*10,
                    Ii1=0.110*10,
                    Ir2=0.0,
                    Ii2=0.0,
                    Ir3=0.0,
                    Ii3=0.0)
load_634.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus_633, api_obj=load_634)

# load_634 = gce.Load(P1=0.160*10,
#                     Q1=0.110*10,
#                     P2=0.0,
#                     Q2=0.0,
#                     P3=0.0,
#                     Q3=0.0)
# load_634.conn = ShuntConnectionType.GroundedStar
# grid.add_load(bus=bus_633, api_obj=load_634)

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
line_632_633 = gce.Line(bus_from=bus_632,
                        bus_to=bus_633,
                        length=500 * 0.0003048)
line_632_633.apply_template(config_602, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_632_633)

# ----------------------------------------------------------------------------------------------------------------------
# Run power flow
# ----------------------------------------------------------------------------------------------------------------------

res = gce.power_flow(grid=grid, options=gce.PowerFlowOptions(three_phase_unbalanced=True))

print(res.get_bus_df())

gce.save_file(grid, "IEEE 13 bus (3-phase).gridcal")