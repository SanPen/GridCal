from VeraGridEngine.api import *

# fname =   '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv (opf).gridcal'
# fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
# fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'
fname = 'C:\Git\Github\GridCal\Grids_and_profiles\grids\IEEE39_1W.gridcal'

main_circuit = FileOpen(fname).open()

# main_circuit.buses[3].controlled_generators[0].enabled_dispatch = False

# get the power flow options from the GUI
solver = SolverType.LINEAR_OPF
mip_solver = MIPSolvers.SCIP
grouping = TimeGrouping.Daily
pf_options = PowerFlowOptions()

options = OptimalPowerFlowOptions(solver=solver,
                                  time_grouping=grouping,
                                  mip_solver=mip_solver,
                                  power_flow_options=pf_options,
                                  unit_commitment=False)

# create the OPF time series instance
# if non_sequential:
optimal_power_flow_time_series = OptimalPowerFlowTimeSeriesDriver(grid=main_circuit,
                                                                  options=options,
                                                                  time_indices=main_circuit.get_all_time_indices(),
                                                                  engine=EngineType.VeraGrid)

optimal_power_flow_time_series.run()

v = optimal_power_flow_time_series.results.voltage
print('Angles\n', np.angle(v))

l = optimal_power_flow_time_series.results.loading
print('Branch loading\n', l)

g = optimal_power_flow_time_series.results.generator_power
print('Gen power\n', g)

pr = optimal_power_flow_time_series.results.bus_shadow_prices
print('Nodal prices \n', pr)

import pandas as pd
pd.DataFrame(optimal_power_flow_time_series.results.loading).to_excel('opf_loading.xlsx')