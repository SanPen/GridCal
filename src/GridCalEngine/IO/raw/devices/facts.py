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
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit


class RawFACTS(RawObject):

    def __init__(self):
        RawObject.__init__(self, "FACTS")

        self.NAME = ""
        self.I = 0
        self.J = 0
        self.MODE = 1  # 0 means out of service
        self.PDES = 0
        self.QDES = 0
        self.VSET = 0
        self.SHMX = 9999.0
        self.TRMX = 0
        self.VTMN = 0.9
        self.VTMX = 1.1
        self.VSMX = 1.0
        self.IMX = 0
        self.LINX = 0.05
        self.RMPCT = 100.0
        self.OWNER = 0
        self.SET1 = 0
        self.SET2 = 0
        self.VSREF = 0
        self.FCREG = 0
        self.NREG = 0
        self.REMOT = 0
        self.MNAME = ""

        self.register_property(property_name='NAME',
                               rawx_key='name',
                               class_type=str,
                               description='The non-blank alphanumeric identifier assigned to this FACTS device',
                               max_chars=12)

        self.register_property(property_name='I',
                               rawx_key='ibus',
                               class_type=int,
                               description='Sending end bus number',
                               min_value=1,
                               max_value=999997)

        self.register_property(property_name='J',
                               rawx_key='jbus',
                               class_type=int,
                               description='Terminal end bus number',
                               min_value=0,
                               max_value=999997)

        self.register_property(property_name='MODE',
                               rawx_key='mode',
                               class_type=int,
                               description='Control mode:\n'
                                           'For a STATCON (i.e., a FACTS devices with a shunt element but no '
                                           'series element),J must be 0 and MODE must be either 0 or 1):\n'
                                           '•  0 - out-of-service (i.e., shunt link open)\n'
                                           '•  1 - shunt link operating\n'
                                           'For a FACTS device with a series element (i.e., J is not 0), MODE may be:\n'
                                           '•  0 - out-of-service (i.e., series and shunt links open)\n'
                                           '•  1 - series and shunt links operating\n'
                                           '•  2 - series link bypassed (i.e., like a zero impedance line) '
                                           'and shunt link operating as a STATCON\n'
                                           '•  3 - series and shunt links operating with series link at constant '
                                           'series impedance\n'
                                           '•  4 - series and shunt links operating with series link at constant '
                                           'series voltage\n'
                                           '•  5 - master device of an IPFC with P and Q setpoints specified; '
                                           'another FACTS device must be designated as the slave device '
                                           '(i.e., its MODE is 6 or 8) of this IPFC\n'
                                           '•  6 - slave device of an IPFC with P and Q setpoints specified; '
                                           'the FACTS device specified in MNAME must be the master device '
                                           '(i.e., its MODE is 5 or 7) of this IPFC. The Q setpoint is ignored '
                                           'as the master device dictates the active power exchanged between '
                                           'the two devices.\n'
                                           '•  7 - master device of an IPFC with constant series voltage setpoints '
                                           'specified;another FACTS device must be designated as the slave device '
                                           '(i.e., its MODEis 6 or 8) of this IPFC\n'
                                           '•  8 - slave device of an IPFC with constant series voltage setpoints '
                                           'specified;the FACTS device specified in MNAME must be the master '
                                           'device (i.e., itsMODE is 5 or 7) of this IPFC. '
                                           'The complex Vd + jVq setpoint is modified during power flow solutions '
                                           'to reflect the active power exchange determined by the master device',
                               min_value=0,
                               max_value=8)

        self.register_property(property_name='PDES',
                               rawx_key='pdes',
                               class_type=float,
                               description='Desired active power flow arriving at the terminal end bus;',
                               unit=Unit(UnitMultiplier.M, UnitSymbol.W))

        self.register_property(property_name='QDES',
                               rawx_key='qdes',
                               class_type=float,
                               description='Desired reactive power flow arriving at the terminal end bus',
                               unit=Unit(UnitMultiplier.M, UnitSymbol.VAr))

        self.register_property(property_name='VSET',
                               rawx_key='vset',
                               class_type=float,
                               description='Voltage setpoint at the sending end bus',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='SHMX',
                               rawx_key='shmx',
                               class_type=float,
                               description='Maximum shunt current at the sending end bus',
                               unit=Unit(UnitMultiplier.M, UnitSymbol.VA))

        self.register_property(property_name='TRMX',
                               rawx_key='trmx',
                               class_type=float,
                               description='Maximum bridge active power transfer',
                               unit=Unit(UnitMultiplier.M, UnitSymbol.W))

        self.register_property(property_name='VTMN',
                               rawx_key='vtmn',
                               class_type=float,
                               description='Minimum voltage at the terminal end bus',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='VTMX',
                               rawx_key='vtmx',
                               class_type=float,
                               description='Maximum voltage at the terminal end bus',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='VSMX',
                               rawx_key='vsmx',
                               class_type=float,
                               description='Maximum series voltage',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='IMX',
                               rawx_key='imx',
                               class_type=int,
                               description='Maximum series current, or zero for no series current limit',
                               unit=Unit(UnitMultiplier.M, UnitSymbol.VA))

        self.register_property(property_name='LINX',
                               rawx_key='linx',
                               class_type=float,
                               description='Reactance of the dummy series element used during power flow solutions',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='RMPCT',
                               rawx_key='rmpct',
                               class_type=float,
                               description='Percent of the total Mvar required to hold the voltage at the bus '
                                           'controlled by the shunt element of this FACTS device that are to '
                                           'be contributed by the shunt element',
                               min_value=0.0,
                               max_value=100.0)

        self.register_property(property_name='OWNER',
                               rawx_key='owner',
                               class_type=int,
                               description='Owner number',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='SET1',
                               rawx_key='set1',
                               class_type=float,
                               description='If MODE is 3, resistance and reactance respectively of the '
                                           'constant impedance, entered in pu; if MODE is 4, the magnitude '
                                           '(in pu) and angle (in degrees) of the constant series voltage '
                                           'with respect to the quantity indicated by VSREF; if MODE is 7 '
                                           'or 8, the real (Vd) and imaginary (Vq) components (in pu) of the '
                                           'constant series voltage with respect to the quantity indicated by '
                                           'VSREF; for other values of MODE, SET1 and SET2 are read, but not '
                                           'saved or used during power flow solutions.')

        self.register_property(property_name='SET2',
                               rawx_key='set2',
                               class_type=float,
                               description='If MODE is 3, resistance and reactance respectively of the '
                                           'constant impedance, entered in pu; if MODE is 4, the magnitude '
                                           '(in pu) and angle (in degrees) of the constant series voltage '
                                           'with respect to the quantity indicated by VSREF; if MODE is 7 '
                                           'or 8, the real (Vd) and imaginary (Vq) components (in pu) of the '
                                           'constant series voltage with respect to the quantity indicated by '
                                           'VSREF; for other values of MODE, SET1 and SET2 are read, but not '
                                           'saved or used during power flow solutions.')

        self.register_property(property_name='VSREF',
                               rawx_key='vsref',
                               class_type=int,
                               description='Series voltage reference code to indicate the series voltage '
                                           'reference of SET1 and SET2 when MODE is 4, 7 or 8',
                               min_value=0,
                               max_value=1)

        self.register_property(property_name='FCREG',
                               rawx_key='fcreg',
                               class_type=int,
                               description='Bus number, or extended bus name enclosed in single quotes',
                               min_value=0,
                               max_value=1)

        self.register_property(property_name='NREG',
                               rawx_key='nreg',
                               class_type=int,
                               description='A node number of bus FCREG',
                               min_value=0,
                               max_value=1)

        self.register_property(property_name='REMOT',
                               rawx_key='remot',
                               class_type=int,
                               description='',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='MNAME',
                               rawx_key='mname',
                               class_type=str,
                               description='')

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if version >= 35:
            '''
            'NAME',I,J,MODE,PDES,QDES,VSET,SHMX,TRMX,VTMN,VTMX,VSMX,IMX,LINX,
            RMPCT,OWNER,SET1,SET2,VSREF,REMOT,'MNAME'
            '''

            self.NAME, self.I, self.J, self.MODE, self.PDES, self.QDES, self.VSET, self.SHMX, \
                self.TRMX, self.VTMN, self.VTMX, self.VSMX, self.IMX, self.LINX, self.RMPCT, self.OWNER, \
                self.SET1, self.SET2, self.VSREF, self.FCREG, self.NREG, self.MNAME = data[0]

        elif 30 <= version <= 34:
            '''
            'NAME',I,J,MODE,PDES,QDES,VSET,SHMX,TRMX,VTMN,VTMX,VSMX,IMX,LINX,
            RMPCT,OWNER,SET1,SET2,VSREF,REMOT,'MNAME'
            '''

            self.NAME, self.I, self.J, self.MODE, self.PDES, self.QDES, self.VSET, self.SHMX, \
                self.TRMX, self.VTMN, self.VTMX, self.VSMX, self.IMX, self.LINX, self.RMPCT, self.OWNER, \
                self.SET1, self.SET2, self.VSREF, self.REMOT, self.MNAME = data[0]

        elif version == 29:
            '''
            'NAME',I,J,MODE,PDES,QDES,VSET,SHMX,TRMX,VTMN,VTMX,VSMX,IMX,LINX,
                RMPCT,OWNER,SET1,SET2,VSREF,REMOT,'MNAME'
            '''

            self.NAME, self.I, self.J, self.MODE, self.PDES, self.QDES, self.VSET, self.SHMX, \
                self.TRMX, self.VTMN, self.VTMX, self.VSMX, self.IMX, self.LINX, self.RMPCT, self.OWNER, \
                self.SET1, self.SET2, self.VSREF, self.REMOT, self.MNAME = data[0]
        else:
            logger.add_warning('Version not implemented for DC Lines', str(version))

    def get_raw_line(self, version):

        if version >= 35:
            '''
            'NAME',I,J,MODE,PDES,QDES,VSET,SHMX,TRMX,VTMN,VTMX,VSMX,IMX,LINX,
            RMPCT,OWNER,SET1,SET2,VSREF,REMOT,'MNAME'
            '''

            return self.format_raw_line([self.NAME, self.I, self.J, self.MODE, self.PDES, self.QDES, self.VSET,
                                         self.SHMX, self.TRMX, self.VTMN, self.VTMX, self.VSMX, self.IMX, self.LINX,
                                         self.RMPCT, self.OWNER, self.SET1, self.SET2, self.VSREF, self.FCREG,
                                         self.NREG, self.MNAME])

        elif 30 <= version <= 34:
            '''
            'NAME',I,J,MODE,PDES,QDES,VSET,SHMX,TRMX,VTMN,VTMX,VSMX,IMX,LINX,
            RMPCT,OWNER,SET1,SET2,VSREF,REMOT,'MNAME'
            '''
            return self.format_raw_line([self.NAME, self.I, self.J, self.MODE, self.PDES, self.QDES, self.VSET,
                                         self.SHMX, self.TRMX, self.VTMN, self.VTMX, self.VSMX, self.IMX, self.LINX,
                                         self.RMPCT, self.OWNER, self.SET1, self.SET2, self.VSREF, self.REMOT,
                                         self.MNAME])

        elif version == 29:
            '''
            'NAME',I,J,MODE,PDES,QDES,VSET,SHMX,TRMX,VTMN,VTMX,VSMX,IMX,LINX,
                RMPCT,OWNER,SET1,SET2,VSREF,REMOT,'MNAME'
            '''

            return self.format_raw_line([self.NAME, self.I, self.J, self.MODE, self.PDES, self.QDES, self.VSET,
                                         self.SHMX, self.TRMX, self.VTMN, self.VTMX, self.VSMX, self.IMX, self.LINX,
                                         self.RMPCT, self.OWNER, self.SET1, self.SET2, self.VSREF, self.REMOT,
                                         self.MNAME])
        else:
            raise Exception('Version not implemented for DC Lines ' + str(version))

    def get_id(self):
        """
        Get the element PSSE ID
        :return: 
        """        
        return "{0}_{1}_1".format(self.I, self.J)

    def is_connected(self):
        return self.I > 0 and self.J > 0
