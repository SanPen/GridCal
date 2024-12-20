# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import List
from GridCalEngine.IO.base.units import Unit
from GridCalEngine.IO.raw.devices.psse_object import RawObject
from GridCalEngine.basic_structures import Logger


class RawImpedanceCorrectionTable(RawObject):

    def __init__(self):
        RawObject.__init__(self, "Area")

        self.I: int = -1

        self.T: List[int] = list()
        self.F_re: List[float] = list()
        self.F_im: List[float] = list()

        self.register_property(property_name="I",
                               rawx_key='iarea',
                               class_type=int,
                               description="Area number",
                               min_value=1,
                               max_value=9999)

    def parse(self, data: List[List[int | float]], version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        self.I = -1

        if version >= 29:
            all_data = list()
            for row in data:
                all_data += row

            if len(all_data) > 0:

                self.I = int(all_data.pop(0))

                if len(all_data) % 3 == 0:
                    for T, F_re, F_im in all_data:
                        self.T.append(T)
                        self.F_re.append(F_re)
                        self.F_im.append(F_im)

                elif len(all_data) % 2 == 0:
                    for T, F in all_data:
                        self.T.append(T)
                        self.F_re.append(F)
                        self.F_im.append(1.0)
                else:
                    logger.add_error('Impedance correction values not divisible by 3 nor 4, hence they are wrong :(',
                                     str(version))

            else:
                logger.add_error('No impedance table data', str(version))

        else:
            logger.add_warning('Impedance correction not defined for version', str(version))

    def get_raw_line(self, version):

        if version >= 29:
            return self.format_raw_line([self.I, self.ISW, self.PDES, self.PTOL, self.ARNAME])
        else:
            raise Exception('Areas not defined for version', str(version))

    def get_id(self) -> str:
        return str(self.I)

    def get_seed(self):
        return "_CA_{}".format(self.I)
