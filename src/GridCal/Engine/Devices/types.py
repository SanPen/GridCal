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


class BranchType(Enum):
    Branch = 'branch'
    Line = 'line'
    Transformer = 'transformer'
    Reactance = 'reactance'
    Switch = 'switch'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return BranchType[s]
        except KeyError:
            return s


class TimeFrame(Enum):
    Continuous = 'Continuous'


class DeviceType(Enum):
    BusDevice = 'Bus'
    BranchDevice = 'Branch'
    BatteryDevice = 'Battery'
    LoadDevice = 'Load'
    GeneratorDevice = 'Generator'
    StaticGeneratorDevice = 'Static Generator'
    ShuntDevice = 'Shunt'
    WireDevice = 'Wire'
    SequenceLineDevice = 'Sequence line'
    UnderGroundLineDevice = 'Underground line'
    TowerDevice = 'Tower'
    TransformerTypeDevice = 'Transformer type'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return DeviceType[s]
        except KeyError:
            return s


class GeneratorTechnologyType(Enum):
    Nuclear = 'Nuclear'
    CombinedCycle = 'Combined cycle'
    OpenCycleGasTurbine = 'Open Cycle Gas Turbine'
    SteamCycle = 'Steam cycle (coal, waste, etc)'
    Photovoltaic = 'Photovoltaic'
    SolarConcentrated = 'Concentrated solar power'
    OnShoreWind = 'On-shore wind power'
    OffShoreWind = 'Off-shore wind power'
    HydroReservoir = 'Hydro with reservoir'
    HydroRunOfRiver = 'Hydro run-of-river'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return GeneratorTechnologyType[s]
        except KeyError:
            return s
