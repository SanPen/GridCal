# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

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

    def parse(self, line: str):
        """

        :param line:
        :return:
        """
        self.node1 = line[0:8].strip()
        self.node2 = line[9:17].strip()
        self.order_code = line[18:19].strip()
        self.status = int(line[20:21].strip())
        self.resistance = float(line[22:28].strip())
        self.reactance = float(line[29:35].strip())
        self.susceptance = float(line[36:44].strip())
        self.current_limit = int(line[45:51].strip())
        self.name = line[53::].strip()