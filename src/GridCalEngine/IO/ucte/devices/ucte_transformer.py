# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from GridCalEngine.IO.ucte.devices.ucte_base import sub_int, sub_str, sub_float
from GridCalEngine.basic_structures import Logger


class UcteTransformer:
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

    def get_primary_key(self):
        """
        Get a transformer primary key
        :return:
        """
        return f"{self.node1}_{self.node2}_{self.order_code}"

    def is_active_and_reducible(self) -> tuple[bool, bool]:
        """
        Returns if this line is active and/or reducible
        :return: active, reducible
        """

        """
        Status
        0:real element in operation (R, X only positive values permitted)
        8: real element out of operation (R, X only positive values permitted)
        1:equivalent element in operation
        9:equivalent element out of operation        
        2:busbar coupler in operation (definition: R=0, X=0, B=0)
        7:busbar coupler out of operation (definition: R=0, X=0, B=0)
        """
        if self.status == 0:
            return True, False
        elif self.status == 8:
            return False, False
        elif self.status == 1:
            return True, False
        elif self.status == 9:
            return False, False
        elif self.status == 2:
            return True, True
        elif self.status == 7:
            return False, True

    def parse(self, line, logger: Logger):
        """

        :param line:
        :param logger:
        :return:
        """

        device = "Transformer"

        self.node1 = sub_str(line, 0, 8, device, "node1", logger)
        self.node2 = sub_str(line, 9, 17, device, "node2", logger)
        self.order_code = sub_str(line, 18, 19, device, "order_code", logger)
        self.status = sub_int(line, 20, 21, device, "status", logger)
        self.rated_voltage1 = sub_float(line, 22, 27, device, "rated_voltage1", logger)
        self.rated_voltage2 = sub_float(line, 28, 33, device, "rated_voltage2", logger)
        self.nominal_power = sub_float(line, 34, 39, device, "nominal_power", logger)
        self.resistance = sub_float(line, 40, 46, device, "resistance", logger)
        self.reactance = sub_float(line, 47, 53, device, "reactance", logger)
        self.susceptance = sub_float(line, 54, 62, device, "susceptance", logger)
        self.conductance = sub_float(line, 63, 69, device, "conductance", logger)
        self.current_limit = sub_int(line, 70, 76, device, "current_limit", logger)
        self.name = sub_str(line, 77, 88, device, "name", logger)
