import os
import numpy as np
import time
import numba as nb
import cProfile
import math
import pstats
from scipy import sparse

from GridCalEngine.api import FileOpen
from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at, NumericalCircuit
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysis, LinearMultiContingencies
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import ContingencyAnalysisOptions, \
    ContingencyAnalysisDriver
from GridCalEngine.basic_structures import Vec, Mat, IntVec

from GridCalEngine.enumerations import BranchImpedanceMode




if __name__ == '__main__':
    # path = os.path.join(
    #     r'C:\Users\posmarfe\OneDrive - REDEIA\Escritorio\2023 MoU Pmode1-3\srap',
    #     '1_hour_MOU_2022_5GW_v6h-B_pmode1_withcont_1link.gridcal'
    # )

    path = os.path.join(
        r'C:\Users\posmarfe\OneDrive - REDEIA\Escritorio\2023 MoU Pmode1-3\srap',
        '15_Caso_2026.gridcal'
    )
    # path = '/home/santi/Descargas/15_Caso_2026.gridcal'
    # path = r"C:\ReposGit\github\fernpos\GridCal5\GridCal\Grids_and_profiles\grids\GB reduced network.gridcal"

    # pr = cProfile.Profile()
    # cProfile.run('run_srap(gridcal_path = path)', r'C:\Users\posmarfe\OneDrive - REDEIA\Escritorio')
    # ps = pstats.Stats(pr)
    # ps.strip_dirs().sort_stats('cumtime').print_stats(0.0001)

    print('Loading grical circuit... ', sep=' ')
    grid = FileOpen(path).open()

    grid.con
