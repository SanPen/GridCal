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
import GridCalEngine.Devices as dev


class RawFixedShunt(RawObject):

    def __init__(self):
        RawObject.__init__(self, "Fixed shunt")

        self.I = 0
        self.ID = ""
        self.STATUS = 1
        self.GL = 0.0
        self.BL = 0.0

        self.register_property(property_name="I",
                               rawx_key="ibus",
                               class_type=int,
                               description="Bus number",
                               min_value=1,
                               max_value=999997)

        self.register_property(property_name="ID",
                               rawx_key="shntid",
                               class_type=str,
                               description="2-character ID",
                               max_chars=2)

        self.register_property(property_name="STATUS",
                               rawx_key="stat",
                               class_type=int,
                               description="Status",
                               min_value=0,
                               max_value=1)

        self.register_property(property_name="GL",
                               rawx_key="gl",
                               class_type=float,
                               unit=Unit.get_mw(),
                               description="Active power load at v=1.0 p.u.")

        self.register_property(property_name="BL",
                               rawx_key="bl",
                               class_type=float,
                               unit=Unit.get_mvar(),
                               description="Reactive power load at v=1.0 p.u.")

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """
        if version >= 29:
            self.I, self.ID, self.STATUS, self.GL, self.BL = data[0]
        else:
            logger.add_warning('Shunt not implemented for the version', str(version))

    def get_raw_line(self, version):

        if version >= 29:
            return self.format_raw_line([self.I, self.ID, self.STATUS, self.GL, self.BL])
        else:
            raise Exception('Shunt not implemented for the version ' + str(version))

    def get_id(self):
        """
        Get the element PSSE ID
        :return:
        """
        return "{0}_{1}".format(self.I, self.ID)

