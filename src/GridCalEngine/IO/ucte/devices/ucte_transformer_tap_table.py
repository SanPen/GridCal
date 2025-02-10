# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

class UcteTransformerTapTable:
    """

    """
    def __init__(self):
        self.node1 = ""  # 0-7: Node 1 code
        self.node2 = ""  # 9-16: Node 2 code
        self.order_code = ""  # 18: Order code
        self.tap_position = 0  # 22-24: Tap position (n')
        self.resistance = 0.0  # 26-31: Resistance (Ω)
        self.reactance = 0.0  # 33-38: Reactance (Ω)
        self.delta_u = 0.0  # 40-44: Voltage deviation (%)
        self.phase_shift = 0.0  # 46-50: Phase shift angle (°)

    def get_primary_key(self):
        """
        Get a transformer primary key
        :return:
        """
        return f"{self.node1}_{self.node2}_{self.order_code}"

    def parse(self, line):
        self.node1 = line[0:8].strip()
        self.node2 = line[9:17].strip()
        self.order_code = line[18:19].strip()
        self.tap_position = int(line[22:25].strip())
        self.resistance = float(line[26:32].strip())
        self.reactance = float(line[33:39].strip())
        self.delta_u = float(line[40:45].strip())
        self.phase_shift = float(line[46:51].strip())
