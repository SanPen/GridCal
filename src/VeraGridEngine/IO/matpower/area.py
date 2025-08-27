# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

class MatpowerArea:

    def __init__(self):
        """

        """
        self.area_i: int = 0
        self.bus_i: int = 0

    def parse_row(self, row):
        """

        :param row:
        :return:
        """
        self.area_i = int(row[0])
        self.bus_i = int(row[1])
