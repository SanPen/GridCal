# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
from GridCalEngine.basic_structures import *
from GridCalEngine.Simulations import *
from GridCalEngine.IO import *
from GridCalEngine.Devices import *
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.enumerations import *


def open_file(filename: Union[str, List[str]]) -> MultiCircuit:
    """
    Open file
    :param filename: name of the file (.gridcal, .ejson, .m, .xml, .zip, etc.) or list of files (.xml, .zip)
    :return: MultiCircuit instance
    """
    return FileOpen(file_name=filename).open()


def save_file(grid: MultiCircuit, filename: str):
    """
    Save file
    :param grid: MultiCircuit instance
    :param filename: name of the file (.gridcal, .ejson)
    """
    FileSave(circuit=grid, file_name=filename).save()


def power_flow(grid: MultiCircuit,
               options: PowerFlowOptions = PowerFlowOptions(),
               engine=EngineType.GridCal) -> PowerFlowResults:
    """
    Run power flow on the snapshot
    :param grid: MultiCircuit instance
    :param options: PowerFlowOptions instance
    :param engine: Engine to run with
    :return: PowerFlowResults instance
    """
    driver = PowerFlowDriver(grid=grid, options=options, engine=engine)

    driver.run()

    return driver.results


def power_flow_ts(grid: MultiCircuit,
                  options: PowerFlowOptions = PowerFlowOptions(),
                  time_indices: Union[IntVec, None] = None,
                  engine=EngineType.GridCal) -> PowerFlowResults:
    """
    Run power flow on the time series
    :param grid: MultiCircuit instance
    :param options: PowerFlowOptions instance (optional)
    :param time_indices: Array of time indices to simulate, if None all are used (optional)
    :param engine: Engine to run with (optional, default GridCal)
    :return: PowerFlowResults instance
    """

    #  compose the time indices
    ti = grid.get_all_time_indices() if time_indices is None else time_indices

    # create the driver
    driver = PowerFlowTimeSeriesDriver(grid=grid,
                                       options=options,
                                       time_indices=ti,
                                       engine=engine)
    # run
    driver.run()

    return driver.results
