import os
import pandas as pd
from GridCalEngine.api import *
import GridCalEngine.enumerations as en

# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
# fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE 118 Bus - ntc_areas.gridcal'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/2869 Pegase.gridcal'
# fname = os.path.join('..', '..', '..', '..', '..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')
# fname = os.path.join('..', '..', '..', '..', '..', 'Grids_and_profiles', 'grids', '2869 Pegase.gridcal')

# folder = r'C:\Users\ramferan\Downloads'
# fname = os.path.join(folder, r'MOU_2022_5GW_v6h-B_pmode1.gridcal')

main_circuit = FileOpen(fname).open()

options_ = ContingencyAnalysisOptions(
    use_provided_flows=False,
    Pf=None,
    engine=en.ContingencyMethod.PowerFlow,
    pf_options=PowerFlowOptions(),
)

simulation = ContingencyAnalysisTimeSeries(
    grid=main_circuit,
    options=options_,
    time_indices=main_circuit.get_all_time_indices(),
    engine=EngineType.GridCal
)

simulation.run()
