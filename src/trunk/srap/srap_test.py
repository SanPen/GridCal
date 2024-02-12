import os
from GridCalEngine.api import FileOpen
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import (ContingencyAnalysisOptions,
                                                                                       ContingencyAnalysisDriver)
from GridCalEngine.enumerations import EngineType, ContingencyMethod
import numpy as np


path= r'C:\Users\posmarfe\OneDrive - REDEIA\Escritorio\2023 MoU Pmode1-3\srap\Test_SRAP.gridcal'
path_reverse= r'C:\Users\posmarfe\OneDrive - REDEIA\Escritorio\2023 MoU Pmode1-3\srap\Test_SRAP_reverse.gridcal'


#First stage of tests
print('Loading grical circuit... ', sep=' ')
grid = FileOpen(path).open()

#test 1
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

test1_result = con_drv.results.report.entries[0].solved_by_srap # Este debe ser positivo. El grupo que aplicarían SRAP serían el 2, y 1 (con un limite de 8 van a entrar los 7 del generador 2 y  1 del generador 1), suficiente para resolver

#test 2
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

test2_result_a = con_drv.results.report.entries[0].solved_by_srap # Este debe ser negativo. El grupo que aplicarían SRAP serían el 2 (con un limite de 1 va a entrar 1 del generador 2), insuficiente para resolver
test2_result_b =  np.around(con_drv.results.report.entries[0].srap_power, decimals=3) == 0.523 #Este es el valor de la ptdf del generador correcto, el que mas influencia proporciona

#test 3
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

test3_result = con_drv.results.report.entries[0].solved_by_srap # Este debe ser positivo. El grupo que aplicarían SRAP serían el 2, y 1 (con un limite de 8 van a entrar los 7 del generador 2 y  1 del generador 1), suficiente para resolver


#Second stage of tests. Reverse line

print('Loading grical circuit... ', sep=' ')
grid = FileOpen(path_reverse).open()


#test 4
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

test4_result = con_drv.results.report.entries[0].solved_by_srap # Este debe ser positivo. El grupo que aplicarían SRAP serían el 2, y 1 (con un limite de 8 van a entrar los 7 del generador 2 y  1 del generador 1), suficiente para resolver

#test 5
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

test5_result_a= con_drv.results.report.entries[0].solved_by_srap # Este debe ser negativo. El grupo que aplicarían SRAP serían el 2 (con un limite de 1 va a entrar 1 del generador 2), insuficiente para resolver
test5_result_b =  np.around(con_drv.results.report.entries[0].srap_power, decimals=3) == -0.523 #Este es el valor de la ptdf del generador correcto, el que mas influencia proporciona

#test 6
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

test6_result = con_drv.results.report.entries[0].solved_by_srap # Este debe ser positivo. El grupo que aplicarían SRAP serían el 2, y 1 (con un limite de 8 van a entrar los 7 del generador 2 y  1 del generador 1), suficiente para resolver




# FAltaria un test en el que se comprobase el grupo que entra
#con_drv.results.report.entries[0].srap_power #saco la potencia que puede mover srap. Si quiero ver  que esta entrando el nodo que quiero, puedo obtenerlo como con_options.srap_max_power*PTDF[n,m]

print(test1_result * (not test2_result_a) * test2_result_b * (not test3_result) * test4_result * (not test5_result_a) * test5_result_b * (not test6_result))