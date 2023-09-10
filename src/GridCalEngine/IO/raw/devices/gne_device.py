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
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol, Unit
from GridCalEngine.IO.raw.devices.psse_object import RawObject
from GridCalEngine.basic_structures import Logger
import GridCalEngine.Core.Devices as dev


class RawGneDevice(RawObject):

    def __init__(self):
        RawObject.__init__(self, "GNE")

    def parse(self, data, version, logger: Logger):
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
            logger.add_warning('Areas not defined for version', str(version))

    def get_raw_line(self, version):

        if version >= 29:
            return self.format_raw_line([])
        else:
            raise Exception('Areas not defined for version', str(version))


