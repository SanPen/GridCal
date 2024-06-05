from GridCalEngine.api import FileOpen
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import (ContingencyAnalysisOptions,
                                                                                       ContingencyAnalysisDriver)
from GridCalEngine.enumerations import EngineType, ContingencyMethod
import numpy as np
import os


def test_contingency_filtes():
    # First stage of tests
    print('Loading grical circuit... ', sep=' ')

    fname = os.path.join('data', 'grids', 'Test_filter_conting_v1.gridcal')
    grid = FileOpen(fname).open()


    # test 1
    print("Running contingency analysis...")
    con_options = ContingencyAnalysisOptions()

    con_options.use_srap = False
    con_options.contingency_method = ContingencyMethod.PTDF

    # NO filter

    #con_options.contingency_groups= ["05463aa28ce148a580b9f73e0b9005dc::Contingency 0","0f3185956e2446b9843100b14fafbf8e::Contingency 1","51e3cfa5edb94488a17e47cc1e43167d::Contingency 2","4a020a6c6f9d44a193fc80097e67093b::Contingency 3", "08912a5f7f834e2db74a5fde460e84f0::Contingency 4", "53a1d22d1b724a8db4f8ba42de6922f9::Contingency 5", "9d6cdd8ec8b2450e9e9f49fdff3adfb6::Contingency 6", "ea776a35fbd94d5bb9e0850a7c872247::Contingency 7"]

    con_drv = ContingencyAnalysisDriver(grid=grid,
                                        options=con_options,
                                        engine=EngineType.GridCal)

    con_drv.run()
    all_conting_loading = con_drv.results.loading

    #Filter area 1

    area1=[0,1,2,3,7] # contingencies that should be considered for area 1

    #Falta condición de opciones de filtro de contingencias

    con_drv = ContingencyAnalysisDriver(grid=grid,
                                        options=con_options,
                                        engine=EngineType.GridCal)

    con_drv.run()
    conting_loading = con_drv.results.loading

    test1_result = np.all(all_conting_loading[area1,:] == conting_loading)


    #Filter area 2
    area2 = [0, 2, 3, 4, 5, 6, 7]

    #Falta condición de opciones de filtro de contingencias

    con_drv = ContingencyAnalysisDriver(grid=grid,
                                        options=con_options,
                                        engine=EngineType.GridCal)

    con_drv.run()
    conting_loading = con_drv.results.loading

    test2_result = np.all(all_conting_loading[area2,:] == conting_loading)


    assert test1_result # The filter should be ok for area 1

    assert test2_result  # The filter should be ok for area 1



