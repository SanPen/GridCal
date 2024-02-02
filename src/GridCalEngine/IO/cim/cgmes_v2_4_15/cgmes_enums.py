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

from enum import Enum


class cgmesProfile(Enum):
    EQ_BD = 'EQ_BD'  # EquipmentBoundary
    TP_BD = 'TP_BD'  # TopologyBoundary
    EQ = 'EQ'  # Equipment
    TP = 'TP'  # Topology
    SSH = 'SSH'  # SteadyStateHypothesis
    SV = 'SV'  # StateVariables
    DY = 'DY'  # Dynamics
    DL = 'DL'  # ?
    GL = 'GL'  # ?

    def __str__(self):
        return 'cgmesProfile.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return cgmesProfile[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class UnitSymbol(Enum):
    VA = 'VA'
    W = 'W'
    VAr = 'VAr'
    VAh = 'VAh'
    Wh = 'Wh'
    VArh = 'VArh'
    V = 'V'
    ohm = 'ohm'
    A = 'A'
    F = 'F'
    H = 'H'
    degC = 'degC'
    s = 's'
    min = 'min'
    h = 'h'
    deg = 'deg'
    rad = 'rad'
    J = 'J'
    N = 'N'
    S = 'S'
    none = 'none'
    Hz = 'Hz'
    g = 'g'
    Pa = 'Pa'
    m = 'm'
    m2 = 'm2'
    m3 = 'm3'


def __str__(self):
    return 'UnitSymbol.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return UnitSymbol[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class UnitMultiplier(Enum):
    p = 'p'
    n = 'n'
    micro = 'micro'
    m = 'm'
    c = 'c'
    d = 'd'
    k = 'k'
    M = 'M'
    G = 'G'
    T = 'T'
    none = 'none'


def __str__(self):
    return 'UnitMultiplier.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return UnitMultiplier[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class DCPolarityKind(Enum):
    positive = 'positive'
    middle = 'middle'
    negative = 'negative'


def __str__(self):
    return 'DCPolarityKind.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return DCPolarityKind[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class DCConverterOperatingModeKind(Enum):
    bipolar = 'bipolar'
    monopolarMetallicReturn = 'monopolarMetallicReturn'
    monopolarGroundReturn = 'monopolarGroundReturn'


def __str__(self):
    return 'DCConverterOperatingModeKind.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return DCConverterOperatingModeKind[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class PhaseCode(Enum):
    ABCN = 'ABCN'
    ABC = 'ABC'
    ABN = 'ABN'
    ACN = 'ACN'
    BCN = 'BCN'
    AB = 'AB'
    AC = 'AC'
    BC = 'BC'
    AN = 'AN'
    BN = 'BN'
    CN = 'CN'
    A = 'A'
    B = 'B'
    C = 'C'
    N = 'N'
    s1N = 's1N'
    s2N = 's2N'
    s12N = 's12N'
    s1 = 's1'
    s2 = 's2'
    s12 = 's12'


def __str__(self):
    return 'PhaseCode.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return PhaseCode[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class Source(Enum):
    PROCESS = 'PROCESS'
    DEFAULTED = 'DEFAULTED'
    SUBSTITUTED = 'SUBSTITUTED'


def __str__(self):
    return 'Source.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return Source[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class Validity(Enum):
    GOOD = 'GOOD'
    QUESTIONABLE = 'QUESTIONABLE'
    INVALID = 'INVALID'


def __str__(self):
    return 'Validity.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return Validity[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class FuelType(Enum):
    coal = 'coal'
    oil = 'oil'
    gas = 'gas'
    lignite = 'lignite'
    hardCoal = 'hardCoal'
    oilShale = 'oilShale'


def __str__(self):
    return 'FuelType.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return FuelType[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class GeneratorControlSource(Enum):
    unavailable = 'unavailable'
    offAGC = 'offAGC'
    onAGC = 'onAGC'
    plantControl = 'plantControl'


def __str__(self):
    return 'GeneratorControlSource.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return GeneratorControlSource[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class Currency(Enum):
    USD = 'USD'
    EUR = 'EUR'
    AUD = 'AUD'
    CAD = 'CAD'
    CHF = 'CHF'
    CNY = 'CNY'
    DKK = 'DKK'
    GBP = 'GBP'
    JPY = 'JPY'
    NOK = 'NOK'
    RUR = 'RUR'
    SEK = 'SEK'
    INR = 'INR'
    other = 'other'


def __str__(self):
    return 'Currency.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return Currency[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class HydroEnergyConversionKind(Enum):
    generator = 'generator'
    pumpAndGenerator = 'pumpAndGenerator'


def __str__(self):
    return 'HydroEnergyConversionKind.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return HydroEnergyConversionKind[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class HydroPlantStorageKind(Enum):
    runOfRiver = 'runOfRiver'
    pumpedStorage = 'pumpedStorage'
    storage = 'storage'


def __str__(self):
    return 'HydroPlantStorageKind.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return HydroPlantStorageKind[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class WindGenUnitKind(Enum):
    offshore = 'offshore'
    onshore = 'onshore'


def __str__(self):
    return 'WindGenUnitKind.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return WindGenUnitKind[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class CurveStyle(Enum):
    constantYValue = 'constantYValue'
    straightLineYValues = 'straightLineYValues'


def __str__(self):
    return 'CurveStyle.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return CurveStyle[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class LimitTypeKind(Enum):

    def __str__(self):
        return 'LimitTypeKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return LimitTypeKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class OperationalLimitDirectionKind(Enum):
    high = 'high'
    low = 'low'
    absoluteValue = 'absoluteValue'


def __str__(self):
    return 'OperationalLimitDirectionKind.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return OperationalLimitDirectionKind[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class PetersenCoilModeKind(Enum):
    fixed = 'fixed'
    manual = 'manual'
    automaticPositioning = 'automaticPositioning'


def __str__(self):
    return 'PetersenCoilModeKind.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return PetersenCoilModeKind[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class WindingConnection(Enum):
    D = 'D'
    Y = 'Y'
    Z = 'Z'
    Yn = 'Yn'
    Zn = 'Zn'
    A = 'A'
    I = 'I'


def __str__(self):
    return 'WindingConnection.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return WindingConnection[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class TransformerControlMode(Enum):
    volt = 'volt'
    reactive = 'reactive'


def __str__(self):
    return 'TransformerControlMode.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return TransformerControlMode[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class RegulatingControlModeKind(Enum):
    voltage = 'voltage'
    activePower = 'activePower'
    reactivePower = 'reactivePower'
    currentFlow = 'currentFlow'
    admittance = 'admittance'
    timeScheduled = 'timeScheduled'
    temperature = 'temperature'
    powerFactor = 'powerFactor'


def __str__(self):
    return 'RegulatingControlModeKind.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return RegulatingControlModeKind[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class ShortCircuitRotorKind(Enum):
    salientPole1 = 'salientPole1'
    salientPole2 = 'salientPole2'
    turboSeries1 = 'turboSeries1'
    turboSeries2 = 'turboSeries2'


def __str__(self):
    return 'ShortCircuitRotorKind.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return ShortCircuitRotorKind[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class SVCControlMode(Enum):
    reactivePower = 'reactivePower'
    voltage = 'voltage'


def __str__(self):
    return 'SVCControlMode.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return SVCControlMode[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class SynchronousMachineKind(Enum):
    generator = 'generator'
    condenser = 'condenser'
    generatorOrCondenser = 'generatorOrCondenser'
    motor = 'motor'
    generatorOrMotor = 'generatorOrMotor'
    motorOrCondenser = 'motorOrCondenser'
    generatorOrCondenserOrMotor = 'generatorOrCondenserOrMotor'


def __str__(self):
    return 'SynchronousMachineKind.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return SynchronousMachineKind[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class ControlAreaTypeKind(Enum):
    AGC = 'AGC'
    Forecast = 'Forecast'
    Interchange = 'Interchange'


def __str__(self):
    return 'ControlAreaTypeKind.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return ControlAreaTypeKind[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class CsOperatingModeKind(Enum):
    inverter = 'inverter'
    rectifier = 'rectifier'


def __str__(self):
    return 'CsOperatingModeKind.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return CsOperatingModeKind[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class CsPpccControlKind(Enum):
    activePower = 'activePower'
    dcVoltage = 'dcVoltage'
    dcCurrent = 'dcCurrent'


def __str__(self):
    return 'CsPpccControlKind.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return CsPpccControlKind[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class VsPpccControlKind(Enum):
    pPcc = 'pPcc'
    udc = 'udc'
    pPccAndUdcDroop = 'pPccAndUdcDroop'
    pPccAndUdcDroopWithCompensation = 'pPccAndUdcDroopWithCompensation'
    pPccAndUdcDroopPilot = 'pPccAndUdcDroopPilot'


def __str__(self):
    return 'VsPpccControlKind.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return VsPpccControlKind[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class VsQpccControlKind(Enum):
    reactivePcc = 'reactivePcc'
    voltagePcc = 'voltagePcc'
    powerFactorPcc = 'powerFactorPcc'


def __str__(self):
    return 'VsQpccControlKind.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return VsQpccControlKind[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class AsynchronousMachineKind(Enum):
    generator = 'generator'
    motor = 'motor'


def __str__(self):
    return 'AsynchronousMachineKind.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return AsynchronousMachineKind[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


class SynchronousMachineOperatingMode(Enum):
    generator = 'generator'
    condenser = 'condenser'
    motor = 'motor'


def __str__(self):
    return 'SynchronousMachineOperatingMode.' + str(self.value)


def __repr__(self):
    return str(self)


@staticmethod
def argparse(s):
    try:
        return SynchronousMachineOperatingMode[s]
    except KeyError:
        return s


@classmethod
def list(cls):
    return list(map(lambda c: c.value, cls))


