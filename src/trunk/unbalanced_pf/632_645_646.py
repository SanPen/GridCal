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
13 Buses
"""
bus_632 = gce.Bus(name='632', Vnom=4.16, xpos=0, ypos=0)
bus_632.is_slack = True
grid.add_bus(obj=bus_632)
gen = gce.Generator()
grid.add_generator(bus = bus_632, api_obj = gen)

bus_645 = gce.Bus(name='645', Vnom=4.16, xpos=-100*5, ypos=0)
grid.add_bus(obj=bus_645)

bus_646 = gce.Bus(name='646', Vnom=4.16, xpos=-200*5, ypos=0)
grid.add_bus(obj=bus_646)

"""
Impedances [Ohm/km]
"""
z_603 = np.array([
    [1.3294 + 1j * 1.3471, 0.2066 + 1j * 0.4591],
    [0.2066 + 1j * 0.4591, 1.3238 + 1j * 1.3569]
], dtype=complex) / 1.60934

y_603 = np.array([
    [1j * 4.7097, 1j * -0.8999],
    [1j * -0.8999, 1j * 4.6658]
], dtype=complex) / 10**6 / 1.60934

"""
Loads
"""
load_645 = gce.Load(G1=0.0,
                    B1=0.0,
                    G2=0.170,
                    B2=-0.125,
                    G3=0.0,
                    B3=0.0)
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

"""
Line Configurations
"""
config_603 = gce.OverheadLineType(name='Config. 603',
                                  Vnom=4.16,
                                  frequency=60)
config_603.z_abc = z_603
config_603.y_abc = y_603
config_603.y_phases_abc = np.array([2,3])
grid.add_overhead_line(config_603)

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
print()
print(np.round(angle, 10))