# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from GridCalEngine.IO.raw.devices.psse_object import RawObject
from GridCalEngine.basic_structures import Logger


class RawMultiLineSection(RawObject):

    def __init__(self):
        RawObject.__init__(self, "MultiLineSection")

        self.I: int = 0
        self.J: int = 0
        self.ID: str = ""
        self.MET: int = 1
        self.DUM1: int = 0
        self.DUM2: int = 0
        self.DUM3: int = 0
        self.DUM4: int = 0
        self.DUM5: int = 0
        self.DUM6: int = 0
        self.DUM7: int = 0
        self.DUM8: int = 0
        self.DUM9: int = 0

        self.register_property(property_name="I",
                               rawx_key='ibus',
                               class_type=int,
                               description="From bus",
                               min_value=1,
                               max_value=9999)

        self.register_property(property_name="J",
                               rawx_key='jbus',
                               class_type=int,
                               description="Bus to")

        self.register_property(property_name="ID",
                               rawx_key='mslid',
                               class_type=float,
                               description="Multi section ID",)

        self.register_property(property_name="MET",
                               rawx_key='met',
                               class_type=int,
                               description="Metered flag",)

        for i in range(1, 10):
            self.register_property(property_name=f"DUM{i}",
                                   rawx_key=f'dum{i}',
                                   class_type=int,
                                   description=f"Dummy bus {i}",)

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if version >= 29:
            # I, ISW, PDES, PTOL, 'ARNAME'
            var = [self.DUM1, self.DUM2, self.DUM3, self.DUM4, self.DUM5, self.DUM6, self.DUM7, self.DUM8, self.DUM9]
            (self.I, self.J, self.ID, self.MET, *var) = data[0]

        else:
            logger.add_warning('Multi-line section not defined for version', str(version))

    def get_raw_line(self, version):

        if version >= 29:
            return self.format_raw_line(["I", "J", "ID", "MET",
                                         "DUM1", "DUM2", "DUM3",
                                         "DUM4", "DUM5", "DUM6",
                                         "DUM7", "DUM8", "DUM9"])
        else:
            raise Exception('Areas not defined for version', str(version))

    def get_id(self) -> str:
        return str(self.I)

    def get_seed(self) -> str:
        return "_CA_{}".format(self.I)
