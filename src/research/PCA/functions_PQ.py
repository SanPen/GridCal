import numpy as np
from GridCal.Engine import *
import random


def translation_stretch_vec(v):
	a = v[0]
	b = v[-1]
	w = []
	for ll in range(len(v)):
		w.append(-a / (b - a) + v[ll] * 1 / (b - a))

	# return np.array(w)
	return w


def V5(p1, p2, p3, p4, p5, p6, p7, p8, indx_Vbus):

	grid = MultiCircuit()

	# Add the buses and the generators and loads attached
	bus1 = Bus('Bus 1', vnom=20)
	bus1.is_slack = True
	grid.add_bus(bus1)

	gen1 = Generator('Slack Generator', voltage_module=1.0)
	grid.add_generator(bus1, gen1)

	bus2 = Bus('Bus 2', vnom=20)
	grid.add_bus(bus2)
	grid.add_load(bus2, Load('load 2', P=p1, Q=p2))

	bus3 = Bus('Bus 3', vnom=20)
	grid.add_bus(bus3)
	grid.add_load(bus3, Load('load 3', P=p3, Q=p4))

	bus4 = Bus('Bus 4', vnom=20)
	grid.add_bus(bus4)
	grid.add_load(bus4, Load('load 4', P=p5, Q=p6))

	bus5 = Bus('Bus 5', vnom=20)
	grid.add_bus(bus5)
	grid.add_load(bus5, Load('load 5', P=p7, Q=p8))

	# add branches (Lines in this case)
	grid.add_line(Line(bus1, bus2, 'line 1-2', r=0.05, x=0.11, b=0.00))
	grid.add_line(Line(bus1, bus3, 'line 1-3', r=0.05, x=0.11, b=0.00))
	grid.add_line(Line(bus1, bus5, 'line 1-5', r=0.03, x=0.08, b=0.00))
	grid.add_line(Line(bus2, bus3, 'line 2-3', r=0.04, x=0.09, b=0.00))
	grid.add_line(Line(bus2, bus5, 'line 2-5', r=0.04, x=0.09, b=0.00))
	grid.add_line(Line(bus3, bus4, 'line 3-4', r=0.06, x=0.13, b=0.00))
	grid.add_line(Line(bus4, bus5, 'line 4-5', r=0.04, x=0.09, b=0.00))

	options = PowerFlowOptions(SolverType.NR, verbose=False)
	power_flow = PowerFlowDriver(grid, options)
	power_flow.run()

	vv5 = abs(power_flow.results.voltage[indx_Vbus])

	return vv5

