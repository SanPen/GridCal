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

from GridCal.grid.CalculationEngine import *
from matplotlib import pyplot as plt

grid = MultiCircuit()
# fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_300BUS.xls'
# fname = 'Pegasus 89 Bus.xlsx'
# fname = 'Illinois200Bus.xlsx'
# fname = 'IEEE_30_new.xlsx'
fname = 'lynn5buspq.xlsx'
# fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_14.xls'
# fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_39Bus(Islands).xls'
grid.load_file(fname)
grid.compile()

options = PowerFlowOptions(SolverType.NR, verbose=False, robust=False, initialize_with_existing_solution=False)

####################################################################################################################
# PowerFlow
####################################################################################################################
print('\n\n')
power_flow = PowerFlow(grid, options)
power_flow.run()

for c in grid.circuits:
    print(c.name)
    # print(pd.DataFrame(circuit.power_flow_input.Ybus.todense()))
    # print('\tV:', c.power_flow_results.voltage)
    print('\t|V|:', abs(c.power_flow_results.voltage))
    print('\t|Sbranch|:', abs(c.power_flow_results.Sbranch))
    print('\t|loading|:', abs(c.power_flow_results.loading) * 100)
    print('\terr:', c.power_flow_results.error)
    print('\tConv:', c.power_flow_results.converged)

print('\n\n', grid.name)
print('\t|V|:', abs(grid.power_flow_results.voltage))
print('\t|Sbranch|:', abs(grid.power_flow_results.Sbranch))
print('\t|loading|:', abs(grid.power_flow_results.loading) * 100)
print('\terr:', grid.power_flow_results.error)
print('\tConv:', grid.power_flow_results.converged)

####################################################################################################################
# Short circuit
####################################################################################################################
# print('\n\n')
# print('Short Circuit')
# sc_options = ShortCircuitOptions(bus_index=[16])
# sc = ShortCircuit(grid, sc_options)
# sc.run()
#
# print('\n\n', grid.name)
# print('\t|V|:', abs(grid.short_circuit_results.voltage))
# print('\t|Sbranch|:', abs(grid.short_circuit_results.Sbranch))
# print('\t|loading|:', abs(grid.short_circuit_results.loading) * 100)

####################################################################################################################
# Time Series
####################################################################################################################
# ts = TimeSeries(grid=grid, options=options)
# ts.run()
#
# if grid.time_series_results is not None:
#     print('\n\nVoltages:\n')
#     print(grid.time_series_results.voltage)
#     print(grid.time_series_results.converged)
#     print(grid.time_series_results.error)
#
#     # plot(grid.master_time_array, abs(grid.time_series_results.loading)*100)
#     # show()
# ts_analysis = TimeSeriesResultsAnalysis(grid.circuits[0].time_series_results)

####################################################################################################################
# Voltage collapse
####################################################################################################################
# vc_options = VoltageCollapseOptions()
# Sbase = zeros(len(grid.buses), dtype=complex)
# for c in grid.circuits:
#     Sbase[c.bus_original_idx] = c.power_flow_input.Sbus
# unitary_vector = -1 + 2 * np.random.random(len(grid.buses))
# # unitary_vector = random.random(len(grid.buses))
# vc_inputs = VoltageCollapseInput(Sbase=Sbase,
#                                  Vbase=grid.power_flow_results.voltage,
#                                  Starget=Sbase * (1+unitary_vector))
# vc = VoltageCollapse(grid=grid, options=vc_options, inputs=vc_inputs)
# vc.run()

# vc.results.plot()
# plt.show()

####################################################################################################################
# Monte Carlo
####################################################################################################################

# mc_sim = MonteCarlo(grid, options)
# mc_sim.run()

####################################################################################################################
# Latin Hypercube
####################################################################################################################

# lhs_sim = LatinHypercubeSampling(grid, options, sampling_points=100)
# lhs_sim.run()
#
# lhs_sim.results.plot('Bus voltage avg')


####################################################################################################################
# Cascading
####################################################################################################################

# cascade = Cascading(grid.copy(), options,
#                     max_additional_islands=5,
#                     cascade_type_=CascadeType.LatinHypercube,
#                     n_lhs_samples_=10)
# cascade.run()
#
# cascade.perform_step_run()
# cascade.perform_step_run()
# cascade.perform_step_run()
# cascade.perform_step_run()

####################################################################################################################
# Fuck up the voltage
####################################################################################################################

# options = PowerFlowOptions(SolverType.LM, verbose=False, robust=False, initialize_with_existing_solution=False)
# opt = Optimize(grid, options, max_iter=10000)
# opt.run()
# opt.plot()
#
# plt.show()