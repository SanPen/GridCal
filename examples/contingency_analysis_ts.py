import os
import pandas as pd
from GridCal.Engine import *
import GridCal.Engine.basic_structures as bs

# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/2869 Pegase.gridcal'
# fname = os.path.join('..', '..', '..', '..', '..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')
# fname = os.path.join('..', '..', '..', '..', '..', 'Grids_and_profiles', 'grids', '2869 Pegase.gridcal')

folder = r'C:\Users\ramferan\Downloads'
fname = os.path.join(folder, r'MOU_2022_5GW_v6h-B_pmode1.gridcal')

main_circuit = FileOpen(fname).open()

options_ = ContingencyAnalysisOptions(
    distributed_slack=True,
    correct_values=True,
    use_provided_flows=False,
    Pf=None,
    pf_results=None,
    engine=bs.ContingencyEngine.PTDF,
    pf_options=None,
)

simulation = ContingencyAnalysisTimeSeries(
    grid=main_circuit,
    options=options_,
)

simulation.run()

print()