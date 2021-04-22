# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import chardet
import re
from typing import List, AnyStr, Dict

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Devices import *


class PSSeGrid:

    def __init__(self, data):
        """

        Args:
            data: array with the values
        """

        self.IC, self.SBASE, self.REV, self.XFRRAT, self.NXFRAT, self.BASFRQ = data

        """
        Case Identification Data
        Bus Data
        Load Data
        Fixed Bus Shunt Data
        Generator Data
        Non-Transformer Branch Data
        Transformer Data
        Area Interchange Data
        Two-Terminal DC Transmission Line Data
        Voltage Source Converter (VSC) DC Transmission Line Data
        Transformer Impedance Correction Tables
        Multi-Terminal DC Transmission Line Data
        Multi-Section Line Grouping Data
        Zone Data
        Interarea Transfer Data
        Owner Data
        FACTS Device Data
        Switched Shunt Data
        GNE Device Data
        Induction Machine Data
        Q Record
        """
        self.buses = list()
        self.loads = list()
        self.shunts = list()
        self.switched_shunts = list()
        self.generators = list()
        self.lines = list()
        self.transformers = list()
        self.hvdc_lines = list()
        self.facts = list()
        self.areas = list()
        self.zones = list()

    def get_circuit(self, logger: Logger):
        """
        Return Newton circuit
        Returns:

        """

        circuit = MultiCircuit(Sbase=self.SBASE)
        circuit.comments = 'Converted from a PSS/e .raw file'

        circuit.areas = [Area(name=x.ARNAME) for x in self.areas]
        circuit.zones = [Zone(name=x.ZONAME) for x in self.zones]

        area_dict = {val.I: elm for val, elm in zip(self.areas, circuit.areas)}
        zones_dict = {val.I: elm for val, elm in zip(self.zones, circuit.zones)}

        # ---------------------------------------------------------------------
        # Bus related
        # ---------------------------------------------------------------------
        psse_bus_dict = dict()
        slack_buses = list()

        for psse_bus in self.buses:

            # relate each PSS bus index with a Newton bus object
            psse_bus_dict[psse_bus.I] = psse_bus.bus

            # replace area idx by area name if available
            if abs(psse_bus.bus.area) in area_dict.keys():
                psse_bus.bus.area = area_dict[abs(psse_bus.bus.area)]

            if abs(psse_bus.bus.zone) in zones_dict.keys():
                psse_bus.bus.zone = zones_dict[abs(psse_bus.bus.zone)]

            if psse_bus.bus.type.value == 3:
                slack_buses.append(psse_bus.I)

            # add the bus to the circuit
            psse_bus.bus.ensure_area_objects(circuit)
            circuit.add_bus(psse_bus.bus)

        for area in self.areas:
            if area.ISW not in slack_buses:
                logger.add_error('The area slack bus is not marked as slack', str(area.ISW))

        # Go through loads
        for psse_load in self.loads:
            bus = psse_bus_dict[psse_load.I]
            api_obj = psse_load.get_object(bus, logger)

            circuit.add_load(bus, api_obj)

        # Go through shunts
        for psse_shunt in self.shunts + self.switched_shunts:
            bus = psse_bus_dict[psse_shunt.I]
            api_obj = psse_shunt.get_object(bus, logger)

            circuit.add_shunt(bus, api_obj)

        # Go through generators
        for psse_gen in self.generators:
            bus = psse_bus_dict[psse_gen.I]
            api_obj = psse_gen.get_object(logger)

            circuit.add_generator(bus, api_obj)

        # ---------------------------------------------------------------------
        # Branches
        # ---------------------------------------------------------------------
        # Go through Branches
        already_there = set()
        for psse_banch in self.lines:
            # get the object
            branch = psse_banch.get_object(psse_bus_dict, self.SBASE, logger)

            if branch.idtag not in already_there:

                # Add to the circuit
                circuit.add_line(branch)

                already_there.add(branch.idtag)

            else:
                logger.add_warning('The RAW file has a repeated line device and it is omitted from the model',
                                   str(branch.idtag))

        # Go through Transformers
        for psse_banch in self.transformers:
            # get the object
            branches = psse_banch.get_object(psse_bus_dict, self.SBASE, logger)

            for branch in branches:
                if branch.idtag not in already_there:
                    # Add to the circuit
                    circuit.add_transformer2w(branch)
                    already_there.add(branch.idtag)

                else:
                    logger.add_warning('The RAW file has a repeated transformer and it is omitted from the model',
                                       branch.idtag)

        # Go through hvdc lines
        for psse_banch in self.hvdc_lines:
            # get the object
            branch = psse_banch.get_object(psse_bus_dict, self.SBASE, logger)

            if branch.idtag not in already_there:

                # Add to the circuit
                circuit.add_hvdc(branch)
                already_there.add(branch.idtag)

            else:
                logger.add_warning('The RAW file has a repeated HVDC line device and it is omitted from the model',
                                   str(branch.idtag))

        # Go through facts lines
        for psse_elm in self.facts:
            # since these may be shunt or series or both, pass the circuit so that the correct device is added
            psse_elm.get_object(psse_bus_dict, self.SBASE, logger, circuit)

        return circuit


class PSSeBus:

    def __init__(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        bustype = {1: BusMode.PQ, 2: BusMode.PV, 3: BusMode.Slack, 4: BusMode.PQ}

        if version == 33:
            n = len(data[0])
            dta = np.zeros(13, dtype=object)
            dta[0:n] = data[0]

            self.I, self.NAME, self.BASKV, self.IDE, self.AREA, self.ZONE, \
            self.OWNER, self.VM, self.VA, self.NVHI, self.NVLO, self.EVHI, self.EVLO = dta

            # create bus
            name = self.NAME.replace("'", "")
            self.bus = Bus(name=name,
                           vnom=self.BASKV, code=str(self.I), vmin=self.EVLO, vmax=self.EVHI, xpos=0, ypos=0, active=True,
                           area=self.AREA, zone=self.ZONE)

        elif version == 32:

            self.I, self.NAME, self.BASKV, self.IDE, self.AREA, self.ZONE, self.OWNER, self.VM, self.VA = data[0]

            # create bus
            name = self.NAME
            self.bus = Bus(name=name, code=str(self.I), vnom=self.BASKV, vmin=0.9, vmax=1.1, xpos=0, ypos=0,
                           active=True, area=self.AREA, zone=self.ZONE)

        elif version in [29, 30]:
            # I, ’NAME’, BASKV, IDE, GL, BL, AREA, ZONE, VM, VA, OWNER
            self.I, self.NAME, self.BASKV, self.IDE, self.GL, self.BL, \
            self.AREA, self.ZONE, self.VM, self.VA, self.OWNER = data[0]

            # create bus
            name = self.NAME
            self.bus = Bus(name=name, code=str(self.I), vnom=self.BASKV, vmin=0.9, vmax=1.1, xpos=0, ypos=0,
                           active=True, area=self.AREA, zone=self.ZONE)

            if self.GL > 0 or self.BL > 0:
                sh = Shunt(name='Shunt_' + str(self.I),
                           G=self.GL, B=self.BL,
                           active=True)

                self.bus.shunts.append(sh)

        else:
            logger.add_warning('Bus not implemented for version', str(version))

        # set type
        if self.IDE in bustype.keys():
            self.bus.type = bustype[self.IDE]
        else:
            self.bus.type = BusMode.PQ

        if int(self.IDE) == 4:
            self.bus.active = False

        if self.bus.type == BusMode.Slack:
            self.bus.is_slack = True

        if int(self.IDE) == 4:
            self.bus.active = False

        # Ensures unique name
        self.bus.name = self.bus.name.replace("'", "").strip()
        self.bus.code = str(self.I)


class PSSeLoad:

    def __init__(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if version == 33:

            n = len(data[0])
            dta = np.zeros(14, dtype=object)
            dta[0:n] = data[0]

            self.I, self.ID, self.STATUS, self.AREA, self.ZONE, self.PL, self.QL, \
            self.IP, self.IQ, self.YP, self.YQ, self.OWNER, self.SCALE, self.INTRPT = dta

        elif version == 32:

            self.I, self.ID, self.STATUS, self.AREA, self.ZONE, self.PL, self.QL, \
            self.IP, self.IQ, self.YP, self.YQ, self.OWNER, self.SCALE = data[0]

        elif version in [29, 30]:
            # I, ID, STATUS, AREA, ZONE, PL, QL, IP, IQ, YP, YQ, OWNER
            self.I, self.ID, self.STATUS, self.AREA, self.ZONE, \
            self.PL, self.QL, self.IP, self.IQ, self.YP, self.YQ, self.OWNER = data[0]

        else:
            logger.add_warning('Load not implemented for version', str(version))

    def get_object(self, bus: Bus, logger: Logger):
        """
        Return Newton Load object
        Returns:
            Newton Load object
        """
        name = str(self.I) + '_' + self.ID.replace("'", "")
        name = name.strip()

        # GL and BL come in MW and MVAr
        vv = bus.Vnom ** 2.0

        if vv == 0:
            logger.add_error('Voltage equal to zero in shunt conversion', name)

        g, b = self.YP, self.YQ
        ir, ii = self.IP, self.IQ
        p, q = self.PL, self.QL

        elm = Load(name=name,
                   idtag=None,
                   code=name,
                   active=bool(self.STATUS),
                   P=p, Q=q)

        return elm


class PSSeSwitchedShunt:

    def __init__(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """
        self.N1 = ''
        self.N2 = ''
        self.N3 = ''
        self.N4 = ''
        self.N5 = ''
        self.N6 = ''
        self.N7 = ''
        self.N8 = ''
        self.B1 = ''
        self.B2 = ''
        self.B3 = ''
        self.B4 = ''
        self.B5 = ''
        self.B6 = ''
        self.B7 = ''
        self.B8 = ''

        var = [self.N1, self.B1,
               self.N2, self.B2,
               self.N3, self.B3,
               self.N4, self.B4,
               self.N5, self.B5,
               self.N6, self.B6,
               self.N7, self.B7,
               self.N8, self.B8, ]

        if version in [34, 33, 32]:
            self.I, self.MODSW, self.ADJM, self.STAT, self.VSWHI, self.VSWLO, \
            self.SWREM, self.RMPCT, self.RMIDNT, self.BINIT, *var = data[0]
        else:
            logger.add_warning('Shunt not implemented for the version', str(version))

    def get_object(self, bus: Bus, logger: Logger):
        """
        Return Newton Load object
        Returns:
            Newton Load object
        """
        name = str(self.I).replace("'", "")
        name = name.strip()

        # GL and BL come in MW and MVAr
        # THey must be in siemens
        vv = bus.Vnom ** 2.0

        if vv == 0:
            logger.add_error('Voltage equal to zero in shunt conversion', name)

        g = 0.0
        if self.MODSW in [1, 2]:
            b = self.BINIT * self.RMPCT / 100.0
        else:
            b = self.BINIT

        elm = Shunt(name='Switched shunt ' + name,
                    G=g, B=b,
                    active=bool(self.STAT))

        return elm


class PSSeShunt:

    def __init__(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """
        if version in [33, 32]:
            self.I, self.ID, self.STATUS, self.GL, self.BL = data[0]
        else:
            logger.add_warning('Shunt not implemented for the version', str(version))

    def get_object(self, bus: Bus, logger: Logger):
        """
        Return Newton Load object
        Returns:
            Newton Load object
        """
        name = str(self.I) + '_' + str(self.ID).replace("'", "")
        name = name.strip()

        # GL and BL come in MW and MVAr
        # They must be in siemens
        vv = bus.Vnom * bus.Vnom

        if vv == 0:
            logger.add_error('Voltage equal to zero in shunt conversion', name)

        g = self.GL
        b = self.BL

        elm = Shunt(name=name,
                    idtag=name,
                    G=g, B=b,
                    active=bool(self.STATUS))

        return elm


class PSSeGenerator:

    def __init__(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        self.I = 0
        self.ID = 0
        self.PG = 0
        self.QG = 0
        self.QT = 0
        self.QB = 0
        self.VS = 0
        self.IREG = 0
        self.MBASE = 0
        self.ZR = 0
        self.ZX = 0
        self.RT = 0
        self.XT = 0
        self.GTAP = 0
        self.STAT = 0
        self.RMPCT = 0
        self.PT = 0
        self.PB = 0
        self.O1 = 0
        self.F1 = 0
        self.O2 = 0
        self.F2 = 0
        self.O3 = 0
        self.F3 = 0
        self.O4 = 0
        self.F4 = 0
        self.WMOD = 0
        self.WPF = 0

        var = [self.O1, self.F1,
               self.O2, self.F2,
               self.O3, self.F3,
               self.O4, self.F4]

        length = len(data[0])

        if version in [33, 32, 30]:

            self.I, self.ID, self.PG, self.QG, self.QT, self.QB, self.VS, self.IREG, self.MBASE, \
            self.ZR, self.ZX, self.RT, self.XT, self.GTAP, self.STAT, self.RMPCT, self.PT, self.PB, *var, \
            self.WMOD, self.WPF = data[0]

        elif version in [29]:
            """
            I,ID,PG,QG,QT,QB,VS,IREG,MBASE,
            ZR,ZX,RT,XT,GTAP,STAT,RMPCT,PT,PB,
            O1,F1,...,O4,F4
            """

            self.I, self.ID, self.PG, self.QG, self.QT, self.QB, self.VS, self.IREG, self.MBASE, \
            self.ZR, self.ZX, self.RT, self.XT, self.GTAP, self.STAT, self.RMPCT, self.PT, self.PB, *var = data[0]

        else:
            logger.add_warning('Generator not implemented for version', str(version))

    def get_object(self, logger: list):
        """
        Return Newton Load object
        Returns:
            Newton Load object
        """
        name = str(self.I) + '_' + str(self.ID).replace("'", "")
        elm = Generator(name=name,
                        idtag=None,
                        code=name,
                        active_power=self.PG,
                        voltage_module=self.VS,
                        Qmin=self.QB,
                        Qmax=self.QT,
                        Snom=self.MBASE,
                        p_max=self.PT,
                        p_min=self.PB,
                        active=bool(self.STAT))

        return elm


class PSSeInductionMachine:

    def __init__(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if version in [30, 32, 33]:
            '''
            I,ID,STAT,SCODE,DCODE,AREA,ZONE,OWNER,TCODE,BCODE,MBASE,RATEKV,
            PCODE,PSET,H,A,B,D,E,RA,XA,XM,R1,X1,R2,X2,X3,E1,SE1,E2,SE2,IA1,IA2,
            XAMULT
            '''
            self.I, self.ID, self.STAT, self.SCODE, self.DCODE, self.AREA, self.ZONE, self.OWNER, \
            self.TCODE, self.BCODE, self.MBASE, self.RATEKV = data[0]

            self.PCODE, self.PSET, self.H, self.A, self.B, self.D, self.E, self.RA, self.XA, self.XM, self.R1, \
            self.X1, self.R2, self.X2, self.X3, self.E1, self.SE1, self.E2, self.SE2, self.IA1, self.IA2 = data[1]

            self.XAMULT = data[2]
        else:
            logger.add_warning('Induction machine not implemented for version', str(version))

    def get_object(self, logger: list):
        """
        Return Newton Load object
        Returns:
            Newton Load object
        """

        elm = Generator(name=str(self.I) + '_' + str(self.ID),
                        active_power=self.PSET,
                        voltage_module=self.RATEKV,
                        Snom=self.MBASE,
                        active=bool(self.STAT))

        return elm


class PSSeBranch:

    def __init__(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        self.O1 = ''
        self.F1 = ''
        self.O2 = ''
        self.F2 = ''
        self.O3 = ''
        self.F3 = ''
        self.O4 = ''
        self.F4 = ''
        var = [self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4]

        if version in [33, 32]:

            '''
            I,J,CKT,R,X,B,RATEA,RATEB,RATEC,GI,BI,GJ,BJ,ST,MET,LEN,O1,F1,...,O4,F4
            '''

            self.I, self.J, self.CKT, self.R, self.X, self.B, self.RATEA, self.RATEB, self.RATEC, \
            self.GI, self.BI, self.GJ, self.BJ, self.ST, self.MET, self.LEN, *var = data[0]

        elif version in [29, 30]:
            """
            v29, v30
            I,J,CKT,R,X,B,RATEA,RATEB,RATEC,GI,BI,GJ,BJ,ST,LEN,01,F1,...,04,F4
            """

            self.I, self.J, self.CKT, self.R, self.X, self.B, self.RATEA, self.RATEB, self.RATEC, \
            self.GI, self.BI, self.GJ, self.BJ, self.ST, self.LEN, *var = data[0]

        else:

            logger.add_warning('Branch not implemented for version', str(version))

    def get_object(self, psse_bus_dict, Sbase, logger: Logger):
        """
        Return Newton branch object
        Args:
            psse_bus_dict: Dictionary that relates PSSe bus indices with Newton Bus objects

        Returns:
            Newton Branch object
        """
        i = abs(self.I)
        j = abs(self.J)
        bus_from = psse_bus_dict[i]
        bus_to = psse_bus_dict[j]
        name = str(i) + '_' + str(j) + '_' + str(self.CKT).replace("'", "").strip()

        branch = Line(bus_from=bus_from, bus_to=bus_to,
                      idtag=None,
                      code=name,
                      name=name,
                      r=self.R,
                      x=self.X,
                      b=self.B,
                      rate=max(self.RATEA, self.RATEB, self.RATEC),
                      active=bool(self.ST),
                      mttf=0,
                      mttr=0,
                      length=self.LEN)
        return branch


class PSSeTwoTerminalDCLine:

    def __init__(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if version in [32, 33, 34]:
            '''
            'NAME',MDC,RDC,SETVL,VSCHD,VCMOD,RCOMP,DELTI,METER,DCVMIN,CCCITMX,CCCACC
            IPR,NBR,ANMXR,ANMNR,RCR,XCR,EBASR,TRR,TAPR,TMXR,TMNR,STPR,ICR,IFR,ITR,IDR,XCAPR
            IPI,NBI,ANMXI,ANMNI,RCI,XCI,EBASI,TRI,TAPI,TMXI,TMNI,STPI,ICI,IFI,ITI,IDI,XCAPI 
            '''

            self.NAME, self.MDC, self.RDC, self.SETVL, self.VSCHD, self.VCMOD, self.RCOMP, self.DELTI, self.METER, \
            self.DCVMIN, self.CCCITMX, self.CCCACC = data[0]

            self.IPR, self.NBR, self.ANMXR, self.ANMNR, self.RCR, self.XCR, self.EBASR, self.TRR, self.TAPR, \
            self.TMXR, self.TMNR, self.STPR, self.ICR, self.IFR, self.ITR, self.IDR, self.XCAPR = data[1]

            self.IPI, self.NBI, self.ANMXI, self.ANMNI, self.RCI, self.XCI, self.EBASI, self.TRI, self.TAPI, \
            self.TMXI, self.TMNI, self.STPI, self.ICI, self.IFI, self.ITI, self.IDI, self.XCAPI = data[2]

        elif version == 29:
            '''
            I,MDC,RDC,SETVL,VSCHD,VCMOD,RCOMP,DELTI,METER,DCVMIN,CCCITMX,CCCACC
            IPR,NBR,ALFMX,ALFMN,RCR,XCR,EBASR,TRR,TAPR,TMXR,TMNR,STPR,ICR,IFR,ITR,IDR,XCAPR
            IPI,NBI,GAMMX,GAMMN,RCI,XCI,EBASI,TRI,TAPI,TMXI,TMNI,STPI,ICI,IFI,ITI,IDI,XCAPI
            '''

            self.I, self.MDC, self.RDC, self.SETVL, self.VSCHD, self.VCMOD, self.RCOMP, self.DELTI, self.METER, \
            self.DCVMIN, self.CCCITMX, self.CCCACC = data[0]

            self.IPR, self.NBR, self.ANMXR, self.ANMNR, self.RCR, self.XCR, self.EBASR, self.TRR, self.TAPR, \
            self.TMXR, self.TMNR, self.STPR, self.ICR, self.IFR, self.ITR, self.IDR, self.XCAPR = data[1]

            self.IPI, self.NBI, self.ANMXI, self.ANMNI, self.RCI, self.XCI, self.EBASI, self.TRI, self.TAPI, \
            self.TMXI, self.TMNI, self.STPI, self.ICI, self.IFI, self.ITI, self.IDI, self.XCAPI = data[2]

            self.NAME = str(self.I)
        else:
            logger.add_warning('Version not implemented for DC Lines', str(version))

    def get_object(self, psse_bus_dict, Sbase, logger: Logger):
        """
        GEt equivalent object
        :param psse_bus_dict:
        :param logger:
        :return:
        """
        bus1 = psse_bus_dict[abs(self.IPR)]
        bus2 = psse_bus_dict[abs(self.IPI)]

        if self.MDC == 1 or self.MDC == 0:
            # SETVL is in MW
            specified_power = self.SETVL
        elif self.MDC == 2:
            # SETVL is in A, specified_power in MW
            specified_power = self.SETVL * self.VSCHD / 1000.0
        else:
            # doesn't say, so zero
            specified_power = 0.0

        z_base = self.VSCHD * self.VSCHD / Sbase
        r_pu = self.RDC / z_base

        Vset_f = 1.0
        Vset_t = 1.0

        name1 = self.NAME.replace("'", "").replace('"', "").replace('/', '').strip()
        idtag = str(self.IPR) + '_' + str(self.IPI) + '_1'

        # set the HVDC line active
        active = bus1.active and bus2.active

        obj = HvdcLine(bus_from=bus1,  # Rectifier as of PSSe
                       bus_to=bus2,  # inverter as of PSSe
                       active=active,
                       name=name1,
                       idtag=idtag,
                       Pset=specified_power,
                       Vset_f=Vset_f,
                       Vset_t=Vset_t,
                       rate=specified_power,
                       min_firing_angle_f=np.deg2rad(self.ANMNR),
                       max_firing_angle_f=np.deg2rad(self.ANMXR),
                       min_firing_angle_t=np.deg2rad(self.ANMNI),
                       max_firing_angle_t=np.deg2rad(self.ANMXI))
        return obj


class PSSeVscDCLine:

    def __init__(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """
        self.O1 = ''
        self.F1 = ''
        self.O2 = ''
        self.F2 = ''
        self.O3 = ''
        self.F3 = ''
        self.O4 = ''
        self.F4 = ''
        var = [self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4]

        if version in [32, 33, 34]:

            '''
            NAME, MDC, RDC, O1, F1, ... O4, F4
            IBUS,TYPE,MODE,DCSET,ACSET,ALOSS,BLOSS,MINLOSS,SMAX,IMAX,PWF,MAXQ,MINQ,REMOT,RMPCT
            IBUS,TYPE,MODE,DCSET,ACSET,ALOSS,BLOSS,MINLOSS,SMAX,IMAX,PWF,MAXQ,MINQ,REMOT,RMPCT
            '''

            self.NAME, self.MDC, self.RDC, *var = data[0]

            self.IBUS1, self.TYPE1, self.MODE1, self.DCSET1, self.ACSET1, self.ALOSS1, self.BLOSS1, self.MINLOSS1, \
            self.SMAX1, self.IMAX1, self.PWF1, self.MAXQ1, self.MINQ1, self.REMOT1, self.RMPCT1 = data[1]

            self.IBUS2, self.TYPE2, self.MODE2, self.DCSET2, self.ACSET2, self.ALOSS2, self.BLOSS2, self.MINLOSS2, \
            self.SMAX2, self.IMAX2, self.PWF2, self.MAXQ2, self.MINQ2, self.REMOT2, self.RMPCT2 = data[2]

        elif version == 29:

            '''
            ’NAME’, MDC, RDC, O1, F1, ... O4, F4
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

    def get_object(self, psse_bus_dict, Sbase, logger: Logger):
        """
        GEt equivalent object
        :param psse_bus_dict:
        :param logger:
        :return:
        """
        bus1 = psse_bus_dict[abs(self.IBUS1)]
        bus2 = psse_bus_dict[abs(self.IBUS2)]

        name1 = self.NAME.replace("'", "").replace('/', '').strip()
        idtag = str(self.IBUS1) + '_' + str(self.IBUS2) + '_1'

        Vset_f = self.ACSET1
        Vset_t = self.ACSET2
        rate = max(self.SMAX1, self.SMAX2)

        specified_power = 0

        obj = HvdcLine(bus_from=bus1,
                       bus_to=bus2,
                       name=name1,
                       idtag=idtag,
                       Pset=specified_power,
                       Vset_f=Vset_f,
                       Vset_t=Vset_t,
                       rate=rate)

        return obj


class PSSeTransformer:

    def __init__(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        self.windings = 0
        self.O1 = ''
        self.F1 = ''
        self.O2 = ''
        self.F2 = ''
        self.O3 = ''
        self.F3 = ''
        self.O4 = ''
        self.F4 = ''
        var = [self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4]

        if version == 33:

            # Line 1: for both types

            self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
            self.NAME, self.STAT, *var, self.VECGRP = data[0]

            if len(data) == 4:
                self.windings = 2

                '''
                I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,’NAME’,STAT,O1,F1,...,O4,F4,VECGRP
                R1-2,X1-2,SBASE1-2
                WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD1,CONT1,RMA1,RMI1,VMA1,VMI1,NTP1,TAB1,CR1,CX1,CNXA1
                WINDV2,NOMV2
                '''

                self.R1_2, self.X1_2, self.SBASE1_2 = data[1]

                n = len(data[2])
                dta = np.zeros(17, dtype=object)
                dta[0:n] = data[2]

                self.WINDV1, self.NOMV1, self.ANG1, self.RATA1, self.RATB1, self.RATC1, self.COD1, self.CONT1, self.RMA1, \
                self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1, self.CNXA1 = dta

                self.WINDV2, self.NOMV2 = data[3]

            else:
                self.windings = 3

                '''
                I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,’NAME’,STAT,O1,F1,...,O4,F4,VECGRP
                R1-2,X1-2,SBASE1-2,R2-3,X2-3,SBASE2-3,R3-1,X3-1,SBASE3-1,VMSTAR,ANSTAR
                WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD1,CONT1,RMA1,RMI1,VMA1,VMI1,NTP1,TAB1,CR1,CX1,CNXA1
                WINDV2,NOMV2,ANG2,RATA2,RATB2,RATC2,COD2,CONT2,RMA2,RMI2,VMA2,VMI2,NTP2,TAB2,CR2,CX2,CNXA2
                WINDV3,NOMV3,ANG3,RATA3,RATB3,RATC3,COD3,CONT3,RMA3,RMI3,VMA3,VMI3,NTP3,TAB3,CR3,CX3,CNXA3
                '''

                self.R1_2, self.X1_2, self.SBASE1_2, self.R2_3, self.X2_3, self.SBASE2_3, self.R3_1, self.X3_1, \
                self.SBASE3_1, self.VMSTAR, self.ANSTAR = data[1]

                self.WINDV1, self.NOMV1, self.ANG1, self.RATA1, self.RATB1, self.RATC1, self.COD1, self.CONT1, \
                self.RMA1, self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1, self.CNXA1 = data[
                    2]

                self.WINDV2, self.NOMV2, self.ANG2, self.RATA2, self.RATB2, self.RATC2, self.COD2, self.CONT2, \
                self.RMA2, self.RMI2, self.VMA2, self.VMI2, self.NTP2, self.TAB2, self.CR2, self.CX2, self.CNXA2 = data[
                    3]

                self.WINDV3, self.NOMV3, self.ANG3, self.RATA3, self.RATB3, self.RATC3, self.COD3, self.CONT3, \
                self.RMA3, self.RMI3, self.VMA3, self.VMI3, self.NTP3, self.TAB3, self.CR3, self.CX3, self.CNXA3 = data[
                    4]

        elif version == 32:

            '''
            I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,’NAME’,STAT,O1,F1,...,O4,F4

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
            else:
                # 3-windings
                self.windings = 3
                self.R1_2, self.X1_2, self.SBASE1_2, self.R2_3, self.X2_3, self.SBASE2_3, self.R3_1, \
                self.X3_1, self.SBASE3_1, self.VMSTAR, self.ANSTAR = data[1]

            # line 3: for both types
            n = len(data[2])
            dta = np.zeros(17, dtype=object)
            dta[0:n] = data[2]
            self.WINDV1, self.NOMV1, self.ANG1, self.RATA1, self.RATB1, self.RATC1, self.COD1, self.CONT1, self.RMA1, \
            self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1, self.CNXA1 = dta

            # line 4
            if len(data[3]) == 2:
                # 2-windings
                self.WINDV2, self.NOMV2 = data[3]
            else:
                # 3 - windings
                self.WINDV2, self.NOMV2, self.ANG2, self.RATA2, self.RATB2, self.RATC2, self.COD2, self.CONT2, \
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
            else:
                # 3-windings
                self.windings = 3
                self.R1_2, self.X1_2, self.SBASE1_2, self.R2_3, self.X2_3, self.SBASE2_3, self.R3_1, \
                self.X3_1, self.SBASE3_1, self.VMSTAR, self.ANSTAR = data[1]

            # line 3: for both types
            self.WINDV1, self.NOMV1, self.ANG1, self.RATA1, self.RATB1, self.RATC1, self.COD1, self.CONT1, self.RMA1, \
            self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1 = data[2]

            # line 4
            if len(data[3]) == 2:
                # 2-windings
                self.WINDV2, self.NOMV2 = data[3]
            else:
                # 3 - windings
                self.WINDV2, self.NOMV2, self.ANG2, self.RATA2, self.RATB2, self.RATC2, self.COD2, self.CONT2, \
                self.RMA2, self.RMI2, self.VMA2, self.VMI2, self.NTP2, self.TAB2, self.CR2, self.CX2, \
                self.WINDV3, self.NOMV3, self.ANG3, self.RATA3, self.RATB3, self.RATC3, self.COD3, self.CONT3, \
                self.RMA3, self.RMI3, self.VMA3, self.VMI3, self.NTP3, self.TAB3, \
                self.CR3, self.CX3 = data[3]

        elif version == 29:

            '''
            In this version 

                2 windings -> 4 lines

                I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,’NAME’,STAT,O1,F1,...,O4,F4
                R1-2,X1-2,SBASE1-2
                WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD,CONT,RMA,RMI,VMA,VMI,NTP,TAB,CR,CX
                WINDV2,NOMV2

                3 windings -> 5 lines

                I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,’NAME’,STAT,O1,F1,...,O4,F4
                R1-2,X1-2,SBASE1-2,R2-3,X2-3,SBASE2-3,R3-1,X3-1,SBASE3-1,VMSTAR,ANSTAR
                WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD,CONT,RMA,RMI,VMA,VMI,NTP,TAB,CR,CX
                WINDV2,NOMV2,ANG2,RATA2,RATB2,RATC2
                WINDV3,NOMV3,ANG3,RATA3,RATB3,RATC3

            '''

            self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
            self.NAME, self.STAT, *var = data[0]

            if len(data[1]) == 3:

                '''
                I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,’NAME’,STAT,O1,F1,...,O4,F4
                R1-2,X1-2,SBASE1-2
                WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD,CONT,RMA,RMI,VMA,VMI,NTP,TAB,CR,CX
                WINDV2,NOMV2
                '''

                # 2-windings
                self.windings = 2
                self.R1_2, self.X1_2, self.SBASE1_2 = data[1]

                self.WINDV1, self.NOMV1, self.ANG1, self.RATA1, self.RATB1, self.RATC1, self.COD1, self.CONT1, self.RMA1, \
                self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1 = data[2]

                self.WINDV2, self.NOMV2 = data[3]

            else:

                '''
                I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,’NAME’,STAT,O1,F1,...,O4,F4
                R1-2,X1-2,SBASE1-2,R2-3,X2-3,SBASE2-3,R3-1,X3-1,SBASE3-1,VMSTAR,ANSTAR

                WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD,CONT,RMA,RMI,VMA,VMI,NTP,TAB,CR,CX

                WINDV2,NOMV2,ANG2,RATA2,RATB2,RATC2

                WINDV3,NOMV3,ANG3,RATA3,RATB3,RATC3
                '''

                # 3-windings
                self.windings = 3

                self.R1_2, self.X1_2, self.SBASE1_2, self.R2_3, self.X2_3, self.SBASE2_3, self.R3_1, \
                self.X3_1, self.SBASE3_1, self.VMSTAR, self.ANSTAR = data[1]

                self.WINDV1, self.NOMV1, self.ANG1, self.RATA1, self.RATB1, self.RATC1, self.COD1, \
                self.CONT1, self.RMA1, self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, \
                self.CR1, self.CX1 = data[2]

                self.WINDV2, self.NOMV2, self.ANG2, self.RATA2, self.RATB2, self.RATC2 = data[3]

                self.WINDV3, self.NOMV3, self.ANG3, self.RATA3, self.RATB3, self.RATC3 = data[4]

        else:
            logger.add_warning('Transformer not implemented for version', str(version))

    def get_object(self, psse_bus_dict, sbase, logger: Logger):
        """
        Return Newton branch object
        Args:
            psse_bus_dict: Dictionary that relates PSSe bus indices with Newton Bus objects

        Returns:
            Newton Branch object
        """

        '''
        R1-2, X1-2 The measured impedance of the transformer between the buses to which its first
            and second windings are connected.

            When CZ is 1, they are the resistance and reactance, respectively, in pu on system
            MVA base and winding voltage base.

            When CZ is 2, they are the resistance and reactance, respectively, in pu on Winding
            1 to 2 MVA base (SBASE1-2) and winding voltage base.

            When CZ is 3, R1-2 is the load loss in watts, and X1-2 is the impedance magnitude
            in pu on Winding 1 to 2 MVA base (SBASE1-2) and winding voltage base. For
            three-phase transformers or three-phase banks of single phase transformers, R1-2
            should specify the three-phase load loss.

            R1-2 = 0.0 by default, but no default is allowed for X1-2.
        '''

        self.CKT = self.CKT.replace("'", "")

        self.NAME = self.NAME.replace("'", "").strip()

        if self.NAME == '':
            self.NAME = str(self.I) + '_' + str(self.J) + '_' + str(self.CKT)
            self.NAME = self.NAME.strip()

        if self.windings == 2:
            bus_from = psse_bus_dict[self.I]
            bus_to = psse_bus_dict[self.J]

            code = str(self.I) + '_' + str(self.J) + '_' + str(self.CKT)
            code = code.strip().replace("'", "")

            """            
            PSS/e's randomness:            
            """
            zbs = bus_from.Vnom * bus_from.Vnom / sbase

            r = self.R1_2
            x = self.X1_2
            g = self.MAG1
            b = self.MAG2
            tap_mod = self.WINDV1 / self.WINDV2
            use_winding_base_voltage = True

            if self.CZ == 3:
                r *= 1e-6 / self.SBASE1_2 / sbase
                x = np.sqrt(self.X1_2 * self.X1_2 - r * r)

            if self.CZ == 2:
                if self.SBASE1_2 > 0:
                    zb = sbase / self.SBASE1_2
                    r *= zb
                    x *= zb
                else:
                    logger.add_error('Transformer SBASE1_2 is zero', code)

            # adjust tap
            if self.CW == 2 or self.CW == 3:
                tap_mod *= bus_to.Vnom / bus_from.Vnom

            if self.CW == 3:
                tap_mod *= self.NOMV1 / self.NOMV2

            if self.NOMV1 == 0:
                V1 = bus_from.Vnom
            else:
                V1 = self.NOMV1

            if self.NOMV2 == 0:
                V2 = bus_to.Vnom
            else:
                V2 = self.NOMV2

            # print(idtag, 'CM', self.CM, 'CW', self.CW, 'CZ', self.CZ)

            elm = Transformer2W(bus_from=bus_from,
                                bus_to=bus_to,
                                idtag=None,
                                code=code,
                                name=self.NAME,
                                HV=V1,
                                LV=V2,
                                r=r,
                                x=x,
                                g=g,
                                b=b,
                                rate=max(self.RATA1, self.RATB1, self.RATC1),
                                tap=tap_mod,
                                shift_angle=np.deg2rad(self.ANG1),
                                active=bool(self.STAT),
                                mttf=0,
                                mttr=0)

            return [elm]

        elif self.windings == 3:

            bus_1 = psse_bus_dict[abs(self.I)]
            bus_2 = psse_bus_dict[abs(self.J)]
            bus_3 = psse_bus_dict[abs(self.K)]
            code = str(self.I) + '_' + str(self.J) + '_' + str(self.K) + '_' + str(self.CKT)

            if self.NOMV1 == 0:
                V1 = bus_1.Vnom
            else:
                V1 = self.NOMV1

            if self.NOMV2 == 0:
                V2 = bus_2.Vnom
            else:
                V2 = self.NOMV2

            if self.NOMV3 == 0:
                V3 = bus_3.Vnom
            else:
                V3 = self.NOMV3

            """            
            PSS/e's randomness:            
            """

            # see: https://en.wikipedia.org/wiki/Per-unit_system
            base_change12 = sbase / self.SBASE1_2
            base_change23 = sbase / self.SBASE2_3
            base_change31 = sbase / self.SBASE3_1

            if self.CZ == 1:
                """
                When CZ is 1, they are the resistance and reactance, respectively, in pu on system
                MVA base and winding voltage base.
                """
                r12 = self.R1_2
                x12 = self.X1_2
                r23 = self.R2_3
                x23 = self.X2_3
                r31 = self.R3_1
                x31 = self.X3_1

            elif self.CZ == 2:

                """
                When CZ is 2, they are the resistance and reactance, respectively, in pu on Winding
                1 to 2 MVA base (SBASE1-2) and winding voltage base.
                """
                zb12 = sbase / self.SBASE1_2
                zb23 = sbase / self.SBASE2_3
                zb31 = sbase / self.SBASE3_1

                r12 = self.R1_2 * zb12
                x12 = self.X1_2 * zb12
                r23 = self.R2_3 * zb23
                x23 = self.X2_3 * zb23
                r31 = self.R3_1 * zb31
                x31 = self.X3_1 * zb31

            elif self.CZ == 3:

                """
                When CZ is 3, R1-2 is the load loss in watts, and X1-2 is the impedance magnitude
                in pu on Winding 1 to 2 MVA base (SBASE1-2) and winding voltage base. For
                three-phase transformers or three-phase banks of single phase transformers, R1-2
                should specify the three-phase load loss.
                """

                r12 = self.R1_2 * 1e-6
                x12 = self.X1_2 * base_change12
                r23 = self.R2_3 * 1e-6
                x23 = self.X2_3 * base_change23
                r31 = self.R3_1 * 1e-6
                x31 = self.X3_1 * base_change31
            else:
                raise Exception('Unknown impedance combination CZ=' + str(self.CZ))

            elm1 = Transformer2W(bus_from=bus_1,
                                 bus_to=bus_2,
                                 idtag=code + '_12',
                                 name=self.NAME,
                                 HV=V1,
                                 LV=V2,
                                 r=r12,
                                 x=x12,
                                 rate=max(self.RATA1, self.RATA2, self.RATA3),
                                 shift_angle=self.ANG1,
                                 active=bool(self.STAT),
                                 mttf=0,
                                 mttr=0)

            elm2 = Transformer2W(bus_from=bus_2,
                                 bus_to=bus_3,
                                 idtag=code + '_23',
                                 name=self.NAME,
                                 HV=V2,
                                 LV=V3,
                                 r=r23,
                                 x=x23,
                                 rate=max(self.RATB1, self.RATB2, self.RATB3),
                                 shift_angle=self.ANG2,
                                 active=bool(self.STAT),
                                 mttf=0,
                                 mttr=0)

            elm3 = Transformer2W(bus_from=bus_3,
                                 bus_to=bus_1,
                                 idtag=code + '_31',
                                 name=self.NAME,
                                 HV=V1,
                                 LV=V3,
                                 r=r31,
                                 x=x31,
                                 rate=max(self.RATC1, self.RATC2, self.RATC3),
                                 shift_angle=self.ANG3,
                                 active=bool(self.STAT),
                                 mttf=0,
                                 mttr=0)

            return [elm1, elm2, elm3]

        else:
            raise Exception(str(self.windings) + ' number of windings!')


class PSSeFACTS:

    def __init__(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if version in [32, 33, 34]:
            '''
            ’NAME’,I,J,MODE,PDES,QDES,VSET,SHMX,TRMX,VTMN,VTMX,VSMX,IMX,LINX,
            RMPCT,OWNER,SET1,SET2,VSREF,REMOT,’MNAME’
            '''

            self.NAME, self.I, self.J, self.MODE, self.PDES, self.QDES, self.VSET, self.SHMX, \
                self.TRMX, self.VTMN, self.VTMX, self.VSMX, self.IMX, self.LINX, self.RMPCT, self.OWNER, \
                self.SET1, self.SET2, self.VSREF, self.REMOT, self.MNAME = data[0]

        elif version == 29:
            '''
            ’NAME’,I,J,MODE,PDES,QDES,VSET,SHMX,TRMX,VTMN,VTMX,VSMX,IMX,LINX,
                RMPCT,OWNER,SET1,SET2,VSREF,REMOT,’MNAME’
            '''

            self.NAME, self.I, self.J, self.MODE, self.PDES, self.QDES, self.VSET, self.SHMX, \
                self.TRMX, self.VTMN, self.VTMX, self.VSMX, self.IMX, self.LINX, self.RMPCT, self.OWNER, \
                self.SET1, self.SET2, self.VSREF, self.REMOT, self.MNAME = data[0]
        else:
            logger.add_warning('Version not implemented for DC Lines', str(version))

    def get_object(self, psse_bus_dict, Sbase, logger: Logger, circuit: MultiCircuit):
        """
        GEt equivalent object
        :param psse_bus_dict:
        :param logger:
        :param circuit:
        :return:
        """
        bus1 = psse_bus_dict[abs(self.I)]

        if abs(self.J) > 0:
            bus2 = psse_bus_dict[abs(self.J)]
        else:
            bus2 = None

        name1 = self.NAME.replace("'", "").replace('"', "").replace('/', '').strip()
        idtag = str(self.I) + '_' + str(self.J) + '_1'

        mode = int(self.MODE)

        if '*' in str(self.SET2):
            self.SET2 = 0.0

        if '*' in str(self.SET1):
            self.SET1 = 0.0

        if mode == 0:
            active = False
        elif mode == 1 and abs(self.J) > 0:
            # shunt link
            logger.add_warning('FACTS mode not implemented', str(mode))

        elif mode == 2:
            # only shunt device: STATCOM
            logger.add_warning('FACTS mode not implemented', str(mode))

        elif mode == 3 and abs(self.J) > 0:  # const Z
            # series and shunt links operating with series link at constant series impedance
            # sh = Shunt(name='FACTS:' + name1, B=self.SHMX)
            # load_from = Load(name='FACTS:' + name1, P=-self.PDES, Q=-self.QDES)
            # gen_to = Generator(name='FACTS:' + name1, active_power=self.PDES, voltage_module=self.VSET)
            # # branch = Line(bus_from=bus1, bus_to=bus2, name='FACTS:' + name1, x=self.LINX)
            # circuit.add_shunt(bus1, sh)
            # circuit.add_load(bus1, load_from)
            # circuit.add_generator(bus2, gen_to)
            # # circuit.add_line(branch)

            elm = UPFC(name=name1,
                       bus_from=bus1,
                       bus_to=bus2,
                       code=idtag,
                       rs=self.SET1, xs=self.SET2,
                       rl=0.0, xl=self.LINX, bl=0.0,
                       rp=0.0, xp=1/self.SHMX if self.SHMX > 0 else 0.0,
                       vp=self.VSET,
                       Pset=self.PDES,
                       Qset=self.QDES,
                       rate=self.IMX + 1e-20)

            circuit.add_upfc(elm)

        elif mode == 4 and abs(self.J) > 0:
            # series and shunt links operating with series link at constant series voltage
            logger.add_warning('FACTS mode not implemented', str(mode))

        elif mode == 5 and abs(self.J) > 0:
            # master device of an IPFC with P and Q setpoints specified;
            # another FACTS device must be designated as the slave device
            # (i.e., its MODE is 6 or 8) of this IPFC.
            logger.add_warning('FACTS mode not implemented', str(mode))

        elif mode == 6 and abs(self.J) > 0:
            # 6 slave device of an IPFC with P and Q setpoints specified;
            #  the FACTS device specified in MNAME must be the master
            #  device (i.e., its MODE is 5 or 7) of this IPFC. The Q setpoint is
            #  ignored as the master device dictates the active power
            #  exchanged between the two devices.
            logger.add_warning('FACTS mode not implemented', str(mode))

        elif mode == 7 and abs(self.J) > 0:
            # master device of an IPFC with constant series voltage setpoints
            # specified; another FACTS device must be designated as the slave
            # device (i.e., its MODE is 6 or 8) of this IPFC
            logger.add_warning('FACTS mode not implemented', str(mode))

        elif mode == 8 and abs(self.J) > 0:
            # slave device of an IPFC with constant series voltage setpoints
            # specified; the FACTS device specified in MNAME must be the
            # master device (i.e., its MODE is 5 or 7) of this IPFC. The complex
            # Vd + jVq setpoint is modified during power flow solutions to reflect
            # the active power exchange determined by the master device
            logger.add_warning('FACTS mode not implemented', str(mode))

        else:
            return None


class PSSeInterArea:

    def __init__(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        self.I = -1

        self.ARNAME = ''

        if version in [29, 30, 32, 33]:
            # I, ISW, PDES, PTOL, 'ARNAME'
            self.I, self.ISW, self.PDES, self.PTOL, self.ARNAME = data[0]

            self.ARNAME = self.ARNAME.replace("'", "").strip()
        else:
            logger.add_warning('Areas not defined for version', str(version))


class PSSeArea:

    def __init__(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        self.I = -1

        self.ARNAME = ''

        if version in [29, 30, 32, 33]:
            # I, ISW, PDES, PTOL, 'ARNAME'
            self.I, self.ISW, self.PDES, self.PTOL, self.ARNAME = data[0]

            self.ARNAME = self.ARNAME.replace("'", "").strip()
        else:
            logger.add_warning('Areas not defined for version', str(version))


class PSSeZone:

    def __init__(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        self.I = -1

        self.ZONAME = ''

        if version in [29, 30, 32, 33]:
            # I, 'ZONAME'
            self.I, self.ZONAME = data[0]

            self.ZONAME = self.ZONAME.replace("'", "").strip()
        else:
            logger.add_warning('Zones not defined for version', str(version))


def interpret_line(line, splitter=','):
    """
    Split text into arguments and parse each of them to an appropriate format (int, float or string)
    Args:
        line: text line
        splitter: value to split by
    Returns: list of arguments
    """
    parsed = list()
    elms = line.split(splitter)

    for elm in elms:
        try:
            # try int
            el = int(elm)
        except ValueError as ex1:
            try:
                # try float
                el = float(elm)
            except ValueError as ex2:
                # otherwise just leave it as string
                el = elm.strip()
        parsed.append(el)
    return parsed


class PSSeParser:

    def __init__(self, file_name):
        """
        Parse PSSe file
        Args:
            file_name: file name or path
        """
        self.parsers = dict()
        self.versions = [33, 32, 30, 29]

        self.logger = Logger()

        self.file_name = file_name

        self.pss_grid, logs = self.parse_psse()

        self.logger += logs

        self.circuit = self.pss_grid.get_circuit(self.logger)

        self.circuit.comments = 'Converted from the PSS/e .raw file ' \
                                + os.path.basename(file_name) + '\n\n' + str(self.logger)

    def read_and_split(self) -> (List[AnyStr], Dict[AnyStr, AnyStr]):
        """
        Read the text file and split it into sections
        :return: list of sections, dictionary of sections by type
        """

        # make a guess of the file encoding
        detection = chardet.detect(open(self.file_name, "rb").read())

        # open the text file into a variable
        txt = ''
        with open(self.file_name, 'r', encoding=detection['encoding']) as my_file:
            for line in my_file:
                if line[0] != '@':
                    txt += line

        # split the text file into sections
        sections = txt.split(' /')

        sections_dict = dict()

        str_a = 'End of'.lower()
        str_b = 'data'.lower()

        for i, sec in enumerate(sections):
            data = sec.split('\n')
            first = data.pop(0).lower()
            if str_a in first:
                if ',' in first:
                    srch = first.split(',')[0]
                else:
                    srch = first
                name = re.search(str_a + '(.*)' + str_b, srch).group(1).strip()
                data2 = sections[i - 1].split('\n')[1:]

                if name.lower() == 'bus':
                    data2.pop(0)
                    data2.pop(0)

                sections_dict[name] = data2

        return sections, sections_dict

    def parse_psse(self) -> (MultiCircuit, List[AnyStr]):
        """
        Parser implemented according to:
            - POM section 4.1.1 Power Flow Raw Data File Contents (v.29)
            - POM section 5.2.1                                   (v.33)
            - POM section 5.2.1                                   (v.32)

        Returns: MultiCircuit, List[str]
        """

        logger = Logger()

        sections, sections_dict = self.read_and_split()

        # header -> new grid
        grid = PSSeGrid(interpret_line(sections[0]))

        if grid.REV not in self.versions:
            msg = 'The PSSe version is not compatible. Compatible versions are:'
            msg += ', '.join([str(a) for a in self.versions])
            logger.add_error(msg)
            return grid, logger
        else:
            version = grid.REV

        # declare contents:
        # section_idx, objects_list, expected_data_length, ObjectT, lines per objects

        # SEQUENCE ORDER:
        # 0:  Case Identification Data
        # 1:  Bus Data
        # 2:  Load Data
        # 3:  Fixed Bus Shunt Data
        # 4:  Generator Data
        # 5:  Non-Transformer Branch Data
        # 6:  Transformer Data
        # 7:  Area Interchange Data
        # 8:  Two-Terminal DC Transmission Line Data
        # 9:  Voltage Source Converter (VSC) DC Transmission Line Data
        # 10: Transformer Impedance Correction Tables
        # 11: Multi-Terminal DC Transmission Line Data
        # 12: Multi-Section Line Grouping Data
        # 13: Zone Data
        # 14: Inter-area Transfer Data
        # 15: Owner Data
        # 16: FACTS Device Data
        # 17: Switched Shunt Data
        # 18: GNE Device Data
        # 19: Induction Machine Data
        # 20: Q Record

        meta_data = dict()
        meta_data['bus'] = [grid.buses, PSSeBus, 1]
        meta_data['load'] = [grid.loads, PSSeLoad, 1]
        meta_data['fixed shunt'] = [grid.shunts, PSSeShunt, 1]
        meta_data['shunt'] = [grid.shunts, PSSeShunt, 1]
        meta_data['switched shunt'] = [grid.switched_shunts, PSSeSwitchedShunt, 1]
        meta_data['generator'] = [grid.generators, PSSeGenerator, 1]
        meta_data['induction machine'] = [grid.generators, PSSeInductionMachine, 3]
        meta_data['branch'] = [grid.lines, PSSeBranch, 1]
        meta_data['transformer'] = [grid.transformers, PSSeTransformer, 4]
        meta_data['two-terminal dc'] = [grid.hvdc_lines, PSSeTwoTerminalDCLine, 3]
        meta_data['two-terminal dc line'] = [grid.hvdc_lines, PSSeTwoTerminalDCLine, 3]
        meta_data['vsc dc line'] = [grid.hvdc_lines, PSSeVscDCLine, 3]
        meta_data['facts device'] = [grid.facts, PSSeFACTS, 1]
        meta_data['area data'] = [grid.areas, PSSeArea, 1]
        meta_data['area'] = [grid.areas, PSSeArea, 1]
        meta_data['area interchange'] = [grid.areas, PSSeArea, 1]
        meta_data['inter-area transfer'] = [grid.areas, PSSeInterArea, 1]
        meta_data['zone'] = [grid.zones, PSSeZone, 1]

        for key, values in meta_data.items():

            # get the parsers for the declared object type
            objects_list, ObjectT, lines_per_object = values

            if key in sections_dict.keys():
                lines = sections_dict[key]

                # iterate ove the object's lines to pack them as expected (normally 1 per object except transformers...)
                l = 0
                while l < len(lines):

                    lines_per_object2 = lines_per_object

                    if version in self.versions and key == 'transformer':
                        # as you know the PSS/e raw format is nuts, that is why for v29 (onwards probably)
                        # the transformers may have 4 or 5 lines to define them
                        if (l + 1) < len(lines):
                            dta = lines[l + 1].split(',')
                            if len(dta) > 3:
                                # 3 - windings
                                lines_per_object2 = 5
                            else:
                                # 2-windings
                                lines_per_object2 = 4

                    if ',' in lines[l]:
                        data = list()
                        for k in range(lines_per_object2):
                            data.append(interpret_line(lines[l + k]))

                        # pick the line that matches the object and split it by line returns \n
                        # object_lines = line.split('\n')

                        # interpret each line of the object and store into data
                        # data is a vector of vectors with data definitions
                        # for the buses, branches, loads etc. data contains 1 vector,
                        # for the transformers data contains 4 vectors
                        # data = [interpret_line(object_lines[k]) for k in range(lines_per_object)]

                        # pass the data to the according object to assign it to the matching variables
                        objects_list.append(ObjectT(data, version, logger))

                    else:
                        if lines[l].strip() != '0':
                            logger.add_info('Skipped', lines[l])

                    # add lines
                    l += lines_per_object2

            else:
                pass

        # add logs for the non parsed objects
        for key in sections_dict.keys():
            if key not in meta_data.keys():
                logger.add_warning('Not implemented in the parser', key)

        return grid, logger


if __name__ == '__main__':
    fname = '/home/santi/Documentos/Transformado.raw'
    pss_parser = PSSeParser(fname)

    print()
