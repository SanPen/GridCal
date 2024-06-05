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
from typing import Union
from GridCalEngine.Devices.Aggregation import *
from GridCalEngine.Devices.Branches import *
from GridCalEngine.Devices.Injections import *
from GridCalEngine.Devices.Substation import *
from GridCalEngine.Devices.Associations import *
from GridCalEngine.Devices.Fluid import *
from GridCalEngine.Devices.measurement import *

# Module imports
from GridCalEngine.Simulations.ATC.available_transfer_capacity_driver import (AvailableTransferCapacityDriver,
                                                                              AvailableTransferCapacityResults)
from GridCalEngine.Simulations.ATC.available_transfer_capacity_ts_driver import (
    AvailableTransferCapacityTimeSeriesDriver, AvailableTransferCapacityTimeSeriesResults)
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import (ContingencyAnalysisDriver,
                                                                                       ContingencyAnalysisResults)
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_ts_driver import (
    ContingencyAnalysisTimeSeriesDriver, ContingencyAnalysisTimeSeriesResults)
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow_driver import (ContinuationPowerFlowDriver,
                                                                                            ContinuationPowerFlowResults)
from GridCalEngine.Simulations.LinearFactors.linear_analysis_driver import LinearAnalysisDriver, LinearAnalysisResults
from GridCalEngine.Simulations.LinearFactors.linear_analysis_ts_driver import (LinearAnalysisTimeSeriesDriver,
                                                                               LinearAnalysisTimeSeriesResults)
from GridCalEngine.Simulations.OPF.opf_driver import OptimalPowerFlowDriver, OptimalPowerFlowResults
from GridCalEngine.Simulations.OPF.opf_ts_driver import (OptimalPowerFlowTimeSeriesDriver,
                                                         OptimalPowerFlowTimeSeriesResults)
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver, PowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_ts_driver import (PowerFlowTimeSeriesDriver,
                                                                      PowerFlowTimeSeriesResults)
from GridCalEngine.Simulations.ShortCircuitStudies.short_circuit_driver import ShortCircuitDriver, ShortCircuitResults
from GridCalEngine.Simulations.Stochastic.stochastic_power_flow_driver import (StochasticPowerFlowDriver,
                                                                               StochasticPowerFlowResults)
from GridCalEngine.Simulations.Clustering.clustering_driver import ClusteringDriver, ClusteringResults
from GridCalEngine.Simulations.Stochastic.blackout_driver import CascadingDriver, CascadingResults
from GridCalEngine.Simulations.InputsAnalysis.inputs_analysis_driver import InputsAnalysisDriver, InputsAnalysisResults
from GridCalEngine.Simulations.InvestmentsEvaluation.investments_evaluation_driver import (InvestmentsEvaluationDriver,
                                                                                           InvestmentsEvaluationResults)
from GridCalEngine.Simulations.SigmaAnalysis.sigma_analysis_driver import SigmaAnalysisDriver, SigmaAnalysisResults
from GridCalEngine.Simulations.NTC.ntc_driver import OptimalNetTransferCapacityDriver, OptimalNetTransferCapacityResults
from GridCalEngine.Simulations.NTC.ntc_ts_driver import (OptimalNetTransferCapacityTimeSeriesDriver,
                                                         OptimalNetTransferCapacityTimeSeriesResults)
from GridCalEngine.Simulations.NodalCapacity.nodal_capacity_ts_driver import (NodalCapacityTimeSeriesDriver,
                                                                              NodalCapacityTimeSeriesResults)
from GridCalEngine.Simulations.Topology.node_groups_driver import NodeGroupsDriver
from GridCalEngine.Simulations.Topology.topology_processor_driver import TopologyProcessorDriver


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
    TopologyProcessorDriver,
    NodalCapacityTimeSeriesDriver
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
    NodalCapacityTimeSeriesResults
]

INJECTION_DEVICE_TYPES = Union[
    Generator,
    Battery,
    Load,
    ExternalGrid,
    StaticGenerator,
    Shunt,
    ControllableShunt,
    CurrentInjection,
    FluidP2x,
    FluidTurbine,
    FluidPump
]

BRANCH_TYPES = Union[
    Line,
    DcLine,
    Transformer2W,
    HvdcLine,
    VSC,
    UPFC,
    Winding,
    Switch,
    SeriesReactance
]

FLUID_TYPES = Union[
    FluidNode,
    FluidPath,
    FluidP2x,
    FluidTurbine,
    FluidPump
]

AREA_TYPES = Union[
    Country,
    Region,
    Community,
    Municipality,
    Area,
    Zone
]

SUBSTATION_TYPES = Union[
    Substation,
    Bus,
    ConnectivityNode,
    BusBar,
    VoltageLevel
]

MEASUREMENT_TYPES = Union[
    IfMeasurement,
    QfMeasurement,
    PfMeasurement,
    QiMeasurement,
    PiMeasurement,
    VmMeasurement
]

ALL_DEV_TYPES = Union[
    INJECTION_DEVICE_TYPES,
    BRANCH_TYPES,
    FLUID_TYPES,
    SUBSTATION_TYPES,
    MEASUREMENT_TYPES,
    AREA_TYPES,
    Transformer3W,
    OverheadLineType,
    Wire,
    Area,
    Zone,
    TransformerType,
    EmissionGas,
    GeneratorEmission,
    GeneratorFuel,
    GeneratorTechnology,
    BranchGroup,
    LineLocations,
    LineLocation,
    ModellingAuthority,
    Fuel,
    Investment,
    InvestmentsGroup,
    Contingency,
    ContingencyGroup,
    Technology,
    UndergroundLineType,
    SequenceLineType
]

CONNECTION_TYPE = Union[ConnectivityNode, Bus, None]
