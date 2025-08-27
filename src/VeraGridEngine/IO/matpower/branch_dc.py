# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

class MatAcDcBranch:
    """
    Class to parse and write DC branch data from MATPOWER .m files.
    """
    def __init__(self):
        # Initialize all attributes to default values
        self.fbusdc = 0         # From DC bus number
        self.tbusdc = 0         # To DC bus number
        self.r = 0.0            # Resistance (p.u.)
        self.l = 0.0            # Inductance (p.u.)
        self.c = 0.0            # Capacitance (p.u.)
        self.rate_a = 0.0       # MVA rating A (long-term)
        self.rate_b = 0.0       # MVA rating B (short-term)
        self.rate_c = 0.0       # MVA rating C (emergency)
        self.status = 1         # Branch status (1=In-service, 0=Out-of-service)

    def parse_row(self, row):
        """
        Parses a single row of DC branch data and assigns values to the instance attributes.
        :param row: List of values corresponding to a MATPOWER DC branch row.
        """
        # Assign values explicitly
        self.fbusdc = int(row[0])         # From DC bus number
        self.tbusdc = int(row[1])         # To DC bus number
        self.r = float(row[2])            # Resistance
        self.l = float(row[3])            # Inductance
        self.c = float(row[4])            # Capacitance
        self.rate_a = float(row[5])       # MVA rating A
        self.rate_b = float(row[6])       # MVA rating B
        self.rate_c = float(row[7])       # MVA rating C
        self.status = int(row[8])         # Branch status
