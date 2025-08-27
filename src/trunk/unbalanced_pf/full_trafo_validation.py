import GridCalEngine.api as gce
from GridCalEngine import WindingType, ShuntConnectionType
import numpy as np

logger = gce.Logger()

grid = gce.MultiCircuit()
grid.fBase = 60

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus_632 = gce.Bus(name='632', Vnom=4.16, xpos=0, ypos=0)
bus_632.is_slack = True
grid.add_bus(obj=bus_632)
gen = gce.Generator(vset = 1.0)
grid.add_generator(bus = bus_632, api_obj = gen)

bus_633 = gce.Bus(name='633', Vnom=4.16, xpos=100*5, ypos=0)
grid.add_bus(obj=bus_633)

bus_634 = gce.Bus(name='634', Vnom=0.48, xpos=200*5, ypos=0)
grid.add_bus(obj=bus_634)

# ----------------------------------------------------------------------------------------------------------------------
# Load
# ----------------------------------------------------------------------------------------------------------------------
load_634 = gce.Load(Ir1=0.140,
                    Ii1=0.100,
                    Ir2=0.120,
                    Ii2=0.090,
                    Ir3=0.100,
                    Ii3=0.080)
load_634.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus_634, api_obj=load_634)

# ----------------------------------------------------------------------------------------------------------------------
# Line
# ----------------------------------------------------------------------------------------------------------------------
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

config_602 = gce.create_known_abc_overhead_template(name='Config. 602',
                                                    z_abc=z_602,
                                                    ysh_abc=y_602,
                                                    phases=np.array([1, 2, 3]),
                                                    Vnom=4.16,
                                                    frequency=60)

grid.add_overhead_line(config_602)

line_632_633 = gce.Line(bus_from=bus_632,
                        bus_to=bus_633,
                        length=500 * 0.0003048)
line_632_633.apply_template(config_602, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_632_633)

# ----------------------------------------------------------------------------------------------------------------------
# Transformer
# ----------------------------------------------------------------------------------------------------------------------

# Yy (Validated with OpenDSS)
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

# Yd
# XFM_1 = gce.Transformer2W(name='XFM-1',
#                           bus_from=bus_633,
#                           bus_to=bus_634,
#                           HV=4.16,
#                           LV=0.48,
#                           nominal_power=0.5,
#                           rate=0.5,
#                           r=1.1*2,
#                           x=2*2)
# XFM_1.conn_f = WindingType.GroundedStar
# XFM_1.conn_t = WindingType.Delta
# grid.add_transformer2w(XFM_1)

# Dy
# XFM_1 = gce.Transformer2W(name='XFM-1',
#                           bus_from=bus_633,
#                           bus_to=bus_634,
#                           HV=4.16,
#                           LV=0.48,
#                           nominal_power=0.5,
#                           rate=0.5,
#                           r=1.1*2,
#                           x=2*2)
# XFM_1.conn_f = WindingType.Delta
# XFM_1.conn_t = WindingType.GroundedStar
# grid.add_transformer2w(XFM_1)

# Dd
# XFM_1 = gce.Transformer2W(name='XFM-1',
#                           bus_from=bus_633,
#                           bus_to=bus_634,
#                           HV=4.16,
#                           LV=0.48,
#                           nominal_power=0.5,
#                           rate=0.5,
#                           r=1.1*2,
#                           x=2*2)
# XFM_1.conn_f = WindingType.Delta
# XFM_1.conn_t = WindingType.Delta
# grid.add_transformer2w(XFM_1)

# ----------------------------------------------------------------------------------------------------------------------
# Run power flow
# ----------------------------------------------------------------------------------------------------------------------
res = gce.power_flow(grid=grid, options=gce.PowerFlowOptions(three_phase_unbalanced=True))

# ----------------------------------------------------------------------------------------------------------------------
# Show the results
# ----------------------------------------------------------------------------------------------------------------------
print(res.get_voltage_df())