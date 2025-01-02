# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

class MatAcDcBus:
    """
    Class to parse and write DC bus data from MATPOWER .m files.
    """
    def __init__(self):
        # Initialize all attributes to default values
        self.busdc_i = 0         # DC bus number
        self.grid = 0           # Associated grid or area identifier
        self.pdc = 0.0          # DC power demand or injection (MW)
        self.vdc = 1.0          # DC voltage magnitude (p.u.)
        self.base_kvdc = 0.0    # Base DC voltage (kV)
        self.vdcmax = 1.1       # Maximum DC voltage (p.u.)
        self.vdcmin = 0.9       # Minimum DC voltage (p.u.)
        self.cdc = 0.0          # DC capacitance (F)

    def parse_row(self, row):
        """
        Parses a single row of DC bus data and assigns values to the instance attributes.
        :param row: List of values corresponding to a MATPOWER DC bus row.
        """
        # Assign values explicitly
        self.busdc_i = int(row[0])         # DC bus number
        self.grid = int(row[1])           # Associated grid or area identifier
        self.pdc = float(row[2])          # DC power demand or injection
        self.vdc = float(row[3])          # DC voltage magnitude
        self.base_kvdc = float(row[4])    # Base DC voltage
        self.vdcmax = float(row[5])       # Maximum DC voltage
        self.vdcmin = float(row[6])       # Minimum DC voltage
        self.cdc = float(row[7])          # DC capacitance
