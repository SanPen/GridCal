import os
from GridCalEngine.api import FileOpen
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import (ContingencyAnalysisOptions,
                                                                                       ContingencyAnalysisDriver)
from GridCalEngine.enumerations import EngineType,ContingencyEngine

if __name__ == '__main__':
    # path = os.path.join(
    #     r'C:\Users\posmarfe\OneDrive - REDEIA\Escritorio\2023 MoU Pmode1-3\srap',
    #     '1_hour_MOU_2022_5GW_v6h-B_pmode1_withcont_1link.gridcal'
    # )

    path = "/home/santi/Escritorio/Redes/15_Caso_2026.gridcal"

    print('Loading grical circuit... ', sep=' ')
    grid = FileOpen(path).open()

    print("Running contingency analysis...")
    con_options = ContingencyAnalysisOptions()
    con_options.use_srap = True
    con_options.engine = ContingencyEngine.PTDF

    con_drv = ContingencyAnalysisDriver(grid=grid,
                                        options=con_options,
                                        engine=EngineType.GridCal)

    con_drv.run()

    print(f"Elapsed: {con_drv.elapsed} s")
    print('Done!')
