# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol, Unit
from GridCalEngine.IO.raw.devices.psse_object import RawObject
from GridCalEngine.basic_structures import Logger
import GridCalEngine.Devices as dev


class RawGneDevice(RawObject):

    def __init__(self):
        RawObject.__init__(self, "GNE")

    @staticmethod
    def parse(data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if version >= 29:

            """
            @!  'NAME',        'MODEL',     NTERM,BUS1...BUSNTERM,NREAL,NINTG,NCHAR
            @!ST,OWNER,NMETR
            @! REAL1...REAL(MIN(10,NREAL))
            @! INTG1...INTG(MIN(10,NINTG))
            @! CHAR1...CHAR(MIN(10,NCHAR))
            
            """

            pass
        else:
            logger.add_warning('GNE not defined for version', str(version))

    def get_raw_line(self, version):

        if version >= 29:
            return self.format_raw_line([])
        else:
            raise Exception('GNE not defined for version', str(version))


