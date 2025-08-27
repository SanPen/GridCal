# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os

from VeraGridEngine.api import *
from VeraGridEngine.Utils.zip_file_mgmt import open_data_frame_from_zip


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
