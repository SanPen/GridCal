# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np


class MatpowerGenerator:
    """
    Class to parse and write generator data from MATPOWER .m files.
    """
    def __init__(self):
        # Initialize all attributes to default values
        self.gen_bus = 0       # Bus number
        self.pg = 0.0          # Real power output (MW)
        self.qg = 0.0          # Reactive power output (MVAr)
        self.qmax = 0.0        # Maximum reactive power output (MVAr)
        self.qmin = 0.0        # Minimum reactive power output (MVAr)
        self.vg = 1.0          # Voltage magnitude setpoint (p.u.)
        self.mbase = 100.0     # Machine MVA base
        self.gen_status = 1    # Generator status (1=In-service, 0=Out-of-service)
        self.pmax = 0.0        # Maximum real power output (MW)
        self.pmin = 0.0        # Minimum real power output (MW)
        self.pc1 = 0.0         # Lower real power output of PQ capability curve (MW)
        self.pc2 = 0.0         # Upper real power output of PQ capability curve (MW)
        self.qc1min = 0.0      # Minimum reactive power output at Pc1 (MVAr)
        self.qc1max = 0.0      # Maximum reactive power output at Pc1 (MVAr)
        self.qc2min = 0.0      # Minimum reactive power output at Pc2 (MVAr)
        self.qc2max = 0.0      # Maximum reactive power output at Pc2 (MVAr)
        self.ramp_agc = 0.0    # Ramp rate for load following/AGC (MW/min)
        self.ramp_10 = 0.0     # Ramp rate for 10-minute reserves (MW)
        self.ramp_30 = 0.0     # Ramp rate for 30-minute reserves (MW)
        self.ramp_q = 0.0      # Ramp rate for reactive power (MVAr/min)
        self.apf = 0.0         # Area participation factor
        self.mu_pmax = 0.0     # Kuhn-Tucker multiplier on upper Pg limit
        self.mu_pmin = 0.0     # Kuhn-Tucker multiplier on lower Pg limit
        self.mu_qmax = 0.0     # Kuhn-Tucker multiplier on upper Qg limit
        self.mu_qmin = 0.0     # Kuhn-Tucker multiplier on lower Qg limit
        self.dispatchable_gen = 0  # Dispatchable generator flag
        self.fix_power_gen = 0     # Fixed power generation flag

        # extra stuff to handle the cost data
        self.name = ""
        self.StartupCost = 0.0
        self.ShutdownCost = 0.0
        self.Cost0 = 0.0
        self.Cost = 0.0
        self.Cost2 = 0.0

    def parse_row(self, row):
        """
        Parses a single row of generator data and assigns values to the instance attributes.
        :param row: List of values corresponding to a MATPOWER generator row.
        """
        # Assign values explicitly
        self.gen_bus = int(row[0])           # Bus number
        self.pg = float(row[1])             # Real power output (MW)
        self.qg = float(row[2])             # Reactive power output (MVAr)
        self.qmax = float(row[3])           # Maximum reactive power output
        self.qmin = float(row[4])           # Minimum reactive power output
        self.vg = float(row[5])             # Voltage magnitude setpoint
        self.mbase = float(row[6])          # Machine MVA base
        self.gen_status = int(row[7])       # Generator status
        self.pmax = float(row[8])           # Maximum real power output
        self.pmin = float(row[9])           # Minimum real power output

        if len(row) > 10:
            self.pc1 = float(row[10])           # Lower real power output of PQ capability curve
            self.pc2 = float(row[11])           # Upper real power output of PQ capability curve
            self.qc1min = float(row[12])        # Minimum reactive power at Pc1
            self.qc1max = float(row[13])        # Maximum reactive power at Pc1
            self.qc2min = float(row[14])        # Minimum reactive power at Pc2
            self.qc2max = float(row[15])        # Maximum reactive power at Pc2
            self.ramp_agc = float(row[16])      # Ramp rate for load following/AGC
            self.ramp_10 = float(row[17])       # Ramp rate for 10-minute reserves
            self.ramp_30 = float(row[18])       # Ramp rate for 30-minute reserves
            self.ramp_q = float(row[19])        # Ramp rate for reactive power
            self.apf = float(row[20])           # Area participation factor

        if len(row) > 21:
            self.mu_pmax = float(row[21])       # Kuhn-Tucker multiplier on upper Pg limit
            self.mu_pmin = float(row[22])       # Kuhn-Tucker multiplier on lower Pg limit
            self.mu_qmax = float(row[23])       # Kuhn-Tucker multiplier on upper Qg limit
            self.mu_qmin = float(row[24])       # Kuhn-Tucker multiplier on lower Qg limit

        if len(row) > 25:
            self.dispatchable_gen = int(row[25])  # Dispatchable generator flag
            self.fix_power_gen = int(row[26])     # Fixed power generation flag


    def parse_cost(self, row, logger):

        curve_model = row[0]
        self.StartupCost = row[1]
        self.ShutdownCost = row[2]
        n_cost = row[3]
        points = row[4:]
        if curve_model == 2:
            if len(points) == 3:
                self.Cost0 = points[2]
                self.Cost = points[1]
                self.Cost2 = points[0]
            elif len(points) == 2:
                self.Cost = points[1]
                self.Cost0 = points[0]
            elif len(points) == 1:
                self.Cost = points[0]
            else:
                logger.add_warning("No curve points declared", self.name, curve_model)

        elif curve_model == 1:
            # fit a quadratic curve
            x = points[0::1]
            y = points[0::2]
            if len(x) == len(y):
                coeff = np.polyfit(x, y, 2)
                self.Cost = coeff[1]
            else:
                logger.add_warning("Curve x not the same length as y", self.name, curve_model)
        else:
            logger.add_warning("Unsupported curve model", self.name, curve_model)