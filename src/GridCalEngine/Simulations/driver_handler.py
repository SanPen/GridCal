# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from warnings import warn
import numpy as np
from GridCalEngine.Devices.multi_circuit import MultiCircuit

from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_options import ContingencyAnalysisOptions
from GridCalEngine.Simulations.ATC.available_transfer_capacity_options import AvailableTransferCapacityOptions
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow_options import ContinuationPowerFlowOptions
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow_input import ContinuationPowerFlowInput
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.Clustering.clustering_options import ClusteringAnalysisOptions
from GridCalEngine.Simulations.InvestmentsEvaluation.investments_evaluation_options import InvestmentsEvaluationOptions

from GridCalEngine.Simulations.ATC.available_transfer_capacity_driver import (AvailableTransferCapacityDriver)
from GridCalEngine.Simulations.ATC.available_transfer_capacity_ts_driver import (
    AvailableTransferCapacityTimeSeriesDriver
)
from GridCalEngine.Simulations.Clustering.clustering_driver import ClusteringDriver
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import (ContingencyAnalysisDriver)
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_ts_driver import (
    ContingencyAnalysisTimeSeriesDriver
)
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow_driver import (
    ContinuationPowerFlowDriver
)
from GridCalEngine.Simulations.InvestmentsEvaluation.investments_evaluation_driver import (InvestmentsEvaluationDriver)
from GridCalEngine.Simulations.LinearFactors.linear_analysis_driver import LinearAnalysisDriver
from GridCalEngine.Simulations.LinearFactors.linear_analysis_ts_driver import (LinearAnalysisTimeSeriesDriver)
from GridCalEngine.Simulations.NodalCapacity.nodal_capacity_ts_driver import (NodalCapacityTimeSeriesDriver)
from GridCalEngine.Simulations.OPF.opf_driver import OptimalPowerFlowDriver
from GridCalEngine.Simulations.OPF.opf_ts_driver import (OptimalPowerFlowTimeSeriesDriver)
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from GridCalEngine.Simulations.PowerFlow.power_flow_ts_driver import (PowerFlowTimeSeriesDriver)
from GridCalEngine.Simulations.ShortCircuitStudies.short_circuit_driver import ShortCircuitDriver
from GridCalEngine.Simulations.Stochastic.stochastic_power_flow_driver import (StochasticPowerFlowDriver)
from GridCalEngine.Simulations.types import DRIVER_OBJECTS
from GridCalEngine.enumerations import SimulationTypes
from GridCalEngine.basic_structures import IntVec


def create_driver(grid: MultiCircuit,
                  driver_tpe: SimulationTypes,
                  time_indices: IntVec | None) -> DRIVER_OBJECTS | None:
    """
    Create driver with the results
    :param grid: MultiCircuit instance
    :param driver_tpe: SimulationTypes
    :param time_indices: list of time indices
    :return: Driver or None
    """
    if time_indices is None:
        time_indices = grid.get_all_time_indices()

    # get the results' object dictionary
    if driver_tpe == SimulationTypes.NetTransferCapacity_run:
        drv = AvailableTransferCapacityDriver(grid=grid,
                                              options=AvailableTransferCapacityOptions())

    elif driver_tpe == SimulationTypes.NetTransferCapacityTS_run:
        drv = AvailableTransferCapacityTimeSeriesDriver(grid=grid,
                                                        options=AvailableTransferCapacityOptions(),
                                                        time_indices=time_indices,
                                                        clustering_results=None)

    elif driver_tpe == SimulationTypes.ContingencyAnalysis_run:
        drv = ContingencyAnalysisDriver(grid=grid,
                                        options=ContingencyAnalysisOptions())

    elif driver_tpe == SimulationTypes.ContingencyAnalysisTS_run:
        drv = ContingencyAnalysisTimeSeriesDriver(grid=grid,
                                                  options=ContingencyAnalysisOptions(),
                                                  time_indices=time_indices,
                                                  clustering_results=None)

    elif driver_tpe == SimulationTypes.ContinuationPowerFlow_run:
        n = grid.get_bus_number()
        drv = ContinuationPowerFlowDriver(grid=grid,
                                          options=ContinuationPowerFlowOptions(),
                                          inputs=ContinuationPowerFlowInput(
                                              Sbase=np.zeros(n, dtype=complex),
                                              Vbase=np.zeros(n, dtype=complex),
                                              Starget=np.zeros(n, dtype=complex)
                                          ),
                                          pf_options=PowerFlowOptions(),
                                          opf_results=None)

    elif driver_tpe == SimulationTypes.LinearAnalysis_run:
        drv = LinearAnalysisDriver(grid=grid, options=None)

    elif driver_tpe == SimulationTypes.LinearAnalysis_TS_run:
        drv = LinearAnalysisTimeSeriesDriver(grid=grid,
                                             options=None,
                                             time_indices=time_indices,
                                             clustering_results=None)

    elif driver_tpe == SimulationTypes.OPF_run:
        drv = OptimalPowerFlowDriver(grid=grid, options=None)

    elif driver_tpe == SimulationTypes.OPFTimeSeries_run:
        drv = OptimalPowerFlowTimeSeriesDriver(grid=grid,
                                               options=None,
                                               time_indices=time_indices,
                                               clustering_results=None)

    elif driver_tpe == SimulationTypes.NodalCapacityTimeSeries_run:
        drv = NodalCapacityTimeSeriesDriver(grid=grid,
                                            options=None,
                                            time_indices=time_indices,
                                            clustering_results=None)

    elif driver_tpe == SimulationTypes.PowerFlow_run:
        drv = PowerFlowDriver(grid=grid, options=PowerFlowOptions())

    elif driver_tpe == SimulationTypes.PowerFlowTimeSeries_run:
        drv = PowerFlowTimeSeriesDriver(grid=grid,
                                        options=PowerFlowOptions(),
                                        time_indices=time_indices,
                                        clustering_results=None)

    elif driver_tpe == SimulationTypes.ShortCircuit_run:
        drv = ShortCircuitDriver(grid=grid,
                                 options=None,
                                 pf_options=None,
                                 pf_results=None,
                                 opf_results=None)

    elif driver_tpe == SimulationTypes.StochasticPowerFlow:
        drv = StochasticPowerFlowDriver(grid=grid, options=PowerFlowOptions())

    elif driver_tpe == SimulationTypes.ClusteringAnalysis_run:
        drv = ClusteringDriver(grid=grid, options=ClusteringAnalysisOptions(0))

    elif driver_tpe == SimulationTypes.InvestmentsEvaluation_run:
        drv = InvestmentsEvaluationDriver(
            grid=grid,
            options=InvestmentsEvaluationOptions(
                max_eval=0,
                pf_options=PowerFlowOptions()
            ),
        )

    else:
        warn(f"Session {driver_tpe} not implemented for disk retrieval :/")
        return None

    return drv
