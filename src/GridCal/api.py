# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
import numpy as np
from typing import Union
import GridCal.Engine as gce


def power_flow(grid: gce.MultiCircuit,
               options: gce.PowerFlowOptions = gce.PowerFlowOptions(),
               engine=gce.EngineType.GridCal) -> gce.PowerFlowResults:
    """
    Run power flow on the snapshot
    :param grid: MultiCircuit instance
    :param options: PowerFlowOptions instance
    :param engine: Engine to run with
    :return: PowerFlowResults instance
    """
    driver = gce.PowerFlowDriver(grid=grid, options=options, engine=engine)

    driver.run()

    return driver.results


def power_flow_ts(grid: gce.MultiCircuit,
                  options: gce.PowerFlowOptions = gce.PowerFlowOptions(),
                  time_indices: Union[gce.IntVec, None] = None,
                  engine=gce.EngineType.GridCal) -> gce.PowerFlowResults:
    """
    Run power flow on the snapshot
    :param grid: MultiCircuit instance
    :param options: PowerFlowOptions instance
    :param time_indices: Array of time indices to simulate, if None all are used
    :param engine: Engine to run with
    :return: PowerFlowResults instance
    """

    #  compose the time indices
    ti = grid.get_all_time_indices() if time_indices is None else time_indices

    # create the driver
    driver = gce.PowerFlowTimeSeriesDriver(grid=grid,
                                           options=options,
                                           time_indices=ti,
                                           engine=engine)
    # run
    driver.run()

    return driver.results
