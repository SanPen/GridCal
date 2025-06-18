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
z_604 = np.array([
    [1.3238 + 1j * 1.3569, 0.2066 + 1j * 0.4591],
    [0.2066 + 1j * 0.4591, 1.3294 + 1j * 1.3471]
], dtype=complex) / 1.60934

y_604 = np.array([
    [1j * 4.6658, 1j * -0.8999],
    [1j * -0.8999, 1j * 4.7097]
], dtype=complex) / 10**6 / 1.60934

"""
Line Configurations
"""
config_604 = gce.OverheadLineType(name='Config. 604',
                                  Vnom=4.16,
                                  frequency=60)
config_604.z_abc = z_604
config_604.y_abc = y_604
config_604.y_phases_abc = np.array([1,3])
grid.add_overhead_line(config_604)

"""
Lines
"""
line_1_2 = gce.Line(bus_from=bus_1,
                        bus_to=bus_2,
                        length= 300 * 0.0003048)
line_1_2.apply_template(config_604, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_1_2)

"""
Loads
"""
load_2 = gce.Load(Ir1=0.0,
                        Ii1=0.0,
                        Ir2=0.0,
                        Ii2=0.0,
                        Ir3=0.17 *100,
                        Ii3=-0.08 *100)
load_2.conn = ShuntConnectionType.Delta
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