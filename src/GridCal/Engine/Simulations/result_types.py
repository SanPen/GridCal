# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

from enum import Enum
from GridCal.Engine.Devices import DeviceType


class ResultTypes(Enum):
    # Power flow
    BusVoltage = 'Bus voltage', DeviceType.BusDevice
    BusVoltagePolar = 'Bus voltage (polar)', DeviceType.BusDevice
    BusActivePower = 'Bus active power', DeviceType.BusDevice
    BusReactivePower = 'Bus reactive power', DeviceType.BusDevice
    BranchPower = 'Branch power', DeviceType.BranchDevice
    BranchCurrent = 'Branch current', DeviceType.BranchDevice
    BranchLoading = 'Branch loading', DeviceType.BranchDevice
    BranchTapModule = 'Branch tap module', DeviceType.BranchDevice
    BranchVoltage = 'Branch voltage drop', DeviceType.BranchDevice
    BranchAngles = 'Branch voltage angles', DeviceType.BranchDevice
    BranchLosses = 'Branch losses', DeviceType.BranchDevice
    BatteryPower = 'Battery power', DeviceType.BatteryDevice
    BatteryEnergy = 'Battery energy', DeviceType.BatteryDevice

    # MonteCarlo
    BusVoltageAverage = 'Bus voltage avg', DeviceType.BusDevice
    BusVoltageStd = 'Bus voltage std', DeviceType.BusDevice
    BusVoltageCDF = 'Bus voltage CDF', DeviceType.BusDevice
    BusPowerCDF = 'Bus power CDF', DeviceType.BusDevice
    BranchCurrentAverage = 'Branch current avg', DeviceType.BranchDevice
    BranchCurrentStd = 'Branch current std', DeviceType.BranchDevice
    BranchCurrentCDF = 'Branch current CDF', DeviceType.BranchDevice
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
    ShadowPrices = 'Bus shadow prices', DeviceType.BusDevice
    BranchOverloads = 'Branch overloads', DeviceType.BranchDevice
    LoadShedding = 'Load shedding', DeviceType.LoadDevice
    ControlledGeneratorShedding = 'Controlled generator shedding', DeviceType.GeneratorDevice
    ControlledGeneratorPower = 'Controlled generator power', DeviceType.GeneratorDevice

    # Short-circuit
    BusShortCircuitPower = 'Bus short circuit power', DeviceType.BusDevice

    # PTDF
    PTDFBranchesSensitivity = 'Branch sensitivity', DeviceType.BranchDevice

    OTDF = 'Outage transfer distribution factors', DeviceType.BranchDevice

    SimulationError = 'Error', DeviceType.BusDevice

    OTDFSimulationError = 'Error', DeviceType.BranchDevice


class SimulationTypes(Enum):
    PowerFlow_run = 'power flow'
    ShortCircuit_run = 'Short circuit'
    MonteCarlo_run = 'Monte Carlo'
    TimeSeries_run = 'Time series power flow'
    VoltageCollapse_run = 'Voltage collapse'
    LatinHypercube_run = 'Latin Hypercube'
    Cascade_run = 'Cascade'
    OPF_run = 'Optimal power flow'
    OPFTimeSeries_run = 'OPF Time series'
    TransientStability_run = 'Transient stability'
    TopologyReduction_run = 'Topology reduction'
    PTDF_run = 'PTDF'
    OTDF_run = 'OTDF'
    Delete_and_reduce_run = 'Delete and reduce'
