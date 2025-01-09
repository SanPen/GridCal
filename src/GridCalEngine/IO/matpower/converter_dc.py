# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

class MatAcDcConverter:
    """
    Class to parse and write converter data from MATPOWER .m files.
    """

    def __init__(self):
        # Initialize all attributes to default values

        # Converter buses, control parameters and AC system data
        self.busdc_i = 0  # DC bus number
        self.busac_i = 0  # AC bus number

        """
        CONVTYPE_DC constants
        3 DCDROOP - DC voltage droop
        2 DCSLACK - DC slack bus
        1 DCNOSLACK -  constant active power bus
        
        CONVTYPE_AC constants
        2 PVC - constant voltage converter control
        1 PQC - constant reactive power converter control
        """
        self.type_dc = 0  # DC converter type
        self.type_ac = 0  # AC converter type


        self.p_g = 0.0  # Active power generation (MW)
        self.q_g = 0.0  # Reactive power generation (MVAr)
        self.islcc = 0  # is LCC?
        self.vtar = 1.0  # Target voltage (p.u.)

        # Impedance values
        self.rtf = 0.0  # Transformer resistance (p.u.)
        self.xtf = 0.0  # Transformer reactance (p.u.)
        self.transformer = 0  # Transformer presence flag
        self.tm = 0.0  # Transformer tap ratio
        self.bf = 0.0  # Filter susceptance (p.u.)
        self.filter_flag = 0  # Filter presence flag
        self.rc = 0.0  # Reactor resistance (p.u.)
        self.xc = 0.0  # Reactor reactance (p.u.)
        self.reactor = 0  # Reactor presence flag
        self.base_kvac = 0.0  # Base AC voltage (kV)
        self.vmmax = 1.1  # Maximum AC voltage (p.u.)
        self.vmmin = 0.9  # Minimum AC voltage (p.u.)
        self.imax = 0.0  # Maximum current (p.u.)
        self.status = 1  # Converter status (1=In-service, 0=Out-of-service)

        # Converter loss data
        self.loss_a = 0.0  # a, constant loss coefficient (MW)
        self.loss_b = 0.0  # b, linear loss coefficient (kV)
        self.loss_crec = 0.0  # r ec , rectifier quadratic loss coefficient (Ω)
        self.loss_cinv = 0.0  # c i nv , inverter quadratic loss coefficient (Ω)

        # DC voltage droop constants (optional)
        self.droop = 0.0  # k, DC voltage droop (MW/p.u)
        self.pdcset = 0.0  # voltage droop power set-point (MW)
        self.vdcset = 1.0  # voltage droop voltage set-point (p.u.)
        self.dvdcset = 0.0  # voltage droop voltage set-point (p.u.)

        # Columns typically added after the power flow
        self.pacmax = 0.0  # Maximum AC active power (MW)
        self.pacmin = 0.0  # Minimum AC active power (MW)
        self.qacmax = 0.0  # Maximum AC reactive power (MVAr)
        self.qacmin = 0.0  # Minimum AC reactive power (MVAr)

    def parse_row(self, row):
        """
        Parses a single row of converter data and assigns values to the instance attributes.
        :param row: List of values corresponding to a MATPOWER converter row.
        """
        # Assign values explicitly
        self.busdc_i = int(row[0])  # DC bus number
        self.busac_i = int(row[1])  # AC bus number
        self.type_dc = int(row[2])  # DC converter type
        self.type_ac = int(row[3])  # AC converter type
        self.p_g = float(row[4])  # Active power generation
        self.q_g = float(row[5])  # Reactive power generation
        self.islcc = int(row[6])  # Isolated operation flag
        self.vtar = float(row[7])  # Target voltage
        self.rtf = float(row[8])  # Transformer resistance
        self.xtf = float(row[9])  # Transformer reactance
        self.transformer = int(row[10])  # Transformer presence flag
        self.tm = float(row[11])  # Transformer tap ratio
        self.bf = float(row[12])  # Filter susceptance
        self.filter_flag = int(row[13])  # Filter presence flag
        self.rc = float(row[14])  # Reactor resistance
        self.xc = float(row[15])  # Reactor reactance
        self.reactor = int(row[16])  # Reactor presence flag
        self.base_kvac = float(row[17])  # Base AC voltage
        self.vmmax = float(row[18])  # Maximum AC voltage
        self.vmmin = float(row[19])  # Minimum AC voltage
        self.imax = float(row[20])  # Maximum current
        self.status = int(row[21])  # Converter status
        self.loss_a = float(row[22])  # Loss coefficient A
        self.loss_b = float(row[23])  # Loss coefficient B
        self.loss_crec = float(row[24])  # Rectifier constant loss
        self.loss_cinv = float(row[25])  # Inverter constant loss
        self.droop = float(row[26])  # Droop control coefficient
        self.pdcset = float(row[27])  # DC power setpoint
        self.vdcset = float(row[28])  # DC voltage setpoint
        self.dvdcset = float(row[29])  # DC voltage deviation setpoint
        self.pacmax = float(row[30])  # Maximum AC active power
        self.pacmin = float(row[31])  # Minimum AC active power
        self.qacmax = float(row[32])  # Maximum AC reactive power
        self.qacmin = float(row[33])  # Minimum AC reactive power
