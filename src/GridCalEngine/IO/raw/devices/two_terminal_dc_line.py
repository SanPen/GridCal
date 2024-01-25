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

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol, Unit
from GridCalEngine.IO.raw.devices.psse_object import RawObject
from GridCalEngine.basic_structures import Logger


class RawTwoTerminalDCLine(RawObject):

    def __init__(self):
        RawObject.__init__(self, "Two-terminal DC line")

        self.NAME = ""
        self.MDC = 0
        self.RDC = 0
        self.SETVL = 0
        self.VSCHD = 0
        self.VCMOD = 0
        self.RCOMP = 0
        self.DELTI = 0
        self.METER = "I"
        self.DCVMIN = 0
        self.CCCITMX = 20
        self.CCCACC = 1.0

        self.IPR = 0
        self.NBR = 0
        self.ANMXR = 0
        self.ANMNR = 0
        self.RCR = 0
        self.XCR = 0
        self.EBASR = 0
        self.TRR = 1.0
        self.TAPR = 0
        self.TMXR = 1.5
        self.TMNR = 0.51
        self.STPR = 0.00625
        self.ICR = 0
        self.NDR = 0
        self.IFR = 0
        self.ITR = 0
        self.IDR = '1'
        self.XCAPR = 0

        self.IPI = 0
        self.NBI = 0
        self.ANMXI = 0
        self.ANMNI = 0
        self.RCI = 0
        self.XCI = 0
        self.EBASI = 0
        self.TRI = 1.0
        self.TAPI = 0
        self.TMXI = 1.5
        self.TMNI = 0.51
        self.STPI = 0.00625
        self.ICI = 0
        self.NDI = 0
        self.IFI = 0
        self.ITI = 0
        self.IDI = '1'
        self.XCAPI = 0

        self.register_property(property_name='NAME',
                               rawx_key='name',
                               class_type=str,
                               description='Line name',
                               max_chars=12)

        self.register_property(property_name='MDC',
                               rawx_key='mdc',
                               class_type=int,
                               description='Control mode: 0 for blocked, 1 for power, 2 for current.',
                               min_value=0,
                               max_value=2)

        self.register_property(property_name='RDC',
                               rawx_key='rdc',
                               class_type=float,
                               description='DC line resistance',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.ohm))

        self.register_property(property_name='SETVL',
                               rawx_key='setvl',
                               class_type=float,
                               description='Sending power',
                               unit=Unit(UnitMultiplier.M, UnitSymbol.W))

        self.register_property(property_name='VSCHD',
                               rawx_key='vschd',
                               class_type=float,
                               description='DC voltage',
                               unit=Unit(UnitMultiplier.k, UnitSymbol.V))

        self.register_property(property_name='VCMOD',
                               rawx_key='vcmod',
                               class_type=float,
                               description='Mode switch dc voltage',
                               unit=Unit(UnitMultiplier.k, UnitSymbol.V))

        self.register_property(property_name='RCOMP',
                               rawx_key='rcomp',
                               class_type=float,
                               description='Compounding resistance',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.ohm))

        self.register_property(property_name='DELTI',
                               rawx_key='delti',
                               class_type=float,
                               description='Margin entered in per unit of desired dc power',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='METER',
                               rawx_key='meter',
                               class_type=str,
                               description='Metered end code of either R (for rectifier) or I (for inverter).')

        self.register_property(property_name='DCVMIN',
                               rawx_key='dcvmin',
                               class_type=float,
                               description='Minimum dc voltage;',
                               unit=Unit(UnitMultiplier.k, UnitSymbol.V))

        self.register_property(property_name='CCCITMX',
                               rawx_key='cccitmx',
                               class_type=int,
                               description='Iteration limit for capacitor commutated two-terminal dc line '
                                           'Newton solution procedure.')

        self.register_property(property_name='CCCACC',
                               rawx_key='cccacc',
                               class_type=float,
                               description='Acceleration factor for capacitor commutated two-terminal dc '
                                           'line Newton solution procedure')

        self.register_property(property_name='IPR',
                               rawx_key='ipr',
                               class_type=int,
                               description='Rectifier converter bus number',
                               min_value=0,
                               max_value=999997)

        self.register_property(property_name='NBR',
                               rawx_key='nbr',
                               class_type=int,
                               description='Rectifier number of bridges in series')

        self.register_property(property_name='ANMXR',
                               rawx_key='anmxr',
                               class_type=float,
                               description='Rectifier nominal maximum rectifier firing angle',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.deg))

        self.register_property(property_name='ANMNR',
                               rawx_key='anmnr',
                               class_type=float,
                               description='Rectifier minimum steady-state rectifier firing angle',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.deg))

        self.register_property(property_name='RCR',
                               rawx_key='rcr',
                               class_type=float,
                               description='Rectifier commutating transformer resistance per bridge',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.ohm))

        self.register_property(property_name='XCR',
                               rawx_key='xcr',
                               class_type=float,
                               description='Rectifier commutating transformer reactance per bridge',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.ohm))

        self.register_property(property_name='EBASR',
                               rawx_key='ebasr',
                               class_type=float,
                               description='Rectifier primary base ac voltage',
                               unit=Unit(UnitMultiplier.k, UnitSymbol.V))

        self.register_property(property_name='TRR',
                               rawx_key='trr',
                               class_type=float,
                               description='Rectifier transformer ratio.')

        self.register_property(property_name='TAPR',
                               rawx_key='tapr',
                               class_type=float,
                               description='Rectifier tap setting',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='TMXR',
                               rawx_key='tmxr',
                               class_type=float,
                               description='Maximum rectifier tap setting.',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='TMNR',
                               rawx_key='tmnr',
                               class_type=float,
                               description='Minimum rectifier tap setting',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='STPR',
                               rawx_key='stpr',
                               class_type=float,
                               description='Rectifier tap step;',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu),
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='ICR',
                               rawx_key='icr',
                               class_type=int,
                               description='Bus number of the rectifier commutating bus',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='NDR',
                               rawx_key='ndr',
                               class_type=int,
                               description='A node number of bus ICR',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='IFR',
                               rawx_key='ifr',
                               class_type=int,
                               description='Winding 1 side from bus number')

        self.register_property(property_name='ITR',
                               rawx_key='itr',
                               class_type=int,
                               description='Winding 2 side to bus number')

        self.register_property(property_name='IDR',
                               rawx_key='idr',
                               class_type=str,
                               description='Circuit identifier; the branch described by IFR, ITR, and IDR must have '
                                           'been entered as a two-winding transformer')

        self.register_property(property_name='XCAPR',
                               rawx_key='xcapr',
                               class_type=float,
                               description='Commutating capacitor reactance magnitude per bridge',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.ohm))

        self.register_property(property_name='IPI',
                               rawx_key='ipi',
                               class_type=int,
                               description='Inverter converter bus number',
                               min_value=0,
                               max_value=999997)

        self.register_property(property_name='NBI',
                               rawx_key='nbi',
                               class_type=int,
                               description='Inverter number of bridges in series')

        self.register_property(property_name='ANMXI',
                               rawx_key='anmxi',
                               class_type=float,
                               description='Inverter nominal maximum Inverter firing angle',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.deg))

        self.register_property(property_name='ANMNI',
                               rawx_key='anmni',
                               class_type=float,
                               description='Inverter minimum steady-state Inverter firing angle',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.deg))

        self.register_property(property_name='RCI',
                               rawx_key='rci',
                               class_type=float,
                               description='Inverter commutating transformer resistance per bridge',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.ohm))

        self.register_property(property_name='XCI',
                               rawx_key='xci',
                               class_type=float,
                               description='Inverter commutating transformer reactance per bridge',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.ohm))

        self.register_property(property_name='EBASI',
                               rawx_key='ebasi',
                               class_type=float,
                               description='Inverter primary base ac voltage',
                               unit=Unit(UnitMultiplier.k, UnitSymbol.V))

        self.register_property(property_name='TRI',
                               rawx_key='tri',
                               class_type=float,
                               description='Inverter transformer ratio.')

        self.register_property(property_name='TAPI',
                               rawx_key='tapi',
                               class_type=float,
                               description='Inverter tap setting',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='TMXI',
                               rawx_key='tmxi',
                               class_type=float,
                               description='Maximum Inverter tap setting.',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='TMNI',
                               rawx_key='tmni',
                               class_type=float,
                               description='Minimum Inverter tap setting',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu))

        self.register_property(property_name='STPI',
                               rawx_key='stpi',
                               class_type=float,
                               description='Inverter tap step;',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.pu),
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='ICI',
                               rawx_key='ici',
                               class_type=int,
                               description='Bus number of the Inverter commutating bus',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='NDI',
                               rawx_key='ndi',
                               class_type=int,
                               description='A node number of bus ICR',
                               min_value=0,
                               max_value=999999)

        self.register_property(property_name='IFI',
                               rawx_key='ifi',
                               class_type=int,
                               description='Winding 1 side from bus number')

        self.register_property(property_name='ITI',
                               rawx_key='iti',
                               class_type=int,
                               description='Winding 2 side to bus number')

        self.register_property(property_name='IDI',
                               rawx_key='idi',
                               class_type=str,
                               description='Circuit identifier; the branch described by IFR, ITR, and IDR must have '
                                           'been entered as a two-winding transformer')

        self.register_property(property_name='XCAPI',
                               rawx_key='xcapi',
                               class_type=float,
                               description='Commutating capacitor reactance magnitude per bridge',
                               unit=Unit(UnitMultiplier.none, UnitSymbol.ohm))

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if 34 <= version >= 35:
            '''
            'NAME',MDC,RDC,SETVL,VSCHD,VCMOD,RCOMP,DELTI,METER,DCVMIN,CCCITMX,CCCACC
            IPR,NBR,ANMXR,ANMNR,RCR,XCR,EBASR,TRR,TAPR,TMXR,TMNR,STPR,ICR,IFR,ITR,IDR,XCAPR
            IPI,NBI,ANMXI,ANMNI,RCI,XCI,EBASI,TRI,TAPI,TMXI,TMNI,STPI,ICI,IFI,ITI,IDI,XCAPI
            '''

            (self.NAME, self.MDC, self.RDC, self.SETVL, self.VSCHD, self.VCMOD, self.RCOMP, self.DELTI, self.METER,
             self.DCVMIN, self.CCCITMX, self.CCCACC) = data[0]

            (self.IPR, self.NBR, self.ANMXR, self.ANMNR, self.RCR, self.XCR, self.EBASR, self.TRR, self.TAPR,
             self.TMXR, self.TMNR, self.STPR, self.ICR, self.NDR, self.IFR, self.ITR, self.IDR, self.XCAPR) = data[1]

            (self.IPI, self.NBI, self.ANMXI, self.ANMNI, self.RCI, self.XCI, self.EBASI, self.TRI, self.TAPI,
             self.TMXI, self.TMNI, self.STPI, self.ICI, self.NDI, self.IFI, self.ITI, self.IDI, self.XCAPI) = data[2]

        elif 30 <= version <= 33:
            '''
            'NAME',MDC,RDC,SETVL,VSCHD,VCMOD,RCOMP,DELTI,METER,DCVMIN,CCCITMX,CCCACC
            IPR,NBR,ANMXR,ANMNR,RCR,XCR,EBASR,TRR,TAPR,TMXR,TMNR,STPR,ICR,IFR,ITR,IDR,XCAPR
            IPI,NBI,ANMXI,ANMNI,RCI,XCI,EBASI,TRI,TAPI,TMXI,TMNI,STPI,ICI,IFI,ITI,IDI,XCAPI
            '''

            (self.NAME, self.MDC, self.RDC, self.SETVL, self.VSCHD, self.VCMOD, self.RCOMP, self.DELTI, self.METER,
             self.DCVMIN, self.CCCITMX, self.CCCACC) = data[0]

            (self.IPR, self.NBR, self.ANMXR, self.ANMNR, self.RCR, self.XCR, self.EBASR, self.TRR, self.TAPR,
             self.TMXR, self.TMNR, self.STPR, self.ICR, self.IFR, self.ITR, self.IDR, self.XCAPR) = data[1]

            (self.IPI, self.NBI, self.ANMXI, self.ANMNI, self.RCI, self.XCI, self.EBASI, self.TRI, self.TAPI,
             self.TMXI, self.TMNI, self.STPI, self.ICI, self.IFI, self.ITI, self.IDI, self.XCAPI) = data[2]

        elif version == 29:
            '''
            I,MDC,RDC,SETVL,VSCHD,VCMOD,RCOMP,DELTI,METER,DCVMIN,CCCITMX,CCCACC
            IPR,NBR,ALFMX,ALFMN,RCR,XCR,EBASR,TRR,TAPR,TMXR,TMNR,STPR,ICR,IFR,ITR,IDR,XCAPR
            IPI,NBI,GAMMX,GAMMN,RCI,XCI,EBASI,TRI,TAPI,TMXI,TMNI,STPI,ICI,IFI,ITI,IDI,XCAPI
            '''

            (self.I, self.MDC, self.RDC, self.SETVL, self.VSCHD, self.VCMOD, self.RCOMP, self.DELTI, self.METER,
             self.DCVMIN, self.CCCITMX, self.CCCACC) = data[0]

            (self.IPR, self.NBR, self.ANMXR, self.ANMNR, self.RCR, self.XCR, self.EBASR, self.TRR, self.TAPR,
             self.TMXR, self.TMNR, self.STPR, self.ICR, self.IFR, self.ITR, self.IDR, self.XCAPR) = data[1]

            (self.IPI, self.NBI, self.ANMXI, self.ANMNI, self.RCI, self.XCI, self.EBASI, self.TRI, self.TAPI,
             self.TMXI, self.TMNI, self.STPI, self.ICI, self.IFI, self.ITI, self.IDI, self.XCAPI) = data[2]

            self.NAME = str(self.I)
        else:
            logger.add_warning('Version not implemented for DC Lines', str(version))

    def get_raw_line(self, version):

        if version >= 35:
            '''
            'NAME',MDC,RDC,SETVL,VSCHD,VCMOD,RCOMP,DELTI,METER,DCVMIN,CCCITMX,CCCACC
            IPR,NBR,ANMXR,ANMNR,RCR,XCR,EBASR,TRR,TAPR,TMXR,TMNR,STPR,ICR,IFR,ITR,IDR,XCAPR
            IPI,NBI,ANMXI,ANMNI,RCI,XCI,EBASI,TRI,TAPI,TMXI,TMNI,STPI,ICI,IFI,ITI,IDI,XCAPI
            '''

            l0 = self.format_raw_line([self.NAME, self.MDC, self.RDC, self.SETVL, self.VSCHD, self.VCMOD, self.RCOMP,
                                       self.DELTI, self.METER, self.DCVMIN, self.CCCITMX, self.CCCACC])

            l1 = self.format_raw_line([self.IPR, self.NBR, self.ANMXR, self.ANMNR, self.RCR, self.XCR, self.EBASR,
                                       self.TRR, self.TAPR, self.TMXR, self.TMNR, self.STPR, self.ICR, self.NDR,
                                       self.IFR, self.ITR, self.IDR, self.XCAPR])

            l2 = self.format_raw_line([self.IPI, self.NBI, self.ANMXI, self.ANMNI, self.RCI, self.XCI, self.EBASI,
                                       self.TRI, self.TAPI, self.TMXI, self.TMNI, self.STPI, self.ICI, self.NDI,
                                       self.IFI,
                                       self.ITI, self.IDI, self.XCAPI])

            return l0 + '\n' + l1 + '\n' + l2

        if 30 <= version <= 34:
            '''
            'NAME',MDC,RDC,SETVL,VSCHD,VCMOD,RCOMP,DELTI,METER,DCVMIN,CCCITMX,CCCACC
            IPR,NBR,ANMXR,ANMNR,RCR,XCR,EBASR,TRR,TAPR,TMXR,TMNR,STPR,ICR,IFR,ITR,IDR,XCAPR
            IPI,NBI,ANMXI,ANMNI,RCI,XCI,EBASI,TRI,TAPI,TMXI,TMNI,STPI,ICI,IFI,ITI,IDI,XCAPI
            '''

            l0 = self.format_raw_line([self.NAME, self.MDC, self.RDC, self.SETVL, self.VSCHD, self.VCMOD, self.RCOMP,
                                       self.DELTI, self.METER, self.DCVMIN, self.CCCITMX, self.CCCACC])

            l1 = self.format_raw_line([self.IPR, self.NBR, self.ANMXR, self.ANMNR, self.RCR, self.XCR, self.EBASR,
                                       self.TRR, self.TAPR, self.TMXR, self.TMNR, self.STPR, self.ICR, self.IFR,
                                       self.ITR, self.IDR, self.XCAPR])

            l2 = self.format_raw_line([self.IPI, self.NBI, self.ANMXI, self.ANMNI, self.RCI, self.XCI, self.EBASI,
                                       self.TRI, self.TAPI, self.TMXI, self.TMNI, self.STPI, self.ICI, self.IFI,
                                       self.ITI, self.IDI, self.XCAPI])

            return l0 + '\n' + l1 + '\n' + l2

        elif version == 29:
            '''
            I,MDC,RDC,SETVL,VSCHD,VCMOD,RCOMP,DELTI,METER,DCVMIN,CCCITMX,CCCACC
            IPR,NBR,ALFMX,ALFMN,RCR,XCR,EBASR,TRR,TAPR,TMXR,TMNR,STPR,ICR,IFR,ITR,IDR,XCAPR
            IPI,NBI,GAMMX,GAMMN,RCI,XCI,EBASI,TRI,TAPI,TMXI,TMNI,STPI,ICI,IFI,ITI,IDI,XCAPI
            '''

            l0 = self.format_raw_line([self.I, self.MDC, self.RDC, self.SETVL, self.VSCHD, self.VCMOD, self.RCOMP,
                                       self.DELTI, self.METER, self.DCVMIN, self.CCCITMX, self.CCCACC])

            l1 = self.format_raw_line([self.IPR, self.NBR, self.ANMXR, self.ANMNR, self.RCR, self.XCR, self.EBASR,
                                       self.TRR, self.TAPR, self.TMXR, self.TMNR, self.STPR, self.ICR, self.IFR,
                                       self.ITR, self.IDR, self.XCAPR])

            l2 = self.format_raw_line([self.IPI, self.NBI, self.ANMXI, self.ANMNI, self.RCI, self.XCI, self.EBASI,
                                       self.TRI, self.TAPI, self.TMXI, self.TMNI, self.STPI, self.ICI, self.IFI,
                                       self.ITI, self.IDI, self.XCAPI])

            return l0 + '\n' + l1 + '\n' + l2
        else:
            raise Exception('Version not implemented for DC Lines ' + str(version))

    def get_id(self):
        """
        Get the element PSSE ID
        :return:
        """
        return "{0}_{1}_1".format(self.IPR, self.IPI)
