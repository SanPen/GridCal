import GridCalEngine.api as gce
from GridCalEngine import WindingType, ShuntConnectionType, AdmittanceMatrix
import numpy as np
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation_3ph import PfBasicFormulation3Ph
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx
import pandas as pd

logger = gce.Logger()

grid = gce.MultiCircuit()
grid.fBase = 60

"""
Buses
"""
bus_1 = gce.Bus(name='1', Vnom=4.16)
bus_1.is_slack = True
grid.add_bus(obj=bus_1)
gen = gce.Generator()
grid.add_generator(bus = bus_1, api_obj = gen)

bus_2 = gce.Bus(name='2', Vnom=4.16)
grid.add_bus(obj=bus_2)

"""
Impedances [Ohm/km]
"""
z_602 = np.array([
    [0.7526 + 1j * 1.1814, 0.1580 + 1j * 0.4236, 0.1560 + 1j * 0.5017],
    [0.1580 + 1j * 0.4236, 0.7475 + 1j * 1.1983, 0.1535 + 1j * 0.3849],
    [0.1560 + 1j * 0.5017, 0.1535 + 1j * 0.3849, 0.7436 + 1j * 1.2112]
], dtype=complex) / 1.60934

y_602 = np.array([
    [1j * 5.6990, 1j * -1.0817, 1j * -1.6905],
    [1j * -1.0817, 1j * 5.1795, 1j * -0.6588],
    [1j * -1.6905, 1j * -0.6588, 1j * 5.4246]
], dtype=complex) / 10**6 / 1.60934

"""
Line Configurations
"""
config_602 = gce.OverheadLineType(name='Config. 602',
                                  Vnom=4.16,
                                  frequency=60)
config_602.z_abc = z_602
config_602.y_abc = y_602
config_602.y_phases_abc = np.array([1,2,3])
grid.add_overhead_line(config_602)

"""
Lines
"""
line_1_2 = gce.Line(bus_from=bus_1,
                        bus_to=bus_2,
                        length= 500 * 0.0003048)
line_1_2.apply_template(config_602, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_1_2)

"""
Loads
"""
load_2 = gce.Load(Ir1=2.0,
                        Ii1=1.0,
                        Ir2=0.0,
                        Ii2=0.0,
                        Ir3=0.0,
                        Ii3=0.0)
load_2.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus_2, api_obj=load_2)

"""
Save Grid
"""
gce.save_file(grid=grid, filename='IEEE 13-bus.gridcal')

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

    res = newton_raphson_fx(problem=problem, verbose=1, max_iter=1000)

    return res

res_3ph = power_flow_3ph(grid)

U = abs(res_3ph.V)
angle = np.degrees(np.angle((res_3ph.V)))
print()
print(np.round(U, 10))
# print(U)
print()
print(np.round(angle, 10))

dU = U[3] - U[5]
print(np.round(dU, 10))