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
                               description='Device name',
                               max_chars=12)

        self.register_property(property_name='I',
                               rawx_key='ibus',
                               class_type=int,
                               description='Bus from number',
                               min_value=1,
                               max_value=999997)

        self.register_property(property_name='J',
                               rawx_key='jbus',
                               class_type=int,
                               description='Bus to number',
                               min_value=0,
                               max_value=999997)

        self.register_property(property_name='MODE',
                               rawx_key='mode',
                               class_type=int,
                               description='Control mode',
                               min_value=0,
                               max_value=8)

        self.register_property(property_name='PDES',
                               rawx_key='pdes',
                               class_type=float,
                               description='Desired active power flow arriving at the "to" bus;',
                               unit=Unit.get_mw())

        self.register_property(property_name='QDES',
                               rawx_key='qdes',
                               class_type=float,
                               description='Desired reactive power flow arriving at the "to" bus',
                               unit=Unit.get_mvar())

        self.register_property(property_name='VSET',
                               rawx_key='vset',
                               class_type=float,
                               description='Voltage set point at the "from" bus',
                               unit=Unit.get_pu())

        self.register_property(property_name='SHMX',
                               rawx_key='shmx',
                               class_type=float,
                               description='Maximum shunt current at the "from" bus',
                               unit=Unit.get_mva())

        self.register_property(property_name='TRMX',
                               rawx_key='trmx',
                               class_type=float,
                               description='Maximum bridge active power transfer',
                               unit=Unit.get_mw())

        self.register_property(property_name='VTMN',
                               rawx_key='vtmn',
                               class_type=float,
                               description='Minimum voltage at the "to" bus',
                               unit=Unit.get_pu())

        self.register_property(property_name='VTMX',
                               rawx_key='vtmx',
                               class_type=float,
                               description='Maximum voltage at the "to" bus',
                               unit=Unit.get_pu())

        self.register_property(property_name='VSMX',
                               rawx_key='vsmx',
                               class_type=float,
                               description='Maximum series voltage',
                               unit=Unit.get_pu())

        self.register_property(property_name='IMX',
                               rawx_key='imx',
                               class_type=int,
                               description='Maximum series current. Zero for no series current limit',
                               unit=Unit.get_mva())

        self.register_property(property_name='LINX',
                               rawx_key='linx',
                               class_type=float,
                               description='Reactance of the series element used during power flow solutions',
                               unit=Unit.get_pu())

        self.register_property(property_name='RMPCT',
                               rawx_key='rmpct',
                               class_type=float,
                               description='Percentage of the total Mvar required to hold the voltage at the bus '
                                           'controlled by the shunt element',
                               min_value=0.0,
                               max_value=100.0,
                               unit=Unit.get_percent())

        self.register_property(property_name='OWNER',
                               rawx_key='owner',
                               class_type=int,
                               description='Owner number',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='SET1',
                               rawx_key='set1',
                               class_type=float,
                               description='Set value 1 (see manual)')

        self.register_property(property_name='SET2',
                               rawx_key='set2',
                               class_type=float,
                               description='Set value  (see manual)')

        self.register_property(property_name='VSREF',
                               rawx_key='vsref',
                               class_type=int,
                               description='Series voltage reference code',
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
                               description='Remote bus number',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='MNAME',
                               rawx_key='mname',
                               class_type=str,
                               description='device name')

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
