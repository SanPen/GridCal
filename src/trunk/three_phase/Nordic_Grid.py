import numpy as np
import GridCalEngine.api as gce

# declare a circuit object
grid = gce.MultiCircuit()

bus1 = gce.Bus('4011', Vnom=400, is_slack = True, area = 'North')
grid.add_bus(bus1)

