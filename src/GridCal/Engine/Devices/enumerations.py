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
    DCLine = 'DC-line'
    VSC = 'VSC'
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

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class TransformerControlType(Enum):

    fixed = '0:Fixed'
    angle = '1:Angle'
    v_from = '3:Control V from'
    v_to = '4:Control V to'
    angle_v_from = '5:Control Angle + V from'
    angle_v_to = '6:Control Angle + V to'

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return TransformerControlType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


def get_transformer_control_numbers_dict():
    """
    Get a dictionary relating the control modes to a number
    """
    return {TransformerControlType.fixed: 0,
            TransformerControlType.angle_tap: 3,
            TransformerControlType.tap: 2,
            TransformerControlType.angle: 1}


class ConverterControlType(Enum):

    # Type I
    theta_vac = '1:Angle+Vac'
    pf_qac = '2:Pflow + Qflow'
    pf_vac = '3:Pflow + Vac'

    # Type II
    vdc_qac = '4:Vdc+Qflow'
    vdc_vac = '5:Vdc+Vac'

    # type III
    # vdc_droop_qac = 6
    # vdc_droop_vac = 7

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return ConverterControlType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


def get_vsc_control_numbers_dict():
    """
    Get a dictionary relating the control modes to a number
    """
    return {ConverterControlType.theta_vac: 1,
            ConverterControlType.pf_qac: 2,
            ConverterControlType.pf_vac: 3,
            ConverterControlType.vdc_qac: 4,
            ConverterControlType.vdc_vac: 5}


class TimeFrame(Enum):
    Continuous = 'Continuous'


class DeviceType(Enum):
    CircuitDevice = 'Circuit'
    BusDevice = 'Bus'
    BranchDevice = 'Branch'
    LineDevice = 'Line'
    Transformer2WDevice = 'Transformer'
    HVDCLineDevice = 'HVDC Line'
    DCLineDevice = 'DC line'
    VscDevice = 'VSC'
    BatteryDevice = 'Battery'
    LoadDevice = 'Load'
    GeneratorDevice = 'Generator'
    StaticGeneratorDevice = 'Static Generator'
    ShuntDevice = 'Shunt'
    ExternalGridDevice = 'External grid'
    WireDevice = 'Wire'
    SequenceLineDevice = 'Sequence line'
    UnderGroundLineDevice = 'Underground line'
    TowerDevice = 'Tower'
    TransformerTypeDevice = 'Transformer type'

    GenericArea = 'Generic Area'
    SubstationDevice = 'Substation'
    AreaDevice = 'Area'
    ZoneDevice = 'Zone'
    CountryDevice = 'Country'

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

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


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

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))
