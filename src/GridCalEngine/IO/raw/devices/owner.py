# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
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
                               max_value=9999,
                               max_chars=4)

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
            return self.format_raw_line(["I", "OWNAME"])
        else:
            raise Exception('Areas not defined for version', str(version))

    def get_id(self) -> str:
        return str(self.I)

    def get_seed(self):
        return "_OW_{0}".format(self.get_id())
