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

from GridCalEngine.api import *
from GridCalEngine.Utils.zip_file_mgmt import open_data_frame_from_zip


def test_time_series():

    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')
    print('Reading...')
    main_circuit = FileOpen(fname).open()

    pf_options = PowerFlowOptions(solver_type=SolverType.NR, verbose=0, control_q=False)

    ts = PowerFlowTimeSeriesDriver(grid=main_circuit, options=pf_options, time_indices=np.arange(0, 96))
    ts.run()

    data = open_data_frame_from_zip(file_name_zip=os.path.join('data', 'results', 'Results_IEEE39_1W.zip'),
                                    file_name='Time series Bus voltage module.csv')

    assert np.allclose(np.abs(ts.results.voltage), data.values[:96])

    data = open_data_frame_from_zip(file_name_zip=os.path.join('data', 'results', 'Results_IEEE39_1W.zip'),
                                    file_name='Time series Branch active power "from".csv')

    assert np.allclose(np.real(ts.results.Sf), data.values[:96])


if __name__ == '__main__':
    test_time_series()
