# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
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
        if version == 34:
            if len(data[0]) == 11:
                (self.I, self.J, self.CKT, self.NAME, self.STYPE, self.STATUS, self.NSTATUS,
                 self.X, self.RATE1, self.RATE2, self.RATE3,) = data[0]
            elif len(data[0]) == 21:
                (self.I, self.J, self.CKT, self.X, self.RATE1, self.RATE2, self.RATE3, self.RATE4, self.RATE5,
                 self.RATE6, self.RATE7, self.RATE8, self.RATE9, self.RATE10, self.RATE11, self.RATE12,
                 self.STATUS, self.NSTATUS, self.METERED, self.STYPE, self.NAME) = data[0]
            else:
                logger.add_warning('Switch line length could not be identified :/', value=",".join(data[0]))

            self.NAME = self.NAME.replace("'", "").strip()
        elif version == 35:
            if len(data[0]) == 21:
                (self.I, self.J, self.CKT, self.X, self.RATE1, self.RATE2, self.RATE3, self.RATE4, self.RATE5,
                 self.RATE6, self.RATE7, self.RATE8, self.RATE9, self.RATE10, self.RATE11, self.RATE12,
                 self.STATUS, self.NSTATUS, self.METERED, self.STYPE, self.NAME) = data[0]
            else:
                logger.add_warning('Switch line length could not be identified :/', value=",".join(data[0]))

            self.NAME = self.NAME.replace("'", "").strip()
        else:
            logger.add_warning('System switching not defined for version', str(version))

    def get_raw_line(self, version):

        if version >= 35:
            return self.format_raw_line(["I", "J", "CKT", "X", "RATE1", "RATE2", "RATE3",
                                         "RATE4", "RATE5", "RATE6", "RATE7", "RATE8", "RATE9",
                                         "RATE10", "RATE11", "RATE12", "STAT", "NSTAT", "MET",
                                         "STYPE", "NAME"])
        else:
            raise Exception('System switching not defined for version', str(version))

    def get_id(self) -> str:
        """
        Get the element PSSE ID
        :return: 
        """
        return "{0}_{1}_{2}".format(self.I, self.J, self.CKT)
