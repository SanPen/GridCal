# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os

import numpy as np

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.Clustering.clustering import kmeans_sampling


def test_clustering():
    """
    This test was originated by
    https://github.com/SanPen/VeraGrid/issues/403
    :return:
    """
    # //tests/data/grids/IEEE39_1W.gridcal
    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')
    print('Reading...')
    grid = gce.FileOpen(fname).open()

    (time_indices, sampled_probabilities, original_sample_idx) = kmeans_sampling(x_input=grid.get_Pbus_prof(),
                                                                                 n_points=20)

    for cluster_idx, time_index in enumerate(time_indices):
        assert original_sample_idx[time_index] == cluster_idx


def test_clustering_ts():
    """
    This test was originated by
    https://github.com/SanPen/VeraGrid/issues/403
    :return:
    """
    # //tests/data/grids/IEEE39_1W.gridcal
    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')
    print('Reading...')
    grid = gce.FileOpen(fname).open()

    options = gce.PowerFlowOptions()
    pf_ts_1 = gce.power_flow_ts(grid, options=options)

    clustering_res = gce.clustering(circuit=grid, n_points=20)
    pf_ts_2 = gce.power_flow_ts(grid,
                                options=options,
                                clustering_results=clustering_res,
                                auto_expand=False)

    # test the we simulated the steps that we wanted to simulate
    for it, t in enumerate(clustering_res.time_indices):
        v1 = pf_ts_1.voltage[t, :]
        v2 = pf_ts_2.voltage[it, :]  # this has size n_clusters=20
        assert np.isclose(v1, v2).all()

    # expand, and re try
    # now for the expanded results, the clustered indices must match the original
    pf_ts_2.expand_clustered_results()
    for t in clustering_res.time_indices:
        v1 = pf_ts_1.voltage[t, :]
        v2 = pf_ts_2.voltage[t, :]  # this has size n_time
        assert np.isclose(v1, v2).all()


def test_clustering_report():
    """
    This test was originated by
    https://github.com/SanPen/VeraGrid/issues/407
    :return:
    """
    # //tests/data/grids/IEEE39_1W.gridcal
    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')
    print('Reading...')
    grid = gce.FileOpen(fname).open()

    options = gce.PowerFlowOptions(generate_report=True)
    clustering_res = gce.clustering(circuit=grid, n_points=20)
    pf_ts_2 = gce.power_flow_ts(grid,
                                options=options,
                                clustering_results=clustering_res,
                                auto_expand=True)

    table = pf_ts_2.mdl(result_type=gce.ResultTypes.SimulationError)
