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


def test_opf_ts():
    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')
    print('Reading...')
    main_circuit = FileOpen(fname).open()

    print('Running OPF-TS...', '')

    power_flow_options = PowerFlowOptions(SolverType.NR,
                                          verbose=False,
                                          initialize_with_existing_solution=False,
                                          multi_core=False,
                                          dispatch_storage=True,
                                          control_q=ReactivePowerControlMode.NoControl,
                                          control_p=True,
                                          retry_with_other_methods=False)

    opf_options = OptimalPowerFlowOptions(verbose=False,
                                          solver=SolverType.DC_OPF,
                                          power_flow_options=power_flow_options,
                                          time_grouping=TimeGrouping.Daily,
                                          mip_solver=MIPSolvers.CBC)
    s = 23
    e = 143
    opf_ts = OptimalPowerFlowTimeSeriesDriver(grid=main_circuit,
                                              options=opf_options,
                                              time_indices=main_circuit.get_all_time_indices())
    opf_ts.run()

    data = open_data_frame_from_zip(file_name_zip=os.path.join('data', 'results', 'Results_IEEE39_1W.zip'),
                                    file_name='OPF time series Bus voltage angle.csv')

    assert np.isclose(np.angle(opf_ts.results.voltage)[s:e], data.values[s:e]).all()

    data = open_data_frame_from_zip(file_name_zip=os.path.join('data', 'results', 'Results_IEEE39_1W.zip'),
                                    file_name='OPF time series Branch power.csv')

    assert np.isclose(np.real(opf_ts.results.Sf)[s:e], data.values[s:e]).all()


if __name__ == '__main__':
    test_opf_ts()
