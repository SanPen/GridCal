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

    def __init__(self) -> None:
        RawObject.__init__(self, "Impedance Correction Table")

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
                    k = 0
                    i = 0
                    ln = len(all_data)
                    while k < ln:
                        if not (all_data[k] == 0 and all_data[k+1] == 0 and all_data[k+2] == 0):
                            self.T.append(all_data[k])
                            self.F_re.append(all_data[k + 1])
                            self.F_im.append(all_data[k + 2])
                        k += 3
                        i += 1

                elif len(all_data) % 2 == 0:
                    k = 0
                    i = 0
                    ln = len(all_data)
                    while k < ln:
                        if not (all_data[k] == 0 and all_data[k + 1] == 0 and all_data[k + 2] == 0):
                            self.T.append(all_data[k])
                            self.F_re.append(all_data[k + 1])
                            self.F_im.append(0.0)
                        k += 3
                        i += 1
                else:
                    logger.add_error('Impedance correction values not divisible by 3 nor 4, hence they are wrong :(',
                                     str(version))

            else:
                logger.add_error('No impedance table data', str(version))

        else:
            logger.add_warning('Impedance correction not defined for version', str(version))

    def get_raw_line(self, version):

        if version >= 29:
            data = [self.I]
            for k in range(12):
                data.append(self.T[k])
                data.append(self.F_re[k])
                data.append(self.F_im[k])
            return ", ".join(data)
        else:
            raise Exception('Impedance correction not defined for version', str(version))

    def get_id(self) -> str:
        return str(self.I)

    def get_seed(self):
        return "_CA_{}".format(self.I)
