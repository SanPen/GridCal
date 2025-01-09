# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

class MatpowerBranch:
    """
    Class to parse and write branch data from MATPOWER .m files.
    """
    def __init__(self):
        # Initialize all attributes to default values
        self.f_bus = 0           # From bus number
        self.t_bus = 0           # To bus number
        self.br_r = 0.0          # Resistance (p.u.)
        self.br_x = 0.0          # Reactance (p.u.)
        self.br_b = 0.0          # Total line charging susceptance (p.u.)
        self.rate_a = 0.0        # MVA rating A (long-term)
        self.rate_b = 0.0        # MVA rating B (short-term)
        self.rate_c = 0.0        # MVA rating C (emergency)
        self.tap = 1.0           # Transformer off nominal turns ratio
        self.shift = 0.0         # Transformer phase shift angle (degrees)
        self.br_status = 1       # Branch status (1=In-service, 0=Out-of-service)
        self.angmin = -360.0     # Minimum angle difference (degrees)
        self.angmax = 360.0      # Maximum angle difference (degrees)
        self.pf = 0.0            # Real power injected at "from" bus end (MW)
        self.qf = 0.0            # Reactive power injected at "from" bus end (MVAr)
        self.pt = 0.0            # Real power injected at "to" bus end (MW)
        self.qt = 0.0            # Reactive power injected at "to" bus end (MVAr)
        self.mu_sf = 0.0         # Kuhn-Tucker multiplier on MVA limit at "from" bus
        self.mu_st = 0.0         # Kuhn-Tucker multiplier on MVA limit at "to" bus
        self.mu_angmin = 0.0     # Kuhn-Tucker multiplier lower angle difference limit
        self.mu_angmax = 0.0     # Kuhn-Tucker multiplier upper angle difference limit
        self.vf_set = 0.0        # Voltage at "from" bus
        self.vt_set = 0.0        # Voltage at "to" bus
        self.ma_max = 0.0        # Maximum angle for the branch
        self.ma_min = 0.0        # Minimum angle for the branch
        self.conv_a = 0.0        # Conversion parameter A
        self.beq = 0.0           # Equivalent branch impedance
        self.k2 = 0.0            # Parameter K2
        self.beq_min = 0.0       # Minimum equivalent branch impedance
        self.beq_max = 0.0       # Maximum equivalent branch impedance
        self.sh_min = 0.0        # Minimum shunt
        self.sh_max = 0.0        # Maximum shunt
        self.gsw = 0.0           # Switching conductance
        self.alpha1 = 0.0        # Parameter Alpha1
        self.alpha2 = 0.0        # Parameter Alpha2
        self.alpha3 = 0.0        # Parameter Alpha3
        self.kdp = 0.0           # Parameter Kdp

        self.is_fubm = False

    def parse_row(self, row):
        """
        Parses a single row of branch data and assigns values to the instance attributes.
        :param row: List of values corresponding to a MATPOWER branch row.
        """
        # Assign values explicitly
        self.f_bus = int(row[0])          # From bus number
        self.t_bus = int(row[1])          # To bus number
        self.br_r = float(row[2])         # Resistance
        self.br_x = float(row[3])         # Reactance
        self.br_b = float(row[4])         # Total line charging susceptance
        self.rate_a = float(row[5])       # MVA rating A
        self.rate_b = float(row[6])       # MVA rating B
        self.rate_c = float(row[7])       # MVA rating C
        self.tap = float(row[8])          # Transformer turns ratio
        self.shift = float(row[9])        # Transformer phase shift angle
        self.br_status = int(row[10])     # Branch status
        self.angmin = float(row[11])      # Minimum angle difference
        self.angmax = float(row[12])      # Maximum angle difference

        if len(row) > 13:
            self.pf = float(row[13])          # Real power injected at "from" bus end
            self.qf = float(row[14])          # Reactive power injected at "from" bus end
            self.pt = float(row[15])          # Real power injected at "to" bus end
            self.qt = float(row[16])          # Reactive power injected at "to" bus end
            self.mu_sf = float(row[17])       # Multiplier on MVA limit at "from" bus
            self.mu_st = float(row[18])       # Multiplier on MVA limit at "to" bus
            self.mu_angmin = float(row[19])   # Multiplier lower angle difference limit
            self.mu_angmax = float(row[20])   # Multiplier upper angle difference limit

        if len(row) == 37:

            self.vf_set = float(row[21])      # Voltage at "from" bus
            self.vt_set = float(row[22])      # Voltage at "to" bus
            self.ma_max = float(row[23])      # Maximum angle
            self.ma_min = float(row[24])      # Minimum angle
            self.conv_a = float(row[25])      # Conversion parameter A
            self.beq = float(row[26])         # Equivalent branch impedance
            self.k2 = float(row[27])          # Parameter K2
            self.beq_min = float(row[28])     # Minimum equivalent branch impedance
            self.beq_max = float(row[29])     # Maximum equivalent branch impedance
            self.sh_min = float(row[30])      # Minimum shunt
            self.sh_max = float(row[31])      # Maximum shunt
            self.gsw = float(row[32])         # Switching conductance
            self.alpha1 = float(row[33])      # Parameter Alpha1
            self.alpha2 = float(row[34])      # Parameter Alpha2
            self.alpha3 = float(row[35])      # Parameter Alpha3
            self.kdp = float(row[36])         # Parameter Kdp

            self.is_fubm = True

