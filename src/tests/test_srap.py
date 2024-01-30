from GridCalEngine.api import FileOpen
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import (ContingencyAnalysisOptions,
                                                                                       ContingencyAnalysisDriver)
from GridCalEngine.enumerations import EngineType, ContingencyMethod
import numpy as np
import os

def test_srap():
    # First stage of tests
    print('Loading grical circuit... ', sep=' ')

    fname = os.path.join('data', 'grids', 'Test_SRAP.gridcal')
    grid = FileOpen(fname).open()

    # test 1
    print("Running contingency analysis...")
    con_options = ContingencyAnalysisOptions()
    con_options.use_srap = True
    con_options.contingency_method = ContingencyMethod.PTDF

    con_options.srap_max_loading = 1.4
    con_options.srap_max_power = 8
    con_drv = ContingencyAnalysisDriver(grid=grid,
                                        options=con_options,
                                        engine=EngineType.NewtonPA)

    con_drv.run()

    test1_result = con_drv.results.report.entries[
        0].solved_by_srap  # Este debe ser positivo. El grupo que aplicarían SRAP serían el 2, y 1 (con un limite de 8 van a entrar los 7 del generador 2 y  1 del generador 1), suficiente para resolver

    assert test1_result

    # test 2
    print("Running contingency analysis...")
    con_options = ContingencyAnalysisOptions()
    con_options.use_srap = True
    con_options.contingency_method = ContingencyMethod.PTDF

    con_options.srap_max_loading = 1.4
    con_options.srap_max_power = 1
    con_drv = ContingencyAnalysisDriver(grid=grid,
                                        options=con_options,
                                        engine=EngineType.NewtonPA)

    con_drv.run()

    test2_result_a = con_drv.results.report.entries[
        0].solved_by_srap  # Este debe ser negativo. El grupo que aplicarían SRAP serían el 2 (con un limite de 1 va a entrar 1 del generador 2), insuficiente para resolver

    assert not test2_result_a

    test2_result_b = np.around(con_drv.results.report.entries[0].srap_power,
                               decimals=3) == 0.523  # Este es el valor de la ptdf del generador correcto, el que mas influencia proporciona

    assert test2_result_b

    # test 3
    print("Running contingency analysis...")
    con_options = ContingencyAnalysisOptions()
    con_options.use_srap = True
    con_options.contingency_method = ContingencyMethod.PTDF

    con_options.srap_max_loading = 1.1
    con_options.srap_max_power = 8
    con_drv = ContingencyAnalysisDriver(grid=grid,
                                        options=con_options,
                                        engine=EngineType.NewtonPA)

    con_drv.run()

    test3_result = con_drv.results.report.entries[
        0].solved_by_srap  # Este debe ser negativo. El srap no entraria dado que la sobrecarga seria mayor que la permitida por el srap

    assert not test3_result

    # Second stage of tests. Reverse line

    # First stage of tests
    print('Loading grical circuit... ', sep=' ')

    fname = os.path.join('data', 'grids', 'Test_SRAP_reverse.gridcal')
    grid = FileOpen(fname).open()

    # test 4
    print("Running contingency analysis...")
    con_options = ContingencyAnalysisOptions()
    con_options.use_srap = True
    con_options.contingency_method = ContingencyMethod.PTDF

    con_options.srap_max_loading = 1.4
    con_options.srap_max_power = 8
    con_drv = ContingencyAnalysisDriver(grid=grid,
                                        options=con_options,
                                        engine=EngineType.NewtonPA)

    con_drv.run()

    test4_result = con_drv.results.report.entries[
        0].solved_by_srap  # Este debe ser positivo. El grupo que aplicarían SRAP serían el 2, y 1 (con un limite de 8 van a entrar los 7 del generador 2 y  1 del generador 1), suficiente para resolver

    assert test4_result

    # test 5
    print("Running contingency analysis...")
    con_options = ContingencyAnalysisOptions()
    con_options.use_srap = True
    con_options.contingency_method = ContingencyMethod.PTDF

    con_options.srap_max_loading = 1.4
    con_options.srap_max_power = 1
    con_drv = ContingencyAnalysisDriver(grid=grid,
                                        options=con_options,
                                        engine=EngineType.NewtonPA)

    con_drv.run()

    test5_result_a = con_drv.results.report.entries[
        0].solved_by_srap  # Este debe ser negativo. El grupo que aplicarían SRAP serían el 2 (con un limite de 1 va a entrar 1 del generador 2), insuficiente para resolver

    assert not test5_result_a

    test5_result_b = np.around(con_drv.results.report.entries[0].srap_power,
                               decimals=3) == -0.523  # Este es el valor de la ptdf del generador correcto, el que mas influencia proporciona
    assert test5_result_b

    # test 6
    print("Running contingency analysis...")
    con_options = ContingencyAnalysisOptions()
    con_options.use_srap = True
    con_options.contingency_method = ContingencyMethod.PTDF

    con_options.srap_max_loading = 1.1
    con_options.srap_max_power = 8
    con_drv = ContingencyAnalysisDriver(grid=grid,
                                        options=con_options,
                                        engine=EngineType.NewtonPA)

    con_drv.run()

    test6_result = con_drv.results.report.entries[
        0].solved_by_srap  # Este debe ser positivo. El grupo que aplicarían SRAP serían el 2, y 1 (con un limite de 8 van a entrar los 7 del generador 2 y  1 del generador 1), suficiente para resolver

    assert not test6_result

    test_summary = (test1_result * (not test2_result_a) * test2_result_b * (not test3_result) * test4_result * (
        not test5_result_a) * test5_result_b * (not test6_result))


    return test_summary


if __name__ == '__main__':
    test_srap()
