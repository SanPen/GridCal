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


class UnitMultiplier(Enum):
    y = 'y'
    z = 'z'
    a = 'a'
    f = 'f'
    p = 'p'
    n = 'n'
    micro = 'micro'
    m = 'm'
    c = 'c'
    d = 'd'
    none = 'none'
    da = 'da'
    h = 'h'
    k = 'k'
    M = 'M'
    G = 'G'
    T = 'T'
    P = 'P'
    E = 'E'
    Z = 'Z'
    Y = 'Y'

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


class UnitSymbol(Enum):
    none = 'none'
    m = 'm'
    kg = 'kg'
    s = 's'
    A = 'A'
    K = 'K'
    mol = 'mol'
    cd = 'cd'
    deg = 'deg'
    rad = 'rad'
    sr = 'sr'
    Gy = 'Gy'
    Bq = 'Bq'
    degC = 'degC'
    Sv = 'Sv'
    F = 'F'
    C = 'C'
    S = 'S'
    H = 'H'
    V = 'V'
    ohm = 'ohm'
    J = 'J'
    N = 'N'
    Hz = 'Hz'
    lx = 'lx'
    lm = 'lm'
    Wb = 'Wb'
    T = 'T'
    W = 'W'
    Pa = 'Pa'
    m2 = 'm2'
    m3 = 'm3'
    mPers = 'mPers'
    mPers2 = 'mPers2'
    m3Pers = 'm3Pers'
    mPerm3 = 'mPerm3'
    kgm = 'kgm'
    kgPerm3 = 'kgPerm3'
    m2Pers = 'm2Pers'
    WPermK = 'WPermK'
    JPerK = 'JPerK'
    ppm = 'ppm'
    rotPers = 'rotPers'
    radPers = 'radPers'
    WPerm2 = 'WPerm2'
    JPerm2 = 'JPerm2'
    SPerm = 'SPerm'
    KPers = 'KPers'
    PaPers = 'PaPers'
    JPerkgK = 'JPerkgK'
    VA = 'VA'
    VAr = 'VAr'
    cosPhi = 'cosPhi'
    Vs = 'Vs'
    V2 = 'V2'
    As = 'As'
    A2 = 'A2'
    A2s = 'A2s'
    VAh = 'VAh'
    Wh = 'Wh'
    VArh = 'VArh'
    VPerHz = 'VPerHz'
    HzPers = 'HzPers'
    character = 'character'
    charPers = 'charPers'
    kgm2 = 'kgm2'
    dB = 'dB'
    WPers = 'WPers'
    lPers = 'lPers'
    dBm = 'dBm'
    h = 'h'
    min = 'min'
    Q = 'Q'
    Qh = 'Qh'
    ohmm = 'ohmm'
    APerm = 'APerm'
    V2h = 'V2h'
    A2h = 'A2h'
    Ah = 'Ah'
    count = 'count'
    ft3 = 'ft3'
    m3Perh = 'm3Perh'
    gal = 'gal'
    Btu = 'Btu'
    l = 'l'
    lPerh = 'lPerh'
    lPerl = 'lPerl'
    gPerg = 'gPerg'
    molPerm3 = 'molPerm3'
    molPermol = 'molPermol'
    molPerkg = 'molPerkg'
    sPers = 'sPers'
    HzPerHz = 'HzPerHz'
    VPerV = 'VPerV'
    APerA = 'APerA'
    VPerVA = 'VPerVA'
    rev = 'rev'
    kat = 'kat'
    JPerkg = 'JPerkg'
    m3Uncompensated = 'm3Uncompensated'
    m3Compensated = 'm3Compensated'
    WPerW = 'WPerW'
    therm = 'therm'
    onePerm = 'onePerm'
    m3Perkg = 'm3Perkg'
    Pas = 'Pas'
    Nm = 'Nm'
    NPerm = 'NPerm'
    radPers2 = 'radPers2'
    JPerm3 = 'JPerm3'
    VPerm = 'VPerm'
    CPerm3 = 'CPerm3'
    CPerm2 = 'CPerm2'
    FPerm = 'FPerm'
    HPerm = 'HPerm'
    JPermol = 'JPermol'
    JPermolK = 'JPermolK'
    CPerkg = 'CPerkg'
    GyPers = 'GyPers'
    WPersr = 'WPersr'
    WPerm2sr = 'WPerm2sr'
    katPerm3 = 'katPerm3'
    d = 'd'
    anglemin = 'anglemin'
    anglesec = 'anglesec'
    ha = 'ha'
    tonne = 'tonne'
    bar = 'bar'
    mmHg = 'mmHg'
    M = 'M'
    kn = 'kn'
    Mx = 'Mx'
    G = 'G'
    Oe = 'Oe'
    Vh = 'Vh'
    WPerA = 'WPerA'
    onePerHz = 'onePerHz'
    VPerVAr = 'VPerVAr'
    ohmPerm = 'ohmPerm'
    kgPerJ = 'kgPerJ'
    JPers = 'JPers'

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


class FuelType(Enum):
    coal = 'coal'
    oil = 'oil'
    gas = 'gas'
    lignite = 'lignite'
    hardCoal = 'hardCoal'
    oilShale = 'oilShale'
    brownCoalLignite = 'brownCoalLignite'
    coalDerivedGas = 'coalDerivedGas'
    peat = 'peat'
    other = 'other'

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
    AED = 'AED'
    AFN = 'AFN'
    ALL = 'ALL'
    AMD = 'AMD'
    ANG = 'ANG'
    AOA = 'AOA'
    ARS = 'ARS'
    AUD = 'AUD'
    AWG = 'AWG'
    AZN = 'AZN'
    BAM = 'BAM'
    BBD = 'BBD'
    BDT = 'BDT'
    BGN = 'BGN'
    BHD = 'BHD'
    BIF = 'BIF'
    BMD = 'BMD'
    BND = 'BND'
    BOB = 'BOB'
    BOV = 'BOV'
    BRL = 'BRL'
    BSD = 'BSD'
    BTN = 'BTN'
    BWP = 'BWP'
    BYR = 'BYR'
    BZD = 'BZD'
    CAD = 'CAD'
    CDF = 'CDF'
    CHF = 'CHF'
    CLF = 'CLF'
    CLP = 'CLP'
    CNY = 'CNY'
    COP = 'COP'
    COU = 'COU'
    CRC = 'CRC'
    CUC = 'CUC'
    CUP = 'CUP'
    CVE = 'CVE'
    CZK = 'CZK'
    DJF = 'DJF'
    DKK = 'DKK'
    DOP = 'DOP'
    DZD = 'DZD'
    EEK = 'EEK'
    EGP = 'EGP'
    ERN = 'ERN'
    ETB = 'ETB'
    EUR = 'EUR'
    FJD = 'FJD'
    FKP = 'FKP'
    GBP = 'GBP'
    GEL = 'GEL'
    GHS = 'GHS'
    GIP = 'GIP'
    GMD = 'GMD'
    GNF = 'GNF'
    GTQ = 'GTQ'
    GYD = 'GYD'
    HKD = 'HKD'
    HNL = 'HNL'
    HRK = 'HRK'
    HTG = 'HTG'
    HUF = 'HUF'
    IDR = 'IDR'
    ILS = 'ILS'
    INR = 'INR'
    IQD = 'IQD'
    IRR = 'IRR'
    ISK = 'ISK'
    JMD = 'JMD'
    JOD = 'JOD'
    JPY = 'JPY'
    KES = 'KES'
    KGS = 'KGS'
    KHR = 'KHR'
    KMF = 'KMF'
    KPW = 'KPW'
    KRW = 'KRW'
    KWD = 'KWD'
    KYD = 'KYD'
    KZT = 'KZT'
    LAK = 'LAK'
    LBP = 'LBP'
    LKR = 'LKR'
    LRD = 'LRD'
    LSL = 'LSL'
    LTL = 'LTL'
    LVL = 'LVL'
    LYD = 'LYD'
    MAD = 'MAD'
    MDL = 'MDL'
    MGA = 'MGA'
    MKD = 'MKD'
    MMK = 'MMK'
    MNT = 'MNT'
    MOP = 'MOP'
    MRO = 'MRO'
    MUR = 'MUR'
    MVR = 'MVR'
    MWK = 'MWK'
    MXN = 'MXN'
    MYR = 'MYR'
    MZN = 'MZN'
    NAD = 'NAD'
    NGN = 'NGN'
    NIO = 'NIO'
    NOK = 'NOK'
    NPR = 'NPR'
    NZD = 'NZD'
    OMR = 'OMR'
    PAB = 'PAB'
    PEN = 'PEN'
    PGK = 'PGK'
    PHP = 'PHP'
    PKR = 'PKR'
    PLN = 'PLN'
    PYG = 'PYG'
    QAR = 'QAR'
    RON = 'RON'
    RSD = 'RSD'
    RUB = 'RUB'
    RWF = 'RWF'
    SAR = 'SAR'
    SBD = 'SBD'
    SCR = 'SCR'
    SDG = 'SDG'
    SEK = 'SEK'
    SGD = 'SGD'
    SHP = 'SHP'
    SLL = 'SLL'
    SOS = 'SOS'
    SRD = 'SRD'
    STD = 'STD'
    SYP = 'SYP'
    SZL = 'SZL'
    THB = 'THB'
    TJS = 'TJS'
    TMT = 'TMT'
    TND = 'TND'
    TOP = 'TOP'
    TRY = 'TRY'
    TTD = 'TTD'
    TWD = 'TWD'
    TZS = 'TZS'
    UAH = 'UAH'
    UGX = 'UGX'
    USD = 'USD'
    UYU = 'UYU'
    UZS = 'UZS'
    VEF = 'VEF'
    VND = 'VND'
    VUV = 'VUV'
    WST = 'WST'
    XAF = 'XAF'
    XCD = 'XCD'
    XOF = 'XOF'
    XPF = 'XPF'
    YER = 'YER'
    ZAR = 'ZAR'
    ZMK = 'ZMK'
    ZWL = 'ZWL'

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


class HydroTurbineKind(Enum):
    francis = 'francis'
    pelton = 'pelton'
    kaplan = 'kaplan'

    def __str__(self):
        return 'HydroTurbineKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return HydroTurbineKind[s]
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


class LimitKind(Enum):

    def __str__(self):
        return 'LimitKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return LimitKind[s]
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
    none = 'none'
    X = 'X'
    XY = 'XY'
    XN = 'XN'
    XYN = 'XYN'

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


class BatteryStateKind(Enum):
    discharging = 'discharging'
    full = 'full'
    waiting = 'waiting'
    charging = 'charging'
    empty = 'empty'

    def __str__(self):
        return 'BatteryStateKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return BatteryStateKind[s]
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


class VsPpccControlKind(Enum):
    pPcc = 'pPcc'
    udc = 'udc'
    pPccAndUdcDroop = 'pPccAndUdcDroop'
    pPccAndUdcDroopWithCompensation = 'pPccAndUdcDroopWithCompensation'
    pPccAndUdcDroopPilot = 'pPccAndUdcDroopPilot'
    phasePcc = 'phasePcc'

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
    pulseWidthModulation = 'pulseWidthModulation'

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
