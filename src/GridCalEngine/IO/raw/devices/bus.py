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
import numpy as np
from GridCalEngine.IO.base.units import Unit
from GridCalEngine.IO.raw.devices.psse_object import RawObject
from GridCalEngine.basic_structures import Logger


class RawBus(RawObject):

    def __init__(self):
        RawObject.__init__(self, "Bus")

        self.I = 1
        self.NAME = ""
        self.BASKV = 0.0
        self.IDE = 1
        self.AREA = 0
        self.ZONE = 0
        self.OWNER = 0
        self.VM = 1.0
        self.VA = 0.0
        self.NVHI = 0
        self.NVLO = 0
        self.EVHI = 0
        self.EVLO = 0

        self.register_property(property_name="I",
                               rawx_key="ibus",
                               class_type=int,
                               description="Bus number",
                               min_value=1,
                               max_value=999997)

        self.register_property(property_name="NAME",
                               rawx_key="name",
                               class_type=str,
                               description="Bus name",
                               max_chars=12)

        self.register_property(property_name="BASKV",
                               rawx_key="baskv",
                               class_type=float,
                               description="Bus base voltage",
                               unit=Unit.get_kv(),
                               min_value=0.0)

        self.register_property(property_name="IDE",
                               rawx_key="ide",
                               class_type=int,
                               description="Bus type (0:Disconnected, 1:PQ, 2:PV, 3:Slack)",
                               min_value=1,
                               max_value=4)

        self.register_property(property_name="AREA",
                               rawx_key="area",
                               class_type=int,
                               description="Area number",
                               min_value=1,
                               max_value=9999)

        self.register_property(property_name="ZONE",
                               rawx_key="zone",
                               class_type=int,
                               description="Zone number",
                               min_value=1,
                               max_value=9999)

        self.register_property(property_name="OWNER",
                               rawx_key="owner",
                               class_type=int,
                               description="Owner number",
                               min_value=1,
                               max_value=9999)

        self.register_property(property_name="VM",
                               rawx_key="vm",
                               class_type=float,
                               description="Bus voltage magnitude",
                               unit=Unit.get_pu(),
                               min_value=0.0,
                               max_value=2.0)

        self.register_property(property_name="VA",
                               rawx_key="va",
                               class_type=float,
                               description="Bus voltage angle",
                               unit=Unit.get_deg(),
                               min_value=0.0,
                               max_value=360.0)

        self.register_property(property_name="NVHI",
                               rawx_key="nvhi",
                               class_type=float,
                               description="Normal voltage magnitude high limit",
                               unit=Unit.get_pu())

        self.register_property(property_name="NVLO",
                               rawx_key="nvlo",
                               class_type=float,
                               description="Normal voltage magnitude low limit",
                               unit=Unit.get_pu())

        self.register_property(property_name="EVHI",
                               rawx_key="evhi",
                               class_type=float,
                               description="Emergency voltage magnitude high limit",
                               unit=Unit.get_pu())

        self.register_property(property_name="EVLO",
                               rawx_key="evlo",
                               class_type=float,
                               description="Emergency voltage magnitude low limit",
                               unit=Unit.get_pu())

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        self.version = version

        if version >= 33:
            n = len(data[0])
            dta = np.zeros(13, dtype=object)
            dta[0:n] = data[0]

            self.I, self.NAME, self.BASKV, self.IDE, self.AREA, self.ZONE, \
                self.OWNER, self.VM, self.VA, self.NVHI, self.NVLO, self.EVHI, self.EVLO = dta

        elif version == 32:

            self.I, self.NAME, self.BASKV, self.IDE, self.AREA, self.ZONE, self.OWNER, self.VM, self.VA = data[0]

        elif version in [29, 30]:
            # I, 'NAME', BASKV, IDE, GL, BL, AREA, ZONE, VM, VA, OWNER
            self.I, self.NAME, self.BASKV, self.IDE, self.GL, self.BL, \
                self.AREA, self.ZONE, self.VM, self.VA, self.OWNER = data[0]


        else:
            logger.add_warning('Bus not implemented for version', str(version))

    def get_raw_line(self, version):
        """
        Get raw file line(s)
        :param version: supported version
        :return:
        """
        # if version >= 33:
        #
        #     return self.format_raw_line(["I", "NAME", "BASKV", "IDE", "AREA", "ZONE",
        #                                  "OWNER", "VM", "VA", "NVHI", "NVLO", "EVHI", "EVLO"])
        #
        # elif version == 32:
        #
        #     return self.format_raw_line(["I", "NAME", "BASKV", "IDE", "AREA", "ZONE",
        #                                  "OWNER", "VM", "VA"])
        #
        # elif version in [29, 30]:
        #
        #     return self.format_raw_line(["I", "NAME", "BASKV", "IDE", "GL", "BL",
        #                                  "AREA", "ZONE", "VM", "VA", "OWNER"])
        #
        # else:
        #     raise Exception('Bus not implemented for version', str(version))

        if version >= 33:
            return self.format_raw_line([self.I, self.NAME, self.BASKV, self.IDE, self.AREA, self.ZONE,
                                         self.OWNER, self.VM, self.VA, self.NVHI, self.NVLO, self.EVHI, self.EVLO])

        elif version == 32:

            return self.format_raw_line([self.I, self.NAME, self.BASKV, self.IDE, self.AREA, self.ZONE,
                                         self.OWNER, self.VM, self.VA])

        elif version in [29, 30]:
            return self.format_raw_line([self.I, self.NAME, self.BASKV, self.IDE, self.GL, self.BL,
                                         self.AREA, self.ZONE, self.VM, self.VA, self.OWNER])

        else:
            raise Exception('Bus not implemented for version', str(version))

    def get_id(self) -> str:
        return str(self.I)


