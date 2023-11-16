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


class cgmesProfile(Enum):
    EQ_BD = 'EQ_BD'  # EquipmentBoundary
    TP_BD = 'TP_BD'  # TopologyBoundary
    EQ = 'EQ'  # Equipment
    TP = 'TP'  # Topology
    SSH = 'SSH'  # SteadyStateHypothesis
    SV = 'SV'  # StateVariables
    DY = 'DY'  # Dynamics

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


class SVCControlMode(Enum):
    volt = 'voltage'
    reactive = 'reactive'

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


class OperationalLimitDirectionKind(Enum):
    '''
    High means that a monitored value above the limit value is a
    violation. If applied to a terminal flow, the positive direction is into the
    terminal.
    '''
    high = 'high'

    '''
    Low means a monitored value below the limit is a violation. If applied
    to a terminal flow, the positive direction is into the terminal.
    '''
    low = 'low'

    '''
    An absoluteValue limit means that a monitored absolute value above
    the limit value is a violation.
    '''
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


class LimitTypeKind(Enum):
    '''
    The Permanent Admissible Transmission Loading (PATL) is the
    loading in Amps, MVA or MW that can be accepted by a network
    branch for an unlimited duration without any risk for the material.
    The duration attribute is not used and shall be excluded for the PATL
    limit type. Hence, only one limit value exists for the PATL type.
    '''
    patl = 'patl'

    '''
    Permanent Admissible Transmission Loading Threshold (PATLT) is a
    value in engineering units defined for PATL and calculated using
    percentage less than 100 of the PATL type intended to alert
    operators of an arising condition. The percentage should be given in
    the name of the OperationalLimitSet. The aceptableDuration is
    another way to express the severity of the limit.
    '''
    patlt = 'patlt'

    '''
    Temporarily Admissible Transmission Loading (TATL) which is the
    loading in Amps, MVA or MW that can be accepted by a branch for a
    certain limited duration.
    The TATL can be defined in different ways:
    as a fixed percentage of the PATL for a given time (for example,
    115% of the PATL that can be accepted during 15 minutes),
    pairs of TATL type and Duration calculated for each line taking into
    account its particular configuration and conditions of functioning (for
    example, it can define a TATL acceptable during 20 minutes and
    another one acceptable during 10 minutes).
    Such a definition of TATL can depend on the initial operating
    conditions of the network element (sag situation of a line). The
    duration attribute can be used define several TATL limit types. Hence
    multiple TATL limit values may exist having different durations.
    '''
    tatl = 'tatl'

    '''
    Tripping Current (TC) is the ultimate intensity without any delay. It is
    defined as the threshold the line will trip without any possible
    remedial actions.
    The tripping of the network element is ordered by protections against
    short circuits or by overload protections, but in any case, the
    activation delay of these protections is not compatible with the
    reaction delay of an operator (less than one minute).
    The duration is always zero and the duration attribute may be left out.
    Hence only one limit value exists for the TC type.
    '''
    tc = 'tc'

    '''
    Tripping Current Threshold (TCT) is a value in engineering units
    defined for TC and calculated using percentage less than 100 of the
    TC type intended to alert operators of an arising condition. The
    percentage should be given in the name of the OperationalLimitSet.
    The aceptableDuration is another way to express the severity of the
    limit.
    '''
    tct = 'tct'

    '''
    Referring to the rating of the equipments, a voltage too high can lead
    to accelerated ageing or the destruction of the equipment.
    This limit type may or may not have duration.
    '''
    highVoltage = 'highVoltage'

    '''
    A too low voltage can disturb the normal operation of some
    protections and transformer equipped with on-load tap changers,
    electronic power devices or can affect the behaviour of the auxiliaries
    of generation units.
    This limit type may or may not have duration.
    '''
    lowVoltage = 'lowVoltage'

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
    s1N = 'S1N'
    s2N = 'S2N'
    s12N = 'S12N'
    s1 = 'S1'
    s2 = 'S2'
    s12 = 'S12'

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
