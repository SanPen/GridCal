# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os

import numpy as np

import GridCalEngine.api as gce


def test_clustering():
    """
    This test was originated by
    https://github.com/SanPen/GridCal/issues/403
    :return:
    """
    # //tests/data/grids/IEEE39_1W.gridcal
    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')
    print('Reading...')
    grid = gce.FileOpen(fname).open()

    options = gce.PowerFlowOptions()
    pf_ts_1 = gce.power_flow_ts(grid, options=options)

    clustering_res = gce.clustering(circuit=grid, n_points=20)
    pf_ts_2 = gce.power_flow_ts(grid, options=options, clustering_results=clustering_res)

    for t in clustering_res.time_indices:
        v1 = pf_ts_1.voltage[t, :]
        v2 = pf_ts_2.voltage[t, :]
        assert np.isclose(v1, v2)

    print()



if __name__ == '__main__':
    test_clustering()