# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

class UcteNode:
    def __init__(self):
        self.node_code = ""  # 0-7: Node (code)
        self.geo_name = ""  # 9-20: Geographical name
        self.status = 0  # 22: Status: 0 = real, 1 = equivalent

        # Node type code (0 = P and Q constant (PQ node);
        # 1 = Q and θ constant, 2 = P and U constant(PU node),
        # 3 = U and θ constant(global slack node, only one in the whole network))
        self.node_type = 0  # 24: Node type code

        self.voltage = 0.0  # 26-31: Voltage (reference value, kV)

        self.active_load = 0.0  # 33-39: Active load (MW)
        self.reactive_load = 0.0  # 41-47: Reactive load (MVAr)

        self.active_gen = 0.0  # 49-55: Active power generation (MW)
        self.reactive_gen = 0.0  # 57-63: Reactive power generation (MVAr)

        self.min_gen_mw = 0.0  # 65-71: Minimum permissible generation (MW) *
        self.max_gen_mw = 0.0  # 73-79: Maximum permissible generation (MW) *
        self.min_gen_mvar = 0.0  # 81-87: Minimum permissible generation (MVAr) *
        self.max_gen_mvar = 0.0  # 89-95: Maximum permissible generation (MVAr) *

        self.static_primary_control = 0.0  # 97-101: Static of primary control (%) *

        self.nominal_power_primary_control = 0.0  # 103-109: Nominal power for primary control (MW) *

        self.short_circuit_power = 0.0  # 111-117: Three-phase short circuit power (MVA) **

        self.xr_ratio = 0.0  # 119-125: X/R ratio **

        # Power plant type *
        # H: hydro, N: nuclear, L: lignite,
        # C: hard coal, G: gas, O: oil, W: wind, F: further
        self.plant_type = ""  # 127: Power plant type (e.g., H: hydro, N: nuclear)

    def has_load(self)-> bool:
        return self.active_load != 0.0 or self.reactive_load != 0.0

    def has_gen(self)-> bool:
        return self.active_gen != 0.0 or self.reactive_gen != 0.0

    def parse(self, line):
        """

        :param line:
        :return:
        """
        self.node_code = line[0:8].strip()
        self.geo_name = line[9:21].strip()
        self.status = int(line[22:23].strip())
        self.node_type = int(line[24:25].strip())
        self.voltage = float(line[26:32].strip())
        self.active_load = float(line[33:40].strip())
        self.reactive_load = float(line[41:48].strip())
        self.active_gen = float(line[49:56].strip())
        self.reactive_gen = float(line[57:64].strip())
        self.min_gen_mw = float(line[65:72].strip()) if line[65:72].strip() else 0.0
        self.max_gen_mw = float(line[73:80].strip()) if line[73:80].strip() else 0.0
        self.min_gen_mvar = float(line[81:88].strip()) if line[81:88].strip() else 0.0
        self.max_gen_mvar = float(line[89:96].strip()) if line[89:96].strip() else 0.0
        self.static_primary_control = float(line[97:102].strip()) if line[97:102].strip() else 0.0
        self.nominal_power_primary_control = float(line[103:110].strip()) if line[103:110].strip() else 0.0
        self.short_circuit_power = float(line[111:118].strip()) if line[111:118].strip() else 0.0
        self.xr_ratio = float(line[119:126].strip()) if line[119:126].strip() else 0.0
        self.plant_type = line[127:128].strip() if line[127:128].strip() else ""
