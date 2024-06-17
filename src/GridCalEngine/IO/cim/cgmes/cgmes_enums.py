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
    OP = 'OP'  # Operation
    SC = 'SC'  # Short Circuit
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


class GeneratorControlSource(Enum):
    onAGC = 'onAGC'
    unavailable = 'unavailable'
    plantControl = 'plantControl'
    offAGC = 'offAGC'

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


class PhaseCode(Enum):
    BC = 'BC'
    CN = 'CN'
    BN = 'BN'
    ABN = 'ABN'
    none = 'none'
    s1 = 's1'
    B = 'B'
    XN = 'XN'
    ACN = 'ACN'
    AC = 'AC'
    X = 'X'
    AN = 'AN'
    s1N = 's1N'
    XY = 'XY'
    AB = 'AB'
    XYN = 'XYN'
    A = 'A'
    s2 = 's2'
    ABCN = 'ABCN'
    s12 = 's12'
    C = 'C'
    BCN = 'BCN'
    ABC = 'ABC'
    N = 'N'
    s2N = 's2N'
    s12N = 's12N'

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


class UnitSymbol(Enum):
    VPerV = 'VPerV'
    JPerkg = 'JPerkg'
    lPers = 'lPers'
    ppm = 'ppm'
    CPerm3 = 'CPerm3'
    FPerm = 'FPerm'
    JPerm2 = 'JPerm2'
    VAr = 'VAr'
    dBm = 'dBm'
    m3Perh = 'm3Perh'
    m = 'm'
    W = 'W'
    Vh = 'Vh'
    JPermol = 'JPermol'
    radPers2 = 'radPers2'
    sr = 'sr'
    lPerh = 'lPerh'
    anglesec = 'anglesec'
    GyPers = 'GyPers'
    A = 'A'
    rad = 'rad'
    WPermK = 'WPermK'
    ohm = 'ohm'
    m2Pers = 'm2Pers'
    Bq = 'Bq'
    JPers = 'JPers'
    JPermolK = 'JPermolK'
    C = 'C'
    WPerm2 = 'WPerm2'
    NPerm = 'NPerm'
    deg = 'deg'
    mol = 'mol'
    Oe = 'Oe'
    WPerm2sr = 'WPerm2sr'
    kgPerJ = 'kgPerJ'
    katPerm3 = 'katPerm3'
    m3Uncompensated = 'm3Uncompensated'
    gPerg = 'gPerg'
    charPers = 'charPers'
    rotPers = 'rotPers'
    HzPerHz = 'HzPerHz'
    JPerK = 'JPerK'
    G = 'G'
    lPerl = 'lPerl'
    VPerHz = 'VPerHz'
    character = 'character'
    kgm2 = 'kgm2'
    HPerm = 'HPerm'
    kn = 'kn'
    mPerm3 = 'mPerm3'
    m3Perkg = 'm3Perkg'
    rev = 'rev'
    kgm = 'kgm'
    A2h = 'A2h'
    molPerkg = 'molPerkg'
    kg = 'kg'
    mPers = 'mPers'
    Wb = 'Wb'
    Sv = 'Sv'
    Pa = 'Pa'
    onePerm = 'onePerm'
    count = 'count'
    Wh = 'Wh'
    m3Compensated = 'm3Compensated'
    Gy = 'Gy'
    bar = 'bar'
    gal = 'gal'
    JPerm3 = 'JPerm3'
    WPersr = 'WPersr'
    VPerVA = 'VPerVA'
    PaPers = 'PaPers'
    ohmPerm = 'ohmPerm'
    none = 'none'
    V2h = 'V2h'
    lx = 'lx'
    molPerm3 = 'molPerm3'
    SPerm = 'SPerm'
    radPers = 'radPers'
    g = 'g'
    Btu = 'Btu'
    Mx = 'Mx'
    onePerHz = 'onePerHz'
    VA = 'VA'
    min = 'min'
    dB = 'dB'
    K = 'K'
    CPerkg = 'CPerkg'
    cd = 'cd'
    kat = 'kat'
    V = 'V'
    HzPers = 'HzPers'
    KPers = 'KPers'
    kgPerm3 = 'kgPerm3'
    mPers2 = 'mPers2'
    WPers = 'WPers'
    S = 'S'
    APerm = 'APerm'
    l = 'l'
    s = 's'
    Nm = 'Nm'
    JPerkgK = 'JPerkgK'
    As = 'As'
    H = 'H'
    WPerW = 'WPerW'
    degC = 'degC'
    J = 'J'
    ft3 = 'ft3'
    therm = 'therm'
    Hz = 'Hz'
    Qh = 'Qh'
    ohmm = 'ohmm'
    h = 'h'
    Ah = 'Ah'
    F = 'F'
    m2 = 'm2'
    V2 = 'V2'
    lm = 'lm'
    d = 'd'
    VPerVAr = 'VPerVAr'
    A2 = 'A2'
    Pas = 'Pas'
    m3 = 'm3'
    CPerm2 = 'CPerm2'
    mmHg = 'mmHg'
    tonne = 'tonne'
    WPerA = 'WPerA'
    ha = 'ha'
    T = 'T'
    VArh = 'VArh'
    m3Pers = 'm3Pers'
    Vs = 'Vs'
    sPers = 'sPers'
    APerA = 'APerA'
    A2s = 'A2s'
    cosPhi = 'cosPhi'
    anglemin = 'anglemin'
    VAh = 'VAh'
    M = 'M'
    molPermol = 'molPermol'
    N = 'N'
    Q = 'Q'
    VPerm = 'VPerm'

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


class Currency(Enum):
    HTG = 'HTG'
    ALL = 'ALL'
    VND = 'VND'
    MXN = 'MXN'
    MRO = 'MRO'
    BOB = 'BOB'
    MMK = 'MMK'
    SDG = 'SDG'
    BBD = 'BBD'
    LAK = 'LAK'
    RUR = 'RUR'
    SBD = 'SBD'
    GEL = 'GEL'
    CLF = 'CLF'
    GNF = 'GNF'
    CNY = 'CNY'
    STD = 'STD'
    AMD = 'AMD'
    TWD = 'TWD'
    MGA = 'MGA'
    TOP = 'TOP'
    VUV = 'VUV'
    BRL = 'BRL'
    MDL = 'MDL'
    BGN = 'BGN'
    MAD = 'MAD'
    COU = 'COU'
    other = 'other'
    TTD = 'TTD'
    KWD = 'KWD'
    PYG = 'PYG'
    SOS = 'SOS'
    XPF = 'XPF'
    MUR = 'MUR'
    COP = 'COP'
    UZS = 'UZS'
    KYD = 'KYD'
    BAM = 'BAM'
    KMF = 'KMF'
    SHP = 'SHP'
    NAD = 'NAD'
    CUP = 'CUP'
    MNT = 'MNT'
    EEK = 'EEK'
    CRC = 'CRC'
    AED = 'AED'
    NOK = 'NOK'
    BHD = 'BHD'
    PKR = 'PKR'
    ARS = 'ARS'
    HNL = 'HNL'
    BDT = 'BDT'
    MVR = 'MVR'
    GTQ = 'GTQ'
    LRD = 'LRD'
    IDR = 'IDR'
    NPR = 'NPR'
    JPY = 'JPY'
    PAB = 'PAB'
    SRD = 'SRD'
    RSD = 'RSD'
    HUF = 'HUF'
    SLL = 'SLL'
    PHP = 'PHP'
    TZS = 'TZS'
    INR = 'INR'
    LBP = 'LBP'
    UYU = 'UYU'
    UAH = 'UAH'
    DKK = 'DKK'
    GMD = 'GMD'
    BSD = 'BSD'
    XCD = 'XCD'
    KHR = 'KHR'
    TMT = 'TMT'
    LKR = 'LKR'
    LVL = 'LVL'
    UGX = 'UGX'
    CLP = 'CLP'
    EUR = 'EUR'
    CAD = 'CAD'
    RWF = 'RWF'
    AUD = 'AUD'
    XOF = 'XOF'
    BOV = 'BOV'
    JOD = 'JOD'
    ISK = 'ISK'
    TRY = 'TRY'
    TND = 'TND'
    QAR = 'QAR'
    ERN = 'ERN'
    GBP = 'GBP'
    SGD = 'SGD'
    ZAR = 'ZAR'
    ZWL = 'ZWL'
    AWG = 'AWG'
    SAR = 'SAR'
    ANG = 'ANG'
    MKD = 'MKD'
    BND = 'BND'
    BIF = 'BIF'
    AFN = 'AFN'
    LTL = 'LTL'
    GYD = 'GYD'
    HRK = 'HRK'
    LSL = 'LSL'
    SCR = 'SCR'
    EGP = 'EGP'
    GHS = 'GHS'
    PLN = 'PLN'
    HKD = 'HKD'
    FKP = 'FKP'
    NGN = 'NGN'
    XAF = 'XAF'
    KRW = 'KRW'
    NZD = 'NZD'
    CUC = 'CUC'
    NIO = 'NIO'
    MOP = 'MOP'
    MYR = 'MYR'
    BTN = 'BTN'
    MZN = 'MZN'
    IRR = 'IRR'
    IQD = 'IQD'
    WST = 'WST'
    ZMK = 'ZMK'
    USD = 'USD'
    ETB = 'ETB'
    KES = 'KES'
    DOP = 'DOP'
    DZD = 'DZD'
    JMD = 'JMD'
    CHF = 'CHF'
    VEF = 'VEF'
    GIP = 'GIP'
    BMD = 'BMD'
    MWK = 'MWK'
    PGK = 'PGK'
    SEK = 'SEK'
    PEN = 'PEN'
    CDF = 'CDF'
    BWP = 'BWP'
    TJS = 'TJS'
    CZK = 'CZK'
    RON = 'RON'
    SZL = 'SZL'
    YER = 'YER'
    BYR = 'BYR'
    KGS = 'KGS'
    OMR = 'OMR'
    KZT = 'KZT'
    ILS = 'ILS'
    FJD = 'FJD'
    CVE = 'CVE'
    THB = 'THB'
    AOA = 'AOA'
    DJF = 'DJF'
    SYP = 'SYP'
    AZN = 'AZN'
    KPW = 'KPW'
    BZD = 'BZD'
    LYD = 'LYD'
    RUB = 'RUB'

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


class UnitMultiplier(Enum):
    Z = 'Z'
    c = 'c'
    none = 'none'
    G = 'G'
    h = 'h'
    P = 'P'
    d = 'd'
    E = 'E'
    da = 'da'
    m = 'm'
    k = 'k'
    z = 'z'
    T = 'T'
    a = 'a'
    y = 'y'
    p = 'p'
    n = 'n'
    M = 'M'
    Y = 'Y'
    micro = 'micro'
    f = 'f'

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


class LimitTypeKind(Enum):
    patl = 'patl'
    tc = 'tc'
    tct = 'tct'
    highVoltage = 'highVoltage'
    tatl = 'tatl'
    lowVoltage = 'lowVoltage'
    patlt = 'patlt'

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


class WindingConnection(Enum):
    Z = 'Z'
    A = 'A'
    Yn = 'Yn'
    Y = 'Y'
    Zn = 'Zn'
    D = 'D'
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


class FuelType(Enum):
    oil = 'oil'
    brownCoalLignite = 'brownCoalLignite'
    peat = 'peat'
    hardCoal = 'hardCoal'
    coalDerivedGas = 'coalDerivedGas'
    oilShale = 'oilShale'
    gas = 'gas'
    other = 'other'
    coal = 'coal'
    lignite = 'lignite'

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


class RegulatingControlModeKind(Enum):
    admittance = 'admittance'
    activePower = 'activePower'
    temperature = 'temperature'
    timeScheduled = 'timeScheduled'
    reactivePower = 'reactivePower'
    powerFactor = 'powerFactor'
    currentFlow = 'currentFlow'
    voltage = 'voltage'

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


class DCPolarityKind(Enum):
    middle = 'middle'
    negative = 'negative'
    positive = 'positive'

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


class SynchronousMachineKind(Enum):
    generatorOrCondenser = 'generatorOrCondenser'
    generator = 'generator'
    generatorOrMotor = 'generatorOrMotor'
    motor = 'motor'
    motorOrCondenser = 'motorOrCondenser'
    generatorOrCondenserOrMotor = 'generatorOrCondenserOrMotor'
    condenser = 'condenser'

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


class OperationalLimitDirectionKind(Enum):
    absoluteValue = 'absoluteValue'
    low = 'low'
    high = 'high'

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
    manual = 'manual'
    fixed = 'fixed'
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


class SVCControlMode(Enum):
    voltage = 'voltage'
    reactivePower = 'reactivePower'

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


class ControlAreaTypeKind(Enum):
    AGC = 'AGC'
    Interchange = 'Interchange'
    Forecast = 'Forecast'

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


class HydroEnergyConversionKind(Enum):
    pumpAndGenerator = 'pumpAndGenerator'
    generator = 'generator'

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


class WindGenUnitKind(Enum):
    onshore = 'onshore'
    offshore = 'offshore'

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


class ShortCircuitRotorKind(Enum):
    turboSeries1 = 'turboSeries1'
    salientPole1 = 'salientPole1'
    turboSeries2 = 'turboSeries2'
    salientPole2 = 'salientPole2'

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


class HydroPlantStorageKind(Enum):
    storage = 'storage'
    pumpedStorage = 'pumpedStorage'
    runOfRiver = 'runOfRiver'

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


class DCConverterOperatingModeKind(Enum):
    bipolar = 'bipolar'
    monopolarGroundReturn = 'monopolarGroundReturn'
    monopolarMetallicReturn = 'monopolarMetallicReturn'

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


class Source(Enum):
    PROCESS = 'PROCESS'
    SUBSTITUTED = 'SUBSTITUTED'
    DEFAULTED = 'DEFAULTED'

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
    INVALID = 'INVALID'
    QUESTIONABLE = 'QUESTIONABLE'
    GOOD = 'GOOD'

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


class DroopSignalFeedbackKind(Enum):
    governorOutput = 'governorOutput'
    electricalPower = 'electricalPower'
    none = 'none'
    fuelValveStroke = 'fuelValveStroke'

    def __str__(self):
        return 'DroopSignalFeedbackKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return DroopSignalFeedbackKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class GenericNonLinearLoadModelKind(Enum):
    loadAdaptive = 'loadAdaptive'
    exponentialRecovery = 'exponentialRecovery'

    def __str__(self):
        return 'GenericNonLinearLoadModelKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return GenericNonLinearLoadModelKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class FrancisGovernorControlKind(Enum):
    electromechanicalElectrohydraulic = 'electromechanicalElectrohydraulic'
    mechanicHydrolicTachoAccelerator = 'mechanicHydrolicTachoAccelerator'
    mechanicHydraulicTransientFeedback = 'mechanicHydraulicTransientFeedback'

    def __str__(self):
        return 'FrancisGovernorControlKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return FrancisGovernorControlKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class IfdBaseKind(Enum):
    iffl = 'iffl'
    ifnl = 'ifnl'
    ifag = 'ifag'
    other = 'other'

    def __str__(self):
        return 'IfdBaseKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return IfdBaseKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class InputSignalKind(Enum):
    fieldCurrent = 'fieldCurrent'
    busVoltage = 'busVoltage'
    branchCurrent = 'branchCurrent'
    busFrequencyDeviation = 'busFrequencyDeviation'
    generatorMechanicalPower = 'generatorMechanicalPower'
    busFrequency = 'busFrequency'
    busVoltageDerivative = 'busVoltageDerivative'
    generatorAcceleratingPower = 'generatorAcceleratingPower'
    rotorSpeed = 'rotorSpeed'
    generatorElectricalPower = 'generatorElectricalPower'
    rotorAngularFrequencyDeviation = 'rotorAngularFrequencyDeviation'

    def __str__(self):
        return 'InputSignalKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return InputSignalKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class ExcST6BOELselectorKind(Enum):
    afterUEL = 'afterUEL'
    noOELinput = 'noOELinput'
    beforeUEL = 'beforeUEL'

    def __str__(self):
        return 'ExcST6BOELselectorKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return ExcST6BOELselectorKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class ExcST7BUELselectorKind(Enum):
    outputHVgate = 'outputHVgate'
    noUELinput = 'noUELinput'
    inputHVgate = 'inputHVgate'
    addVref = 'addVref'

    def __str__(self):
        return 'ExcST7BUELselectorKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return ExcST7BUELselectorKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class SynchronousMachineModelKind(Enum):
    subtransientSimplified = 'subtransientSimplified'
    subtransient = 'subtransient'
    subtransientTypeF = 'subtransientTypeF'
    subtransientTypeJ = 'subtransientTypeJ'
    subtransientSimplifiedDirectAxis = 'subtransientSimplifiedDirectAxis'

    def __str__(self):
        return 'SynchronousMachineModelKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return SynchronousMachineModelKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class ExcREXSFeedbackSignalKind(Enum):
    fieldCurrent = 'fieldCurrent'
    outputVoltage = 'outputVoltage'
    fieldVoltage = 'fieldVoltage'

    def __str__(self):
        return 'ExcREXSFeedbackSignalKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return ExcREXSFeedbackSignalKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class StaticLoadModelKind(Enum):
    zIP1 = 'zIP1'
    constantZ = 'constantZ'
    exponential = 'exponential'
    zIP2 = 'zIP2'

    def __str__(self):
        return 'StaticLoadModelKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return StaticLoadModelKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class ExcIEEEST1AUELselectorKind(Enum):
    inputHVgateVoltageOutput = 'inputHVgateVoltageOutput'
    inputAddedToErrorSignal = 'inputAddedToErrorSignal'
    ignoreUELsignal = 'ignoreUELsignal'
    inputHVgateErrorSignal = 'inputHVgateErrorSignal'

    def __str__(self):
        return 'ExcIEEEST1AUELselectorKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return ExcIEEEST1AUELselectorKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class RemoteSignalKind(Enum):
    remoteBusVoltageAmplitudeDerivative = 'remoteBusVoltageAmplitudeDerivative'
    remoteBusVoltageFrequencyDeviation = 'remoteBusVoltageFrequencyDeviation'
    remotePuBusVoltageDerivative = 'remotePuBusVoltageDerivative'
    remoteBusFrequencyDeviation = 'remoteBusFrequencyDeviation'
    remoteBranchCurrentAmplitude = 'remoteBranchCurrentAmplitude'
    remoteBusVoltageFrequency = 'remoteBusVoltageFrequency'
    remoteBusVoltageAmplitude = 'remoteBusVoltageAmplitude'
    remoteBusVoltage = 'remoteBusVoltage'
    remoteBusFrequency = 'remoteBusFrequency'

    def __str__(self):
        return 'RemoteSignalKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return RemoteSignalKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class WindQcontrolModesKind(Enum):
    openLoopReactivePower = 'openLoopReactivePower'
    powerFactor = 'powerFactor'
    voltage = 'voltage'
    reactivePower = 'reactivePower'

    def __str__(self):
        return 'WindQcontrolModesKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return WindQcontrolModesKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class WindLVRTQcontrolModesKind(Enum):
    mode2 = 'mode2'
    mode1 = 'mode1'
    mode3 = 'mode3'

    def __str__(self):
        return 'WindLVRTQcontrolModesKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return WindLVRTQcontrolModesKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class WindLookupTableFunctionKind(Enum):
    fpslip = 'fpslip'
    pwp = 'pwp'
    fpomega = 'fpomega'
    ipvdl = 'ipvdl'
    tcwdu = 'tcwdu'
    iqmax = 'iqmax'
    iqvdl = 'iqvdl'
    tuover = 'tuover'
    qmaxp = 'qmaxp'
    qmaxu = 'qmaxu'
    tfunder = 'tfunder'
    omegap = 'omegap'
    prr = 'prr'
    ipmax = 'ipmax'
    qminp = 'qminp'
    tfover = 'tfover'
    qwp = 'qwp'
    tduwt = 'tduwt'
    fdpf = 'fdpf'
    tuunder = 'tuunder'
    qminu = 'qminu'

    def __str__(self):
        return 'WindLookupTableFunctionKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return WindLookupTableFunctionKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class ExcST7BOELselectorKind(Enum):
    inputLVgate = 'inputLVgate'
    noOELinput = 'noOELinput'
    outputLVgate = 'outputLVgate'
    addVref = 'addVref'

    def __str__(self):
        return 'ExcST7BOELselectorKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return ExcST7BOELselectorKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class RotorKind(Enum):
    salientPole = 'salientPole'
    roundRotor = 'roundRotor'

    def __str__(self):
        return 'RotorKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return RotorKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class OrientationKind(Enum):
    negative = 'negative'
    positive = 'positive'

    def __str__(self):
        return 'OrientationKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return OrientationKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class VsPpccControlKind(Enum):
    pPccAndUdcDroopWithCompensation = 'pPccAndUdcDroopWithCompensation'
    pPccAndUdcDroop = 'pPccAndUdcDroop'
    phasePcc = 'phasePcc'
    pPcc = 'pPcc'
    pPccAndUdcDroopPilot = 'pPccAndUdcDroopPilot'
    udc = 'udc'

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


class CsPpccControlKind(Enum):
    activePower = 'activePower'
    dcCurrent = 'dcCurrent'
    dcVoltage = 'dcVoltage'

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
    motor = 'motor'
    generator = 'generator'
    condenser = 'condenser'

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


class VsQpccControlKind(Enum):
    voltagePcc = 'voltagePcc'
    pulseWidthModulation = 'pulseWidthModulation'
    reactivePcc = 'reactivePcc'
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


class CsOperatingModeKind(Enum):
    rectifier = 'rectifier'
    inverter = 'inverter'

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


class LimitKind(Enum):
    patl = 'patl'
    tc = 'tc'
    tct = 'tct'
    highVoltage = 'highVoltage'
    warningVoltage = 'warningVoltage'
    tatl = 'tatl'
    stability = 'stability'
    lowVoltage = 'lowVoltage'
    operationalVoltageLimit = 'operationalVoltageLimit'
    patlt = 'patlt'
    alarmVoltage = 'alarmVoltage'

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


class HydroTurbineKind(Enum):
    pelton = 'pelton'
    kaplan = 'kaplan'
    francis = 'francis'

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


class BatteryStateKind(Enum):
    full = 'full'
    empty = 'empty'
    charging = 'charging'
    discharging = 'discharging'
    waiting = 'waiting'

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


class WindQcontrolModeKind(Enum):
    openLoopReactivePower = 'openLoopReactivePower'
    openLooppowerFactor = 'openLooppowerFactor'
    reactivePower = 'reactivePower'
    powerFactor = 'powerFactor'
    voltage = 'voltage'

    def __str__(self):
        return 'WindQcontrolModeKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return WindQcontrolModeKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class WindUVRTQcontrolModeKind(Enum):
    mode2 = 'mode2'
    mode1 = 'mode1'
    mode0 = 'mode0'

    def __str__(self):
        return 'WindUVRTQcontrolModeKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return WindUVRTQcontrolModeKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class GovHydro4ModelKind(Enum):
    francisPelton = 'francisPelton'
    simple = 'simple'
    kaplan = 'kaplan'

    def __str__(self):
        return 'GovHydro4ModelKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return GovHydro4ModelKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class WindPlantQcontrolModeKind(Enum):
    uqStatic = 'uqStatic'
    powerFactor = 'powerFactor'
    voltageControl = 'voltageControl'
    reactivePower = 'reactivePower'

    def __str__(self):
        return 'WindPlantQcontrolModeKind.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return WindPlantQcontrolModeKind[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))
