# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List
from VeraGridEngine.IO.base.units import Unit
from VeraGridEngine.IO.raw.devices.psse_object import RawObject
from VeraGridEngine.basic_structures import Logger


class RawArea(RawObject):

    def __init__(self):
        RawObject.__init__(self, "Area")

        self.I: int = -1
        self.ISW: int = 0
        self.PDES: float = 0.0
        self.PTOL: float = 0.0
        self.ARNAME: str = ''

        self.register_property(property_name="I",
                               rawx_key='iarea',
                               class_type=int,
                               description="Area number",
                               min_value=1,
                               max_value=9999)

        self.register_property(property_name="ISW",
                               rawx_key='isw',
                               class_type=int,
                               description="Bus number of the area slack bus for area interchange control. ")

        self.register_property(property_name="PDES",
                               rawx_key='pdes',
                               class_type=float,
                               description="Desired net interchange leaving the area (export)",
                               unit=Unit.get_mw())

        self.register_property(property_name="PTOL",
                               rawx_key='ptol',
                               class_type=float,
                               description="Interchange tolerance bandwidth.",
                               unit=Unit.get_mw())

        self.register_property(property_name="ARNAME",
                               rawx_key='arname',
                               class_type=str,
                               description="Area name",
                               max_chars=12)

    def parse(self, data: List[List[str | int | float]], version: int, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        self.I = -1

        self.ARNAME = ''

        if version >= 29:
            if len(data[0]) == 5:
                # I, ISW, PDES, PTOL, 'ARNAME'
                self.I, self.ISW, self.PDES, self.PTOL, self.ARNAME = data[0]
            else:
                logger.add_warning('Undefined number of Area attributes', value=len(data[0]), expected_value=5)
                self.try_parse(values=data[0])

            self.ARNAME = self.ARNAME.replace("'", "").strip()
        else:
            logger.add_warning('Areas not defined for version', str(version))

    def get_raw_line(self, version):

        if version >= 29:
            return self.format_raw_line(["I", "ISW", "PDES", "PTOL", "ARNAME"])
        else:
            raise Exception('Areas not defined for version', str(version))

    def get_id(self) -> str:
        return str(self.I)

    def get_seed(self) -> str:
        return "_CA_{}".format(self.I)
