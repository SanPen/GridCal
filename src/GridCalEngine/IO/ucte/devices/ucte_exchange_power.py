# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from GridCalEngine.IO.ucte.devices.ucte_base import sub_int, sub_str, sub_float
from GridCalEngine.basic_structures import Logger


class UcteExchangePower:
    def __init__(self):
        self.country1 = ""  # 0-1: Country 1 (ISO code)
        self.country2 = ""  # 3-4: Country 2 (ISO code)
        self.active_power = 0.0  # 6-12: Scheduled active power exchange (MW)
        self.comments = ""  # 14-25: Optional comments

    def parse(self, line, logger: Logger):
        """

        :param line:
        :param logger:
        :return:
        """

        device = "Exchange Power"
        self.country1 = sub_str(line, 0, 2, device, "country1", logger)
        self.country2 = sub_str(line, 3, 5, device, "country2", logger)
        self.active_power = sub_float(line, 6, 13, device, "active_power", logger)
        self.comments = sub_str(line, 14, 26, device, "comments", logger)
