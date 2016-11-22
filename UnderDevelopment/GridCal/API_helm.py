# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import numpy as np

from grid.CircuitOO import *

np.set_printoptions(precision=4)
grid = MultiCircuit()


# grid.load_file('Muthu4Bus.xls')
# grid.load_file('IEEE_30BUS.xls')
grid.load_file('IEEE_39Bus.xls')
# grid.load_file('case9target.xls')
grid.compile()

# print('Ybus:\n', grid.circuits[0].power_flow_input.Ybus.todense())

options = PowerFlowOptions(SolverType.HELM, verbose=False, robust=False, tolerance=1e-9)
power_flow = PowerFlow(grid, options)
power_flow.run()

print('\n\n', grid.name)
print('\t|V|:', abs(grid.power_flow_results.voltage))
print('\t|Sbranch|:', abs(grid.power_flow_results.Sbranch))
print('\t|loading|:', abs(grid.power_flow_results.loading) * 100)
print('\terr:', grid.power_flow_results.error)
print('\tConv:', grid.power_flow_results.converged)
