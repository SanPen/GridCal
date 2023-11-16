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

from enum import Enum
from GridCalEngine.enumerations import DeviceType


class ResultTypes(Enum):
    # Power flow
    BusVoltage = 'Voltage', DeviceType.BusDevice
    BusVoltagePolar = 'Voltage (polar)', DeviceType.BusDevice
    BusActivePower = 'P: Active power', DeviceType.BusDevice
    BusReactivePower = 'Q: Reactive power', DeviceType.BusDevice
    BranchPower = 'Sf: Power', DeviceType.BranchDevice
    BranchActivePowerFrom = 'Pf: Active power "from"', DeviceType.BranchDevice
    BranchReactivePowerFrom = 'Qf: Reactive power "from"', DeviceType.BranchDevice
    BranchActivePowerTo = 'Pt: Active power "to"', DeviceType.BranchDevice
    BranchReactivePowerTo = 'Qt: Reactive power "to"', DeviceType.BranchDevice

    BranchCurrent = 'I: Current', DeviceType.BranchDevice
    BranchActiveCurrentFrom = 'Irf: Active current "from"', DeviceType.BranchDevice
    BranchReactiveCurrentFrom = 'Iif: Reactive current "from"', DeviceType.BranchDevice
    BranchActiveCurrentTo = 'Irt: Active current "to"', DeviceType.BranchDevice
    BranchReactiveCurrentTo = 'Iit: Reactive current "to"', DeviceType.BranchDevice

    BranchTapModule = 'm: Tap module', DeviceType.BranchDevice
    BranchTapAngle = '𝜏: Tap angle', DeviceType.BranchDevice
    BranchBeq = 'Beq: Equivalent susceptance', DeviceType.BranchDevice

    BranchLoading = 'Branch Loading', DeviceType.BranchDevice
    Transformer2WTapModule = 'Transformer tap module', DeviceType.Transformer2WDevice
    BranchVoltage = 'ΔV: Voltage modules drop', DeviceType.BranchDevice
    BranchAngles = 'Δθ: Voltage angles drop', DeviceType.BranchDevice
    BranchLosses = 'Branch losses', DeviceType.BranchDevice
    BranchActiveLosses = 'Pl: Active losses', DeviceType.BranchDevice
    BranchReactiveLosses = 'Ql: Reactive losses', DeviceType.BranchDevice
    BranchActiveLossesPercentage = 'Pl: Active losses (%)', DeviceType.BranchDevice
    BatteryPower = 'Battery power', DeviceType.BatteryDevice
    BatteryEnergy = 'Battery energy', DeviceType.BatteryDevice

    HvdcLosses = 'HVDC losses', DeviceType.HVDCLineDevice
    HvdcPowerFrom = 'HVDC power "from"', DeviceType.HVDCLineDevice
    HvdcLoading = 'HVDC loading', DeviceType.HVDCLineDevice
    HvdcPowerTo = 'HVDC power "to"', DeviceType.HVDCLineDevice

    # StochasticPowerFlowDriver
    BusVoltageAverage = 'Bus voltage avg', DeviceType.BusDevice
    BusVoltageStd = 'Bus voltage std', DeviceType.BusDevice
    BusVoltageCDF = 'Bus voltage CDF', DeviceType.BusDevice
    BusPowerCDF = 'Bus power CDF', DeviceType.BusDevice
    BranchPowerAverage = 'Branch power avg', DeviceType.BranchDevice
    BranchPowerStd = 'Branch power std', DeviceType.BranchDevice
    BranchPowerCDF = 'Branch power CDF', DeviceType.BranchDevice
    BranchLoadingAverage = 'loading avg', DeviceType.BranchDevice
    BranchLoadingStd = 'Loading std', DeviceType.BranchDevice
    BranchLoadingCDF = 'Loading CDF', DeviceType.BranchDevice
    BranchLossesAverage = 'Losses avg', DeviceType.BranchDevice
    BranchLossesStd = 'Losses std', DeviceType.BranchDevice
    BranchLossesCDF = 'Losses CDF', DeviceType.BranchDevice

    # PF
    BusVoltageModule = 'V: Voltage module', DeviceType.BusDevice
    BusVoltageAngle = 'θ: Voltage angle', DeviceType.BusDevice
    BusPower = 'Bus power', DeviceType.BusDevice
    BusShadowPrices = 'Nodal shadow prices', DeviceType.BusDevice
    BranchOverloads = 'Branch overloads', DeviceType.BranchDevice
    LoadShedding = 'Load shedding', DeviceType.LoadDevice
    GeneratorShedding = 'Generator shedding', DeviceType.GeneratorDevice
    GeneratorPower = 'Generator power', DeviceType.GeneratorDevice
    BusVoltagePolarPlot = 'Voltage plot', DeviceType.BusDevice

    # OPF-NTC
    HvdcOverloads = 'HVDC overloads', DeviceType.HVDCLineDevice
    NodeSlacks = 'Nodal slacks', DeviceType.BusDevice
    GenerationDelta = 'Generation deltas', DeviceType.GeneratorDevice
    GenerationDeltaSlacks = 'Generation delta slacks', DeviceType.GeneratorDevice
    InterAreaExchange = 'Inter-Area exchange', DeviceType.NoDevice
    LossesPercentPerArea = 'Losses % per area', DeviceType.NoDevice
    LossesPerArea = 'Losses per area', DeviceType.NoDevice
    ActivePowerFlowPerArea = 'Active power flow per area', DeviceType.NoDevice
    LossesPerGenPerArea = 'Losses per generation unit in area', DeviceType.NoDevice

    # NTC TS
    OpfNtcTsContingencyReport = 'Contingency flow report', DeviceType.NoDevice
    OpfNtcTsBaseReport = 'Base flow report', DeviceType.NoDevice


    # Short-circuit
    BusShortCircuitActivePower = 'Short circuit active power', DeviceType.BusDevice
    BusShortCircuitReactivePower = 'Short circuit reactive power', DeviceType.BusDevice

    # PTDF
    PTDF = 'PTDF', DeviceType.BranchDevice
    PTDFBusVoltageSensitivity = 'Bus voltage sensitivity', DeviceType.BusDevice

    LODF = 'LODF', DeviceType.BranchDevice

    MaxOverloads = 'Maximum contingency flow', DeviceType.BranchDevice
    ContingencyFlows = 'Contingency flow', DeviceType.BranchDevice
    ContingencyLoading = 'Contingency loading', DeviceType.BranchDevice
    WorstContingencyFlows = 'Worst contingency Sf', DeviceType.BranchDevice
    WorstContingencyLoading = 'Worst contingency loading', DeviceType.BranchDevice
    ContingencyFrequency = 'Contingency frequency', DeviceType.BranchDevice
    ContingencyRelativeFrequency = 'Contingency relative frequency', DeviceType.BranchDevice

    SimulationError = 'Error', DeviceType.BusDevice

    OTDFSimulationError = 'Error', DeviceType.BranchDevice

    # contingency analysis
    ContingencyAnalysisReport = 'Contingencies report', DeviceType.NoDevice

    # sigma
    SigmaReal = 'Sigma real', DeviceType.BusDevice
    SigmaImag = 'Sigma imaginary', DeviceType.BusDevice
    SigmaDistances = 'Sigma distances', DeviceType.BusDevice
    SigmaPlusDistances = 'Sigma + distances', DeviceType.BusDevice

    # ATC
    AvailableTransferCapacityMatrix = 'Available transfer capacity', DeviceType.BranchDevice
    AvailableTransferCapacity = 'Available transfer capacity (final)', DeviceType.BranchDevice
    AvailableTransferCapacityN = 'Available transfer capacity (N)', DeviceType.BranchDevice
    AvailableTransferCapacityAlpha = 'Sensitivity to the exchange', DeviceType.BranchDevice
    AvailableTransferCapacityAlphaN1 = 'Sensitivity to the exchange (N-1)', DeviceType.BranchDevice
    NetTransferCapacity = 'Net transfer capacity', DeviceType.BranchDevice
    AvailableTransferCapacityReport = 'ATC Report', DeviceType.NoDevice

    # NTC
    # ContingencyFlowsReport = 'Contingency Report', DeviceType.NoDevice
    # ContingencyFlowsBranchReport = 'Contingency Branch Report', DeviceType.NoDevice
    # ContingencyFlowsGenerationReport = 'Contingency Generation Report', DeviceType.NoDevice
    # ContingencyFlowsHvdcReport = 'Contingency Hvdc Report', DeviceType.NoDevice

    BaseFlowReport = 'Ntc: Base flow report', DeviceType.NoDevice
    ContingencyFlowsReport = 'Ntc: Contingency flow report', DeviceType.NoDevice
    ContingencyFlowsBranchReport = 'Ntc: Contingency flow report. (Branch)', DeviceType.NoDevice
    ContingencyFlowsGenerationReport = 'Ntc: Contingency flow report. (Generation)', DeviceType.NoDevice
    ContingencyFlowsHvdcReport = 'Ntc: Contingency flow report. (Hvdc)', DeviceType.NoDevice

    # Time series
    TsBaseFlowReport = 'Time series base flow report', DeviceType.NoDevice
    TsContingencyFlowReport = 'Time series contingency flow report', DeviceType.NoDevice
    TsContingencyFlowBranchReport = 'Time series Contingency flow report (Branches)', DeviceType.NoDevice
    TsContingencyFlowGenerationReport = 'Time series contingency flow report. (Generation)', DeviceType.NoDevice
    TsContingencyFlowHvdcReport = 'Time series contingency flow report. (Hvdc)', DeviceType.NoDevice
    TsGenerationPowerReport = 'Time series generation power report', DeviceType.NoDevice
    TsGenerationDeltaReport = 'Time series generation delta power report', DeviceType.NoDevice
    TsAlphaReport = 'Time series sensitivity to the exchange report', DeviceType.NoDevice
    TsWorstAlphaN1Report = 'Time series worst sensitivity to the exchange report (N-1)', DeviceType.NoDevice
    TsBranchMonitoring = 'Time series branch monitoring logic report', DeviceType.BranchDevice
    TsCriticalBranches = 'Time series critical Branches report', DeviceType.BranchDevice
    TsContingencyBranches = 'Time series contingency Branches report', DeviceType.BranchDevice

    # Clustering
    ClusteringReport = 'Clustering time series report', DeviceType.NoDevice

    # inputs analysis
    ZoneAnalysis = 'Zone analysis', DeviceType.NoDevice
    CountryAnalysis = 'Country analysis', DeviceType.NoDevice
    AreaAnalysis = 'Area analysis', DeviceType.NoDevice

    AreaGenerationAnalysis = 'Area generation analysis', DeviceType.NoDevice
    ZoneGenerationAnalysis = 'Zone generation analysis', DeviceType.NoDevice
    CountryGenerationAnalysis = 'Country generation analysis', DeviceType.NoDevice

    AreaLoadAnalysis = 'Area load analysis', DeviceType.NoDevice
    ZoneLoadAnalysis = 'Zone load analysis', DeviceType.NoDevice
    CountryLoadAnalysis = 'Country load analysis', DeviceType.NoDevice

    AreaBalanceAnalysis = 'Area balance analysis', DeviceType.NoDevice
    ZoneBalanceAnalysis = 'Zone balance analysis', DeviceType.NoDevice
    CountryBalanceAnalysis = 'Country balance analysis', DeviceType.NoDevice

    # Short circuit
    BusVoltageModule0 = 'Voltage module (0)', DeviceType.BusDevice
    BusVoltageAngle0 = 'Voltage angle (0)', DeviceType.BusDevice
    BranchActivePowerFrom0 = 'Branch active power "from" (0)', DeviceType.BranchDevice
    BranchReactivePowerFrom0 = 'Branch reactive power "from" (0)', DeviceType.BranchDevice
    BranchActiveCurrentFrom0 = 'Branch active current "from" (0)', DeviceType.BranchDevice
    BranchReactiveCurrentFrom0 = 'Branch reactive current "from" (0)', DeviceType.BranchDevice
    BranchLoading0 = 'Branch loading (0)', DeviceType.BranchDevice
    BranchActiveLosses0 = 'Branch active losses (0)', DeviceType.BranchDevice
    BranchReactiveLosses0 = 'Branch reactive losses (0)', DeviceType.BranchDevice

    BusVoltageModule1 = 'Voltage module (1)', DeviceType.BusDevice
    BusVoltageAngle1 = 'Voltage angle (1)', DeviceType.BusDevice
    BranchActivePowerFrom1 = 'Branch active power "from" (1)', DeviceType.BranchDevice
    BranchReactivePowerFrom1 = 'Branch reactive power "from" (1)', DeviceType.BranchDevice
    BranchActiveCurrentFrom1 = 'Branch active current "from" (1)', DeviceType.BranchDevice
    BranchReactiveCurrentFrom1 = 'Branch reactive current "from" (1)', DeviceType.BranchDevice
    BranchLoading1 = 'Branch loading (1)', DeviceType.BranchDevice
    BranchActiveLosses1 = 'Branch active losses (1)', DeviceType.BranchDevice
    BranchReactiveLosses1 = 'Branch reactive losses (1)', DeviceType.BranchDevice

    BusVoltageModule2 = 'Voltage module (2)', DeviceType.BusDevice
    BusVoltageAngle2 = 'Voltage angle (2)', DeviceType.BusDevice
    BranchActivePowerFrom2 = 'Branch active power "from" (2)', DeviceType.BranchDevice
    BranchReactivePowerFrom2 = 'Branch reactive power "from" (2)', DeviceType.BranchDevice
    BranchActiveCurrentFrom2 = 'Branch active current "from" (2)', DeviceType.BranchDevice
    BranchReactiveCurrentFrom2 = 'Branch reactive current "from" (2)', DeviceType.BranchDevice
    BranchLoading2 = 'Branch loading (2)', DeviceType.BranchDevice
    BranchActiveLosses2 = 'Branch active losses (2)', DeviceType.BranchDevice
    BranchReactiveLosses2 = 'Branch reactive losses (2)', DeviceType.BranchDevice
    BranchMonitoring = 'Branch monitoring logic', DeviceType.BranchDevice

    ShortCircuitInfo = 'Short-circuit information', DeviceType.NoDevice

    # classifiers
    BusResults = 'Bus', DeviceType.NoDevice
    BranchResults = 'Branch', DeviceType.NoDevice
    HvdcResults = 'Hvdc', DeviceType.NoDevice
    AreaResults = 'Area', DeviceType.NoDevice
    InfoResults = 'Information', DeviceType.NoDevice
    ReportsResults = 'Reports', DeviceType.NoDevice
    SlacksResults = 'Slacks', DeviceType.NoDevice
    DispatchResults = 'Dispatch', DeviceType.NoDevice
    FlowReports = 'Flow Reports', DeviceType.NoDevice
    Sensibilities = 'Sensibilities', DeviceType.NoDevice
    SeriesResults = 'Series', DeviceType.NoDevice
    SnapshotResults = 'Snapshot', DeviceType.NoDevice
    NTCResults = 'NTC', DeviceType.NoDevice
    SpecialPlots = 'Special plots', DeviceType.NoDevice

    GeneratorResults = 'Generators', DeviceType.GeneratorDevice
    LoadResults = 'Loads', DeviceType.LoadDevice
    BatteryResults = 'Batteries', DeviceType.BatteryDevice

    # investments evaluation
    InvestmentsReportResults = 'Investments evaluation report', DeviceType.NoDevice
    InvestmentsParetoPlot = 'Pareto plot', DeviceType.NoDevice
    InvestmentsIterationsPlot = 'Itertions plot', DeviceType.NoDevice

    def __str__(self):
        return self.value[0]

    def __repr__(self):
        return str(self.value[0])

    @staticmethod
    def argparse(s):
        try:
            return ResultTypes[s]
        except KeyError:
            return s

