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
import GridCalEngine.api as gce


def test_ntc_ultra_simple() -> None:
    """

    :return:
    """
    np.set_printoptions(precision=4)
    fname = os.path.join('data', 'grids', 'red_ultra_simple_ntc.gridcal')

    grid = gce.open_file(fname)

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                           objects_to=[grid.areas[1]])

    opf_options = gce.OptimalPowerFlowOptions()
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        area_from_bus_idx=info.idx_bus_from,
        area_to_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        use_branch_rating_contribution=True,
        consider_contingencies=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results

    assert res.converged
    assert np.isclose(res.Sf[0].real, 100.0)
    assert res.dSbus.sum() == 0.0
    assert res.dSbus[0] == 50.0


def test_ntc_ieee_14() -> None:
    """

    :return:
    """
    np.set_printoptions(precision=4)
    fname = os.path.join('data', 'grids', 'IEEE14 - ntc areas_voltages_hvdc_shifter_l10free.gridcal')

    grid = gce.open_file(fname)

    info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                           objects_to=[grid.areas[1]])

    opf_options = gce.OptimalPowerFlowOptions()
    lin_options = gce.LinearAnalysisOptions()

    ntc_options = gce.OptimalNetTransferCapacityOptions(
        area_from_bus_idx=info.idx_bus_from,
        area_to_bus_idx=info.idx_bus_to,
        transfer_method=gce.AvailableTransferMode.InstalledPower,
        loading_threshold_to_report=98.0,
        skip_generation_limits=True,
        transmission_reliability_margin=0.1,
        branch_exchange_sensitivity=0.01,
        use_branch_exchange_sensitivity=True,
        branch_rating_contribution=1.0,
        use_branch_rating_contribution=True,
        consider_contingencies=True,
        opf_options=opf_options,
        lin_options=lin_options
    )

    drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

    drv.run()

    res = drv.results

    assert res.converged
