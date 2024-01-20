# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import os

import numpy as np

from GridCalEngine.api import *
from tests.zip_file_mgmt import open_data_frame_from_zip


def test_contingency():
    """
    Check that the contingencies match conceptually
    :return:
    """
    fname = os.path.join('data', 'grids', 'IEEE14_contingency.gridcal')
    main_circuit = FileOpen(fname).open()
    pf_options = PowerFlowOptions(SolverType.NR,
                                  verbose=False,
                                  initialize_with_existing_solution=False,
                                  dispatch_storage=True,
                                  control_q=ReactivePowerControlMode.NoControl,
                                  control_p=False)

    options = ContingencyAnalysisOptions(pf_options=pf_options, engine=ContingencyMethod.PowerFlow)
    cont_analysis_driver = ContingencyAnalysisDriver(grid=main_circuit, options=options,
                                                     linear_multiple_contingencies=None)
    cont_analysis_driver.run()
    print("")

    for i, line in enumerate(main_circuit.get_lines()):
        line.active = False
        pf_driver = PowerFlowDriver(grid=main_circuit, options=pf_options)
        pf_driver.run()

        # assert that the power flow matches whatevet it was done with the contingencies
        assert (np.isclose(cont_analysis_driver.results.Sf[i, :], pf_driver.results.Sf).all())

        assert cont_analysis_driver.results.Sf[i, i] == complex(0, 0)

        line.active = True






def test_linear_contingency():
    #fname = os.path.join('data', 'grids', 'IEEE14_contingency.gridcal')
    fname = os.path.join('data', 'grids', 'IEEE14-2_4_1-3_4_1.gridcal')
    main_circuit = FileOpen(fname).open()
    pf_options = PowerFlowOptions(SolverType.NR,
                                  verbose=False,
                                  initialize_with_existing_solution=False,
                                  dispatch_storage=True,
                                  control_q=ReactivePowerControlMode.NoControl,
                                  control_p=False)

    linear_analysis = LinearAnalysisDriver(grid=main_circuit)
    linear_analysis.run()
    linear_multi_contingency = LinearMultiContingencies(grid=main_circuit)
    linear_multi_contingency.compute(ptdf=linear_analysis.results.PTDF, lodf=linear_analysis.results.LODF)

    options = ContingencyAnalysisOptions(pf_options=pf_options, engine=ContingencyMethod.PTDF)
    cont_analysis_driver = ContingencyAnalysisDriver(grid=main_circuit, options=options,
                                                     linear_multiple_contingencies=linear_multi_contingency)
    cont_analysis_driver.run()
    print("")



# def test_lodf():
#     fname = os.path.join('data', 'grids', 'IEEE14_contingency.gridcal')
#     main_circuit = FileOpen(fname).open()
#     pf_options = PowerFlowOptions(SolverType.NR,
#                                   verbose=False,
#                                   initialize_with_existing_solution=False,
#                                   dispatch_storage=True,
#                                   control_q=ReactivePowerControlMode.NoControl,
#                                   control_p=False)
#
#     linear_analysis = LinearAnalysisDriver(grid=main_circuit)
#     linear_analysis.run()
#     linear_multi_contingency = LinearMultiContingencies(grid=main_circuit)
#     linear_multi_contingency.update(ptdf=linear_analysis.results.PTDF, lodf=linear_analysis.results.LODF)
#
#     options = ContingencyAnalysisOptions(pf_options=pf_options, engine=ContingencyEngine.PTDF)
#     cont_analysis_driver = ContingencyAnalysisDriver(grid=main_circuit, options=options,
#                                                      linear_multiple_contingencies=linear_multi_contingency)
#     cont_analysis_driver.run()


# def test_ptdf():  # ver tests archivo de tests de PTDF
#     fname = os.path.join('data', 'grids', 'case14.m')
#     main_circuit = FileOpen(fname).open()
#     pf_options = PowerFlowOptions(SolverType.NR,
#                                   verbose=False,
#                                   initialize_with_existing_solution=False,
#                                   dispatch_storage=True,
#                                   control_q=ReactivePowerControlMode.NoControl,
#                                   control_p=False)
#
#     branches = main_circuit.get_branches()
#
#     branches_id = [x.code for x in branches]
#     print(branches_id)
#     nodes = main_circuit.get_buses()
#     nodes_id = [x.code for x in nodes]
#     print(nodes_id)
#
#     ptdf_result = np.loadtxt(os.path.join('data', 'results', 'comparison', 'IEEE 14 ptdf.csv'), delimiter=',')
#
#     linear_analysis_opt = LinearAnalysisOptions(distribute_slack=False, correct_values=False)
#
#     linear_analysis = LinearAnalysisDriver(grid=main_circuit, options=linear_analysis_opt)
#     linear_analysis.run()
#
#     #TODO Revisar orden
#     #res = linear_analysis.results.PTDF - ptdf_result
#     #print(res)
#     assert(np.isclose(linear_analysis.results.PTDF, ptdf_result).all())



