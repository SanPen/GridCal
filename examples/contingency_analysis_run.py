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
# folder = r'\\mornt4.ree.es\DESRED\DPE-Internacional\Interconexiones\FRANCIA\2023 MoU Pmode3\Pmode3_conting\5GW\h_pmode1_esc_inst'

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

linear_multiple_contingencies = LinearMultiContingencies(grid=main_circuit)

simulation = ContingencyAnalysisDriver(
    grid=main_circuit,
    options=options_,
    linear_multiple_contingencies=linear_multiple_contingencies
)

simulation.run()

# save the result
br_names = [b.name for b in main_circuit.branches]
br_names2 = ['#' + b.name for b in main_circuit.branches]

with pd.ExcelWriter('LODF IEEE30.xlsx') as w:
    pd.DataFrame(
        data=simulation.results.Sf.real,
        columns=br_names,
        index=['base'] + br_names2
    ).to_excel(
        w,
        sheet_name='branch power'
    )
