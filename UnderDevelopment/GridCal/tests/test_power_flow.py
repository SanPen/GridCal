from GridCal.Engine.CalculationEngine import *


grid = MultiCircuit()
# fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_300BUS.xls'
# fname = 'Pegasus 89 Bus.xlsx'
# fname = 'Illinois200Bus.xlsx'
fname = 'IEEE_30_new.xlsx'
# fname = 'lynn5buspq.xlsx'
# fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_14.xls'
# fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_39Bus(Islands).xls'
grid.load_file(fname)
grid.compile()

options = PowerFlowOptions(SolverType.NR,
                           verbose=False,
                           robust=False,
                           initialize_with_existing_solution=False,
                           control_q=False)

####################################################################################################################
# PowerFlow
####################################################################################################################
print('\n\n')
power_flow = PowerFlow(grid, options)
power_flow.run()

for c in grid.circuits:
    print(c.name)
    # print('\t|V|:', abs(c.power_flow_results.voltage))
    # print('\t|Sbranch|:', abs(c.power_flow_results.Sbranch))
    # print('\t|loading|:', abs(c.power_flow_results.loading) * 100)
    # print('\terr:', c.power_flow_results.error)
    # print('\tConv:', c.power_flow_results.converged)

    df = c.get_bus_pf_results_df()
    print(df)

df = grid.get_bus_pf_results_df()
print(df)

# print('\n\n', grid.name)
# print('\t|V|:', abs(grid.power_flow_results.voltage))
# print('\t|Sbranch|:', abs(grid.power_flow_results.Sbranch))
# print('\t|loading|:', abs(grid.power_flow_results.loading) * 100)
# print('\terr:', grid.power_flow_results.error)
# print('\tConv:', grid.power_flow_results.converged)