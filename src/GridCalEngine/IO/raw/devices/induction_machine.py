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
import GridCalEngine.Devices as dev


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
                               description='One or  two character ID',
                               max_chars=2)

        self.register_property(property_name='STATUS',
                               rawx_key='stat',
                               class_type=int,
                               description='Status',
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
                               description='Machine design code.\n'
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
                               description='Area number', )

        self.register_property(property_name='ZONE',
                               rawx_key='zone',
                               class_type=int,
                               description='Zone number', )

        self.register_property(property_name='OWNER',
                               rawx_key='owner',
                               class_type=int,
                               description='Owner number', )

        self.register_property(property_name='TCODE',
                               rawx_key='tcode',
                               class_type=int,
                               description='Type of mechanical load torque variation:\n'
                                           '•  1 - Simple power law\n'
                                           '•  2 - WECC model',
                               min_value=1,
                               max_value=2)

        self.register_property(property_name='BCODE',
                               rawx_key='bcode',
                               class_type=int,
                               description='Machine base power code:\n'
                                           '•  1 - Mechanical power (MW) output of the machine\n'
                                           '•  2 - Apparent electrical power (MVA) drawn by the machine',
                               min_value=1,
                               max_value=2)

        self.register_property(property_name='MBASE',
                               rawx_key='mbase',
                               class_type=float,
                               description='Nominal power (see the manual for more funkyness).',
                               unit=Unit.get_mva())

        self.register_property(property_name='RATEKV',
                               rawx_key='ratekv',
                               class_type=float,
                               description='Rated voltage',
                               unit=Unit.get_kv())

        self.register_property(property_name='PCODE',
                               rawx_key='pcode',
                               class_type=int,
                               description='Scheduled power code',
                               min_value=1,
                               max_value=2)

        self.register_property(property_name='PSET',
                               rawx_key='pset',
                               class_type=float,
                               unit=Unit.get_mw(),
                               description='Scheduled  active  power (see the manual).')

        self.register_property(property_name='H',
                               rawx_key='hconst',
                               class_type=float,
                               description='Machine inertia, in per unit on MBASE base.',
                               unit=Unit.get_pu())

        self.register_property(property_name='A',
                               rawx_key='aconst',
                               class_type=float,
                               description='A parameter to model the torque of the mechanical load with speed. (see manual)')

        self.register_property(property_name='B',
                               rawx_key='bconst',
                               class_type=float,
                               description='B parameter to model the torque of the mechanical load with speed. (see manual)')

        self.register_property(property_name='D',
                               rawx_key='dconst',
                               class_type=float,
                               description='D parameter to model the torque of the mechanical load with speed. (see manual)')

        self.register_property(property_name='E',
                               rawx_key='econst',
                               class_type=float,
                               description='E parameter to model the torque of the mechanical load with speed. (see manual)')

        self.register_property(property_name='RA',
                               rawx_key='ra',
                               class_type=float,
                               description='Armature resistance',
                               unit=Unit.get_pu())

        self.register_property(property_name='XA',
                               rawx_key='xa',
                               class_type=float,
                               description='Armature leakage reactance.',
                               unit=Unit.get_pu())

        self.register_property(property_name='XM',
                               rawx_key='xm',
                               class_type=float,
                               description='Unsaturated magnetizing reactance.',
                               unit=Unit.get_pu())

        self.register_property(property_name='R1',
                               rawx_key='r1',
                               class_type=float,
                               description='Resistance of the first rotor winding.',
                               unit=Unit.get_pu())

        self.register_property(property_name='X1',
                               rawx_key='x1',
                               class_type=float,
                               description='Reactance of the first rotor winding.',
                               unit=Unit.get_pu())

        self.register_property(property_name='R2',
                               rawx_key='r2',
                               class_type=float,
                               description='Resistance of the second rotor winding.',
                               unit=Unit.get_pu())

        self.register_property(property_name='X2',
                               rawx_key='x2',
                               class_type=float,
                               description='Reactance of the second rotor winding.',
                               unit=Unit.get_pu())

        self.register_property(property_name='X3',
                               rawx_key='x3',
                               class_type=float,
                               description='Third rotor reactance.',
                               unit=Unit.get_pu())

        self.register_property(property_name='E1',
                               rawx_key='e1',
                               class_type=float,
                               description='First terminal voltage point from the open circuit saturation  curve.',
                               unit=Unit.get_pu())

        self.register_property(property_name='SE1',
                               rawx_key='se1',
                               class_type=float,
                               description='Saturation factor at terminal voltage E1, S(E1).')

        self.register_property(property_name='E2',
                               rawx_key='e2',
                               class_type=float,
                               description='Second terminal voltage point from the open circuit saturation curve.',
                               unit=Unit.get_pu())

        self.register_property(property_name='SE2',
                               rawx_key='se2',
                               class_type=float,
                               description='Saturation factor at terminal voltage E2, S(E2)')

        self.register_property(property_name='IA1',
                               rawx_key='ia1',
                               class_type=float,
                               description='Stator currents in PU specifying saturation of the stator '
                                           'leakage reactance, XA.',
                               unit=Unit.get_pu())

        self.register_property(property_name='IA2',
                               rawx_key='ia2',
                               class_type=float,
                               description='Stator currents in PU specifying saturation of the stator '
                                           'leakage reactance, XA.',
                               unit=Unit.get_pu())

        self.register_property(property_name='XAMULT',
                               rawx_key='xamult',
                               class_type=float,
                               description='Multiplier for the saturated value. Allowed value 0 to 1.0.',
                               unit=Unit.get_pu())

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if version >= 34:
            '''
            I,'ID',ST,SC,DC,AREA,ZONE,OWNER,TC,BC,  MBASE, RATEKV,PC, PSET, 
            H, A, B, D, E, RA, XA, XM, R1, X1, R2, X2, X3, E1, SE1, E2, SE2,   IA1,   IA2, XAMULT
            '''
            # 3010,"1 ", 1, 1, 2, 5, 4, 5, 1, 1, 1.000, 21.600,1, 1.0000, 1.000, 1.000, 1.000, 1.000, 1.000
            if len(data) == 1:
                (self.I, self.ID, self.STATUS, self.SCODE, self.DCODE, self.AREA, self.ZONE, self.OWNER,
                 self.TCODE, self.BCODE, self.MBASE, self.RATEKV,
                 self.PCODE, self.PSET, self.H, self.A, self.B, self.D, self.E) = data[0]

            elif len(data) == 3:
                (self.I, self.ID, self.STATUS, self.SCODE, self.DCODE, self.AREA, self.ZONE, self.OWNER,
                 self.TCODE, self.BCODE, self.MBASE, self.RATEKV) = data[0]

                (self.PCODE, self.PSET, self.H, self.A, self.B, self.D, self.E,
                 self.RA, self.XA, self.XM, self.R1,
                 self.X1, self.R2, self.X2, self.X3,
                 self.E1, self.SE1, self.E2, self.SE2,
                 self.IA1, self.IA2) = data[1]

                self.XAMULT = data[2]
            else:
                logger.add_warning('Incorrect number of lines for Induction machine', str(len(data)))

        elif 29 <= version <= 33:
            '''
            I,ID,STAT,SCODE,DCODE,AREA,ZONE,OWNER,TCODE,BCODE,MBASE,RATEKV,
            PCODE,PSET,H,A,B,D,E,RA,XA,XM,R1,X1,R2,X2,X3,E1,SE1,E2,SE2,IA1,IA2,
            XAMULT
            '''

            if len(data) == 1:
                (self.I, self.ID, self.STATUS, self.SCODE, self.DCODE, self.AREA, self.ZONE, self.OWNER,
                 self.TCODE, self.BCODE, self.MBASE, self.RATEKV,
                 self.PCODE, self.PSET, self.H, self.A, self.B, self.D, self.E) = data[0]

            elif len(data) == 3:
                (self.I, self.ID, self.STATUS, self.SCODE, self.DCODE, self.AREA, self.ZONE, self.OWNER,
                 self.TCODE, self.BCODE, self.MBASE, self.RATEKV) = data[0]

                (self.PCODE, self.PSET, self.H, self.A, self.B, self.D, self.E,
                 self.RA, self.XA, self.XM, self.R1,
                 self.X1, self.R2, self.X2, self.X3,
                 self.E1, self.SE1, self.E2, self.SE2,
                 self.IA1, self.IA2) = data[1]

                self.XAMULT = data[2]
            else:
                logger.add_warning('Incorrect number of lines for Induction machine', str(len(data)))
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
