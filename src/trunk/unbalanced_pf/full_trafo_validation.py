import VeraGridEngine.api as gce
from VeraGridEngine import WindingType, ShuntConnectionType, SolverType

logger = gce.Logger()

grid = gce.MultiCircuit()
grid.fBase = 60

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus_632 = gce.Bus(name='632', Vnom=4.16)
bus_632.is_slack = True
grid.add_bus(obj=bus_632)
gen = gce.Generator()
grid.add_generator(bus=bus_632, api_obj=gen)

bus_634 = gce.Bus(name='634', Vnom=0.48)
grid.add_bus(obj=bus_634)

# ----------------------------------------------------------------------------------------------------------------------
# Load
# ----------------------------------------------------------------------------------------------------------------------
load_634 = gce.Load(G1=0.140*5,
                    B1=0.100*5,
                    G2=0.120*5,
                    B2=0.090*5,
                    G3=0.100*5,
                    B3=0.080*5)
load_634.conn = ShuntConnectionType.Delta
grid.add_load(bus=bus_634, api_obj=load_634)

# load_634 = gce.Load(Ir1=0.140*2,
#                     Ii1=0.100*2,
#                     Ir2=0.120*2,
#                     Ii2=0.090*2,
#                     Ir3=0.100*2,
#                     Ii3=0.080*2)
# load_634.conn = ShuntConnectionType.GroundedStar
# grid.add_load(bus=bus_634, api_obj=load_634)

# ----------------------------------------------------------------------------------------------------------------------
# Transformer
# ----------------------------------------------------------------------------------------------------------------------
trafo = gce.Transformer2W(name='XFM-1',
                          bus_from=bus_632,
                          bus_to=bus_634,
                          HV=4.16,
                          LV=0.48,
                          nominal_power=0.5,
                          rate=0.5,
                          r=1.1*2,
                          x=2*2)
trafo.conn_f = WindingType.GroundedStar
trafo.conn_t = WindingType.Delta
grid.add_transformer2w(trafo)

# ----------------------------------------------------------------------------------------------------------------------
# Run power flow
# ----------------------------------------------------------------------------------------------------------------------
res = gce.power_flow(grid=grid, options=gce.PowerFlowOptions(three_phase_unbalanced=True,
                                                             solver_type=SolverType.LM))

# ----------------------------------------------------------------------------------------------------------------------
# Show the results
# ----------------------------------------------------------------------------------------------------------------------
print("\n", res.get_voltage_3ph_df())
print("\nConverged? ", res.converged)
print("\nIterations: ", res.iterations)