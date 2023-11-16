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
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol, Unit
from GridCalEngine.IO.raw.devices.psse_object import RawObject
from GridCalEngine.basic_structures import Logger
from GridCalEngine.IO.raw.raw_functions import get_psse_transformer_impedances
import GridCalEngine.Core.Devices as dev
import numpy as np


class RawTransformer(RawObject):

    def __init__(self):
        RawObject.__init__(self, "Transformer")

        self.windings = 0

        self.I = 0
        self.J = 0
        self.K = 0
        self.CKT = 0
        self.CW = 1
        self.CZ = 1
        self.CM = 1
        self.MAG1 = 0
        self.MAG2 = 0
        self.NMETR = 2
        self.NAME = ""
        self.STAT = 1
        self.VECGRP = ""
        self.ZCOD = 0

        self.R1_2 = 0.0
        self.X1_2 = 0.0
        self.R2_3 = 0.0
        self.X2_3 = 0.0
        self.R3_1 = 0.0
        self.X3_1 = 0.0

        self.SBASE1_2 = 100.0
        self.SBASE2_3 = 100.0
        self.SBASE3_1 = 100.0

        self.VMSTAR = 1.0
        self.ANSTAR = 0.0

        self.WINDV1 = 1.0
        self.NOMV1 = 0
        self.ANG1 = 0

        self.COD1 = 0
        self.CONT1 = 0
        self.NODE1 = 0
        self.RMA1 = 1.1
        self.RMI1 = 0.9
        self.VMA1 = 1.1
        self.VMI1 = 0.9
        self.NTP1 = 33
        self.TAB1 = 0
        self.CR1 = 0
        self.CX1 = 0
        self.CNXA1 = 0

        self.WINDV2 = 0
        self.NOMV2 = 0

        # in case of 3 W
        self.ANG2 = 0

        self.COD2 = 0
        self.CONT2 = 0
        self.NODE2 = 0
        self.RMA2 = 1.1
        self.RMI2 = 0.9
        self.VMA2 = 1.1
        self.VMI2 = 0.9
        self.NTP2 = 33
        self.TAB2 = 0
        self.CR2 = 0
        self.CX2 = 0
        self.CNXA2 = 0

        self.WINDV3 = 0
        self.NOMV3 = 0
        self.ANG3 = 0

        self.COD3 = 0
        self.CONT3 = 0
        self.NODE3 = 0
        self.RMA3 = 1.1
        self.RMI3 = 0.9
        self.VMA3 = 1.1
        self.VMI3 = 0.9
        self.NTP3 = 0
        self.TAB3 = 0
        self.CR3 = 0
        self.CX3 = 0
        self.CNXA3 = 0

        self.RATE1_1 = 0
        self.RATE1_2 = 0
        self.RATE1_3 = 0
        self.RATE1_4 = 0
        self.RATE1_5 = 0
        self.RATE1_6 = 0
        self.RATE1_7 = 0
        self.RATE1_8 = 0
        self.RATE1_9 = 0
        self.RATE1_10 = 0
        self.RATE1_11 = 0
        self.RATE1_12 = 0

        self.RATE2_1 = 0
        self.RATE2_2 = 0
        self.RATE2_3 = 0
        self.RATE2_4 = 0
        self.RATE2_5 = 0
        self.RATE2_6 = 0
        self.RATE2_7 = 0
        self.RATE2_8 = 0
        self.RATE2_9 = 0
        self.RATE2_10 = 0
        self.RATE2_11 = 0
        self.RATE2_12 = 0

        self.RATE3_1 = 0
        self.RATE3_2 = 0
        self.RATE3_3 = 0
        self.RATE3_4 = 0
        self.RATE3_5 = 0
        self.RATE3_6 = 0
        self.RATE3_7 = 0
        self.RATE3_8 = 0
        self.RATE3_9 = 0
        self.RATE3_10 = 0
        self.RATE3_11 = 0
        self.RATE3_12 = 0

        self.O1 = 0
        self.F1 = 0.0
        self.O2 = 0
        self.F2 = 0.0
        self.O3 = 0
        self.F3 = 0.0
        self.O4 = 0
        self.F4 = 0.0

        self.register_property(property_name='I',
                               rawx_key='ibus',
                               class_type=int,
                               description='Bus I number',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='J',
                               rawx_key='jbus',
                               class_type=int,
                               description='Bus J number',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='K',
                               rawx_key='kbus',
                               class_type=int,
                               description='Bus K number',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='CKT',
                               rawx_key='ckt',
                               class_type=str,
                               description='Circuit identifier',
                               max_chars=2)

        self.register_property(property_name='CW',
                               rawx_key='cw',
                               class_type=int,
                               description='Winding input mode (see manual)',
                               min_value=1,
                               max_value=3)

        self.register_property(property_name='CZ',
                               rawx_key='cz',
                               class_type=int,
                               description='Series Impedance input mode (see manual)',
                               min_value=1,
                               max_value=3)

        self.register_property(property_name='CM',
                               rawx_key='cm',
                               class_type=int,
                               description='Magnetizing impedance input mode (see manual)',
                               min_value=1,
                               max_value=2)

        self.register_property(property_name='MAG1',
                               rawx_key='mag1',
                               class_type=int,
                               description='Magnetizing admittance 1 (see manual)')

        self.register_property(property_name='MAG2',
                               rawx_key='mag2',
                               class_type=int,
                               description='Magnetizing admittance 2 (see manual)')

        self.register_property(property_name='NMETR',
                               rawx_key='nmet',
                               class_type=int,
                               description='Non-metered end code (see manual)',
                               min_value=1,
                               max_value=3)

        self.register_property(property_name='NAME',
                               rawx_key='name',
                               class_type=str,
                               description='Name',
                               max_chars=40)

        self.register_property(property_name='STAT',
                               rawx_key='stat',
                               class_type=int,
                               description='Status of the several windings (see manual)',
                               min_value=0,
                               max_value=4)

        self.register_property(property_name='VECGRP',
                               rawx_key='vecgrp',
                               class_type=str,
                               description='Vector group (has zero effect, information only)',
                               max_chars=12)

        self.register_property(property_name='ZCOD',
                               rawx_key='zcod',
                               class_type=int,
                               description='Impedance code (see manual)',
                               min_value=0,
                               max_value=1)

        self.register_property(property_name='R1_2',
                               rawx_key='r1_2',
                               class_type=float,
                               description='1->2 resistance or other stuff (see manual)',
                               unit=Unit.get_pu())

        self.register_property(property_name='X1_2',
                               rawx_key='x1_2',
                               class_type=float,
                               description='1->2 reactance or other stuff (see manual)',
                               unit=Unit.get_pu())

        self.register_property(property_name='R2_3',
                               rawx_key='r2_3',
                               class_type=float,
                               description='2->3 resistance or other stuff (see manual)',
                               unit=Unit.get_pu())

        self.register_property(property_name='X2_3',
                               rawx_key='x2_3',
                               class_type=float,
                               description='2->3 reactance or other stuff (see manual)',
                               unit=Unit.get_pu())

        self.register_property(property_name='R3_1',
                               rawx_key='r3_1',
                               class_type=float,
                               description='3->1 resistance or other stuff (see manual)',
                               unit=Unit.get_pu())

        self.register_property(property_name='X3_1',
                               rawx_key='x3_1',
                               class_type=float,
                               description='3->1 reactance or other stuff (see manual)',
                               unit=Unit.get_pu())

        self.register_property(property_name='SBASE1_2',
                               rawx_key='sbase1_2',
                               class_type=float,
                               description='1->2 base power',
                               unit=Unit.get_mvar())

        self.register_property(property_name='SBASE2_3',
                               rawx_key='sbase2_3',
                               class_type=float,
                               description='2->3 base power',
                               unit=Unit.get_mvar())

        self.register_property(property_name='SBASE3_1',
                               rawx_key='sbase3_1',
                               class_type=float,
                               description='3->1 base power',
                               unit=Unit.get_mvar())

        self.register_property(property_name='VMSTAR',
                               rawx_key='vmstar',
                               class_type=float,
                               description='The voltage magnitude at the center star point',
                               unit=Unit.get_pu())

        self.register_property(property_name='ANSTAR',
                               rawx_key='anstar',
                               class_type=float,
                               description='The bus voltage phase angle at the center star point.',
                               unit=Unit.get_deg())

        # --------------------------------------------------------------------------------------------------------------

        self.register_property(property_name='WINDV1',
                               rawx_key='windv1',
                               class_type=float,
                               description='Winding 1 off-nominal turns ratio or other stuff (see manual)')

        self.register_property(property_name='NOMV1',
                               rawx_key='nomv1',
                               class_type=float,
                               description='Winding 1 voltage base in kV or other stuff (see manual)',
                               unit=Unit.get_kv())

        self.register_property(property_name='ANG1',
                               rawx_key='ang1',
                               class_type=int,
                               description='Winding 1 phase shift angle in degrees.',
                               unit=Unit.get_deg())

        self.register_property(property_name='COD1',
                               rawx_key='cod1',
                               class_type=int,
                               description='Winding 1 control mode.',
                               min_value=-5,
                               max_value=5)
        self.register_property(property_name='CONT1',
                               rawx_key='cont1',
                               class_type=int,
                               description='Control bus for the winding 1.',
                               min_value=0,
                               max_value=999999)
        self.register_property(property_name='NODE1',
                               rawx_key='node1',
                               class_type=int,
                               description='A node number of bus CONT1.',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='RMA1',
                               rawx_key='rma1',
                               class_type=float,
                               description='Winding 1 upper limit depending of COD1 and CW')

        self.register_property(property_name='RMI1',
                               rawx_key='rmi1',
                               class_type=float,
                               description='Winding 1 lower limit depending of COD1 and CW')

        self.register_property(property_name='VMA1',
                               rawx_key='vma1',
                               class_type=float,
                               description='Winding 1 upper voltage limit depending of COD1.')

        self.register_property(property_name='VMI1',
                               rawx_key='vmi1',
                               class_type=float,
                               description='Winding 1 lower voltage limit depending of COD1.')

        self.register_property(property_name='NTP1',
                               rawx_key='ntp1',
                               class_type=int,
                               description='Winding 1 number of tap positions available (see manual)',
                               min_value=2,
                               max_value=9999)

        self.register_property(property_name='TAB1',
                               rawx_key='tab1',
                               class_type=int,
                               description='Winding 1  number  of  a  transformer  impedance  correction  table (see manual)',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='CR1',
                               rawx_key='cr1',
                               class_type=float,
                               description='Winding 1 load drop compensation resistance (see manual)',
                               unit=Unit.get_pu())

        self.register_property(property_name='CX1',
                               rawx_key='cx1',
                               class_type=float,
                               description='Winding 1 load drop compensation reactance (see manual)',
                               unit=Unit.get_pu())

        self.register_property(property_name='CNXA1',
                               rawx_key='cnxa1',
                               class_type=int,
                               description='',
                               min_value=0,
                               max_value=999999)

        for i in range(1, 13):
            self.register_property(property_name='RATE1_{}'.format(i),
                                   rawx_key='wdg1rate{}'.format(i),
                                   class_type=float,
                                   description='Winding rating {}'.format(i),
                                   unit=Unit.get_mva())

        # --------------------------------------------------------------------------------------------------------------

        self.register_property(property_name='WINDV2',
                               rawx_key='windv2',
                               class_type=float,
                               description='Winding 2 off-nominal turns ratio or other stuff (see manual)')

        self.register_property(property_name='NOMV2',
                               rawx_key='nomv2',
                               class_type=float,
                               description='Winding 2 voltage base in kV or other stuff (see manual)',
                               unit=Unit.get_kv())

        self.register_property(property_name='ANG2',
                               rawx_key='ang2',
                               class_type=int,
                               description='Winding 2 phase shift angle in degrees.',
                               unit=Unit.get_deg())

        self.register_property(property_name='COD2',
                               rawx_key='cod2',
                               class_type=int,
                               description='Winding 2 control mode.',
                               min_value=-5,
                               max_value=5)
        self.register_property(property_name='CONT2',
                               rawx_key='cont2',
                               class_type=int,
                               description='Control bus for the winding 2.',
                               min_value=0,
                               max_value=999999)
        self.register_property(property_name='NODE2',
                               rawx_key='node2',
                               class_type=int,
                               description='A node number of bus CONT1.',
                               min_value=0,
                               max_value=999999)
        self.register_property(property_name='RMA2',
                               rawx_key='rma2',
                               class_type=float,
                               description='Winding 2 upper limit depending of COD1 and CW')
        self.register_property(property_name='RMI2',
                               rawx_key='rmi2',
                               class_type=float,
                               description='Winding 2 lower limit depending of COD1 and CW')

        self.register_property(property_name='VMA2',
                               rawx_key='vma2',
                               class_type=float,
                               description='Winding 2 upper voltage limit depending of COD1.')

        self.register_property(property_name='VMI2',
                               rawx_key='vmi2',
                               class_type=float,
                               description='Winding 2 lower voltage limit depending of COD1.')

        self.register_property(property_name='NTP2',
                               rawx_key='ntp2',
                               class_type=int,
                               description='Winding 2 number of tap positions available (see manual)',
                               min_value=2,
                               max_value=9999)
        self.register_property(property_name='TAB2',
                               rawx_key='tab2',
                               class_type=int,
                               description='Winding 2 number  of  a  transformer  impedance  correction  table (see manual)',
                               min_value=0,
                               max_value=999999)
        self.register_property(property_name='CR2',
                               rawx_key='cr2',
                               class_type=float,
                               description='Winding 2 load drop compensation resistance (see manual)',
                               unit=Unit.get_pu())
        self.register_property(property_name='CX2',
                               rawx_key='cx2',
                               class_type=float,
                               description='Winding 1 load drop compensation reactance (see manual)',
                               unit=Unit.get_pu())
        self.register_property(property_name='CNXA2',
                               rawx_key='cnxa2',
                               class_type=int,
                               description='',
                               min_value=0,
                               max_value=999999)

        for i in range(1, 13):
            self.register_property(property_name='RATE2_{}'.format(i),
                                   rawx_key='wdg2rate{}'.format(i),
                                   class_type=float,
                                   description='Winding rating',
                                   unit=Unit.get_mva())

        # --------------------------------------------------------------------------------------------------------------

        self.register_property(property_name='WINDV3',
                               rawx_key='windv3',
                               class_type=float,
                               description='Winding 3 off-nominal turns ratio or other stuff (see manual)')

        self.register_property(property_name='NOMV3',
                               rawx_key='nomv3',
                               class_type=float,
                               description='Winding 3 voltage base in kV or other stuff (see manual)',
                               unit=Unit.get_kv())

        self.register_property(property_name='ANG3',
                               rawx_key='ang3',
                               class_type=int,
                               description='Winding 3 phase shift angle in degrees.',
                               unit=Unit.get_deg())

        self.register_property(property_name='COD3',
                               rawx_key='cod3',
                               class_type=int,
                               description='Winding 3 control mode.',
                               min_value=-5,
                               max_value=5)
        self.register_property(property_name='CONT3',
                               rawx_key='cont3',
                               class_type=int,
                               description='Control bus for the winding 3',
                               min_value=0,
                               max_value=999999)
        self.register_property(property_name='NODE3',
                               rawx_key='node3',
                               class_type=int,
                               description='A node number of bus CONT3.',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='RMA3',
                               rawx_key='rma3',
                               class_type=float,
                               description='Winding 3 upper limit depending of COD1 and CW')

        self.register_property(property_name='RMI3',
                               rawx_key='rmi3',
                               class_type=float,
                               description='Winding 3 lower limit depending of COD1 and CW')

        self.register_property(property_name='VMA3',
                               rawx_key='vma3',
                               class_type=float,
                               description='Winding 3 upper voltage limit depending of COD1.')

        self.register_property(property_name='VMI3',
                               rawx_key='vmi3',
                               class_type=float,
                               description='Winding 3 lower voltage limit depending of COD1.')

        self.register_property(property_name='NTP3',
                               rawx_key='ntp3',
                               class_type=int,
                               description='Winding 3 number of tap positions available (see manual)',
                               min_value=2,
                               max_value=9999)

        self.register_property(property_name='TAB3',
                               rawx_key='tab3',
                               class_type=int,
                               description='Winding 1  number  of  a  transformer  impedance  correction  table (see manual)',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='CR3',
                               rawx_key='cr3',
                               class_type=float,
                               description='Winding 3 load drop compensation resistance (see manual)',
                               unit=Unit.get_pu())

        self.register_property(property_name='CX3',
                               rawx_key='cx3',
                               class_type=float,
                               description='Winding 3 load drop compensation reactance (see manual)',
                               unit=Unit.get_pu())

        self.register_property(property_name='CNXA3',
                               rawx_key='cnxa3',
                               class_type=int,
                               description='',
                               min_value=0,
                               max_value=999999)

        for i in range(1, 13):
            self.register_property(property_name='RATE3_{}'.format(i),
                                   rawx_key='wdg3rate{}'.format(i),
                                   class_type=float,
                                   description='Winding 3 rating {}'.format(i),
                                   unit=Unit.get_mva())

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

        if version >= 34:

            # Line 1: for both types
            self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                self.NAME, self.STAT, *var, self.VECGRP, self.ZCOD = data[0]

            if len(data) == 4:
                self.windings = 2

                '''
                @!  I,   J,   K,'CKT',CW,CZ,CM,  MAG1,    MAG2,NMETR,        'N A M E',        STAT,O1, F1,  O2, F2,  O3, F3,  O4, F4,   'VECGRP', ZCOD
                @!  R1-2,    X1-2,  SBASE1-2,   R2-3,    X2-3,  SBASE2-3,   R3-1,    X3-1,  SBASE3-1, VMSTAR,  ANSTAR
                @!WINDV1, NOMV1,  ANG1, RATE1-1, RATE1-2, RATE1-3, RATE1-4, RATE1-5, RATE1-6, RATE1-7, RATE1-8, RATE1-9, RATE1-10, RATE1-11, RATE1-12,COD1,CONT1,  NOD1,  RMA1,  RMI1,  VMA1,  VMI1, NTP1,TAB1, CR1,   CX1,  CNXA1
                @!WINDV2, NOMV2,  ANG2, RATE2-1, RATE2-2, RATE2-3, RATE2-4, RATE2-5, RATE2-6, RATE2-7, RATE2-8, RATE2-9, RATE2-10, RATE2-11, RATE2-12,COD2,CONT2,  NOD2,  RMA2,  RMI2,  VMA2,  VMI2, NTP2,TAB2, CR2,   CX2,  CNXA2
                @!WINDV3, NOMV3,  ANG3, RATE3-1, RATE3-2, RATE3-3, RATE3-4, RATE3-5, RATE3-6, RATE3-7, RATE3-8, RATE3-9, RATE3-10, RATE3-11, RATE3-12,COD3,CONT3,  NOD3,  RMA3,  RMI3,  VMA3,  VMI3, NTP3,TAB3, CR3,   CX3,  CNXA3
                '''

                self.R1_2, self.X1_2, self.SBASE1_2 = data[1]

                self.WINDV1, self.NOMV1, self.ANG1, \
                    self.RATE1_1, self.RATE1_2, self.RATE1_3, self.RATE1_4, self.RATE1_5, self.RATE1_6, \
                    self.RATE1_7, self.RATE1_8, self.RATE1_9, self.RATE1_10, self.RATE1_11, self.RATE1_12, \
                    self.COD1, self.CONT1, self.NODE1, self.RMA1, \
                    self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1, self.CNXA1 = data[2]

                self.WINDV2, self.NOMV2 = data[3]

            else:
                self.windings = 3

                '''
                I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,'NAME',STAT,O1,F1,...,O4,F4,VECGRP
                R1-2,X1-2,SBASE1-2,R2-3,X2-3,SBASE2-3,R3-1,X3-1,SBASE3-1,VMSTAR,ANSTAR
                WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD1,CONT1,RMA1,RMI1,VMA1,VMI1,NTP1,TAB1,CR1,CX1,CNXA1
                WINDV2,NOMV2,ANG2,RATA2,RATB2,RATC2,COD2,CONT2,RMA2,RMI2,VMA2,VMI2,NTP2,TAB2,CR2,CX2,CNXA2
                WINDV3,NOMV3,ANG3,RATA3,RATB3,RATC3,COD3,CONT3,RMA3,RMI3,VMA3,VMI3,NTP3,TAB3,CR3,CX3,CNXA3
                '''

                self.R1_2, self.X1_2, self.SBASE1_2, self.R2_3, self.X2_3, self.SBASE2_3, self.R3_1, self.X3_1, \
                    self.SBASE3_1, self.VMSTAR, self.ANSTAR = data[1]

                self.WINDV1, self.NOMV1, self.ANG1, \
                    self.RATE1_1, self.RATE1_2, self.RATE1_3, self.RATE1_4, self.RATE1_5, self.RATE1_6, \
                    self.RATE1_7, self.RATE1_8, self.RATE1_9, self.RATE1_10, self.RATE1_11, self.RATE1_12, \
                    self.COD1, self.CONT1, self.NODE1, \
                    self.RMA1, self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1, self.CNXA1 = \
                    data[2]

                self.WINDV2, self.NOMV2, self.ANG2, \
                    self.RATE2_1, self.RATE2_2, self.RATE2_3, self.RATE2_4, self.RATE2_5, self.RATE2_6, \
                    self.RATE2_7, self.RATE2_8, self.RATE2_9, self.RATE2_10, self.RATE2_11, self.RATE2_12, \
                    self.COD2, self.CONT2, self.NODE2, \
                    self.RMA2, self.RMI2, self.VMA2, self.VMI2, self.NTP2, self.TAB2, self.CR2, self.CX2, self.CNXA2 = \
                    data[3]

                self.WINDV3, self.NOMV3, self.ANG3, \
                    self.RATE3_1, self.RATE3_2, self.RATE3_3, self.RATE3_4, self.RATE3_5, self.RATE3_6, \
                    self.RATE3_7, self.RATE3_8, self.RATE3_9, self.RATE3_10, self.RATE3_11, self.RATE3_12, \
                    self.COD3, self.CONT3, self.NODE3, \
                    self.RMA3, self.RMI3, self.VMA3, self.VMI3, self.NTP3, self.TAB3, self.CR3, self.CX3, self.CNXA3 = \
                    data[4]

        elif version == 33:

            # Line 1: for both types
            self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                self.NAME, self.STAT, *var, self.VECGRP = data[0]

            if len(data) == 4:
                self.windings = 2

                '''
                I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,'NAME',STAT,O1,F1,...,O4,F4,VECGRP
                R1-2,X1-2,SBASE1-2
                WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD1,CONT1,RMA1,RMI1,VMA1,VMI1,NTP1,TAB1,CR1,CX1,CNXA1
                WINDV2,NOMV2
                '''

                self.R1_2, self.X1_2, self.SBASE1_2 = data[1]

                n = len(data[2])
                dta = np.zeros(17, dtype=object)
                dta[0:n] = data[2]

                self.WINDV1, self.NOMV1, self.ANG1, self.RATE1_1, self.RATE1_2, self.RATE1_3, self.COD1, self.CONT1, self.RMA1, \
                    self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1, self.CNXA1 = dta

                self.WINDV2, self.NOMV2 = data[3]

            else:
                self.windings = 3

                '''
                I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,'NAME',STAT,O1,F1,...,O4,F4,VECGRP
                R1-2,X1-2,SBASE1-2,R2-3,X2-3,SBASE2-3,R3-1,X3-1,SBASE3-1,VMSTAR,ANSTAR
                WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD1,CONT1,RMA1,RMI1,VMA1,VMI1,NTP1,TAB1,CR1,CX1,CNXA1
                WINDV2,NOMV2,ANG2,RATA2,RATB2,RATC2,COD2,CONT2,RMA2,RMI2,VMA2,VMI2,NTP2,TAB2,CR2,CX2,CNXA2
                WINDV3,NOMV3,ANG3,RATA3,RATB3,RATC3,COD3,CONT3,RMA3,RMI3,VMA3,VMI3,NTP3,TAB3,CR3,CX3,CNXA3
                '''

                self.R1_2, self.X1_2, self.SBASE1_2, self.R2_3, self.X2_3, self.SBASE2_3, self.R3_1, self.X3_1, \
                    self.SBASE3_1, self.VMSTAR, self.ANSTAR = data[1]

                self.WINDV1, self.NOMV1, self.ANG1, self.RATE1_1, self.RATE1_2, self.RATE1_3, self.COD1, self.CONT1, \
                    self.RMA1, self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1, self.CNXA1 = \
                    data[2]

                self.WINDV2, self.NOMV2, self.ANG2, self.RATE2_1, self.RATE2_1, self.RATE2_3, self.COD2, self.CONT2, \
                    self.RMA2, self.RMI2, self.VMA2, self.VMI2, self.NTP2, self.TAB2, self.CR2, self.CX2, self.CNXA2 = \
                    data[3]

                self.WINDV3, self.NOMV3, self.ANG3, self.RATE3_1, self.RATE3_2, self.RATE3_3, self.COD3, self.CONT3, \
                    self.RMA3, self.RMI3, self.VMA3, self.VMI3, self.NTP3, self.TAB3, self.CR3, self.CX3, self.CNXA3 = \
                    data[4]

        elif version == 32:

            '''
            I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,'NAME',STAT,O1,F1,...,O4,F4
      
            R1-2,X1-2,SBASE1-2,R2-3,X2-3,SBASE2-3,R3-1,X3-1,SBASE3-1,VMSTAR,ANSTAR
      
            WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD1,CONT1,RMA1,RMI1,VMA1,VMI1,NTP1,TAB1,CR1,CX1,CNXA1
      
            WINDV2,NOMV2,ANG2,RATA2,RATB2,RATC2,COD2,CONT2,RMA2,RMI2,VMA2,VMI2,NTP2,TAB2,CR2,CX2,CNXA2
            WINDV3,NOMV3,ANG3,RATA3,RATB3,RATC3,COD3,CONT3,RMA3,RMI3,VMA3,VMI3,NTP3,TAB3,CR3,CX3,CNXA3
            '''

            # Line 1: for both types
            self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                self.NAME, self.STAT, *var = data[0]

            if len(data[1]) == 3:
                # 2-windings
                self.windings = 2
                self.R1_2, self.X1_2, self.SBASE1_2 = data[1]
            elif len(data[1]) == 2:
                # 2-windings
                self.windings = 2
                self.R1_2, self.X1_2 = data[1]
                self.SBASE1_2 = 100.0  # 100 MVA by default
            else:
                # 3-windings
                self.windings = 3
                self.R1_2, self.X1_2, self.SBASE1_2, self.R2_3, self.X2_3, self.SBASE2_3, self.R3_1, \
                    self.X3_1, self.SBASE3_1, self.VMSTAR, self.ANSTAR = data[1]

            # line 3: for both types
            n = len(data[2])
            dta = np.zeros(17, dtype=object)
            dta[0:n] = data[2]
            self.WINDV1, self.NOMV1, self.ANG1, self.RATE1_1, self.RATE1_2, self.RATE1_3, self.COD1, self.CONT1, self.RMA1, \
                self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1, self.CNXA1 = dta

            # line 4
            if len(data[3]) == 2:
                # 2-windings
                self.windings = 2
                self.WINDV2, self.NOMV2 = data[3]
            else:
                # 3 - windings
                self.windings = 3
                self.WINDV2, self.NOMV2, self.ANG2, self.RATE2_1, self.RATE2_2, self.RATE2_3, self.COD2, self.CONT2, \
                    self.RMA2, self.RMI2, self.VMA2, self.VMI2, self.NTP2, self.TAB2, self.CR2, self.CX2, self.CNXA2, \
                    self.WINDV3, self.NOMV3, self.ANG3, self.RATA3, self.RATB3, self.RATC3, self.COD3, self.CONT3, \
                    self.RMA3, self.RMI3, self.VMA3, self.VMI3, self.NTP3, self.TAB3, \
                    self.CR3, self.CX3, self.CNXA3 = data[3]

        elif version == 30:

            """
            I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,'NAME',STAT,Ol,Fl 04,F4
      
            R1—2,X1—2,SBASE1—2,R2—3,X2—3,SBASE2—3,R3—1,X3—1,SBASE3—1,VMSTAR,ANSTAR
      
            WINDV1,NOMV1,ANG1, RATA1, BATB1, RATC1, COD1, CONT1, RMA1, RMI1,VMA1,VMI1,NTP1, TAB1, CR1, CX1
      
            WINDV2 ,NOMV2 , ANG2 , RATA2 , BATB2 , RATC2, COD2, CONT2 , RMA2 , RMI2 , VMA2 , VMI2 ,NTP2, TAB2,CR2, CX2
            WINDV3,NOMV3,ANG3, RATA3, BATB3, RATC3, COD3, CONT3, RMA3, RMI3,VMA3,VMI3,NTP3, TAB3, CR3, CX3
            """

            self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                self.NAME, self.STAT, *var = data[0]

            if len(data[1]) == 3:
                # 2-windings
                self.windings = 2
                self.R1_2, self.X1_2, self.SBASE1_2 = data[1]
            elif len(data[1]) == 2:
                # 2-windings
                self.windings = 2
                self.R1_2, self.X1_2 = data[1]
                self.SBASE1_2 = 100.0  # 100 MVA by default
            else:
                # 3-windings
                self.windings = 3
                self.R1_2, self.X1_2, self.SBASE1_2, self.R2_3, self.X2_3, self.SBASE2_3, self.R3_1, \
                    self.X3_1, self.SBASE3_1, self.VMSTAR, self.ANSTAR = data[1]

            # line 3: for both types
            self.WINDV1, self.NOMV1, self.ANG1, self.RATE1_1, self.RATE1_2, self.RATE1_3, self.COD1, self.CONT1, self.RMA1, \
                self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1 = data[2]

            # line 4
            if len(data[3]) == 2:
                # 2-windings
                self.windings = 2
                self.WINDV2, self.NOMV2 = data[3]
            else:
                # 3 - windings
                self.windings = 3
                self.WINDV2, self.NOMV2, self.ANG2, self.RATE2_1, self.RATE2_2, self.RATE2_3, self.COD2, self.CONT2, \
                    self.RMA2, self.RMI2, self.VMA2, self.VMI2, self.NTP2, self.TAB2, self.CR2, self.CX2, \
                    self.WINDV3, self.NOMV3, self.ANG3, self.RATA3, self.RATB3, self.RATC3, self.COD3, self.CONT3, \
                    self.RMA3, self.RMI3, self.VMA3, self.VMI3, self.NTP3, self.TAB3, \
                    self.CR3, self.CX3 = data[3]

        elif version == 29:

            '''
            In this version 
      
              2 windings -> 4 lines
      
              I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,'NAME',STAT,O1,F1,...,O4,F4
              R1-2,X1-2,SBASE1-2
              WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD,CONT,RMA,RMI,VMA,VMI,NTP,TAB,CR,CX
              WINDV2,NOMV2
      
              3 windings -> 5 lines
      
              I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,'NAME',STAT,O1,F1,...,O4,F4
              R1-2,X1-2,SBASE1-2,R2-3,X2-3,SBASE2-3,R3-1,X3-1,SBASE3-1,VMSTAR,ANSTAR
              WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD,CONT,RMA,RMI,VMA,VMI,NTP,TAB,CR,CX
              WINDV2,NOMV2,ANG2,RATA2,RATB2,RATC2
              WINDV3,NOMV3,ANG3,RATA3,RATB3,RATC3
      
            '''

            self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                self.NAME, self.STAT, *var = data[0]

            if len(data[1]) == 3:

                '''
                I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,'NAME',STAT,O1,F1,...,O4,F4
                R1-2,X1-2,SBASE1-2
                WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD,CONT,RMA,RMI,VMA,VMI,NTP,TAB,CR,CX
                WINDV2,NOMV2
                '''

                # 2-windings
                self.windings = 2
                self.R1_2, self.X1_2, self.SBASE1_2 = data[1]

                self.WINDV1, self.NOMV1, self.ANG1, self.RATE1_1, self.RATE1_2, self.RATE1_3, self.COD1, self.CONT1, self.RMA1, \
                    self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1 = data[2]

                self.WINDV2, self.NOMV2 = data[3]

            else:

                '''
                I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,'NAME',STAT,O1,F1,...,O4,F4
                R1-2,X1-2,SBASE1-2,R2-3,X2-3,SBASE2-3,R3-1,X3-1,SBASE3-1,VMSTAR,ANSTAR
        
                WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD,CONT,RMA,RMI,VMA,VMI,NTP,TAB,CR,CX
        
                WINDV2,NOMV2,ANG2,RATA2,RATB2,RATC2
        
                WINDV3,NOMV3,ANG3,RATA3,RATB3,RATC3
                '''

                # 3-windings
                self.windings = 3

                self.R1_2, self.X1_2, self.SBASE1_2, self.R2_3, self.X2_3, self.SBASE2_3, self.R3_1, \
                    self.X3_1, self.SBASE3_1, self.VMSTAR, self.ANSTAR = data[1]

                self.WINDV1, self.NOMV1, self.ANG1, self.RATE1_1, self.RATE1_2, self.RATE1_3, self.COD1, \
                    self.CONT1, self.RMA1, self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, \
                    self.CR1, self.CX1 = data[2]

                self.WINDV2, self.NOMV2, self.ANG2, self.RATE2_1, self.RATE2_2, self.RATE2_3 = data[3]

                self.WINDV3, self.NOMV3, self.ANG3, self.RATE3_1, self.RATE3_2, self.RATE3_3 = data[4]

        else:
            logger.add_warning('Transformer not implemented for version', str(version))

    def get_raw_line(self, version):

        var = [self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4]

        if version >= 34:

            # Line 1: for both types
            l0 = self.format_raw_line([self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1,
                                       self.MAG2, self.NMETR, self.NAME, self.STAT] + var + [self.VECGRP, self.ZCOD])

            if self.windings == 2:

                '''
                I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,'NAME',STAT,O1,F1,...,O4,F4,VECGRP
                R1-2,X1-2,SBASE1-2
                WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD1,CONT1,RMA1,RMI1,VMA1,VMI1,NTP1,TAB1,CR1,CX1,CNXA1
                WINDV2,NOMV2
                '''

                l1 = self.format_raw_line([self.R1_2, self.X1_2, self.SBASE1_2])

                l2 = self.format_raw_line([self.WINDV1, self.NOMV1, self.ANG1,
                                           self.RATE1_1, self.RATE1_2, self.RATE1_3, self.RATE1_4, self.RATE1_5,
                                           self.RATE1_6, self.RATE1_7, self.RATE1_8, self.RATE1_9, self.RATE1_10,
                                           self.RATE1_11, self.RATE1_12, self.COD1, self.CONT1, self.NODE1, self.RMA1,
                                           self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1,
                                           self.CNXA1])

                l3 = self.format_raw_line([self.WINDV2, self.NOMV2])

                return l0 + '\n' + l1 + '\n' + l2 + '\n' + l3

            elif self.windings == 3:

                '''
                I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,'NAME',STAT,O1,F1,...,O4,F4,VECGRP
                R1-2,X1-2,SBASE1-2,R2-3,X2-3,SBASE2-3,R3-1,X3-1,SBASE3-1,VMSTAR,ANSTAR
                WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD1,CONT1,RMA1,RMI1,VMA1,VMI1,NTP1,TAB1,CR1,CX1,CNXA1
                WINDV2,NOMV2,ANG2,RATA2,RATB2,RATC2,COD2,CONT2,RMA2,RMI2,VMA2,VMI2,NTP2,TAB2,CR2,CX2,CNXA2
                WINDV3,NOMV3,ANG3,RATA3,RATB3,RATC3,COD3,CONT3,RMA3,RMI3,VMA3,VMI3,NTP3,TAB3,CR3,CX3,CNXA3
                '''

                l1 = self.format_raw_line([self.R1_2, self.X1_2, self.SBASE1_2, self.R2_3, self.X2_3, self.SBASE2_3,
                                           self.R3_1, self.X3_1, self.SBASE3_1, self.VMSTAR, self.ANSTAR])

                l2 = self.format_raw_line([self.WINDV1, self.NOMV1, self.ANG1,
                                           self.RATE1_1, self.RATE1_2, self.RATE1_3, self.RATE1_4, self.RATE1_5,
                                           self.RATE1_6, self.RATE1_7, self.RATE1_8, self.RATE1_9, self.RATE1_10,
                                           self.RATE1_11, self.RATE1_12, self.COD1, self.CONT1, self.NODE1,
                                           self.RMA1, self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1,
                                           self.CX1, self.CNXA1])

                l3 = self.format_raw_line([self.WINDV2, self.NOMV2, self.ANG2,
                                           self.RATE2_1, self.RATE2_2, self.RATE2_3, self.RATE2_4, self.RATE2_5,
                                           self.RATE2_6, self.RATE2_7, self.RATE2_8, self.RATE2_9, self.RATE2_10,
                                           self.RATE2_11, self.RATE2_12, self.COD2, self.CONT2, self.NODE2,
                                           self.RMA2, self.RMI2, self.VMA2, self.VMI2, self.NTP2, self.TAB2, self.CR2,
                                           self.CX2, self.CNXA2])

                l4 = self.format_raw_line([self.WINDV3, self.NOMV3, self.ANG3,
                                           self.RATE3_1, self.RATE3_2, self.RATE3_3, self.RATE3_4, self.RATE3_5,
                                           self.RATE3_6, self.RATE3_7, self.RATE3_8, self.RATE3_9, self.RATE3_10,
                                           self.RATE3_11, self.RATE3_12, self.COD3, self.CONT3, self.NODE3,
                                           self.RMA3, self.RMI3, self.VMA3, self.VMI3, self.NTP3, self.TAB3, self.CR3,
                                           self.CX3, self.CNXA3])

                return l0 + '\n' + l1 + '\n' + l2 + '\n' + l3 + '\n' + l4

            else:
                raise Exception("Wrong number of windings")

        elif version == 33:

            # Line 1: for both types
            l0 = self.format_raw_line([self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1,
                                       self.MAG2, self.NMETR, self.NAME, self.STAT] + var + [self.VECGRP])

            if self.windings == 2:

                '''
                I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,'NAME',STAT,O1,F1,...,O4,F4,VECGRP
                R1-2,X1-2,SBASE1-2
                WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD1,CONT1,RMA1,RMI1,VMA1,VMI1,NTP1,TAB1,CR1,CX1,CNXA1
                WINDV2,NOMV2
                '''

                l1 = self.format_raw_line([self.R1_2, self.X1_2, self.SBASE1_2])

                l2 = self.format_raw_line([self.WINDV1, self.NOMV1, self.ANG1, self.RATE1_1, self.RATE1_2,
                                           self.RATE1_3, self.COD1, self.CONT1, self.RMA1, self.RMI1, self.VMA1,
                                           self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1, self.CNXA1])

                l3 = self.format_raw_line([self.WINDV2, self.NOMV2])

                return l0 + '\n' + l1 + '\n' + l2 + '\n' + l3

            elif self.windings == 3:

                '''
                I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,'NAME',STAT,O1,F1,...,O4,F4,VECGRP
                R1-2,X1-2,SBASE1-2,R2-3,X2-3,SBASE2-3,R3-1,X3-1,SBASE3-1,VMSTAR,ANSTAR
                WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD1,CONT1,RMA1,RMI1,VMA1,VMI1,NTP1,TAB1,CR1,CX1,CNXA1
                WINDV2,NOMV2,ANG2,RATA2,RATB2,RATC2,COD2,CONT2,RMA2,RMI2,VMA2,VMI2,NTP2,TAB2,CR2,CX2,CNXA2
                WINDV3,NOMV3,ANG3,RATA3,RATB3,RATC3,COD3,CONT3,RMA3,RMI3,VMA3,VMI3,NTP3,TAB3,CR3,CX3,CNXA3
                '''

                l1 = self.format_raw_line([self.R1_2, self.X1_2, self.SBASE1_2, self.R2_3, self.X2_3, self.SBASE2_3,
                                           self.R3_1, self.X3_1, self.SBASE3_1, self.VMSTAR, self.ANSTAR])

                l2 = self.format_raw_line([self.WINDV1, self.NOMV1, self.ANG1, self.RATE1_1, self.RATE1_2,
                                           self.RATE1_3, self.COD1, self.CONT1, self.RMA1, self.RMI1, self.VMA1,
                                           self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1, self.CNXA1])

                l3 = self.format_raw_line([self.WINDV2, self.NOMV2, self.ANG2, self.RATE2_1, self.RATE2_1,
                                           self.RATE2_3, self.COD2, self.CONT2, self.RMA2, self.RMI2, self.VMA2,
                                           self.VMI2, self.NTP2, self.TAB2, self.CR2, self.CX2, self.CNXA2])

                l4 = self.format_raw_line([self.WINDV3, self.NOMV3, self.ANG3, self.RATE3_1, self.RATE3_2,
                                           self.RATE3_3, self.COD3, self.CONT3, self.RMA3, self.RMI3, self.VMA3,
                                           self.VMI3, self.NTP3, self.TAB3, self.CR3, self.CX3, self.CNXA3])

                return l0 + '\n' + l1 + '\n' + l2 + '\n' + l3 + '\n' + l4

            else:
                raise Exception("Wrong number of windings")

        else:
            raise Exception('Transformer not implemented for version ' + str(version))

    def get_id(self):

        if self.windings == 2:
            return "{0}_{1}_{2}".format(self.I, self.J, self.CKT)
        elif self.windings == 3:
            return "{0}_{1}_{2}_{3}".format(self.I, self.J, self.K, self.CKT)
        else:
            raise Exception("unsupported number of windings")

    def get_2w_pu_impedances(self, Sbase, v_bus_i, v_bus_j):
        """
        Get the 2-winding impedances if this is a 2-winding transformer
        :param Sbase: system base power in MVA
        :param v_bus_i: Nominal voltage of the bus I in kV
        :param v_bus_j: Nominal voltage of the bus J in kV
        :return:
        """

        assert self.windings == 2

        # yeah, self.NOMV1 and self.NOMV2 may be zero....
        NOMV1 = self.NOMV1 if self.NOMV1 > 0 else v_bus_i
        NOMV2 = self.NOMV2 if self.NOMV2 > 0 else v_bus_j
        z_base_winding = (NOMV1 * NOMV1) / self.SBASE1_2
        z_base_sys = (v_bus_i * v_bus_i) / Sbase

        'The winding data I/O code defines the units in which the turns ratios '
        'WINDV1, WINDV2 and WINDV3 are specified (the units of RMAn and RMIn are '
        'also governed by CW when CODn is 1 or 2):\n'
        '• 1 for off-nominal turns ratio in pu of winding bus base voltage\n'
        '• 2 for winding voltage in kV\n'
        '• 3 for off-nominal turns ratio in pu of nominal winding voltage, NOMV1, NOMV2 and NOMV3.'
        if self.CW == 1:
            """
            WINDV1 is the Winding 1 off-nominal turns ratio in pu of Winding1 bus base voltage
            """
            ti = self.WINDV1
            tj = self.WINDV2
            tap_module = ti / tj

        elif self.CW == 2:
            """
            WINDV1 is the actual Winding 1 voltage in kV; WINDV1 is equal to the base voltage of bus I by default.
            """
            ti = self.WINDV1 / v_bus_i
            tj = self.WINDV2 / v_bus_j
            tap_module = ti / tj

        elif self.CW == 3:
            """
            WINDV1 is the Winding 1 off-nominal turns ratio in pu of nominal Winding 1 voltage,
            """
            ti = self.WINDV1 / NOMV1
            tj = self.WINDV2 / NOMV2
            tap_module = ti / tj
        else:
            raise Exception("Invalid value of CW")

        # --------------------------------------------------------------------------------------------------------------

        if self.CZ == 1:
            """
            1 for resistance and reactance in pu on system MVA base and winding voltage base
            translating: impedances in the system base, do noting
            """
            r = self.R1_2
            x = self.X1_2

        elif self.CZ == 2:
            """
            2 for resistance and reactance in pu on a specified MVA base and winding voltage base
            translating: impedances in the machine base with S=SBASE1_2 and V=NOMV1 
            """
            # base change from winding base to system base
            r_ohm = self.R1_2 * z_base_winding
            x_ohm = self.X1_2 * z_base_winding
            r = r_ohm / z_base_sys
            x = x_ohm / z_base_sys

        elif self.CZ == 3:
            """
            3 for transformer load loss in watts and impedance magnitude in pu on a 
            specified MVA base and winding voltage base
            
            R1-2 is the load loss in watts, and X1-2 is the impedance magnitude in  pu  
            on  Winding  1  to  2  MVA  base (SBASE1-2) and  winding  voltage  base
            """
            # Series impedance
            Pcu = self.R1_2  # load loss AKA copper losses
            zsc = self.X1_2  # short circuit impedance
            rsc = (Pcu / 1000.0) / self.SBASE1_2
            if rsc < zsc:
                xsc = np.sqrt(zsc ** 2 - rsc ** 2)
            else:
                xsc = 0.0

            # base change from winding base to system base
            r_ohm = rsc * z_base_winding
            x_ohm = xsc * z_base_winding
            r = r_ohm / z_base_sys
            x = x_ohm / z_base_sys
        else:
            raise Exception("Invalid value of CZ")

        # --------------------------------------------------------------------------------------------------------------

        if self.CM == 1:
            """
            1 for complex  admittance  in pu  on  system  MVA  base  and Winding 1 bus voltage base
            """
            g = self.MAG1
            b = self.MAG2

        elif self.CM == 2:
            """
            2 for no load loss in watts and exciting current in pu on Winding 1 to two 
            MVA base (SBASE1-2) and nominal Winding 1 voltage, NOMV1
            """
            Pfe = self.MAG1 / 1000.0  # Iron losses, AKA magnetic losses (kW) Mag1 comes in W, convert it to kW
            I0 = self.MAG2  # No-load current (%)
            Sn = self.SBASE1_2  # Base power MVA

            # Shunt impedance (leakage)
            if Pfe > 0.0 and I0 > 0.0:
                rfe = Sn / (Pfe / 1000.0)
                zm = 1.0 / (I0 / 100.0)
                val = (1.0 / (zm ** 2)) - (1.0 / (rfe ** 2))
                if val > 0:
                    xm = 1.0 / np.sqrt(val)
                    rm = np.sqrt(xm * xm - zm * zm)
                else:
                    xm = 0.0
                    rm = 0.0

            else:
                rm = 0.0
                xm = 0.0

            # base change from winding base to system base
            r_ohm = rm * z_base_winding
            x_ohm = xm * z_base_winding
            rsh = r_ohm / z_base_sys
            xsh = x_ohm / z_base_sys

            # convert shunt impedance to shunt admittance
            ysh = 1 / (rsh + 1j * xsh)
            g = ysh.real
            b = ysh.imag
        else:
            raise Exception("Invalid value of CM")

        tap_angle = np.deg2rad(self.ANG1)  # ANG2 is ignored for 2W transformers

        return r, x, g, b, tap_module, tap_angle
