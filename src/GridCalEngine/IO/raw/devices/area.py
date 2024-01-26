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

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        self.I = -1

        self.ARNAME = ''

        if version >= 29:
            # I, ISW, PDES, PTOL, 'ARNAME'
            self.I, self.ISW, self.PDES, self.PTOL, self.ARNAME = data[0]

            self.ARNAME = self.ARNAME.replace("'", "").strip()
        else:
            logger.add_warning('Areas not defined for version', str(version))

    def get_raw_line(self, version):

        if version >= 29:
            return self.format_raw_line([self.I, self.ISW, self.PDES, self.PTOL, self.ARNAME])
        else:
            raise Exception('Areas not defined for version', str(version))

    def get_id(self) -> str:
        return str(self.I)

    def get_seed(self):
        return "_CA_{}".format(self.I)
