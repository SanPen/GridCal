# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List, Any
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
        self.OWNER = 1
        self.VM = 1.0
        self.VA = 0.0
        self.NVHI = 1.05
        self.NVLO = 0.95
        self.EVHI = 1.1
        self.EVLO = 0.9
        self.GL = 0.0
        self.BL = 0.0

        self.register_property(property_name="I",
                               rawx_key="ibus",
                               class_type=int,
                               description="Bus number",
                               min_value=1,
                               max_value=999997,
                               max_chars=6)

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
                               min_value=0.0,
                               format_rule=".4f")

        self.register_property(property_name="IDE",
                               rawx_key="ide",
                               class_type=int,
                               description="Bus type (0:Disconnected, 1:PQ, 2:PV, 3:Slack)",
                               min_value=1,
                               max_value=4,
                               max_chars=1)

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
                               max_value=2.0,
                               format_rule=".5f")

        self.register_property(property_name="VA",
                               rawx_key="va",
                               class_type=float,
                               description="Bus voltage angle",
                               unit=Unit.get_deg(),
                               min_value=0.0,
                               max_value=360.0,
                               format_rule=".4f")

        self.register_property(property_name="NVHI",
                               rawx_key="nvhi",
                               class_type=float,
                               description="Normal voltage magnitude high limit",
                               unit=Unit.get_pu(),
                               format_rule=".5f")

        self.register_property(property_name="NVLO",
                               rawx_key="nvlo",
                               class_type=float,
                               description="Normal voltage magnitude low limit",
                               unit=Unit.get_pu(),
                               format_rule=".5f")

        self.register_property(property_name="EVHI",
                               rawx_key="evhi",
                               class_type=float,
                               description="Emergency voltage magnitude high limit",
                               unit=Unit.get_pu(),
                               format_rule=".5f")

        self.register_property(property_name="EVLO",
                               rawx_key="evlo",
                               class_type=float,
                               description="Emergency voltage magnitude low limit",
                               unit=Unit.get_pu(),
                               format_rule=".5f")

    def parse(self, data: List[List[Any]], version: int, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        self.version = version

        if version >= 33:

            (self.I, self.NAME, self.BASKV, self.IDE, self.AREA, self.ZONE,
             self.OWNER, self.VM, self.VA, self.NVHI, self.NVLO, self.EVHI, self.EVLO) = self.extend_or_curtail(data[0], 13)

        elif version == 32:

            (self.I, self.NAME, self.BASKV, self.IDE, self.AREA, self.ZONE,
             self.OWNER, self.VM, self.VA) = self.extend_or_curtail(data[0], 9)

        elif version in [29, 30]:

            (self.I, self.NAME, self.BASKV, self.IDE, self.GL, self.BL,
             self.AREA, self.ZONE, self.VM, self.VA, self.OWNER) = self.extend_or_curtail(data[0], 11)


        else:
            logger.add_warning('Bus not implemented for version', str(version))

    def get_raw_line(self, version: int):
        """
        Get raw file line(s)
        :param version: supported version
        :return:
        """

        if version >= 33:
            return self.format_raw_line(["I", "NAME", "BASKV", "IDE", "AREA", "ZONE",
                                         "OWNER", "VM", "VA", "NVHI", "NVLO", "EVHI", "EVLO"])

        elif version == 32:

            return self.format_raw_line(["I", "NAME", "BASKV", "IDE", "AREA", "ZONE",
                                         "OWNER", "VM", "VA"])

        elif version in [29, 30]:
            return self.format_raw_line(["I", "NAME", "BASKV", "IDE", "GL", "BL",
                                         "AREA", "ZONE", "VM", "VA", "OWNER"])

        else:
            raise Exception('Bus not implemented for version', str(version))

    def get_id(self) -> str:
        return str(self.I)
