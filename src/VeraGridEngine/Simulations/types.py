# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from typing import Union
# Module imports
from VeraGridEngine.Simulations.ATC.available_transfer_capacity_driver import (AvailableTransferCapacityDriver,
                                                                               AvailableTransferCapacityResults)
from VeraGridEngine.Simulations.ATC.available_transfer_capacity_ts_driver import (
    AvailableTransferCapacityTimeSeriesDriver, AvailableTransferCapacityTimeSeriesResults)
from VeraGridEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import (ContingencyAnalysisDriver,
                                                                                        ContingencyAnalysisResults)
from VeraGridEngine.Simulations.ContingencyAnalysis.contingency_analysis_ts_driver import (
    ContingencyAnalysisTimeSeriesDriver, ContingencyAnalysisTimeSeriesResults)
from VeraGridEngine.Simulations.ContinuationPowerFlow.continuation_power_flow_driver import (ContinuationPowerFlowDriver,
                                                                                             ContinuationPowerFlowResults)
from VeraGridEngine.Simulations.LinearFactors.linear_analysis_driver import LinearAnalysisDriver, LinearAnalysisResults
from VeraGridEngine.Simulations.LinearFactors.linear_analysis_ts_driver import (LinearAnalysisTimeSeriesDriver,
                                                                                LinearAnalysisTimeSeriesResults)
from VeraGridEngine.Simulations.OPF.opf_driver import OptimalPowerFlowDriver, OptimalPowerFlowResults
from VeraGridEngine.Simulations.OPF.opf_ts_driver import (OptimalPowerFlowTimeSeriesDriver,
                                                          OptimalPowerFlowTimeSeriesResults)
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver, PowerFlowResults
from VeraGridEngine.Simulations.PowerFlow.power_flow_ts_driver import (PowerFlowTimeSeriesDriver,
                                                                       PowerFlowTimeSeriesResults)
from VeraGridEngine.Simulations.ShortCircuitStudies.short_circuit_driver import ShortCircuitDriver, ShortCircuitResults
from VeraGridEngine.Simulations.Stochastic.stochastic_power_flow_driver import (StochasticPowerFlowDriver,
                                                                                StochasticPowerFlowResults)
from VeraGridEngine.Simulations.Clustering.clustering_driver import ClusteringDriver, ClusteringResults
from VeraGridEngine.Simulations.Reliability.blackout_driver import CascadingDriver, CascadingResults
from VeraGridEngine.Simulations.InputsAnalysis.inputs_analysis_driver import InputsAnalysisDriver, InputsAnalysisResults
from VeraGridEngine.Simulations.InvestmentsEvaluation.investments_evaluation_driver import (InvestmentsEvaluationDriver,
                                                                                            InvestmentsEvaluationResults)
from VeraGridEngine.Simulations.SigmaAnalysis.sigma_analysis_driver import SigmaAnalysisDriver, SigmaAnalysisResults
from VeraGridEngine.Simulations.NTC.ntc_driver import OptimalNetTransferCapacityDriver, OptimalNetTransferCapacityResults
from VeraGridEngine.Simulations.NTC.ntc_ts_driver import (OptimalNetTransferCapacityTimeSeriesDriver,
                                                          OptimalNetTransferCapacityTimeSeriesResults)
from VeraGridEngine.Simulations.NodalCapacity.nodal_capacity_ts_driver import (NodalCapacityTimeSeriesDriver,
                                                                               NodalCapacityTimeSeriesResults)
from VeraGridEngine.Simulations.Topology.node_groups_driver import NodeGroupsDriver
from VeraGridEngine.Simulations.Reliability.reliability_driver import ReliabilityStudyDriver, ReliabilityResults

DRIVER_OBJECTS = Union[
    AvailableTransferCapacityDriver,
    AvailableTransferCapacityTimeSeriesDriver,
    ContingencyAnalysisDriver,
    ContingencyAnalysisTimeSeriesDriver,
    ContinuationPowerFlowDriver,
    LinearAnalysisDriver,
    LinearAnalysisTimeSeriesDriver,
    OptimalPowerFlowDriver,
    OptimalPowerFlowTimeSeriesDriver,
    PowerFlowDriver,
    PowerFlowTimeSeriesDriver,
    ShortCircuitDriver,
    StochasticPowerFlowDriver,
    ClusteringDriver,
    CascadingDriver,
    SigmaAnalysisDriver,
    OptimalNetTransferCapacityDriver,
    OptimalNetTransferCapacityTimeSeriesDriver,
    NodeGroupsDriver,
    InputsAnalysisDriver,
    InvestmentsEvaluationDriver,
    NodalCapacityTimeSeriesDriver,
    ReliabilityStudyDriver
]

RESULTS_OBJECTS = Union[
    AvailableTransferCapacityResults,
    AvailableTransferCapacityTimeSeriesResults,
    ContingencyAnalysisResults,
    ContingencyAnalysisTimeSeriesResults,
    ContinuationPowerFlowResults,
    LinearAnalysisResults,
    LinearAnalysisTimeSeriesResults,
    OptimalPowerFlowResults,
    OptimalPowerFlowTimeSeriesResults,
    PowerFlowResults,
    PowerFlowTimeSeriesResults,
    ShortCircuitResults,
    StochasticPowerFlowResults,
    ClusteringResults,
    CascadingResults,
    SigmaAnalysisResults,
    OptimalNetTransferCapacityResults,
    OptimalNetTransferCapacityTimeSeriesResults,
    InputsAnalysisResults,
    InvestmentsEvaluationResults,
    NodalCapacityTimeSeriesResults,
    ReliabilityResults
]