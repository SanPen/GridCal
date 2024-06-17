from GridCalEngine.api import FileOpen
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import (ContingencyAnalysisOptions,
                                                                                       ContingencyAnalysisDriver)
from GridCalEngine.enumerations import EngineType, ContingencyMethod
import numpy as np
import os


def test_contingency_filtes() -> None:
    """
    Tests that the contingency filtering works
    :return: 
    """
    # First stage of tests
    print('Loading grical circuit... ', sep=' ')

    fname = os.path.join('data', 'grids', 'Test_filter_conting_v1.gridcal')
    grid = FileOpen(fname).open()

    # test 1
    print("Running contingency analysis...")
    con_options = ContingencyAnalysisOptions()
    con_options.use_srap = False
    con_options.contingency_method = ContingencyMethod.PTDF

    cg_idx_dict = {a: i for i, a in enumerate(grid.get_contingency_groups())}

    # ------------------------------------------------------------------------------------------------------------------
    # NO filter
    con_drv = ContingencyAnalysisDriver(grid=grid,
                                        options=con_options,
                                        engine=EngineType.GridCal)

    con_drv.run()
    all_conting_loading = con_drv.results.loading

    # ------------------------------------------------------------------------------------------------------------------
    # Filter area 1

    # contingencies that should be considered for area 1
    area1 = grid.get_areas()[0]
    con_options.contingency_groups = grid.get_contingency_groups_in(grouping_elements=[area1])
    area1_con_groups_idx = np.array([cg_idx_dict[cg] for cg in con_options.contingency_groups])
    assert np.all(area1_con_groups_idx == np.array([0, 1, 2, 3, 7]))

    con_drv = ContingencyAnalysisDriver(grid=grid,
                                        options=con_options,
                                        engine=EngineType.GridCal)

    con_drv.run()
    conting_loading = con_drv.results.loading

    test1_result = np.all(all_conting_loading[area1_con_groups_idx, :] == conting_loading)
    assert test1_result  # The filter should be ok for area 1

    # ------------------------------------------------------------------------------------------------------------------
    # Filter area 2
    area2 = grid.get_areas()[1]
    con_options.contingency_groups = grid.get_contingency_groups_in(grouping_elements=[area2])
    area2_con_groups_idx = np.array([cg_idx_dict[cg] for cg in con_options.contingency_groups])
    assert np.all(area2_con_groups_idx == np.array([0, 2, 3, 4, 5, 6, 7]))

    # Falta condición de opciones de filtro de contingencias

    con_drv = ContingencyAnalysisDriver(grid=grid,
                                        options=con_options,
                                        engine=EngineType.GridCal)

    con_drv.run()
    conting_loading = con_drv.results.loading

    test2_result = np.all(all_conting_loading[area2_con_groups_idx, :] == conting_loading)
    assert test2_result  # The filter should be ok for area 1
