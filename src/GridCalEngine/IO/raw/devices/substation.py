# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol, Unit
from GridCalEngine.IO.raw.devices.psse_object import RawObject
from GridCalEngine.basic_structures import Logger
import GridCalEngine.Devices as dev


class RawSubstation(RawObject):

    def __init__(self):
        RawObject.__init__(self, "Substation")

        self.IS: int = 0
        self.NAME: str = ""
        self.LATI: float = 0.0
        self.LONG: float = 0.0
        self.SGR: float = 0.0

        self.register_property(property_name="IS",
                               rawx_key='isub',
                               class_type=int,
                               description="Substation number ",
                               min_value=1,
                               max_value=99999)

        self.register_property(property_name="NAME",
                               rawx_key='name',
                               class_type=str,
                               description="Substation name.",
                               max_chars=40)

        self.register_property(property_name="LATI",
                               rawx_key='lati',
                               class_type=float,
                               description="Substation latitude.",
                               min_value=-90,
                               max_chars=90,
                               unit=Unit.get_deg())

        self.register_property(property_name="LONG",
                               rawx_key='long',
                               class_type=float,
                               description="Substation longitude.",
                               min_value=-180,
                               max_chars=180,
                               unit=Unit.get_deg())

        self.register_property(property_name="SGR",
                               rawx_key='sgr',
                               class_type=float,
                               description="Substation grounding DC resistance in ohms.",
                               unit=Unit.get_ohm())

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if version == 34:

            if len(data[0]) == 5:
                self.IS, self.NAME, self.LATI, self.LONG, self.SGR = data[0]
            elif len(data[0]) == 4:
                self.IS, self.NAME, self.LATI, self.LONG = data[0]
            else:
                logger.add_warning('Substation line length could not be identified :/', value=",".join(data[0]))

        elif version == 35:

            if len(data[0]) == 5:
                self.IS, self.NAME, self.LATI, self.LONG, self.SGR = data[0]
            elif len(data[0]) == 4:
                self.IS, self.NAME, self.LATI, self.LONG = data[0]
            else:
                logger.add_warning('Substation line length could not be identified :/', value=",".join(data[0]))

        else:
            logger.add_warning('Substation not defined for version', str(version))

    def get_raw_line(self, version):

        if version >= 35:
            return self.format_raw_line(["IS", "NAME", "LATI", "LONG", "SGR"])
        else:
            raise Exception('Substation not defined for version', str(version))

    def get_id(self) -> str:
        return str(self.IS)
