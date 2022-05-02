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


class BranchType(Enum):
    Branch = 'branch'
    Line = 'line'
    DCLine = 'DC-line'
    VSC = 'VSC'
    UPFC = 'UPFC'
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
    Pt = '1:Pt'
    Qt = '2:Qt'
    PtQt = '3:Pt+Qt'
    Vt = '4:Vt'
    PtVt = '5:Pt+Vt'

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


class ConverterControlType(Enum):

    # Type I
    # theta_vac = '1:Angle+Vac'
    # pf_qac = '2:Pflow + Qflow'
    # pf_vac = '3:Pflow + Vac'
    #
    # # Type II
    # vdc_qac = '4:Vdc+Qflow'
    # vdc_vac = '5:Vdc+Vac'
    #
    # # type III
    # vdc_droop_qac = '6:VdcDroop+Qac'
    # vdc_droop_vac = '7:VdcDroop+Vac'

    type_0_free = '0:Free'

    type_I_1 = '1:Vac'
    type_I_2 = '2:Pdc+Qac'
    type_I_3 = '3:Pdc+Vac'

    type_II_4 = '4:Vdc+Qac'
    type_II_5 = '5:Vdc+Vac'

    type_III_6 = '6:Droop+Qac'
    type_III_7 = '7:Droop+Vac'

    type_IV_I = '8:Vdc'
    type_IV_II = '9:Pdc'

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


class HvdcControlType(Enum):
    type_0_free = '0:Free'
    type_1_Pset = '1:Pdc'

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


class GenerationNtcFormulation(Enum):
    Proportional = 'Proportional'
    Optimal = 'Optimal'


class TimeFrame(Enum):
    Continuous = 'Continuous'


class DeviceType(Enum):
    NoDevice = "NoDevice"
    CircuitDevice = 'Circuit'
    BusDevice = 'Bus'
    BranchDevice = 'Branch'
    BranchTypeDevice = 'Branch template'
    LineDevice = 'Line'
    LineTypeDevice = 'Line Template'
    Transformer2WDevice = 'Transformer'
    Transformer3WDevice = 'Transformer3W'
    HVDCLineDevice = 'HVDC Line'
    DCLineDevice = 'DC line'
    VscDevice = 'VSC'
    BatteryDevice = 'Battery'
    LoadDevice = 'Load'
    GeneratorDevice = 'Generator'
    StaticGeneratorDevice = 'Static Generator'
    ShuntDevice = 'Shunt'
    UpfcDevice = 'UPFC'  # unified power flow controller
    ExternalGridDevice = 'External grid'
    WireDevice = 'Wire'
    SequenceLineDevice = 'Sequence line'
    UnderGroundLineDevice = 'Underground line'
    TowerDevice = 'Tower'
    TransformerTypeDevice = 'Transformer type'
    SwitchDevice = 'Switch'

    GenericArea = 'Generic Area'
    SubstationDevice = 'Substation'
    AreaDevice = 'Area'
    ZoneDevice = 'Zone'
    CountryDevice = 'Country'

    Technology = 'Technology'
    TechnologyGroup = 'Technology Group'
    TechnologyCategory = 'Technology Category'

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
