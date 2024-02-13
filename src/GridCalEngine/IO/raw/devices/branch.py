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
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol, Unit
from GridCalEngine.IO.raw.devices.psse_object import RawObject
from GridCalEngine.basic_structures import Logger


class RawBranch(RawObject):

    def __init__(self):
        RawObject.__init__(self, "Branch")

        self.I: int = 0
        self.J: int = 0
        self.CKT: str = '1'
        self.R = 0
        self.X = 0
        self.B = 0

        self.NAME = ''

        # rates for newer versions (34 and above)
        self.RATE1 = 0
        self.RATE2 = 0
        self.RATE3 = 0
        self.RATE4 = 0
        self.RATE5 = 0
        self.RATE6 = 0
        self.RATE7 = 0
        self.RATE8 = 0
        self.RATE9 = 0
        self.RATE10 = 0
        self.RATE11 = 0
        self.RATE12 = 0

        self.GI = 0
        self.BI = 0
        self.GJ = 0
        self.BJ = 0
        self.ST = 1
        self.MET = 1
        self.LEN = 0.0

        self.O1 = 0
        self.F1 = 0.0
        self.O2 = 0
        self.F2 = 0.0
        self.O3 = 0
        self.F3 = 0.0
        self.O4 = 0
        self.F4 = 0.0

        self.register_property(property_name="I",
                               rawx_key="ibus",
                               class_type=int,
                               description="Branch from bus number",
                               min_value=1,
                               max_value=999997)

        self.register_property(property_name="J",
                               rawx_key="jbus",
                               class_type=int,
                               description="Branch to bus number",
                               min_value=1,
                               max_value=999997)

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
                                   max_value=9999)
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

        var = [self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4]
        if version >= 34:

            """
            I,     J,'CKT',     R,          X,         B, 'N A M E'                 ,   
            RATE1,   RATE2,   RATE3,   RATE4,   RATE5,   RATE6,   RATE7,   RATE8,   RATE9,  RATE10,  RATE11,  RATE12,    
            GI,       BI,       GJ,       BJ,STAT,MET,  LEN,  O1,  F1,    O2,  F2,    O3,  F3,    O4,  F4
            """

            return self.format_raw_line([self.I, self.J, self.CKT, self.R, self.X, self.B, self.NAME,
                                         self.RATE1, self.RATE2, self.RATE3, self.RATE4, self.RATE5, self.RATE6,
                                         self.RATE7, self.RATE8, self.RATE9, self.RATE10, self.RATE11, self.RATE12,
                                         self.GI, self.BI, self.GJ, self.BJ, self.ST, self.MET, self.LEN] + var)

        elif version in [32, 33]:

            '''
            I,J,CKT,R,X,B,RATE1,RATE2,RATE3,GI,BI,GJ,BJ,ST,MET,LEN,O1,F1,...,O4,F4
            '''

            return self.format_raw_line([self.I, self.J, self.CKT, self.R, self.X, self.B,
                                         self.RATE1, self.RATE2, self.RATE3, self.GI, self.BI, self.GJ, self.BJ,
                                         self.ST, self.MET, self.LEN] + var)

        elif version in [29, 30]:
            """
            v29, v30
            I,J,CKT,R,X,B,RATE1,RATE2,RATE3,GI,BI,GJ,BJ,ST,LEN,01,F1,...,04,F4
            """

            return self.format_raw_line([self.I, self.J, self.CKT, self.R, self.X, self.B,
                                         self.RATE1, self.RATE2, self.RATE3, self.GI, self.BI, self.GJ, self.BJ,
                                         self.ST, self.LEN] + var)

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
