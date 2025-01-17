# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.raw.devices.psse_object import RawObject
from GridCalEngine.basic_structures import Logger


class RawZone(RawObject):

    def __init__(self):
        RawObject.__init__(self, "Zone")

        self.I = -1
        self.ZONAME = ''

        self.register_property(property_name="I",
                               rawx_key='izone',
                               class_type=int,
                               description="Zone number",
                               min_value=1,
                               max_value=9999)

        self.register_property(property_name="ZONAME",
                               rawx_key='zoname',
                               class_type=str,
                               description="Zone name",
                               max_chars=12)

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if version >= 29:
            # I, 'ZONAME'
            self.I, self.ZONAME = data[0]

            self.ZONAME = self.ZONAME.replace("'", "").strip()
        else:
            logger.add_warning('Zones not defined for version', str(version))

    def get_raw_line(self, version):

        if version >= 29:
            return self.format_raw_line(["I", "ZONAME"])
        else:
            raise Exception('Zone not defined for version', str(version))

    def get_id(self) -> str:
        return str(self.I)

    def get_seed(self):
        return "_ZN_{0}".format(self.get_id())