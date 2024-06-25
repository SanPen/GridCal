# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
from GridCalEngine.IO.base.units import Unit
from GridCalEngine.IO.raw.devices.psse_object import RawObject
from GridCalEngine.basic_structures import Logger


class RawSwitchedShunt(RawObject):

    def __init__(self):
        RawObject.__init__(self, "Switched shunt")

        self.I = 0
        self.ID = ''
        '''
        MODSW:
        0 - locked
        1 - discrete adjustment, local voltage control
        2 - continuous adjustment, local voltage control
        3 - discrete adjustment, local generator reactive power control (WTF?)
        4 - discrete adjustment, branch voltage control (see RMIDNT)
        5 - discrete adjustment, local admittance control (WTF?)
        6 - discrete adjustment, reactive power control for FACTS (see RMIDNT)
        '''
        self.MODSW = 0
        self.ADJM = 0
        self.STAT = 0
        self.VSWHI = 1
        self.VSWLO = 1
        self.SWREM = 0
        self.SWREG = 0
        self.NREG = 0
        self.RMPCT = 1
        self.RMIDNT = ''
        self.BINIT = 0

        self.S1 = 0
        self.S2 = 0
        self.S3 = 0
        self.S4 = 0
        self.S5 = 0
        self.S6 = 0
        self.S7 = 0
        self.S8 = 0

        self.N1 = 0
        self.N2 = 0
        self.N3 = 0
        self.N4 = 0
        self.N5 = 0
        self.N6 = 0
        self.N7 = 0
        self.N8 = 0

        self.B1 = 0.0
        self.B2 = 0.0
        self.B3 = 0.0
        self.B4 = 0.0
        self.B5 = 0.0
        self.B6 = 0.0
        self.B7 = 0.0
        self.B8 = 0.0

        self.register_property(property_name="I",
                               rawx_key="ibus",
                               class_type=int,
                               description="Bus number",
                               min_value=1,
                               max_value=999997)

        self.register_property(property_name="ID",
                               rawx_key="shntid",
                               class_type=str,
                               description="Load 2-character ID",
                               max_chars=2)

        self.register_property(property_name="MODSW",
                               rawx_key="modsw",
                               class_type=int,
                               description="Control mode",
                               min_value=0,
                               max_value=6)

        self.register_property(property_name="ADJM",
                               rawx_key="adjm",
                               class_type=int,
                               description="Adjustment method",
                               min_value=0,
                               max_value=1)

        self.register_property(property_name="STAT",
                               rawx_key="stat",
                               class_type=int,
                               description="Status",
                               min_value=0,
                               max_value=1)

        self.register_property(property_name="VSWHI",
                               rawx_key="vswhi",
                               class_type=float,
                               description="Controlled voltage upper limit",
                               unit=Unit.get_pu())

        self.register_property(property_name="VSWLO",
                               rawx_key="vswlo",
                               class_type=float,
                               description="Controlled voltage upper limit",
                               unit=Unit.get_pu())

        self.register_property(property_name="SWREG",
                               rawx_key="swreg",
                               class_type=int,
                               description="Controlled voltage bus",
                               min_value=0,
                               max_value=999997)

        self.register_property(property_name="NREG",
                               rawx_key="nreg",
                               class_type=int,
                               description="Node number of bus IREG when IREG's bus is a substation",
                               min_value=0,
                               max_value=999997)

        self.register_property(property_name="RMPCT",
                               rawx_key="rmpct",
                               class_type=float,
                               description="Percent of the total Mvar required to hold the voltage at the control bus",
                               min_value=0,
                               max_value=100.0,
                               unit=Unit.get_percent())

        self.register_property(property_name="RMIDNT",
                               rawx_key="rmidnt",
                               class_type=str,
                               description="Controlled branch for VSC like operation")

        self.register_property(property_name="BINIT",
                               rawx_key="binit",
                               class_type=float,
                               description="Initial switched shunt admittance",
                               unit=Unit.get_pu())

        for i in range(8):
            self.register_property(property_name="S{}".format(i + 1),
                                   rawx_key="s{}".format(i + 1),
                                   class_type=int,
                                   description="Initial switched shunt status of one for in-service "
                                               "and zero for out-of-service for block i",
                                   min_value=0,
                                   max_value=1)
        for i in range(8):
            self.register_property(property_name="N{}".format(i + 1),
                                   rawx_key="n{}".format(i + 1),
                                   class_type=int,
                                   description="Number of steps for block i",
                                   min_value=0,
                                   max_value=99999)
        for i in range(8):
            self.register_property(property_name="B{}".format(i + 1),
                                   rawx_key="b{}".format(i + 1),
                                   class_type=float,
                                   description="Admittance increment for each of Ni steps in block i;",
                                   unit=Unit.get_mvar())

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        field_values = data[0]

        def parse_dynamic_fields(fields: list[str], values: list):
            """

            :param fields:
            :param values:
            :return:
            """
            for index, value in enumerate(values):
                field = fields[index]
                setattr(self, field, value)

        if version >= 35:
            self.I, self.ID, self.MODSW, self.ADJM, self.STAT, self.VSWHI, self.VSWLO, \
                self.SWREG, self.NREG, self.RMPCT, self.RMIDNT, self.BINIT, *dynamic_values = field_values

            parse_dynamic_fields(
                [
                    'S1', 'N1', 'B1',
                    'S2', 'N2', 'B2',
                    'S3', 'N3', 'B3',
                    'S4', 'N4', 'B4',
                    'S5', 'N5', 'B5',
                    'S6', 'N6', 'B6',
                    'S7', 'N7', 'B7',
                    'S8', 'N8', 'B8'
                ],
                dynamic_values)

        elif version >= 29 <= 34:
            rest = []

            self.I, self.MODSW, self.ADJM, self.STAT, self.VSWHI, self.VSWLO, \
                self.SWREM, self.RMPCT, self.RMIDNT, self.BINIT, *dynamic_values = field_values

            parse_dynamic_fields(
                [
                    'N1', 'B1',
                    'N2', 'B2',
                    'N3', 'B3',
                    'N4', 'B4',
                    'N5', 'B5',
                    'N6', 'B6',
                    'N7', 'B7',
                    'N8', 'B8'
                ],
                dynamic_values)

            # In this version, the RAW format does not support the S.
            # S is set to 1 by default.
            for i in range(1, 9):
                if getattr(self, f"N{i}") != 0:
                    setattr(self, f"S{i}", 1)
        else:
            logger.add_warning('Shunt not implemented for the version', str(version))

    def get_raw_line(self, version):

        if version >= 35:

            var = [self.N1, self.B1,
                   self.N2, self.B2,
                   self.N3, self.B3,
                   self.N4, self.B4,
                   self.N5, self.B5,
                   self.N6, self.B6,
                   self.N7, self.B7,
                   self.N8, self.B8, ]

            return self.format_raw_line([self.I, self.ID, self.MODSW, self.ADJM, self.STAT, self.VSWHI, self.VSWLO,
                                         self.SWREG, self.NREG, self.RMPCT, self.RMIDNT, self.BINIT] + var)

        elif version >= 29 <= 34:

            var = [self.N1, self.B1,
                   self.N2, self.B2,
                   self.N3, self.B3,
                   self.N4, self.B4,
                   self.N5, self.B5,
                   self.N6, self.B6,
                   self.N7, self.B7,
                   self.N8, self.B8, ]

            return self.format_raw_line([self.I, self.MODSW, self.ADJM, self.STAT, self.VSWHI, self.VSWLO,
                                         self.SWREM, self.RMPCT, self.RMIDNT, self.BINIT] + var)
        else:
            raise Exception('Shunt not implemented for the version ' + str(version))

    def get_id(self):
        """
        Get the element PSSE ID
        :return: 
        """
        return "{0}_{1}".format(self.I, self.ID)
