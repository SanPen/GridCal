import os
import pandas as pd
from GridCal.Engine import *

# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/2869 Pegase.gridcal'
fname = os.path.join('..', '..', '..', '..', '..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')
# fname = os.path.join('..', '..', '..', '..', '..', 'Grids_and_profiles', 'grids', '2869 Pegase.gridcal')

main_circuit = FileOpen(fname).open()

options_ = ContingencyAnalysisOptions()
simulation = ContingencyAnalysisDriver(grid=main_circuit, options=options_)
simulation.run()

# save the result
br_names = [b.name for b in main_circuit.branches]
br_names2 = ['#' + b.name for b in main_circuit.branches]

with pd.ExcelWriter('LODF IEEE30.xlsx') as w:
    pd.DataFrame(data=simulation.results.Sf.real,
                 columns=br_names,
                 index=['base'] + br_names2).to_excel(w, sheet_name='branch power')
