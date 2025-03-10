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
                  time_indices: IntVec) -> DRIVER_OBJECTS | None:
    """
    Create driver with the results
    :param grid: MultiCircuit instance
    :param driver_tpe: SimulationTypes
    :param time_indices: list of time indices
    :return: Driver or None
    """

    # get the results' object dictionary
    if driver_tpe == AvailableTransferCapacityDriver:
        drv = AvailableTransferCapacityDriver(grid=grid,
                                              options=AvailableTransferCapacityOptions())

    elif driver_tpe == AvailableTransferCapacityTimeSeriesDriver:
        drv = AvailableTransferCapacityTimeSeriesDriver(grid=grid,
                                                        options=AvailableTransferCapacityOptions(),
                                                        time_indices=time_indices,
                                                        clustering_results=None)

    elif driver_tpe == ContingencyAnalysisDriver:
        drv = ContingencyAnalysisDriver(grid=grid,
                                        options=ContingencyAnalysisOptions())

    elif driver_tpe == ContingencyAnalysisTimeSeriesDriver:
        drv = ContingencyAnalysisTimeSeriesDriver(grid=grid,
                                                  options=ContingencyAnalysisOptions(),
                                                  time_indices=time_indices,
                                                  clustering_results=None)

    elif driver_tpe == ContinuationPowerFlowDriver:
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

    elif driver_tpe == LinearAnalysisDriver:
        drv = LinearAnalysisDriver(grid=grid, options=None)

    elif driver_tpe == ContinuationPowerFlowDriver:
        drv = LinearAnalysisTimeSeriesDriver(grid=grid,
                                             options=None,
                                             time_indices=time_indices,
                                             clustering_results=None)

    elif driver_tpe == OptimalPowerFlowDriver:
        drv = OptimalPowerFlowDriver(grid=grid, options=None)

    elif driver_tpe == OptimalPowerFlowTimeSeriesDriver:
        drv = OptimalPowerFlowTimeSeriesDriver(grid=grid,
                                               options=None,
                                               time_indices=time_indices,
                                               clustering_results=None)

    elif driver_tpe == NodalCapacityTimeSeriesDriver:
        drv = NodalCapacityTimeSeriesDriver(grid=grid,
                                            options=None,
                                            time_indices=time_indices,
                                            clustering_results=None)

    elif driver_tpe == PowerFlowDriver:
        drv = PowerFlowDriver(grid=grid, options=PowerFlowOptions())

    elif driver_tpe == PowerFlowTimeSeriesDriver:
        drv = PowerFlowTimeSeriesDriver(grid=grid,
                                        options=PowerFlowOptions(),
                                        time_indices=time_indices,
                                        clustering_results=None)

    elif driver_tpe == ShortCircuitDriver:
        drv = ShortCircuitDriver(grid=grid,
                                 options=None,
                                 pf_options=None,
                                 pf_results=None,
                                 opf_results=None)

    elif driver_tpe == StochasticPowerFlowDriver:
        drv = StochasticPowerFlowDriver(grid=grid, options=PowerFlowOptions())

    elif driver_tpe == ClusteringDriver:
        drv = ClusteringDriver(grid=grid, options=ClusteringAnalysisOptions(0))

    elif driver_tpe == InvestmentsEvaluationDriver:
        drv = InvestmentsEvaluationDriver(grid=grid,
                                          options=InvestmentsEvaluationOptions(max_eval=0,
                                                                               pf_options=PowerFlowOptions()), )

    else:
        warn(f"Session {driver_tpe} not implemented for disk retrieval :/")
        return None

    return drv
