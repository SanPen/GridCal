# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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


class RawVscDCLine(RawObject):

    def __init__(self):
        RawObject.__init__(self, "VSC DC line")

        self.O1 = 0
        self.F1 = 0.0
        self.O2 = 0
        self.F2 = 0.0
        self.O3 = 0
        self.F3 = 0.0
        self.O4 = 0
        self.F4 = 0.0

        self.NAME = ""
        self.MDC = 1
        self.RDC = 0

        self.IBUS1 = 0
        self.TYPE1 = 1
        self.MODE1 = 1
        self.DCSET1 = 0
        self.ACSET1 = 1.0
        self.ALOSS1 = 0
        self.BLOSS1 = 0
        self.MINLOSS1 = 0
        self.SMAX1 = 0
        self.IMAX1 = 0
        self.PWF1 = 0
        self.MAXQ1 = 0
        self.MINQ1 = 0
        self.REMOT1 = 0  # not in PSS 35

        self.VSREG1 = 0  # from PSSe 35
        self.NREG1 = 0  # from PSSe 35
        self.RMPCT1 = 0

        self.IBUS2 = 0
        self.TYPE2 = 0
        self.MODE2 = 0
        self.DCSET2 = 0
        self.ACSET2 = 0
        self.ALOSS2 = 0
        self.BLOSS2 = 0
        self.MINLOSS2 = 0
        self.SMAX2 = 0
        self.IMAX2 = 0
        self.PWF2 = 0
        self.MAXQ2 = 0
        self.MINQ2 = 0
        self.REMOT2 = 0  # not in PSSe 35
        self.VSREG2 = 0  # from PSSe 35
        self.NREG2 = 0  # from PSSe 35
        self.RMPCT2 = 100.0

        self.register_property(property_name='NAME',
                               rawx_key='name',
                               class_type=str,
                               description='Device name',
                               max_chars=12)

        self.register_property(property_name='MDC',
                               rawx_key='mdc',
                               class_type=int,
                               description='Control mode:\n'
                                           '•  0 - for out-of-service\n'
                                           '•  1 - for in-service',
                               min_value=0,
                               max_value=1)

        self.register_property(property_name='RDC',
                               rawx_key='rdc',
                               class_type=float,
                               description='The dc line resistance',
                               min_value=0,
                               max_value=999999,
                               unit=Unit.get_ohm())

        # --------------------------------------------------------------------------------------------------------------

        self.register_property(property_name='IBUS1',
                               rawx_key='ibus1',
                               class_type=int,
                               description='Converter bus number, ',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='TYPE1',
                               rawx_key='type1',
                               class_type=int,
                               description='Code for the type of converter dc control:\n'
                                           '•  0 - for converter out-of-service\n'
                                           '•  1 - for dc voltage control\n'
                                           '•  2 -for MW control\n'
                                           'When both converters are in-service, exactly one '
                                           'converter of each VSC dc line must be TYPE 1.',
                               min_value=0,
                               max_value=2)

        self.register_property(property_name='MODE1',
                               rawx_key='mode1',
                               class_type=int,
                               description='Converter ac control mode:'
                                           '1 -> AC voltage control\n'
                                           '2 -> fixed AC power factor\n',
                               min_value=0,
                               max_value=2)

        self.register_property(property_name='DCSET1',
                               rawx_key='dcset1',
                               class_type=float,
                               description='Converter dc setpoint (see manual)',
                               unit=Unit.get_mw())

        self.register_property(property_name='ACSET1',
                               rawx_key='acset1',
                               class_type=float,
                               description='Converter ac setpoint. 1-> AC voltage, 2-> power factor',
                               unit=Unit.get_pu())

        self.register_property(property_name='ALOSS1',
                               rawx_key='aloss1',
                               class_type=float,
                               description='Losses constant coefficient: loss = ALOSS + (Idc * BLOSS)',
                               unit=Unit.get_kw())

        self.register_property(property_name='BLOSS1',
                               rawx_key='bloss1',
                               class_type=float,
                               description='Losses proportional coefficient: loss = ALOSS + (Idc * BLOSS)',
                               unit=Unit.get_kw(),
                               denominator_unit=Unit.get_a())

        self.register_property(property_name='MINLOSS1',
                               rawx_key='minloss1',
                               class_type=int,
                               description='Minimum converter losses',
                               unit=Unit.get_kw())

        self.register_property(property_name='SMAX1',
                               rawx_key='smax1',
                               class_type=float,
                               description='Converter MVA rating',
                               unit=Unit.get_mw())

        self.register_property(property_name='IMAX1',
                               rawx_key='imax1',
                               class_type=float,
                               description='Converter ac current rating',
                               unit=Unit.get_a())

        self.register_property(property_name='PWF1',
                               rawx_key='pwf1',
                               class_type=float,
                               description='Power weighting factor fraction (see manual)',
                               min_value=0.0,
                               max_value=1.0)

        self.register_property(property_name='MAXQ1',
                               rawx_key='maxq1',
                               class_type=float,
                               description='Reactive power upper limit (see manual)',
                               unit=Unit.get_mvar())

        self.register_property(property_name='MINQ1',
                               rawx_key='minq1',
                               class_type=float,
                               description='Reactive power lower limit (see manual)',
                               unit=Unit.get_mvar())

        self.register_property(property_name='REMOT1',
                               rawx_key='remot1',
                               class_type=int,
                               description='Control bus (see manual)',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='VSREG1',
                               rawx_key='vseg1',
                               class_type=int,
                               description='Control bus (see manual)',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='NREG1',
                               rawx_key='nreg1',
                               class_type=int,
                               description='Control node (see manual)',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='RMPCT1',
                               rawx_key='rmpct1',
                               class_type=float,
                               description='Percent of the total Mvar required to hold the voltage at '
                                           'the bus controlled by IBUS (see manual)',
                               unit=Unit.get_percent())

        # --------------------------------------------------------------------------------------------------------------

        self.register_property(property_name='IBUS2',
                               rawx_key='ibus2',
                               class_type=int,
                               description='Converter bus number',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='TYPE2',
                               rawx_key='type2',
                               class_type=int,
                               description='Converter ac control mode:'
                                           '0 -> out of service\n'
                                           '1 -> AC voltage control\n'
                                           '2 -> fixed AC power factor\n',
                               min_value=0,
                               max_value=2)

        self.register_property(property_name='MODE2',
                               rawx_key='mode2',
                               class_type=int,
                               description='Converter ac control mode:'
                                           '1 -> AC voltage control\n'
                                           '2 -> fixed AC power factor\n',
                               min_value=1,
                               max_value=2)

        self.register_property(property_name='DCSET2',
                               rawx_key='dcset2',
                               class_type=float,
                               description='Converter dc setpoint (see manual)',
                               unit=Unit.get_mw())

        self.register_property(property_name='ACSET2',
                               rawx_key='acset2',
                               class_type=float,
                               description='Converter ac setpoint. 1-> AC voltage, 2-> power factor',
                               unit=Unit.get_pu())

        self.register_property(property_name='ALOSS2',
                               rawx_key='aloss2',
                               class_type=float,
                               description='Losses constant coefficient: loss = ALOSS + (Idc * BLOSS)',
                               unit=Unit.get_kw())

        self.register_property(property_name='BLOSS2',
                               rawx_key='bloss2',
                               class_type=float,
                               description='Losses proportional coefficient: loss = ALOSS + (Idc * BLOSS)',
                               unit=Unit.get_kw(),
                               denominator_unit=Unit.get_a())

        self.register_property(property_name='MINLOSS2',
                               rawx_key='minloss2',
                               class_type=int,
                               description='Minimum converter losses',
                               unit=Unit.get_kw())

        self.register_property(property_name='SMAX2',
                               rawx_key='smax2',
                               class_type=float,
                               description='Converter MVA rating',
                               unit=Unit.get_mw())

        self.register_property(property_name='IMAX2',
                               rawx_key='imax2',
                               class_type=float,
                               description='Converter ac current rating',
                               unit=Unit.get_a())

        self.register_property(property_name='PWF2',
                               rawx_key='pwf2',
                               class_type=float,
                               description='Power weighting factor fraction (see manual)')

        self.register_property(property_name='MAXQ2',
                               rawx_key='maxq2',
                               class_type=float,
                               description='Reactive power upper limit (see manual)',
                               unit=Unit.get_mvar())

        self.register_property(property_name='MINQ2',
                               rawx_key='minq2',
                               class_type=float,
                               description='Reactive power lower limit (see manual)',
                               unit=Unit.get_mvar())

        self.register_property(property_name='REMOT2',
                               rawx_key='remot2',
                               class_type=int,
                               description='Control bus (see manual)',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='VSREG2',
                               rawx_key='vseg2',
                               class_type=int,
                               description='Control bus (see manual)',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='NREG2',
                               rawx_key='nreg2',
                               class_type=int,
                               description='Control node (see manual)',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='RMPCT2',
                               rawx_key='rmpct2',
                               class_type=float,
                               description='Percent of the total Mvar required to hold the voltage at '
                                           'the bus controlled by IBUS (see manual)',
                               unit=Unit.get_percent())

        # --------------------------------------------------------------------------------------------------------------
        for i in range(4):
            self.register_property(property_name="O{}".format(i + 1),
                                   rawx_key="o{}".format(i + 1),
                                   class_type=int,
                                   description="Owner number {}".format(i + 1),
                                   min_value=1,
                                   max_value=9999)
            self.register_property(property_name="F{}".format(i + 1),
                                   rawx_key="f{}".format(i + 1),
                                   class_type=float,
                                   description="Ownership fraction {}".format(i + 1),
                                   min_value=0.0,
                                   max_value=1.0)

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        var = [self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4]

        if version >= 35:

            '''
            NAME, MDC, RDC, O1, F1, ... O4, F4
            IBUS,TYPE,MODE,DCSET,ACSET,ALOSS,BLOSS,MINLOSS,SMAX,IMAX,PWF,MAXQ,MINQ,REMOT,RMPCT
            '''

            self.NAME, self.MDC, self.RDC, *var = data[0]

            self.IBUS1, self.TYPE1, self.MODE1, self.DCSET1, self.ACSET1, self.ALOSS1, self.BLOSS1, self.MINLOSS1, \
            self.SMAX1, self.IMAX1, self.PWF1, self.MAXQ1, self.MINQ1, self.VSREG1, self.NREG1, self.RMPCT1 = data[1]

            self.IBUS2, self.TYPE2, self.MODE2, self.DCSET2, self.ACSET2, self.ALOSS2, self.BLOSS2, self.MINLOSS2, \
            self.SMAX2, self.IMAX2, self.PWF2, self.MAXQ2, self.MINQ2, self.VSREG2, self.NREG2, self.RMPCT2 = data[2]

        if 30 <= version <= 34:

            '''
            NAME, MDC, RDC, O1, F1, ... O4, F4
            IBUS,TYPE,MODE,DCSET,ACSET,ALOSS,BLOSS,MINLOSS,SMAX,IMAX,PWF,MAXQ,MINQ,REMOT,RMPCT
            '''

            self.NAME, self.MDC, self.RDC, *var = data[0]

            self.IBUS1, self.TYPE1, self.MODE1, self.DCSET1, self.ACSET1, self.ALOSS1, self.BLOSS1, self.MINLOSS1, \
            self.SMAX1, self.IMAX1, self.PWF1, self.MAXQ1, self.MINQ1, self.REMOT1, self.RMPCT1 = data[1]

            self.IBUS2, self.TYPE2, self.MODE2, self.DCSET2, self.ACSET2, self.ALOSS2, self.BLOSS2, self.MINLOSS2, \
            self.SMAX2, self.IMAX2, self.PWF2, self.MAXQ2, self.MINQ2, self.REMOT2, self.RMPCT2 = data[2]

        elif version == 29:

            '''
            'NAME', MDC, RDC, O1, F1, ... O4, F4
            IBUS,TYPE,MODE,DCSET,ACSET,ALOSS,BLOSS,MINLOSS,SMAX,IMAX,PWF,MAXQ,MINQ,REMOT,RMPCT
            IBUS,TYPE,MODE,DCSET,ACSET,ALOSS,BLOSS,MINLOSS,SMAX,IMAX,PWF,MAXQ,MINQ,REMOT,RMPCT
            '''

            self.NAME, self.MDC, self.RDC, *var = data[0]

            self.IBUS1, self.TYPE1, self.MODE1, self.DCSET1, self.ACSET1, self.ALOSS1, self.BLOSS1, self.MINLOSS1, \
            self.SMAX1, self.IMAX1, self.PWF1, self.MAXQ1, self.MINQ1, self.REMOT1, self.RMPCT1 = data[1]

            self.IBUS2, self.TYPE2, self.MODE2, self.DCSET2, self.ACSET2, self.ALOSS2, self.BLOSS2, self.MINLOSS2, \
            self.SMAX2, self.IMAX2, self.PWF2, self.MAXQ2, self.MINQ2, self.REMOT2, self.RMPCT2 = data[2]

        else:
            logger.add_warning('Version not implemented for VSC-DC Lines', str(version))

    def get_raw_line(self, version):

        var = [self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4]

        if version >= 35:
            '''
            NAME, MDC, RDC, O1, F1, ... O4, F4
            IBUS,TYPE,MODE,DCSET,ACSET,ALOSS,BLOSS,MINLOSS,SMAX,IMAX,PWF,MAXQ,MINQ,REMOT,RMPCT
            '''

            l0 = self.format_raw_line([self.NAME, self.MDC, self.RDC] + var)

            l1 = self.format_raw_line([self.IBUS1, self.TYPE1, self.MODE1, self.DCSET1, self.ACSET1, self.ALOSS1,
                                      self.BLOSS1, self.MINLOSS1, self.SMAX1, self.IMAX1, self.PWF1,
                                      self.MAXQ1, self.MINQ1, self.VSREG1, self.NREG1, self.RMPCT1])

            l2 = self.format_raw_line([self.IBUS2, self.TYPE2, self.MODE2, self.DCSET2, self.ACSET2, self.ALOSS2,
                                      self.BLOSS2, self.MINLOSS2, self.SMAX2, self.IMAX2, self.PWF2, self.MAXQ2,
                                      self.MINQ2, self.VSREG2, self.NREG2, self.RMPCT2])

            return l0 + '\n' + l1 + '\n' + l2

        if 30 <= version <= 34:

            '''
            NAME, MDC, RDC, O1, F1, ... O4, F4
            IBUS,TYPE,MODE,DCSET,ACSET,ALOSS,BLOSS,MINLOSS,SMAX,IMAX,PWF,MAXQ,MINQ,REMOT,RMPCT
            '''

            l0 = self.format_raw_line([self.NAME, self.MDC, self.RDC] + var)

            l1 = self.format_raw_line([self.IBUS1, self.TYPE1, self.MODE1, self.DCSET1, self.ACSET1, self.ALOSS1,
                                       self.BLOSS1, self.MINLOSS1, self.SMAX1, self.IMAX1, self.PWF1, self.MAXQ1,
                                       self.MINQ1, self.REMOT1, self.RMPCT1])

            l2 = self.format_raw_line([self.IBUS2, self.TYPE2, self.MODE2, self.DCSET2, self.ACSET2, self.ALOSS2,
                                       self.BLOSS2, self.MINLOSS2, self.SMAX2, self.IMAX2, self.PWF2, self.MAXQ2,
                                       self.MINQ2, self.REMOT2, self.RMPCT2])

            return l0 + '\n' + l1 + '\n' + l2

        elif version == 29:

            '''
            'NAME', MDC, RDC, O1, F1, ... O4, F4
            IBUS,TYPE,MODE,DCSET,ACSET,ALOSS,BLOSS,MINLOSS,SMAX,IMAX,PWF,MAXQ,MINQ,REMOT,RMPCT
            IBUS,TYPE,MODE,DCSET,ACSET,ALOSS,BLOSS,MINLOSS,SMAX,IMAX,PWF,MAXQ,MINQ,REMOT,RMPCT
            '''

            l0 = self.format_raw_line([self.NAME, self.MDC, self.RDC] + var)

            l1 = self.format_raw_line([self.IBUS1, self.TYPE1, self.MODE1, self.DCSET1, self.ACSET1,
                                       self.ALOSS1, self.BLOSS1, self.MINLOSS1, self.SMAX1, self.IMAX1,
                                       self.PWF1, self.MAXQ1, self.MINQ1, self.REMOT1, self.RMPCT1])

            l2 = self.format_raw_line([self.IBUS2, self.TYPE2, self.MODE2, self.DCSET2, self.ACSET2,
                                       self.ALOSS2, self.BLOSS2, self.MINLOSS2, self.SMAX2, self.IMAX2,
                                       self.PWF2, self.MAXQ2, self.MINQ2, self.REMOT2, self.RMPCT2])

            return l0 + '\n' + l1 + '\n' + l2

        else:
            raise Exception('Version not implemented for VSC-DC Lines ' + str(version))

    def get_id(self):
        """
        Get the element PSSE ID
        :return:
        """
        return "{0}_{1}_1".format(self.IBUS1, self.IBUS2)


