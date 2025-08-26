# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from GridCalEngine.IO.base.units import Unit
from GridCalEngine.IO.raw.devices.psse_object import RawObject
from GridCalEngine.basic_structures import Logger


class RawInterArea(RawObject):

    def __init__(self):
        RawObject.__init__(self, "Inter area")

        self.I = -1
        self.ARNAME = ''
        self.ISW = 0
        self.PDES = 0
        self.PTOL = 0

        self.register_property(property_name="I",
                               rawx_key='iarea',
                               class_type=int,
                               description="Area number",
                               min_value=1,
                               max_value=9999)

        self.register_property(property_name="ISW",
                               rawx_key='isw',
                               class_type=int,
                               description="Area slack bus number.")

        self.register_property(property_name="PDES",
                               rawx_key='pdes',
                               class_type=float,
                               description="Desired net interchange leaving the area.",
                               unit=Unit.get_mw())

        self.register_property(property_name="PTOL",
                               rawx_key='ptol',
                               class_type=float,
                               description="Interchange tolerance bandwidth.",
                               unit=Unit.get_mw())

        self.register_property(property_name="ARNAME",
                               rawx_key='arname',
                               class_type=str,
                               description="Name.",
                               max_chars=12)

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if version >= 29:
            # I, ISW, PDES, PTOL, 'ARNAME'
            if len(data[0]) == 5:
                self.I, self.ISW, self.PDES, self.PTOL, self.ARNAME = data[0]

            elif len(data[0]) == 4:
                self.I, self.ISW, self.ARNAME, self.PDES = data[0]

            else:
                logger.add_warning(f'Unrecognized number of inter-area arguments {len(data[0])}', str(version))
                self.try_parse(values=data[0])

            self.ARNAME = self.ARNAME.replace("'", "").strip()
        else:
            logger.add_warning('Inter-Areas not defined for version', str(version))

    def get_raw_line(self, version):

        if version >= 29:
            return self.format_raw_line(["I", "ISW", "PDES", "PTOL", "ARNAME"])
        else:
            raise Exception('Inter-Areas not defined for version', str(version))

    def get_id(self) -> str:
        return str(self.I)

