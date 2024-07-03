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
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import run_nonlinear_opf, NonlinearOPFResults
from GridCalEngine.basic_structures import *
from GridCalEngine.Simulations import *
from GridCalEngine.IO import *
from GridCalEngine.Devices import *
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.enumerations import *
from GridCalEngine.Topology.detect_substations import detect_substations


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


def save_cgmes_file(grid: MultiCircuit,
                    filename: str,
                    cgmes_boundary_set_path: str,
                    cgmes_version: CGMESVersions = CGMESVersions.v2_4_15,
                    pf_results: Union[None, PowerFlowResults] = None, ) -> Logger:
    """
    Save the grid in CGMES format
    :param grid: MultiCircuit
    :param filename: name of the CGMES file(.zip)
    :param cgmes_boundary_set_path: Path to the boundary set in a single zip file
    :param cgmes_version: CGMESVersions
    :param pf_results: Matching PowerFlowResults (optional)
    :return: Logger
    """
    # define a logger
    logger = Logger()

    # define the export options
    options = FileSavingOptions()
    options.one_file_per_profile = False
    options.cgmes_profiles = [cgmesProfile.EQ,
                              cgmesProfile.OP,
                              cgmesProfile.TP,
                              cgmesProfile.SSH]
    options.cgmes_version = cgmes_version

    if pf_results is not None:
        # pack the results for saving
        pf_session_data = DriverToSave(name="powerflow results",
                                       tpe=SimulationTypes.PowerFlow_run,
                                       results=pf_results,
                                       logger=logger)

        options.sessions_data.append(pf_session_data)

        options.cgmes_profiles.append(cgmesProfile.SV)

    # since the CGMES boundary set is an external file, you need to define where it is
    options.cgmes_boundary_set = cgmes_boundary_set_path

    # save in CGMES format
    handler = FileSave(circuit=grid, file_name=filename, options=options)
    logger += handler.save_cgmes()

    return logger


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


def acopf(grid: MultiCircuit,
          pf_options: PowerFlowOptions = PowerFlowOptions(),
          opf_options: OptimalPowerFlowOptions = OptimalPowerFlowOptions(),
          plot_error: bool = False,
          pf_init: bool = True) -> NonlinearOPFResults:
    """
    Run AC Optimal Power Flow
    :param grid: MultiCircuit instance
    :param pf_options: Power Flow Options instance (optional)
    :param opf_options: Optimal Power Flow Options instance (optional)
    :param plot_error: Boolean that selects to plot error
    :param pf_init: Boolean that selects a powerflow initialization of the problem
    :return: AC Optimal Power Flow results
    """

    acopf_res = run_nonlinear_opf(grid=grid,
                                  pf_options=pf_options,
                                  opf_options=opf_options,
                                  plot_error=plot_error,
                                  pf_init=pf_init)

    return acopf_res
