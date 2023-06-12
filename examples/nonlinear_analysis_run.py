from GridCal.Engine import *

fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'

main_circuit = FileOpen(fname).open()

options = NonLinearAnalysisOptions()
simulation = NonLinearAnalysisDriver(grid=main_circuit, options=options)
simulation.run()
ptdf_df = simulation.results.mdl(result_type=ResultTypes.PTDFBranchesSensitivity)

print(ptdf_df.get_data_frame())
