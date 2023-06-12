from GridCal.Engine import *

# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'

main_circuit = FileOpen(fname).open()

# get the power flow options from the GUI
solver = SolverType.Simple_OPF
mip_solver = MIPSolvers.CBC
grouping = TimeGrouping.Daily
pf_options = PowerFlowOptions()

options = OptimalPowerFlowOptions(solver=solver,
                                  time_grouping=grouping,
                                  mip_solver=mip_solver,
                                  power_flow_options=pf_options)

start = 0
end = len(main_circuit.time_profile)

# create the OPF time series instance
# if non_sequential:
optimal_power_flow_time_series = OptimalPowerFlowTimeSeries(grid=main_circuit,
                                                            options=options,
                                                            start_=start,
                                                            end_=end)

optimal_power_flow_time_series.run()

v = optimal_power_flow_time_series.results.voltage
print('Angles\n', np.angle(v))

l = optimal_power_flow_time_series.results.loading
print('Branch loading\n', l)

g = optimal_power_flow_time_series.results.generator_power
print('Gen power\n', g)

pr = optimal_power_flow_time_series.results.shadow_prices
print('Nodal prices \n', pr)

import pandas as pd
pd.DataFrame(optimal_power_flow_time_series.results.loading).to_excel('opf_loading.xlsx')