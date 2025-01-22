# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

class UcteExchangePower:
    def __init__(self):
        self.country1 = ""  # 0-1: Country 1 (ISO code)
        self.country2 = ""  # 3-4: Country 2 (ISO code)
        self.active_power = 0.0  # 6-12: Scheduled active power exchange (MW)
        self.comments = ""  # 14-25: Optional comments

    def parse(self, line):
        self.country1 = line[0:2].strip()
        self.country2 = line[3:5].strip()
        self.active_power = float(line[6:13].strip())
        self.comments = line[14:26].strip()
