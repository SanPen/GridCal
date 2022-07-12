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

from enum import Enum
from GridCal.Engine.Devices import DeviceType


class ResultTypes(Enum):
    # Power flow
    BusVoltage = 'Bus voltage', DeviceType.BusDevice
    BusVoltagePolar = 'Bus voltage (polar)', DeviceType.BusDevice
    BusActivePower = 'Bus active power', DeviceType.BusDevice
    BusReactivePower = 'Bus reactive power', DeviceType.BusDevice
    BranchPower = 'Branch power', DeviceType.BranchDevice
    BranchActivePowerFrom = 'Branch active power "from"', DeviceType.BranchDevice
    BranchReactivePowerFrom = 'Branch reactive power "from"', DeviceType.BranchDevice
    BranchActivePowerTo = 'Branch active power "to"', DeviceType.BranchDevice
    BranchReactivePowerTo = 'Branch reactive power "to"', DeviceType.BranchDevice

    BranchCurrent = 'Branch current', DeviceType.BranchDevice
    BranchActiveCurrentFrom = 'Branch active current "from"', DeviceType.BranchDevice
    BranchReactiveCurrentFrom = 'Branch reactive current "from"', DeviceType.BranchDevice
    BranchActiveCurrentTo = 'Branch active current "to"', DeviceType.BranchDevice
    BranchReactiveCurrentTo = 'Branch reactive current "to"', DeviceType.BranchDevice

    BranchTapModule = 'Branch tap module', DeviceType.BranchDevice
    BranchTapAngle = 'Branch tap angle', DeviceType.BranchDevice
    BranchBeq = 'Branch Beq', DeviceType.BranchDevice

    BranchLoading = 'Branch loading', DeviceType.BranchDevice
    Transformer2WTapModule = 'Transformer tap module', DeviceType.Transformer2WDevice
    BranchVoltage = 'Branch voltage drop', DeviceType.BranchDevice
    BranchAngles = 'Branch voltage angles', DeviceType.BranchDevice
    BranchLosses = 'Branch losses', DeviceType.BranchDevice
    BranchActiveLosses = 'Branch active losses', DeviceType.BranchDevice
    BranchReactiveLosses = 'Branch reactive losses', DeviceType.BranchDevice
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
    BranchLoadingAverage = 'Branch loading avg', DeviceType.BranchDevice
    BranchLoadingStd = 'Branch loading std', DeviceType.BranchDevice
    BranchLoadingCDF = 'Branch loading CDF', DeviceType.BranchDevice
    BranchLossesAverage = 'Branch losses avg', DeviceType.BranchDevice
    BranchLossesStd = 'Branch losses std', DeviceType.BranchDevice
    BranchLossesCDF = 'Branch losses CDF', DeviceType.BranchDevice

    # OPF
    BusVoltageModule = 'Bus voltage module', DeviceType.BusDevice
    BusVoltageAngle = 'Bus voltage angle', DeviceType.BusDevice
    BusPower = 'Bus power', DeviceType.BusDevice
    BusShadowPrices = 'Bus shadow prices', DeviceType.BusDevice
    BranchOverloads = 'Branch overloads', DeviceType.BranchDevice
    LoadShedding = 'Load shedding', DeviceType.LoadDevice
    GeneratorShedding = 'Generator shedding', DeviceType.GeneratorDevice
    GeneratorPower = 'Generator power', DeviceType.GeneratorDevice

    # OPF-NTC
    HvdcOverloads = 'HVDC overloads', DeviceType.HVDCLineDevice
    NodeSlacks = 'Nodal slacks', DeviceType.BusDevice
    GenerationDelta = 'Generation deltas', DeviceType.GeneratorDevice
    GenerationDeltaSlacks = 'Generation delta slacks', DeviceType.GeneratorDevice
    InterAreaExchange = 'Inter-Area exchange', DeviceType.NoDevice

    OptimalNetTransferCapacityTimeSeriesReport = 'Optimal net transfer capacity series report', DeviceType.NoDevice

    # Short-circuit
    BusShortCircuitPower = 'Bus short circuit power', DeviceType.BusDevice

    # PTDF
    PTDFBranchesSensitivity = 'Branch Flow sensitivity', DeviceType.BranchDevice
    PTDFBusVoltageSensitivity = 'Bus voltage sensitivity', DeviceType.BusDevice

    OTDF = 'Outage transfer distribution factors', DeviceType.BranchDevice

    MaxOverloads = 'Maximum contingency flow', DeviceType.BranchDevice
    ContingencyFlows = 'Contingency flow', DeviceType.BranchDevice
    ContingencyLoading = 'Contingency loading', DeviceType.BranchDevice
    WorstContingencyFlows = 'Worst contingency Sf', DeviceType.BranchDevice
    WorstContingencyLoading = 'Worst contingency loading', DeviceType.BranchDevice
    ContingencyFrequency = 'Contingency frequency', DeviceType.BranchDevice
    ContingencyRelativeFrequency = 'Contingency relative frequency', DeviceType.BranchDevice

    SimulationError = 'Error', DeviceType.BusDevice

    OTDFSimulationError = 'Error', DeviceType.BranchDevice

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
    AvailableTransferCapacityBeta = 'Sensitivity to the exchange (N-1)', DeviceType.BranchDevice
    NetTransferCapacity = 'Net transfer capacity', DeviceType.BranchDevice
    AvailableTransferCapacityReport = 'ATC Report', DeviceType.NoDevice

    ContingencyFlowsReport = 'Contingency Report', DeviceType.NoDevice
    ContingencyFlowsBranchReport = 'Contingency Branch Report', DeviceType.NoDevice
    ContingencyFlowsGenerationReport = 'Contingency Generation Report', DeviceType.NoDevice
    ContingencyFlowsHvdcReport = 'Contingency Hvdc Report', DeviceType.NoDevice

    # inputs analysis
    ZoneAnalysis = 'Zone analysis', DeviceType.NoDevice
    CountryAnalysis = 'Country analysis', DeviceType.NoDevice
    AreaAnalysis = 'Area analysis', DeviceType.NoDevice

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return ResultTypes[s]
        except KeyError:
            return s

