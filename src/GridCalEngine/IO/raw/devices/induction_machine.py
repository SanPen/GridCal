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
import GridCalEngine.Core.Devices as dev


class RawInductionMachine(RawObject):

    def __init__(self):
        RawObject.__init__(self, "Induction machine")

        self.I = 0
        self.ID = "1"
        self.STATUS = 1
        self.SCODE = 1
        self.DCODE = 2
        self.AREA = 0
        self.ZONE = 0
        self.OWNER = 0
        self.TCODE = 1
        self.BCODE = 1
        self.MBASE = 100
        self.RATEKV = 0
        self.PCODE = 1
        self.PSET = 0

        self.H = 1.0
        self.A = 1.0
        self.B = 1.0
        self.D = 1.0
        self.E = 1.0

        self.RA = 0
        self.XA = 0
        self.XM = 2.5

        self.R1 = 999.0
        self.X1 = 999.0
        self.R2 = 999.0
        self.X2 = 999.0
        self.X3 = 0.0

        self.E1 = 1.0
        self.SE1 = 0
        self.E2 = 1.2
        self.SE2 = 0
        self.IA1 = 0
        self.IA2 = 0
        self.XAMULT = 1.0

        self.register_property(property_name='I',
                               rawx_key='ibus',
                               class_type=int,
                               description='Bus number',
                               min_value=0,
                               max_value=999997)

        self.register_property(property_name='ID',
                               rawx_key='imid',
                               class_type=str,
                               description='One or  two character  uppercase  non-blank  alphanumeric  machine '
                                           'identifier used to distinguish among multiple induction machines at bus I. '
                                           'It is recommend-ed that, at buses for which a single induction machine is '
                                           'present, it be designated as having the machine identifier "1".',
                               max_chars=2)

        self.register_property(property_name='STATUS',
                               rawx_key='stat',
                               class_type=int,
                               description='Machine status of 1 for in-service and 0 for out-of-service',
                               min_value=0,
                               max_value=1)

        self.register_property(property_name='SCODE',
                               rawx_key='scode',
                               class_type=int,
                               description='Machine standard code: \n'
                                           '1:NEMA\n'
                                           '2:IEC',
                               min_value=1,
                               max_value=2)

        self.register_property(property_name='DCODE',
                               rawx_key='dcode',
                               class_type=int,
                               description='Machine design code. Following are allowed machine design codes:\n'
                                           '•  0 - for Custom design with equivalent circuit reactances specified\n'
                                           '•  1 - for NEMA Design A\n'
                                           '•  2 - for NEMA Design B / IEC Design N\n'
                                           '•  3 - for NEMA Design C / IEC Design H\n'
                                           '•  4 - for NEMA Design D\n'
                                           '•  5 - for NEMA Design E',
                               min_value=0,
                               max_value=5)

        self.register_property(property_name='AREA',
                               rawx_key='area',
                               class_type=int,
                               description='Area to which the induction machine is assigned ',)

        self.register_property(property_name='ZONE',
                               rawx_key='zone',
                               class_type=int,
                               description='Zone to which the induction machine is assigned ',)

        self.register_property(property_name='OWNER',
                               rawx_key='owner',
                               class_type=int,
                               description='Owner to which the induction machine is assigned ',)

        self.register_property(property_name='TCODE',
                               rawx_key='tcode',
                               class_type=int,
                               description='Type of mechanical load torque variation:\n'
                                           '•  1 - for the simple power law\n'
                                           '•  2 - for the WECC model',
                               min_value=1,
                               max_value=2)

        self.register_property(property_name='BCODE',
                               rawx_key='bcode',
                               class_type=int,
                               description='Machine base power code:\n'
                                           '•  1 - for 1 for mechanical power (MW) output of the machine\n'
                                           '•  2 - for apparent electrical power (MVA) drawn by the machine',
                               min_value=1,
                               max_value=2)

        self.register_property(property_name='MBASE',
                               rawx_key='mbase',
                               class_type=float,
                               description='Machine base power; entered in MW or MVA. '
                                           'This value is specified according toBCODE, and could be either '
                                           'the mechanical rating of the machine or the electrical input. '
                                           'It is necessary only that the per unit values entered for the '
                                           'equivalent circuit parameters match the base power.',
                               unit=Unit(UnitMultiplier.M, UnitSymbol.VA))

        self.register_property(property_name='RATEKV',
                               rawx_key='ratekv',
                               class_type=float,
                               description='Rated voltage',
                               unit=Unit(UnitMultiplier.k, UnitSymbol.V))

        self.register_property(property_name='PCODE',
                               rawx_key='pcode',
                               class_type=int,
                               description='Scheduled power code',
                               min_value=1,
                               max_value=2)

        self.register_property(property_name='PSET',
                               rawx_key='pset',
                               class_type=float,
                               unit=Unit(UnitMultiplier.M, UnitSymbol.W),
                               description='Scheduled  active  power  for  a  terminal  voltage  at  the  '
                                           'machine  of  1.0  pu  of  the machine rated voltage; entered in MW. '
                                           'This value is specified according to PCODE,and is either the '
                                           'mechanical power output of the machine or the real electrical power  '
                                           'drawn  by  the  machine.  The  sign  convention  used  is  that  '
                                           'PSET  specifies power supplied to the machine:A positive value of '
                                           'electrical power means that the machine is operating as a mo-tor;  '
                                           'similarly,  a  positive  value  of  mechanical  power  output  means  '
                                           'that the machine is driving a mechanical load and operating as a motor.')

        self.register_property(property_name='H',
                               rawx_key='hconst',
                               class_type=float,
                               description='Machine inertia; entered in per unit on MBASE base.',
                               unit=Unit.get_pu())

        self.register_property(property_name='A',
                               rawx_key='aconst',
                               class_type=float,
                               description='Constants that describe the variation of the torque of the '
                                           'mechanical load with speed. If TCODE is 1 (simple power law model), '
                                           'only D is used; if TCODE is 2 (WECCmodel), all of these constants '
                                           'are used.')

        self.register_property(property_name='B',
                               rawx_key='bconst',
                               class_type=float,
                               description='Constants that describe the variation of the torque of the '
                                           'mechanical load withspeed. If TCODE is 1 (simple power law model), '
                                           'only D is used; if TCODE is 2 (WECCmodel), all of these constants '
                                           'are used.')

        self.register_property(property_name='D',
                               rawx_key='dconst',
                               class_type=float,
                               description='Constants that describe the variation of the torque of the '
                                           'mechanical load withspeed. If TCODE is 1 (simple power law model), '
                                           'only D is used; if TCODE is 2 (WECCmodel), all of these constants '
                                           'are used.')

        self.register_property(property_name='E',
                               rawx_key='econst',
                               class_type=float,
                               description='Constants that describe the variation of the torque of the '
                                           'mechanical load withspeed. If TCODE is 1 (simple power law model), '
                                           'only D is used; if TCODE is 2 (WECCmodel), all of these constants '
                                           'are used.')

        self.register_property(property_name='RA',
                               rawx_key='ra',
                               class_type=float,
                               description='rmature resistance, Ra (> 0.0); entered in per unit on '
                                           'the power base MBASE and voltage base RATEKV',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='XA',
                               rawx_key='xa',
                               class_type=float,
                               description='Armature leakage reactance, Xa (> 0.0); '
                                           'entered in per unit on the power baseMBASE and voltage base RATEKV.',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='XM',
                               rawx_key='xm',
                               class_type=float,
                               description='Unsaturated magnetizing reactance, Xm (> 0.0); entered in per unit '
                                           'on the powerbase MBASE and voltage base RATEKV.',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='R1',
                               rawx_key='r1',
                               class_type=float,
                               description='Resistance of the first rotor winding ("cage"), r1 (> 0.0); '
                                           'entered in per unit on the power base MBASE and voltage base RATEKV.',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='X1',
                               rawx_key='x1',
                               class_type=float,
                               description='Reactance of the first rotor winding ("cage"), X1 (>0.0); '
                                           'entered in per unit on the power base MBASE and voltage base RATEKV.',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='R2',
                               rawx_key='r2',
                               class_type=float,
                               description='Resistance of the second rotor winding ("cage"), r2 (> 0.0); '
                                           'entered in per unit on the power base MBASE and voltage base RATEKV.',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='X2',
                               rawx_key='x2',
                               class_type=float,
                               description='Reactance of the second rotor winding ("cage"), X2 (>0.0); '
                                           'entered in per unit onthe power base MBASE and voltage base RATEKV.',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='X3',
                               rawx_key='x3',
                               class_type=float,
                               description='Third rotor reactance, X3 (> 0.0); '
                                           'entered in per unit on the power base MBASEand voltage base RATEKV.',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='E1',
                               rawx_key='e1',
                               class_type=float,
                               description='First  terminal  voltage  point  from  the  open  circuit  '
                                           'saturation  curve,  E1  (>  0.0);entered in per unit on RATEKV base.',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='SE1',
                               rawx_key='se1',
                               class_type=float,
                               description='Saturation factor at terminal voltage E1, S(E1).')

        self.register_property(property_name='E2',
                               rawx_key='e2',
                               class_type=float,
                               description='Second terminal voltage point from the open circuit saturation curve,'
                                           'E2 (> 0.0);entered in per unit on RATEKV base.',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='SE2',
                               rawx_key='se2',
                               class_type=float,
                               description='Saturation factor at terminal voltage E2, S(E2)')

        self.register_property(property_name='IA1',
                               rawx_key='ia1',
                               class_type=float,
                               description='Stator currents in PU specifying saturation of the stator '
                                           'leakage reactance, XA.',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='IA2',
                               rawx_key='ia2',
                               class_type=float,
                               description='Stator currents in PU specifying saturation of the stator '
                                           'leakage reactance, XA.',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='XAMULT',
                               rawx_key='xamult',
                               class_type=float,
                               description='Multiplier for the saturated value. Allowed value 0 to 1.0.',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if version > 30:
            '''
            I,ID,STAT,SCODE,DCODE,AREA,ZONE,OWNER,TCODE,BCODE,MBASE,RATEKV,
            PCODE,PSET,H,A,B,D,E,RA,XA,XM,R1,X1,R2,X2,X3,E1,SE1,E2,SE2,IA1,IA2,
            XAMULT
            '''
            self.I, self.ID, self.STATUS, self.SCODE, self.DCODE, self.AREA, self.ZONE, self.OWNER, \
                self.TCODE, self.BCODE, self.MBASE, self.RATEKV = data[0]

            self.PCODE, self.PSET, self.H, self.A, self.B, self.D, self.E, self.RA, self.XA, self.XM, self.R1, \
                self.X1, self.R2, self.X2, self.X3, self.E1, self.SE1, self.E2, self.SE2, self.IA1, self.IA2 = data[1]

            self.XAMULT = data[2]
        else:
            logger.add_warning('Induction machine not implemented for version', str(version))

    def get_raw_line(self, version):

        if version >= 30:
            '''
            I,ID,STAT,SCODE,DCODE,AREA,ZONE,OWNER,TCODE,BCODE,MBASE,RATEKV,
            PCODE,PSET,H,A,B,D,E,RA,XA,XM,R1,X1,R2,X2,X3,E1,SE1,E2,SE2,IA1,IA2,
            XAMULT
            '''
            return self.format_raw_line([self.I, self.ID, self.STATUS, self.SCODE, self.DCODE, self.AREA, self.ZONE,
                                         self.OWNER, self.TCODE, self.BCODE, self.MBASE, self.RATEKV]) + "\n" + \
                   self.format_raw_line([self.PCODE, self.PSET, self.H, self.A, self.B, self.D, self.E, self.RA,
                                         self.XA, self.XM, self.R1, self.X1, self.R2, self.X2, self.X3, self.E1,
                                         self.SE1, self.E2, self.SE2, self.IA1, self.IA2]) + "\n" + \
                   self.format_raw_line([self.XAMULT])
        else:
            raise Exception('Induction machine not implemented for version ' + str(version))

    def get_id(self):
        """
        Get the element PSSE ID
        :return:
        """
        return "{0}_{1}".format(self.I, self.ID)

    def get_object(self, logger: list):
        """
        Return Newton Load object
        Returns:
            Newton Load object
        """

        elm = dev.Generator(name=str(self.I) + '_' + str(self.ID),
                            P=self.PSET,
                            vset=self.RATEKV,
                            Snom=self.MBASE,
                            active=bool(self.STATUS))

        return elm
