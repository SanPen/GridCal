# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

class UcteTransformerRegulation:
    def __init__(self):
        self.node1 = ""  # 0-7: Node 1 (non-regulated winding) To bus for GridCal
        self.node2 = ""  # 9-16: Node 2 (regulated winding) From bus for GridCal
        self.order_code = ""  # 18: Order code

        # Phase regulation
        self.delta_u1 = 0.0  # 20-24: δu1 (%)
        self.n1 = 0  # 26-27: Number of taps (n1)
        self.n1_prime = 0  # 29-31: Alternate taps (n1')
        self.u1 = 0.0  # 33-37: U1 (kV, optional)

        # Angle regulation
        self.delta_u2 = 0.0  # 39-43: δu2 (%)
        self.theta = 0.0  # 45-49: Θ (°)
        self.n2 = 0  # 51-52: Number of taps (n2)
        self.n2_prime = 0  # 54-56: Alternate taps (n2')
        self.p = 0.0  # 58-62: P (MW, optional)
        self.regulation_type = ""  # 64-67: Regulation type (ASYM, SYMM)

    def get_primary_key(self):
        """
        Get a transformer primary key
        :return:
        """
        return f"{self.node1}_{self.node2}_{self.order_code}"

    def parse(self, line: str):
        """

        :param line:
        :return:
        """
        self.node1 = line[0:8].strip()
        self.node2 = line[9:17].strip()
        self.order_code = line[18:19].strip()

        self.delta_u1 = float(line[20:25].strip()) if line[20:25].strip() else 0.0
        self.n1 = int(line[26:28].strip()) if line[26:28].strip() else 0
        self.n1_prime = int(line[29:32].strip()) if line[29:32].strip() else 0
        self.u1 = float(line[33:38].strip()) if line[33:38].strip() else 0.0

        self.delta_u2 = float(line[39:44].strip()) if line[39:44].strip() else 0.0
        self.theta = float(line[45:50].strip()) if line[45:50].strip() else 0.0
        self.n2 = int(line[51:53].strip()) if line[51:53].strip() else 0
        self.n2_prime = int(line[54:57].strip()) if line[54:57].strip() else 0
        self.p = float(line[58:63].strip()) if line[58:63].strip() else 0.0
        self.regulation_type = line[64:68].strip() if line[64:68].strip() else ""
