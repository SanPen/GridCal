# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

try:
    from GridCalEngine.enumerations import *
    from GridCalEngine.basic_structures import *
    from GridCalEngine.Simulations import *
    from GridCalEngine.IO import *
    from GridCalEngine.Devices import *
    from GridCalEngine.DataStructures import *
    from GridCalEngine.Topology import *
    from GridCalEngine.Compilers import *
    from GridCalEngine.IO.file_handler import FileOpen, FileSave, FileSavingOptions
    from GridCalEngine.IO.gridcal.remote import (gather_model_as_jsons_for_communication, RemoteInstruction,
                                                 SimulationTypes, send_json_data, get_certificate_path, get_certificate)

    PROPERLY_LOADED_API = True
except ModuleNotFoundError as e:
    print("Modules not found :/", e)
    PROPERLY_LOADED_API = False
except NameError as e:
    print("Name not found :/", e)
    PROPERLY_LOADED_API = False

if PROPERLY_LOADED_API:
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
        options.cgmes_one_file_per_profile = False
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
                   options: PowerFlowOptions | None = None,
                   engine=EngineType.GridCal) -> PowerFlowResults:
        """
        Run power flow on the snapshot
        :param grid: MultiCircuit instance
        :param options: PowerFlowOptions instance
        :param engine: Engine to run with
        :return: PowerFlowResults instance
        """
        if options is None:
            options = PowerFlowOptions()

        driver = PowerFlowDriver(grid=grid, options=options, engine=engine)

        driver.run()

        return driver.results


    def power_flow_ts(grid: MultiCircuit,
                      options: PowerFlowOptions | None = None,
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
        if options is None:
            options = PowerFlowOptions()

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


    def linear_power_flow(grid: MultiCircuit,
                          options: LinearAnalysisOptions | None = None) -> LinearAnalysisResults:
        """
        Run linear power flow on the snapshot
        :param grid: MultiCircuit instance
        :param options: LinearAnalysisOptions instance
        :return: LinearAnalysisResults instance
        """
        if options is None:
            options = LinearAnalysisOptions()

        # snapshot
        sn_driver = LinearAnalysisDriver(grid=grid, options=options)
        sn_driver.run()

        return sn_driver.results


    def linear_power_flow_ts(grid: MultiCircuit,
                             options: LinearAnalysisOptions | None = None) -> LinearAnalysisTimeSeriesResults:
        """
        Run linear power flow time series
        :param grid: MultiCircuit instance
        :param options: LinearAnalysisOptions instance
        :return: LinearAnalysisTimeSeriesResults instance
        """
        if options is None:
            options = LinearAnalysisOptions()

        # snapshot
        sn_driver = LinearAnalysisTimeSeriesDriver(grid=grid, options=options)
        sn_driver.run()

        return sn_driver.results


    def short_circuit(grid: MultiCircuit,
                      fault_index: int,
                      fault_type=FaultType.LG,
                      pf_options: PowerFlowOptions = PowerFlowOptions(),
                      pf_results: PowerFlowResults | None = None) -> ShortCircuitResults:
        """
        Run short circuit
        :param grid: MultiCircuit instance
        :param fault_index: Bus fault index
        :param fault_type: Short circuit FaultType
        :param pf_options: Power Flow Options instance (optional)
        :param pf_results: PowerFlowResults (optional, if none, a power flow is run)
        :return: Short circuit results
        """
        if pf_results is None:
            pf_results = power_flow(grid=grid,
                                    options=pf_options)

        sc_options = ShortCircuitOptions(bus_index=fault_index,
                                         fault_type=fault_type)

        sc = ShortCircuitDriver(grid=grid,
                                options=sc_options,
                                pf_options=pf_options,
                                pf_results=pf_results)
        sc.run()

        return sc.results


    def continuation_power_flow(grid: MultiCircuit,
                                options: ContinuationPowerFlowOptions | None = None,
                                pf_options: PowerFlowOptions = PowerFlowOptions(),
                                pf_results: PowerFlowResults | None = None,
                                factor: Vec | float = 2.0,
                                stop_at=CpfStopAt.Full) -> ShortCircuitResults:
        """
        Run continuation power flow circuit
        :param grid: MultiCircuit instance
        :param options: ContinuationPowerFlowOptions instance (optional)
        :param pf_options: Power Flow Options instance (optional)
        :param pf_results: PowerFlowResults (optional, if none, a power flow is run)
        :param factor: number or vector to multiply the base power injection to provide the loading direction.
                        If a vector, it must be the same size as Sbus  (optional)
        :param stop_at: Where to stop [CpfStopAt.Full, Nose, ExtraOverloads] (optional)
        :return: Short circuit results
        """
        if pf_results is None:
            pf_results = power_flow(grid=grid,
                                    options=pf_options)

        # declare the CPF options
        if options is None:
            options = ContinuationPowerFlowOptions(step=0.001,
                                                   approximation_order=CpfParametrization.ArcLength,
                                                   adapt_step=True,
                                                   step_min=0.00001,
                                                   step_max=0.2,
                                                   error_tol=1e-3,
                                                   tol=1e-6,
                                                   max_it=20,
                                                   stop_at=stop_at,
                                                   verbose=False)

        # We compose the target direction
        base_power = pf_results.Sbus / grid.Sbase
        vc_inputs = ContinuationPowerFlowInput(Sbase=base_power,
                                               Vbase=pf_results.voltage,
                                               Starget=base_power * factor)

        # declare the CPF driver and run
        vc = ContinuationPowerFlowDriver(grid=grid,
                                         options=options,
                                         inputs=vc_inputs,
                                         pf_options=pf_options)
        vc.run()

        return vc.results


    def nonlinear_opf(grid: MultiCircuit,
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


    def linear_opf(grid: MultiCircuit,
                   options: OptimalPowerFlowOptions = OptimalPowerFlowOptions()) -> OptimalPowerFlowResults:
        """
        Run Linear Optimal Power Flow
        :param grid: MultiCircuit instance
        :param options: Optimal Power Flow Options instance (optional)
        :return: Linear Optimal Power Flow results
        """

        # declare the snapshot opf
        opf_driver = OptimalPowerFlowDriver(grid=grid, options=options)
        opf_driver.run()

        return opf_driver.results


    def contingencies_ts(circuit: MultiCircuit,
                         use_clustering: bool = False,
                         n_points: int = 100,
                         use_srap=False,
                         srap_max_power=1300.0,
                         srap_top_n=5,
                         srap_deadband=10,
                         srap_rever_to_nominal_rating=True,
                         detailed_massive_report=True,
                         contingency_deadband=0.0,
                         contingency_method=ContingencyMethod.PTDF) -> ContingencyAnalysisTimeSeriesResults:
        """
        Run a time series contingency analysis
        :param circuit: MultiCircuit instance
        :param use_clustering: Use clustering?
        :param n_points: Number of points for clustering
        :param use_srap: Use SRAP?
        :param srap_max_power: Max power in SRAP
        :param srap_top_n: Top number of SRAP nodes to consider
        :param srap_deadband: Deadband for SRAP power
        :param srap_rever_to_nominal_rating: Revert to nominal rating for SRAP flow
        :param detailed_massive_report: Detailed massive report?
        :param contingency_deadband: Deadband for contingency analysis
        :param contingency_method: Contingency analysis method (ContingencyMethod)
        :return: ContingencyAnalysisTimeSeriesResults
        """

        if use_clustering:
            options_clustering = ClusteringAnalysisOptions(n_points=n_points)
            driver_clustering = ClusteringDriver(grid=circuit, options=options_clustering)
            driver_clustering.run()
            clustering_results_ = driver_clustering.results
        else:
            clustering_results_ = None

        # declare the contingency analysis options
        options_contingencies = ContingencyAnalysisOptions(
            use_provided_flows=False,
            Pf=None,
            pf_options=PowerFlowOptions(SolverType.DC),
            lin_options=LinearAnalysisOptions(),
            use_srap=use_srap,
            srap_max_power=srap_max_power,
            srap_top_n=srap_top_n,
            srap_deadband=srap_deadband,
            srap_rever_to_nominal_rating=srap_rever_to_nominal_rating,
            detailed_massive_report=detailed_massive_report,
            contingency_deadband=contingency_deadband,
            contingency_method=contingency_method,
            contingency_groups=circuit.contingency_groups
        )

        # declare the contingency drivers
        driver_contingencies = ContingencyAnalysisTimeSeriesDriver(
            grid=circuit,
            options=options_contingencies,
            time_indices=circuit.get_all_time_indices(),
            clustering_results=clustering_results_
        )

        # run!
        driver_contingencies.run()

        if use_clustering:
            # this reconciles the results time steps properly
            driver_contingencies.results.expand_clustered_results()

        return driver_contingencies.results
