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
from GridCalEngine.IO.base.units import Unit
from GridCalEngine.IO.raw.devices.psse_object import RawObject
from GridCalEngine.basic_structures import Logger


class RawSystemSwitchingDevice(RawObject):

    def __init__(self):
        RawObject.__init__(self, "System switching device")

        self.I = 0
        self.J = 0
        self.CKT = ""
        self.X = 0.0
        self.RATE1 = 0.0
        self.RATE2 = 0.0
        self.RATE3 = 0.0
        self.RATE4 = 0.0
        self.RATE5 = 0.0
        self.RATE6 = 0.0
        self.RATE7 = 0.0
        self.RATE8 = 0.0
        self.RATE9 = 0.0
        self.RATE10 = 0.0
        self.RATE11 = 0.0
        self.RATE12 = 0.0
        self.STATUS = 1
        self.NSTATUS = 1
        self.METERED = 0
        self.STYPE = 1
        self.NAME = ""

        self.register_property(property_name="I",
                               rawx_key='ibus',
                               class_type=int,
                               description="From bus number.",
                               min_value=1,
                               max_value=999997)

        self.register_property(property_name="J",
                               rawx_key='jbus',
                               class_type=int,
                               description="From bus number.",
                               min_value=1,
                               max_value=999997)

        self.register_property(property_name="CKT",
                               rawx_key="ckt",
                               class_type=str,
                               description="Owner number",
                               max_chars=2)

        self.register_property(property_name="X",
                               rawx_key="xpu",
                               class_type=float,
                               description="Branch reactance")

        self.register_property(property_name="STATUS",
                               rawx_key="stat",
                               class_type=int,
                               description="Switch status, 1: closed, 0: open")

        self.register_property(property_name="NSTATUS",
                               rawx_key="nstat",
                               class_type=int,
                               description="Normal service status, 1 for normally open and 0 for normally close")

        self.register_property(property_name="METERED",
                               rawx_key="met",
                               class_type=int,
                               description="Metered end")

        self.register_property(property_name="STYPE",
                               rawx_key="stype",
                               class_type=int,
                               description="Switching device type:\n"
                                           "1 - Generic connector\n"
                                           "2 - Circuit breaker\n"
                                           "3 - Disconnect switch")

        self.register_property(property_name="NAME",
                               rawx_key='name',
                               class_type=str,
                               description="Device name",
                               max_chars=12)

        for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]:
            self.register_property(property_name="RATE{}".format(i),
                                   rawx_key="rate{}".format(i),
                                   class_type=float,
                                   description="Rating power",
                                   unit=Unit.get_mva())

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if version >= 35:
            # I, ISW, PDES, PTOL, 'ARNAME'
            self.I, self.J, self.CKT, self.X, self.RATE1, self.RATE2, self.RATE3, self.RATE4, self.RATE5, \
                self.RATE6, self.RATE7, self.RATE8, self.RATE9, self.RATE10, self.RATE11, self.RATE12, \
                self.STAT, self.NSTAT, self.MET, self.STYPE, self.NAME = data[0]

            self.NAME = self.NAME.replace("'", "").strip()
        else:
            logger.add_warning('Areas not defined for version', str(version))

    def get_raw_line(self, version):

        if version >= 35:
            return self.format_raw_line([self.I, self.J, self.CKT, self.X, self.RATE1, self.RATE2, self.RATE3,
                                         self.RATE4, self.RATE5, self.RATE6, self.RATE7, self.RATE8, self.RATE9,
                                         self.RATE10, self.RATE11, self.RATE12, self.STAT, self.NSTAT, self.MET,
                                         self.STYPE, self.NAME])
        else:
            raise Exception('Areas not defined for version', str(version))

    def get_id(self):
        """
        Get the element PSSE ID
        :return: 
        """        
        return "{0}_{1}_{2}".format(self.I, self.J, self.CKT)
