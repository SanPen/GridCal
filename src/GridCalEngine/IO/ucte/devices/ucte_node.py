# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from GridCalEngine.IO.ucte.devices.ucte_base import try_get
from GridCalEngine.basic_structures import Logger


UCTE_VOLTAGE_MAP = {
            "0": 750,
            "1": 380,
            "2": 220,
            "3": 150,
            "4": 120,
            "5": 110,
            "6": 70,
            "7": 27,
            "8": 330,
            "9": 500,
            "A": 26,
            "B": 25,
            "C": 24,
            "D": 23,
            "E": 22,
            "F": 21,
            "G": 20,
            "H": 19,
            "I": 18,
            "J": 17,
            "K": 15.7,
            "L": 15,
            "M": 13.7,
            "N": 13,
            "O": 12,
            "P": 11,
            "Q": 9.8,
            "R": 9,
            "S": 8,
            "T": 7,
            "U": 6,
            "V": 5,
            "W": 4,
            "X": 3,
            "Y": 2,
            "Z": 1,
        }


def try_parse_voltage(val: str | float, name: str, logger: Logger) -> float:
    """

    :return:
    """
    try:
        return float(val)
    except ValueError:
        val2 =  UCTE_VOLTAGE_MAP.get(val, None)
        if val2 is None:
            logger.add_error('Could not parse UCTE voltage',
                             device=name, value=f"'{val}'")
            return 1.0
        else:
            return val2

class UcteNode:
    def __init__(self):
        self.node_code = ""  # 0-7: Node (code)
        self.geo_name = ""  # 9-20: Geographical name
        self.status = 0  # 22: Status: 0 = real, 1 = equivalent

        # Node type code (0 = P and Q constant (PQ node);
        # 1 = Q and θ constant, 2 = P and U constant(PU node),
        # 3 = U and θ constant(global slack node, only one in the whole network))
        self.node_type = 0  # 24: Node type code

        self.voltage = float  # 26-31: Voltage (reference value, kV)

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

    def parse(self, line: str, logger: Logger):
        """

        :param line:
        :param logger:
        :return:
        """
        # self.node_code = line[0:8].strip()
        # self.geo_name = line[9:21].strip()
        # self.status = int(line[22:23].strip())
        # self.node_type = int(line[24:25].strip())
        # self.voltage = try_parse_voltage(val=line[26:32].strip(), name=self.node_code, logger=logger)
        # self.active_load = float(line[33:40].strip())
        # self.reactive_load = float(line[41:48].strip())
        # self.active_gen = float(line[49:56].strip())
        # self.reactive_gen = float(line[57:64].strip())
        # self.min_gen_mw = float(line[65:72].strip()) if line[65:72].strip() else 0.0
        # self.max_gen_mw = float(line[73:80].strip()) if line[73:80].strip() else 0.0
        # self.min_gen_mvar = float(line[81:88].strip()) if line[81:88].strip() else 0.0
        # self.max_gen_mvar = float(line[89:96].strip()) if line[89:96].strip() else 0.0
        # self.static_primary_control = float(line[97:102].strip()) if line[97:102].strip() else 0.0
        # self.nominal_power_primary_control = float(line[103:110].strip()) if line[103:110].strip() else 0.0
        # self.short_circuit_power = float(line[111:118].strip()) if line[111:118].strip() else 0.0
        # self.xr_ratio = float(line[119:126].strip()) if line[119:126].strip() else 0.0
        # self.plant_type = line[127:128].strip() if line[127:128].strip() else ""
        device = "Node"
        self.node_code = try_get(line, 0, 8, str, device, "node_code", logger)
        self.geo_name = try_get(line, 9, 21, str, device, "geo_name", logger)
        self.status = try_get(line, 22, 23, int, device, "status", logger)
        self.node_type = try_get(line, 24, 25, int, device, "node_type", logger)
        self.voltage = try_parse_voltage(val=line[26:32].strip(), name=self.node_code, logger=logger)
        self.active_load = try_get(line, 33, 40, float, device, "active_load", logger)
        self.reactive_load = try_get(line, 41, 48, float, device, "reactive_load", logger)
        self.active_gen = try_get(line, 49, 56, float, device, "active_gen", logger)
        self.reactive_gen = try_get(line, 57, 64, float, device, "reactive_gen", logger)
        self.min_gen_mw = try_get(line, 65, 72, float, device, "min_gen_mw", logger)
        self.max_gen_mw = try_get(line, 73, 80, float, device, "max_gen_mw", logger)
        self.min_gen_mvar = try_get(line, 81, 88, float, device, "min_gen_mvar", logger)
        self.max_gen_mvar = try_get(line, 89, 96, float, device, "max_gen_mvar", logger)
        self.static_primary_control = try_get(line, 97, 102, float, device, "static_primary_control", logger)
        self.nominal_power_primary_control = try_get(line, 103, 110, float, device,
                                                     "nominal_power_primary_control", logger)
        self.short_circuit_power = try_get(line, 111, 118, float, device, "short_circuit_power", logger)
        self.xr_ratio = try_get(line, 119, 126, float, device, "xr_ratio", logger)
        self.plant_type = try_get(line, 127, 128, str, device, "plant_type", logger)

