from GridCalEngine.api import *
import pandas as pd

# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'

main_circuit = FileOpen(fname).open()

# get the power flow options from the GUI
solver = SolverType.SIMPLE_OPF
mip_solver = MIPSolvers.CBC
grouping = TimeGrouping.Daily
pf_options = PowerFlowOptions()

options = OptimalPowerFlowOptions(solver=solver,
                                  time_grouping=grouping,
                                  mip_solver=mip_solver,
                                  power_flow_options=pf_options)

# create the OPF time series instance
# if non_sequential:
optimal_power_flow_time_series = OptimalPowerFlowTimeSeriesDriver(grid=main_circuit,
                                                                  options=options,
                                                                  time_indices=main_circuit.get_all_time_indices())

optimal_power_flow_time_series.run()

v = optimal_power_flow_time_series.results.voltage
print('Angles\n', np.angle(v))

l = optimal_power_flow_time_series.results.loading
print('Branch loading\n', l)

g = optimal_power_flow_time_series.results.generator_power
print('Gen power\n', g)

pr = optimal_power_flow_time_series.results.bus_shadow_prices
print('Nodal prices \n', pr)

pd.DataFrame(optimal_power_flow_time_series.results.loading).to_excel('opf_loading.xlsx')
