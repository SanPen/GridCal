# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol, Unit
from GridCalEngine.IO.raw.devices.psse_object import RawObject
from GridCalEngine.basic_structures import Logger


class RawBranch(RawObject):

    def __init__(self) -> None:
        RawObject.__init__(self, "Branch")

        self._I: int = 0
        self._J: int = 0
        self._CKT: str = '1'
        self._R: float = 0.0
        self._X: float = 0.0
        self._B: float = 0.0

        self._NAME: str = ''

        # rates for newer versions (34 and above)
        self._RATE1: float = 0.0
        self._RATE2: float = 0.0
        self._RATE3: float = 0.0
        self._RATE4: float = 0.0
        self._RATE5: float = 0.0
        self._RATE6: float = 0.0
        self._RATE7: float = 0.0
        self._RATE8: float = 0.0
        self._RATE9: float = 0.0
        self._RATE10: float = 0.0
        self._RATE11: float = 0.0
        self._RATE12: float = 0.0

        self._GI: float = 0.0
        self._BI: float = 0.0
        self._GJ: float = 0.0
        self._BJ: float = 0.0
        self._ST: int = 1
        self._MET: int = 1
        self._LEN: float = 0.0

        self._O1: int = 1
        self._F1: float = 1.0
        self._O2: int = 0
        self._F2: float = 0.0
        self._O3: int = 0
        self._F3: float = 0.0
        self._O4: int = 0
        self._F4: float = 0.0

        self.register_property(property_name="I",
                               rawx_key="ibus",
                               class_type=int,
                               description="Branch from bus number",
                               min_value=1,
                               max_value=999997,
                               max_chars=6)

        self.register_property(property_name="J",
                               rawx_key="jbus",
                               class_type=int,
                               description="Branch to bus number",
                               min_value=1,
                               max_value=999997,
                               max_chars=6)

        self.register_property(property_name="CKT",
                               rawx_key="ckt",
                               class_type=str,
                               description="Owner number",
                               max_chars=2)

        self.register_property(property_name="R",
                               rawx_key="rpu",
                               class_type=float,
                               description="Branch resistance",
                               unit=Unit.get_pu())

        self.register_property(property_name="X",
                               rawx_key="xpu",
                               class_type=float,
                               description="Branch reactance",
                               unit=Unit.get_pu())

        self.register_property(property_name="B",
                               rawx_key="bpu",
                               class_type=float,
                               description="Branch shunt susceptance",
                               unit=Unit.get_pu())

        self.register_property(property_name="NAME",
                               rawx_key="name",
                               class_type=str,
                               description="Branch name",
                               max_chars=40)

        self.register_property(property_name="GI",
                               rawx_key="gi",
                               class_type=float,
                               description="Branch shunt conductance at the from side",
                               unit=Unit.get_pu())

        self.register_property(property_name="BI",
                               rawx_key="bi",
                               class_type=float,
                               description="Branch shunt susceptance at the from side",
                               unit=Unit.get_pu())

        self.register_property(property_name="GJ",
                               rawx_key="gj",
                               class_type=float,
                               description="Branch shunt condictance at the to side",
                               unit=Unit.get_pu())

        self.register_property(property_name="BJ",
                               rawx_key="bj",
                               class_type=float,
                               description="Branch shunt susceptance at the to side",
                               unit=Unit.get_pu())

        self.register_property(property_name="ST",
                               rawx_key="stat",
                               class_type=int,
                               description="Branch status",
                               min_value=0,
                               max_value=1)

        self.register_property(property_name="MET",
                               rawx_key="met",
                               class_type=int,
                               description="Metered end flag, <=1: Bus from, >=2: bus to",
                               min_value=0,
                               max_value=999)

        self.register_property(property_name="LEN",
                               rawx_key="len",
                               class_type=float,
                               description="Line length",
                               unit=Unit.get_km())

        for i in range(4):
            self.register_property(property_name="O{}".format(i + 1),
                                   rawx_key="o{}".format(i + 1),
                                   class_type=int,
                                   description="Owner number",
                                   min_value=1,
                                   max_value=9999,
                                   max_chars=4)
        for i in range(4):
            self.register_property(property_name="F{}".format(i + 1),
                                   rawx_key="f{}".format(i + 1),
                                   class_type=float,
                                   description="Ownership fraction",
                                   min_value=0.0,
                                   max_value=1.0)

        for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]:
            self.register_property(property_name="RATE{}".format(i),
                                   rawx_key="rate{}".format(i),
                                   class_type=float,
                                   description="Branch rating power",
                                   unit=Unit(UnitMultiplier.M, UnitSymbol.VA))

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        var = [self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4]

        if version >= 35:

            """
            I,     J,'CKT',     R,          X,         B, 'N A M E'                 ,   
            RATE1,   RATE2,   RATE3,   RATE4,   RATE5,   RATE6,   RATE7,   RATE8,   RATE9,  RATE10,  RATE11,  RATE12,    
            GI,       BI,       GJ,       BJ,STAT,MET,  LEN,  O1,  F1,    O2,  F2,    O3,  F3,    O4,  F4
            """

            """
            I,     J,'CKT',      R,           X,       B,                   'N A M E'                 ,  
            RATE1,  RATE2,  RATE3,  RATE4,  RATE5,  RATE6,  RATE7,  RATE8,  RATE9, RATE10, RATE11, RATE12,   
            GI,      BI,      GJ,      BJ,STAT,MET, LEN,  O1,  F1,    O2,  F2,    O3,  F3,    O4,  F4
            """

            if len(data[0]) >= 26:
                (self.I, self.J, self.CKT, self.R, self.X, self.B, self.NAME,
                 self.RATE1, self.RATE2, self.RATE3, self.RATE4, self.RATE5, self.RATE6,
                 self.RATE7, self.RATE8, self.RATE9, self.RATE10, self.RATE11, self.RATE12,
                 self.GI, self.BI, self.GJ, self.BJ, self.ST, self.MET, self.LEN, *var) = data[0]
            else:
                (self.I, self.J, self.CKT, self.R, self.X, self.B, self.NAME,
                 self.RATE1, self.RATE2, self.RATE3,
                 self.GI, self.BI, self.GJ, self.BJ, self.ST, self.MET, self.LEN, *var) = data[0]

        elif version == 34:

            """
            I,     J,'CKT',     R,          X,         B, 'N A M E'                 ,   
            RATE1,   RATE2,   RATE3,   RATE4,   RATE5,   RATE6,   RATE7,   RATE8,   RATE9,  RATE10,  RATE11,  RATE12,    
            GI,       BI,       GJ,       BJ,STAT,MET,  LEN,  O1,  F1,    O2,  F2,    O3,  F3,    O4,  F4
            """

            self.I, self.J, self.CKT, self.R, self.X, self.B, self.NAME, \
                self.RATE1, self.RATE2, self.RATE3, self.RATE4, self.RATE5, self.RATE6, \
                self.RATE7, self.RATE8, self.RATE9, self.RATE10, self.RATE11, self.RATE12, \
                self.GI, self.BI, self.GJ, self.BJ, self.ST, self.MET, self.LEN, *var = data[0]

        elif version in [32, 33]:

            '''
            I,J,CKT,R,X,B,RATE1,RATE2,RATE3,GI,BI,GJ,BJ,ST,MET,LEN,O1,F1,...,O4,F4
            '''

            self.I, self.J, self.CKT, self.R, self.X, self.B, self.RATE1, self.RATE2, self.RATE3, \
                self.GI, self.BI, self.GJ, self.BJ, self.ST, self.MET, self.LEN, *var = data[0]

        elif version in [29, 30]:
            """
            v29, v30
            I,J,CKT,R,X,B,RATE1,RATE2,RATE3,GI,BI,GJ,BJ,ST,LEN,01,F1,...,04,F4
            """

            self.I, self.J, self.CKT, self.R, self.X, self.B, self.RATE1, self.RATE2, self.RATE3, \
                self.GI, self.BI, self.GJ, self.BJ, self.ST, self.LEN, *var = data[0]

        else:

            logger.add_warning('Branch not implemented for version', str(version))

    def get_raw_line(self, version):

        var = ["O1", "F1", "O2", "F2", "O3", "F3", "O4", "F4"]

        if version >= 34:

            """
            I,     J,'CKT',     R,          X,         B, 'N A M E'                 ,   
            RATE1,   RATE2,   RATE3,   RATE4,   RATE5,   RATE6,   RATE7,   RATE8,   RATE9,  RATE10,  RATE11,  RATE12,    
            GI,       BI,       GJ,       BJ,STAT,MET,  LEN,  O1,  F1,    O2,  F2,    O3,  F3,    O4,  F4
            """

            return self.format_raw_line(["I", "J", "CKT", "R", "X", "B", "NAME",
                                         "RATE1", "RATE2", "RATE3", "RATE4", "RATE5", "RATE6",
                                         "RATE7", "RATE8", "RATE9", "RATE10", "RATE11", "RATE12",
                                         "GI", "BI", "GJ", "BJ", "ST", "MET", "LEN"] + var)

        elif version in [32, 33]:

            '''
            I,J,CKT,R,X,B,RATE1,RATE2,RATE3,GI,BI,GJ,BJ,ST,MET,LEN,O1,F1,...,O4,F4
            '''

            return self.format_raw_line(["I", "J", "CKT", "R", "X", "B",
                                         "RATE1", "RATE2", "RATE3", "GI", "BI", "GJ", "BJ",
                                         "ST", "MET", "LEN"] + var)

        elif version in [29, 30]:
            """
            v29, v30
            I,J,CKT,R,X,B,RATE1,RATE2,RATE3,GI,BI,GJ,BJ,ST,LEN,01,F1,...,04,F4
            """

            return self.format_raw_line(["I", "J", "CKT", "R", "X", "B",
                                         "RATE1", "RATE2", "RATE3", "GI", "BI", "GJ", "BJ",
                                         "ST", "LEN"] + var)

        else:

            raise Exception('Branch not implemented for version', str(version))

    def get_id(self):
        """
        Get the element PSSE ID
        :return:
        """
        return "{0}_{1}_{2}".format(self.I, self.J, self.CKT)

    def get_seed(self):
        return "_BR_{}".format(self.get_id())

    @property
    def I(self):
        return self._I

    @I.setter
    def I(self, value):
        self._I = value

    @property
    def J(self):
        return self._J

    @J.setter
    def J(self, value):
        self._J = value

    @property
    def CKT(self):
        return self._CKT

    @CKT.setter
    def CKT(self, value):
        self._CKT = value

    @property
    def R(self):
        return self._R

    @R.setter
    def R(self, value):
        self._R = value

    @property
    def X(self):
        return self._X

    @X.setter
    def X(self, value):
        self._X = value

    @property
    def B(self):
        return self._B

    @B.setter
    def B(self, value):
        self._B = value

    @property
    def NAME(self):
        return self._NAME

    @NAME.setter
    def NAME(self, value):
        self._NAME = value

    # Individual property methods for each RATE attribute
    @property
    def RATE1(self):
        return self._RATE1

    @RATE1.setter
    def RATE1(self, value):
        self._RATE1 = value

    @property
    def RATE2(self):
        return self._RATE2

    @RATE2.setter
    def RATE2(self, value):
        self._RATE2 = value

    @property
    def RATE3(self):
        return self._RATE3

    @RATE3.setter
    def RATE3(self, value):
        self._RATE3 = value

    @property
    def RATE4(self):
        return self._RATE4

    @RATE4.setter
    def RATE4(self, value):
        self._RATE4 = value

    @property
    def RATE5(self):
        return self._RATE5

    @RATE5.setter
    def RATE5(self, value):
        self._RATE5 = value

    @property
    def RATE6(self):
        return self._RATE6

    @RATE6.setter
    def RATE6(self, value):
        self._RATE6 = value

    @property
    def RATE7(self):
        return self._RATE7

    @RATE7.setter
    def RATE7(self, value):
        self._RATE7 = value

    @property
    def RATE8(self):
        return self._RATE8

    @RATE8.setter
    def RATE8(self, value):
        self._RATE8 = value

    @property
    def RATE9(self):
        return self._RATE9

    @RATE9.setter
    def RATE9(self, value):
        self._RATE9 = value

    @property
    def RATE10(self):
        return self._RATE10

    @RATE10.setter
    def RATE10(self, value):
        self._RATE10 = value

    @property
    def RATE11(self):
        return self._RATE11

    @RATE11.setter
    def RATE11(self, value):
        self._RATE11 = value

    @property
    def RATE12(self):
        return self._RATE12

    @RATE12.setter
    def RATE12(self, value):
        self._RATE12 = value

    @property
    def GI(self):
        return self._GI

    @GI.setter
    def GI(self, value):
        self._GI = value

    @property
    def BI(self):
        return self._BI

    @BI.setter
    def BI(self, value):
        self._BI = value

    @property
    def GJ(self):
        return self._GJ

    @GJ.setter
    def GJ(self, value):
        self._GJ = value

    @property
    def BJ(self):
        return self._BJ

    @BJ.setter
    def BJ(self, value):
        self._BJ = value

    @property
    def ST(self):
        return self._ST

    @ST.setter
    def ST(self, value):
        self._ST = value

    @property
    def MET(self):
        return self._MET

    @MET.setter
    def MET(self, value):
        self._MET = value

    @property
    def LEN(self):
        return self._LEN

    @LEN.setter
    def LEN(self, value):
        self._LEN = value

    @property
    def O1(self):
        return self._O1

    @O1.setter
    def O1(self, value):
        self._O1 = value

    @property
    def F1(self):
        return self._F1

    @F1.setter
    def F1(self, value):
        self._F1 = value

    @property
    def O2(self):
        return self._O2

    @O2.setter
    def O2(self, value):
        self._O2 = value

    @property
    def F2(self):
        return self._F2

    @F2.setter
    def F2(self, value):
        self._F2 = value

    @property
    def O3(self):
        return self._O3

    @O3.setter
    def O3(self, value):
        self._O3 = value

    @property
    def F3(self):
        return self._F3

    @F3.setter
    def F3(self, value):
        self._F3 = value

    @property
    def O4(self):
        return self._O4

    @O4.setter
    def O4(self, value):
        self._O4 = value

    @property
    def F4(self):
        return self._F4

    @F4.setter
    def F4(self, value):
        self._F4 = value
