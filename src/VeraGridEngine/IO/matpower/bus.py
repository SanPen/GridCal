# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

class MatpowerBus:
    """
    Class to parse and write bus data from MATPOWER .m files.
    """
    def __init__(self):
        # Initialize all attributes to default values
        self.bus_i = 0              # Bus number
        self.bus_type = 0           # Bus type (PQ, PV, REF, NONE)
        self.pd = 0.0               # Real power demand (MW)
        self.qd = 0.0               # Reactive power demand (MVAr)
        self.gs = 0.0               # Shunt conductance (MW at V=1.0 p.u.)
        self.bs = 0.0               # Shunt susceptance (MVAr at V=1.0 p.u.)
        self.bus_area = 1           # Area number (1-100)
        self.vm = 1.0               # Voltage magnitude (p.u.)
        self.va = 0.0               # Voltage angle (degrees)
        self.base_kv = 0.0          # Base voltage (kV)
        self.zone = 1               # Loss zone (1-999)
        self.vmax = 1.1             # Maximum voltage magnitude (p.u.)
        self.vmin = 0.9             # Minimum voltage magnitude (p.u.)
        self.lam_p = 0.0            # Lagrange multiplier on real power mismatch
        self.lam_q = 0.0            # Lagrange multiplier on reactive power mismatch
        self.mu_vmax = 0.0          # Kuhn-Tucker multiplier on upper voltage limit
        self.mu_vmin = 0.0          # Kuhn-Tucker multiplier on lower voltage limit
        self.bus_x = 0.0            # X position for graphical representation
        self.bus_y = 0.0            # Y position for graphical representation
        self.collapsed = 0          # Collapsed flag
        self.dispatchable_bus = 0   # Dispatchable bus flag
        self.fix_power_bus = 0      # Fixed power bus flag

        self.name = ""

    def parse_row(self, row):
        """
        Parses a single row of bus data and assigns values to the instance attributes.
        :param row: List of values corresponding to a MATPOWER bus row.
        """
        # Assign values explicitly
        self.bus_i = int(row[0])           # Bus number
        self.bus_type = int(row[1])        # Bus type
        self.pd = float(row[2])            # Real power demand
        self.qd = float(row[3])            # Reactive power demand
        self.gs = float(row[4])            # Shunt conductance
        self.bs = float(row[5])            # Shunt susceptance
        self.bus_area = int(row[6])        # Area number
        self.vm = float(row[7])            # Voltage magnitude
        self.va = float(row[8])            # Voltage angle
        self.base_kv = float(row[9])       # Base voltage
        self.zone = int(row[10])           # Loss zone
        self.vmax = float(row[11])         # Maximum voltage magnitude
        self.vmin = float(row[12])         # Minimum voltage magnitude

        if len(row) > 13:
            self.lam_p = float(row[13])        # Lagrange multiplier on real power mismatch
            self.lam_q = float(row[14])        # Lagrange multiplier on reactive power mismatch
            self.mu_vmax = float(row[15])      # Kuhn-Tucker multiplier on upper voltage limit
            self.mu_vmin = float(row[16])      # Kuhn-Tucker multiplier on lower voltage limit

        if len(row) > 17:
            self.bus_x = float(row[17])        # X position
            self.bus_y = float(row[18])        # Y position

        if len(row) > 19:
            self.collapsed = int(row[19])      # Collapsed flag
            self.dispatchable_bus = int(row[20])  # Dispatchable bus flag
            self.fix_power_bus = int(row[21])     # Fixed power bus flag

        self.name = f"{self.bus_i}"