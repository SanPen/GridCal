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
from GridCalEngine.IO.raw.devices.psse_object import RawObject
from GridCalEngine.basic_structures import Logger


class RawOwner(RawObject):

    def __init__(self):
        RawObject.__init__(self, "Owner")

        self.I = -1
        self.OWNAME = ''

        self.register_property(property_name="I",
                               rawx_key='izone',
                               class_type=int,
                               description="Zone number",
                               min_value=1,
                               max_value=9999)

        self.register_property(property_name="OWNAME",
                               rawx_key='owname',
                               class_type=str,
                               description="Owner name",
                               max_chars=12)

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if version >= 29:
            # I, 'ZONAME'
            self.I, self.OWNAME = data[0]

            self.OWNAME = self.OWNAME.replace("'", "").strip()
        else:
            logger.add_warning('Zones not defined for version', str(version))

    def get_raw_line(self, version):

        if version >= 29:
            return self.format_raw_line([self.I, self.OWNAME])
        else:
            raise Exception('Areas not defined for version', str(version))

    def get_id(self) -> str:
        return str(self.I)

    def get_seed(self):
        return "_OW_{0}".format(self.get_id())
