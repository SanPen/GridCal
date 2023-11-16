
from enum import Enum


class UnitSymbol(Enum):
    """
    Unit symbol
    """

    VA = 'VA'
    W = 'W'
    VAr = 'VAr'
    VAh = 'VAh'
    Wh = 'WH'
    VArh = 'VArh'
    V = 'V'
    ohm = 'ohm'
    A = 'A'
    F = 'F'
    H = 'H'
    degC = 'degC'
    s = 's'
    minutes = 'min'
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
    pu = 'p.u.'  # Not in the CIM standard, but makes sense to exist here
    PerCent = "%"
    Money = "€"
    kVperMVAr = "kV/MVAr"
    t = "t"  # ton
    kg = 'kg'

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
    """
    Unit multiplier
    """

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

    def toNum(self):
        return UnitMultiplier2num(self)


def UnitMultiplier2num(val: UnitMultiplier):
    """
    Convert unit multiplier to the corresponding number
    :param val:
    :return:
    """
    if val == UnitMultiplier.p:
        return 1e-12
    elif val == UnitMultiplier.n:
        return 1e-9
    elif val == UnitMultiplier.micro:
        return 1e-6
    elif val == UnitMultiplier.m:
        return 1e-3
    elif val == UnitMultiplier.c:
        return 1e-2
    elif val == UnitMultiplier.d:
        return 1e-1
    elif val == UnitMultiplier.k:
        return 1e3
    elif val == UnitMultiplier.M:
        return 1e6
    elif val == UnitMultiplier.G:
        return 1e9
    elif val == UnitMultiplier.T:
        return 1e12
    elif val == UnitMultiplier.none:
        return 1.0


class Unit:
    """
    General unit
    """

    def __init__(self,
                 multiplier: UnitMultiplier = UnitMultiplier.none,
                 symbol: UnitSymbol = UnitSymbol.none):

        self.multiplier = multiplier
        self.symbol = symbol

    def has_unit(self) -> bool:
        """
        Has units?
        """
        return self.symbol != UnitSymbol.none

    def get_unit(self) -> str:
        """

        :return:
        """
        if self.multiplier == UnitMultiplier.none and self.symbol == UnitSymbol.none:
            return ""

        elif self.multiplier == UnitMultiplier.none and self.symbol != UnitSymbol.none:
            return self.symbol.value

        elif self.multiplier != UnitMultiplier.none and self.symbol == UnitSymbol.none:
            return self.multiplier.value  # this should be wrong...

        elif self.multiplier != UnitMultiplier.none and self.symbol != UnitSymbol.none:
            return self.multiplier.value + self.symbol.value

        else:
            return ""

    @staticmethod
    def get_kv():
        return Unit(UnitMultiplier.k, UnitSymbol.V)

    @staticmethod
    def get_km():
        return Unit(UnitMultiplier.k, UnitSymbol.m)

    @staticmethod
    def get_pu():
        return Unit(UnitMultiplier.none, UnitSymbol.pu)

    @staticmethod
    def get_ohm():
        return Unit(UnitMultiplier.none, UnitSymbol.ohm)

    @staticmethod
    def get_deg():
        return Unit(UnitMultiplier.none, UnitSymbol.deg)

    @staticmethod
    def get_rad():
        return Unit(UnitMultiplier.none, UnitSymbol.rad)

    @staticmethod
    def get_percent():
        return Unit(UnitMultiplier.none, UnitSymbol.PerCent)

    @staticmethod
    def get_a():
        return Unit(UnitMultiplier.none, UnitSymbol.A)

    @staticmethod
    def get_kw():
        return Unit(UnitMultiplier.k, UnitSymbol.W)

    @staticmethod
    def get_mw():
        return Unit(UnitMultiplier.M, UnitSymbol.W)

    @staticmethod
    def get_mva():
        return Unit(UnitMultiplier.M, UnitSymbol.VA)

    @staticmethod
    def get_mvar():
        return Unit(UnitMultiplier.M, UnitSymbol.VAr)

