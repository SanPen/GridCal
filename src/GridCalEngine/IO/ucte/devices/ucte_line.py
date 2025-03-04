# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from GridCalEngine.IO.ucte.devices.ucte_base import sub_int, sub_str, sub_float
from GridCalEngine.basic_structures import Logger

class UcteLine:
    def __init__(self):
        self.node1 = ""  # 0-7: Node 1 code
        self.node2 = ""  # 9-16: Node 2 code
        self.order_code = ""  # 18: Order code


        self.status = 0  # 20: Status

        self.resistance = 0.0  # 22-27: Resistance (Ω)
        self.reactance = 0.0  # 29-34: Reactance (Ω)
        self.susceptance = 0.0  # 36-43: Susceptance (µS)
        self.current_limit = 0  # 45-50: Current limit (A)
        self.name = ""

    def is_active_and_reducible(self) -> tuple[bool, bool]:
        """
        Returns if this line is active and/or reducible
        :return: active, reducible
        """

        """
        Status
        0: real element in operation (R, X only positive values permitted)
        8: real element out of operation (R, X only positive values permitted)
        1: equivalent element in operation
        9: equivalent element out of operation        
        2: busbar coupler in operation (definition: R=0, X=0, B=0)
        7: busbar coupler out of operation (definition: R=0, X=0, B=0)
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

    def parse(self, line: str, logger: Logger):
        """

        :param line:
        :param logger:
        :return:
        """

        device = "Line"
        self.node1 = sub_str(line, 0, 8, device,"node1",  logger)
        self.node2 = sub_str(line, 9, 17,device,  "node2", logger)
        self.order_code = sub_str(line, 18, 19, device, "", logger)
        self.status = sub_int(line, 20, 21, device, "status", logger)
        self.resistance = sub_float(line, 22, 28, device, "resistance", logger)
        self.reactance = sub_float(line, 29, 35, device, "reactance", logger)
        self.susceptance = sub_float(line, 36, 44, device, "susceptance", logger)
        self.current_limit = sub_int(line, 45, 51, device, "current_limit", logger)
        self.name = sub_str(line, 53, len(line), device, "name", logger)