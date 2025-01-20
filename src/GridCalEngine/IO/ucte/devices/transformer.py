# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

class Transformer:
    def __init__(self):
        self.node1 = ""  # 0-7: Node 1 code (non-regulated winding)
        self.node2 = ""  # 9-16: Node 2 code (regulated winding)
        self.order_code = ""  # 18: Order code
        self.status = 0  # 20: Status
        self.rated_voltage1 = 0.0  # 22-26: Rated voltage 1 (kV)
        self.rated_voltage2 = 0.0  # 28-32: Rated voltage 2 (kV)
        self.nominal_power = 0.0  # 34-38: Nominal power (MVA)
        self.resistance = 0.0  # 40-45: Resistance (Ω)
        self.reactance = 0.0  # 47-52: Reactance (Ω)
        self.susceptance = 0.0  # 54-61: Susceptance (µS)
        self.conductance = 0.0  # 63-68: Conductance (µS)
        self.current_limit = 0  # 70-75: Current limit (A)
        self.name = ""

    def parse(self, line):
        self.node1 = line[0:8].strip()
        self.node2 = line[9:17].strip()
        self.order_code = line[18:19].strip()
        self.status = int(line[20:21].strip())
        self.rated_voltage1 = float(line[22:27].strip())
        self.rated_voltage2 = float(line[28:33].strip())
        self.nominal_power = float(line[34:39].strip())
        self.resistance = float(line[40:46].strip())
        self.reactance = float(line[47:53].strip())
        self.susceptance = float(line[54:62].strip())
        self.conductance = float(line[63:69].strip())
        self.current_limit = int(line[70:76].strip())
        self.name = line[77:88].strip()