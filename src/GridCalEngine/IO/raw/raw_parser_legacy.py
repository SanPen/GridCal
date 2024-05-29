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
import os
import numpy as np
import chardet
import re
from typing import List, AnyStr, Dict, Union

from GridCalEngine.Devices.multi_circuit import MultiCircuit
import GridCalEngine.Devices as dev
from GridCalEngine.basic_structures import Logger


class PSSeObject:
    """
    Abstract PSSe object
    """

    def __init__(self):
        self.REV = 33


class PSSeGrid:
    """
    Collection of PSSe objects represnting a grid
    """

    def __init__(self, data):
        """

        Args:
            data: array with the values
        """
        a = ""
        b = ""
        var = [a, b]
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
        Inter-area Transfer Data
        Owner Data
        FACTS Device Data
        Switched Shunt Data
        GNE Device Data
        Induction Machine Data
        Q Record
        """
        self.buses: List[PSSeBus] = list()
        self.loads: List[PSSeLoad] = list()
        self.shunts: List[PSSeShunt] = list()
        self.switched_shunts: List[PSSeSwitchedShunt] = list()
        self.generators: List[PSSeGenerator] = list()
        self.branches: List[PSSeBranch] = list()
        self.transformers: List[PSSeTransformer] = list()
        self.hvdc_lines = list()
        self.facts: List[PSSeFACTS] = list()
        self.areas: List[PSSeArea] = list()
        self.zones: List[PSSeZone] = list()

    def get_circuit(self, logger: Logger, branch_connection_voltage_tolerance: float = 0.1) -> MultiCircuit:
        """
        Returns GridCal circuit
        :param logger: Logger
        :param branch_connection_voltage_tolerance: tolerance in p.u. of a branch voltage to be considered a transformer
        :return: MultiCircuit instance
        """

        circuit = MultiCircuit(Sbase=self.SBASE)
        circuit.comments = 'Converted from a PSS/e .raw file'

        circuit.areas = [dev.Area(name=x.ARNAME) for x in self.areas]
        circuit.zones = [dev.Zone(name=x.ZONAME) for x in self.zones]

        area_dict = {val.I: elm for val, elm in zip(self.areas, circuit.areas)}
        zones_dict = {val.I: elm for val, elm in zip(self.zones, circuit.zones)}

        # scan for missing zones or areas (yes, PSSe is so crappy that can reference areas that do not exist)
        missing_areas = False
        missing_zones = False
        for psse_bus in self.buses:

            # replace area idx by area name if available
            if abs(psse_bus.bus.area) not in area_dict.keys():
                area_dict[abs(psse_bus.bus.area)] = dev.Area(name='A' + str(abs(psse_bus.bus.area)))
                missing_areas = True

            if abs(psse_bus.bus.zone) not in zones_dict.keys():
                zones_dict[abs(psse_bus.bus.zone)] = dev.Zone(name='Z' + str(abs(psse_bus.bus.zone)))
                missing_zones = True

        if missing_areas:
            circuit.areas = [v for k, v in area_dict.items()]

        if missing_zones:
            circuit.zones = [v for k, v in zones_dict.items()]

        # ---------------------------------------------------------------------
        # Bus related
        # ---------------------------------------------------------------------
        psse_bus_dict = dict()
        slack_buses = list()

        for psse_bus in self.buses:

            # relate each PSSe bus index with a Newton bus object
            psse_bus_dict[psse_bus.I] = psse_bus.bus

            # replace area idx by area name if available
            if abs(psse_bus.bus.area) in area_dict.keys():
                psse_bus.bus.area = area_dict[abs(psse_bus.bus.area)]

            if abs(psse_bus.bus.zone) in zones_dict.keys():
                psse_bus.bus.zone = zones_dict[abs(psse_bus.bus.zone)]

            if psse_bus.bus.type.value == 3:
                slack_buses.append(psse_bus.I)

            # add the bus to the circuit
            # psse_bus.bus.ensure_area_objects(circuit)
            circuit.add_bus(psse_bus.bus)

            # in legacy PSSe buses there are sunts...so add them
            if psse_bus.shunt is not None:
                circuit.add_shunt(bus=psse_bus.bus, api_obj=psse_bus.shunt)

        for area in self.areas:
            if area.ISW not in slack_buses:
                logger.add_error('The area slack bus is not marked as slack', str(area.ISW))

        # Go through loads
        for psse_load in self.loads:
            bus = psse_bus_dict[psse_load.I]
            api_obj = psse_load.get_object(bus, logger)

            circuit.add_load(bus, api_obj)

        # Go through shunts
        for psse_shunt in self.shunts:
            if psse_shunt.I in psse_bus_dict:
                bus = psse_bus_dict[psse_shunt.I]
                api_obj = psse_shunt.get_object(bus, logger)
                circuit.add_shunt(bus, api_obj)
            else:
                logger.add_error("Shunt bus missing", psse_shunt.I, psse_shunt.I)

        for psse_shunt in self.switched_shunts:
            if psse_shunt.I in psse_bus_dict:
                bus = psse_bus_dict[psse_shunt.I]
                api_obj = psse_shunt.get_object(bus, logger)
                circuit.add_shunt(bus, api_obj)
            else:
                logger.add_error("Switched shunt bus missing", psse_shunt.I, psse_shunt.I)

        # Go through generators
        for psse_gen in self.generators:
            bus = psse_bus_dict[psse_gen.I]
            api_obj = psse_gen.get_object(logger)

            circuit.add_generator(bus, api_obj)

        # Go through Branches
        branches_already_there = set()

        # Go through Transformers
        for psse_branch in self.transformers:
            # get the object
            branches = psse_branch.get_object(psse_bus_dict, self.SBASE, logger)

            for branch in branches:
                if branch.idtag not in branches_already_there:
                    # Add to the circuit
                    circuit.add_transformer2w(branch)
                    branches_already_there.add(branch.idtag)

                else:
                    logger.add_warning('The RAW file has a repeated transformer and it is omitted from the model',
                                       branch.idtag)

        # Go through the Branches
        for psse_branch in self.branches:
            # get the object
            branch = psse_branch.get_object(psse_bus_dict, self.SBASE, logger)

            if branch.should_this_be_a_transformer(
                    branch_connection_voltage_tolerance):  # detect if this branch is actually a transformer

                logger.add_error(msg="Converted line to transformer due to excessive voltage difference",
                                 device=str(branch.idtag))

                transformer = branch.get_equivalent_transformer()

                # Add to the circuit
                circuit.add_transformer2w(transformer)
                branches_already_there.add(branch.idtag)

            else:

                if branch.idtag not in branches_already_there:

                    # Add to the circuit
                    circuit.add_line(branch, logger=logger)
                    branches_already_there.add(branch.idtag)

                else:
                    logger.add_warning('The RAW file has a repeated line device and it is omitted from the model',
                                       str(branch.idtag))

        # Go through hvdc lines
        for psse_branch in self.hvdc_lines:
            # get the object
            branch = psse_branch.get_object(psse_bus_dict, self.SBASE, logger)

            if branch.idtag not in branches_already_there:

                # Add to the circuit
                circuit.add_hvdc(branch)
                branches_already_there.add(branch.idtag)

            else:
                logger.add_warning('The RAW file has a repeated HVDC line device and it is omitted from the model',
                                   str(branch.idtag))

        # Go through facts
        for psse_elm in self.facts:
            # since these may be shunt or series or both, pass the circuit so that the correct device is added
            if psse_elm.is_connected():
                psse_elm.get_object(psse_bus_dict, self.SBASE, logger, circuit)

        return circuit


class PSSeBus(PSSeObject):

    def __init__(self):
        PSSeObject.__init__(self)

        self.bus: Union[dev.Bus, None] = None
        self.shunt: Union[dev.Shunt, None] = None

        self.I = 1
        self.NAME = ""
        self.BASKV = 1
        self.IDE = 1
        self.AREA = 0
        self.ZONE = 0
        self.OWNER = 0
        self.VM = 1.0
        self.VA = 0.0
        self.NVHI = 0
        self.NVLO = 0
        self.EVHI = 0
        self.EVLO = 0

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        bustype = {1: dev.BusMode.PQ, 2: dev.BusMode.PV, 3: dev.BusMode.Slack, 4: dev.BusMode.PQ}

        if version >= 33:
            n = len(data[0])
            dta = np.zeros(13, dtype=object)
            dta[0:n] = data[0]

            self.I, self.NAME, self.BASKV, self.IDE, self.AREA, self.ZONE, \
                self.OWNER, self.VM, self.VA, self.NVHI, self.NVLO, self.EVHI, self.EVLO = dta

            # create bus
            name = self.NAME.replace("'", "")
            self.bus = dev.Bus(name=name,
                               Vnom=self.BASKV, code=str(self.I), vmin=self.EVLO, vmax=self.EVHI, xpos=0, ypos=0,
                               active=True,
                               area=self.AREA, zone=self.ZONE, Vm0=self.VM, Va0=np.deg2rad(self.VA))

        elif version == 32:

            self.I, self.NAME, self.BASKV, self.IDE, self.AREA, self.ZONE, self.OWNER, self.VM, self.VA = data[0]

            # create bus
            name = self.NAME
            self.bus = dev.Bus(name=name, code=str(self.I), Vnom=self.BASKV, vmin=self.NVLO, vmax=self.NVHI, xpos=0,
                               ypos=0,
                               active=True, area=self.AREA, zone=self.ZONE, Vm0=self.VM, Va0=np.deg2rad(self.VA))

        elif version in [29, 30]:
            # I, 'NAME', BASKV, IDE, GL, BL, AREA, ZONE, VM, VA, OWNER
            self.I, self.NAME, self.BASKV, self.IDE, self.GL, self.BL, \
                self.AREA, self.ZONE, self.VM, self.VA, self.OWNER = data[0]

            # create bus
            name = self.NAME
            self.bus = dev.Bus(name=name, code=str(self.I), Vnom=self.BASKV, vmin=0.9, vmax=1.1, xpos=0, ypos=0,
                               active=True, area=self.AREA, zone=self.ZONE, Vm0=self.VM, Va0=np.deg2rad(self.VA))

            if self.GL > 0 or self.BL > 0:
                self.shunt = dev.Shunt(name='Shunt_' + str(self.I),
                                       G=self.GL, B=self.BL,
                                       active=True)

        else:
            logger.add_warning('Bus not implemented for version', str(version))

        # set type
        if self.IDE in bustype.keys():
            self.bus.type = bustype[self.IDE]
        else:
            self.bus.type = dev.BusMode.PQ

        if int(self.IDE) == 4:
            self.bus.active = False

        if self.bus.type == dev.BusMode.Slack:
            self.bus.is_slack = True

        # Ensures unique name
        self.bus.name = self.bus.name.replace("'", "").strip()

        self.bus.code = str(self.I)

        if self.bus.name == '':
            self.bus.name = 'Bus ' + str(self.I)


class PSSeLoad(PSSeObject):

    def __init__(self):
        PSSeObject.__init__(self)

        self.I = 0
        self.ID = ''
        self.STATUS = 1
        self.AREA = 0
        self.ZONE = 0
        self.PL = 0
        self.QL = 0
        self.IP = 0
        self.IQ = 0
        self.YP = 0
        self.YQ = 0
        self.OWNER = 0
        self.SCALE = 0
        self.INTRPT = 0

        self.DGENP = 0
        self.DGENQ = 0
        self.DGENM = 0
        self.LOADTYPE = ''

    def parse(self, data, version, logger: Logger):

        """

        :param data:
        :param version:
        :param logger:
        """

        if version >= 35:

            self.I, self.ID, self.STATUS, self.AREA, self.ZONE, self.PL, self.QL, \
                self.IP, self.IQ, self.YP, self.YQ, self.OWNER, self.SCALE, self.INTRPT, \
                self.DGENP, self.DGENQ, self.DGENM, self.LOADTYPE = data[0]

        elif version in [33, 34]:

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

            self.SCALE = 1.0

        else:
            logger.add_warning('Load not implemented for version', str(version))

    def get_object(self, bus: dev.Bus, logger: Logger):
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
            logger.add_error('Voltage equal to zero in load conversion', name)

        # self.SCALEs means if the load is scalable, so omit it
        g = self.YP
        b = self.YQ
        ir = self.IP
        ii = -self.IQ
        p = self.PL
        q = self.QL

        elm = dev.Load(name=name,
                       idtag=None,
                       code=name,
                       active=bool(self.STATUS),
                       P=p, Q=q, Ir=ir, Ii=ii, G=g, B=b)

        return elm


class PSSeSwitchedShunt(PSSeObject):

    def __init__(self):
        PSSeObject.__init__(self)

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

        self.I = 0
        self.MODSW = 0
        self.ADJM = 0
        self.STAT = 0
        self.VSWHI = 1
        self.VSWLO = 1
        self.SWREM = 0
        self.RMPCT = 1
        self.RMIDNT = 0
        self.BINIT = 0

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if version >= 29:

            var = [self.N1, self.B1,
                   self.N2, self.B2,
                   self.N3, self.B3,
                   self.N4, self.B4,
                   self.N5, self.B5,
                   self.N6, self.B6,
                   self.N7, self.B7,
                   self.N8, self.B8, ]

            self.I, self.MODSW, self.ADJM, self.STAT, self.VSWHI, self.VSWLO, \
                self.SWREM, self.RMPCT, self.RMIDNT, self.BINIT, *var = data[0]
        else:
            logger.add_warning('Shunt not implemented for the version', str(version))

    def get_object(self, bus: dev.Bus, logger: Logger):
        """
        Return Newton Load object
        Returns:
            Newton Load object
        """
        name = str(self.I).replace("'", "")
        name = name.strip()

        # GL and BL come in MW and MVAr
        # They must be in siemens
        vv = bus.Vnom ** 2.0

        if vv == 0:
            logger.add_error('Voltage equal to zero in shunt conversion', name)

        g = 0.0
        if self.MODSW in [1, 2]:
            b = self.BINIT * self.RMPCT / 100.0
        else:
            b = self.BINIT

        elm = dev.Shunt(name='Switched shunt ' + name,
                        G=g, B=b,
                        active=bool(self.STAT),
                        code=name)

        return elm


class PSSeShunt(PSSeObject):

    def __init__(self):
        PSSeObject.__init__(self)

        self.I = 0
        self.ID = ""
        self.STATUS = 1
        self.GL = 0
        self.BL = 0

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """
        if version >= 29:
            self.I, self.ID, self.STATUS, self.GL, self.BL = data[0]
        else:
            logger.add_warning('Shunt not implemented for the version', str(version))

    def get_object(self, bus: dev.Bus, logger: Logger):
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

        elm = dev.Shunt(name=name,
                        idtag=None,
                        G=g, B=b,
                        active=bool(self.STATUS),
                        code=name)

        return elm


class PSSeGenerator(PSSeObject):

    def __init__(self):
        PSSeObject.__init__(self)

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

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        var = [self.O1, self.F1,
               self.O2, self.F2,
               self.O3, self.F3,
               self.O4, self.F4]

        if version >= 30:
            # I,'ID',      PG,        QG,        QB,     VS,    IREG,     MBASE,
            # ZR,         ZX,         RT,         XT,     GTAP,STAT, RMPCT,      PT,        PB,
            # O1,  F1,    O2,  F2,    O3,  F3,    O4,  F4,
            # WMOD,  WPF
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

    def get_object(self, logger: Logger):
        """
        Return Newton Load object
        Returns:
            Newton Load object
        """
        name = str(self.I) + '_' + str(self.ID).replace("'", "")
        elm = dev.Generator(name=name,
                            idtag=None,
                            code=name,
                            P=self.PG,
                            vset=self.VS,
                            Qmin=self.QB,
                            Qmax=self.QT,
                            Snom=self.MBASE,
                            Pmax=self.PT,
                            Pmin=self.PB,
                            active=bool(self.STAT))

        return elm


class PSSeInductionMachine(PSSeObject):

    def __init__(self):
        PSSeObject.__init__(self)

        self.I = 0
        self.ID = ""
        self.STAT = 1
        self.SCODE = ""
        self.DCODE = ""
        self.AREA = 0
        self.ZONE = 0
        self.OWNER = 0
        self.TCODE = 0
        self.BCODE = 0
        self.MBASE = 0
        self.RATEKV = 0
        self.PCODE = 0
        self.PSET = 0
        self.H = 0
        self.A = 0
        self.B = 0
        self.D = 0
        self.E = 0
        self.RA = 0
        self.XA = 0
        self.XM = 0
        self.R1 = 0
        self.X1 = 0
        self.R2 = 0
        self.X2 = 0
        self.X3 = 0
        self.E1 = 0
        self.SE1 = 0
        self.E2 = 0
        self.SE2 = 0
        self.IA1 = 0
        self.IA2 = 0
        self.XAMULT = 1.0

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

        elm = dev.Generator(name=str(self.I) + '_' + str(self.ID),
                            P=self.PSET,
                            vset=self.RATEKV,
                            Snom=self.MBASE,
                            active=bool(self.STAT))

        return elm


class PSSeBranch(PSSeObject):

    def __init__(self):
        PSSeObject.__init__(self)

        self.O1 = ''
        self.F1 = ''
        self.O2 = ''
        self.F2 = ''
        self.O3 = ''
        self.F3 = ''
        self.O4 = ''
        self.F4 = ''

        self.I = 0
        self.J = 0
        self.CKT = 0
        self.R = 0
        self.X = 0
        self.B = 0

        self.NAME = ''

        self.RATEA = 0
        self.RATEB = 0
        self.RATEC = 0

        self.RATE1 = 0
        self.RATE2 = 0
        self.RATE3 = 0
        self.RATE4 = 0
        self.RATE5 = 0
        self.RATE6 = 0
        self.RATE7 = 0
        self.RATE8 = 0
        self.RATE9 = 0
        self.RATE10 = 0
        self.RATE11 = 0
        self.RATE12 = 0

        self.GI = 0
        self.BI = 0
        self.GJ = 0
        self.BJ = 0
        self.ST = 1
        self.MET = 0
        self.LEN = 0

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        var = [self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4]
        if version >= 34:

            """
            I,     J,'CKT',     R,          X,         B, 'N A M E'                 ,   
            RATE1,   RATE2,   RATE3,   RATE4,   RATE5,   RATE6,   RATE7,   RATE8,   RATE9,  RATE10,  RATE11,  RATE12,    
            GI,       BI,       GJ,       BJ,STAT,MET,  LEN,  O1,  F1,    O2,  F2,    O3,  F3,    O4,  F4
            """

            self.I, self.J, self.CKT, self.R, self.X, self.B, self.NAME, \
                self.RATE1, self.RATE2, self.RATE3, self.RATE4, self.RATE5, self.RATE6, \
                self.RATE7, self.RATE8, self.RATE9, self.RATE10, self.RATE11, self.RATE12, \
                self.GI, self.BI, self.GJ, self.BJ, self.ST, self.MET, self.LEN, *var = data[0]

            self.RATEA = self.RATE1
            self.RATEB = self.RATE1

        elif version in [32, 33]:

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
        :param psse_bus_dict: Dictionary that relates PSSe bus indices with Newton Bus objects
        :param Sbase: Base power in MVA
        :param logger: Logger
        :return: Branch object
        """

        i = abs(self.I)
        j = abs(self.J)
        bus_from = psse_bus_dict[i]
        bus_to = psse_bus_dict[j]
        code = str(i) + '_' + str(j) + '_' + str(self.CKT).replace("'", "").strip()

        if self.NAME.strip() == '':
            name = "{0}_{1}_{2}_{3}_{4}_{5}_{6}".format(i, bus_from.name, bus_from.Vnom, j, bus_to.name, bus_to.Vnom,
                                                        self.CKT)
            name = name.replace("'", "").replace(" ", "").strip()
        else:
            name = self.NAME.strip()

        contingency_factor = self.RATEB / self.RATEA if self.RATEA > 0.0 else 1.0

        if contingency_factor == 0:
            contingency_factor = 1.0

        branch = dev.Line(bus_from=bus_from,
                          bus_to=bus_to,
                          idtag=None,
                          code=code,
                          name=name,
                          r=self.R,
                          x=self.X,
                          b=self.B,
                          rate=self.RATEA,
                          contingency_factor=round(contingency_factor, 6),
                          active=bool(self.ST),
                          mttf=0,
                          mttr=0,
                          length=self.LEN)
        return branch


class PSSeTwoTerminalDCLine(PSSeObject):

    def __init__(self):
        PSSeObject.__init__(self)

        self.NAME = ""
        self.MDC = 0
        self.RDC = 0
        self.SETVL = 0
        self.VSCHD = 0
        self.VCMOD = 0
        self.RCOMP = 0
        self.DELTI = 0
        self.METER = 0
        self.DCVMIN = 0
        self.CCCITMX = 0
        self.CCCACC = 0

        self.IPR = 0
        self.NBR = 0
        self.ANMXR = 0
        self.ANMNR = 0
        self.RCR = 0
        self.XCR = 0
        self.EBASR = 0
        self.TRR = 0
        self.TAPR = 0
        self.TMXR = 0
        self.TMNR = 0
        self.STPR = 0
        self.ICR = 0
        self.IFR = 0
        self.ITR = 0
        self.IDR = 0
        self.XCAPR = 0

        self.IPI = 0
        self.NBI = 0
        self.ANMXI = 0
        self.ANMNI = 0
        self.RCI = 0
        self.XCI = 0
        self.EBASI = 0
        self.TRI = 0
        self.TAPI = 0
        self.TMXI = 0
        self.TMNI = 0
        self.STPI = 0
        self.ICI = 0
        self.IFI = 0
        self.ITI = 0
        self.IDI = 0
        self.XCAPI = 0

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if version >= 30:
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

        # z_base = self.VSCHD * self.VSCHD / Sbase
        # r_pu = self.RDC / z_base

        Vset_f = 1.0
        Vset_t = 1.0

        name1 = self.NAME.replace("'", "").replace('"', "").replace('/', '').strip()
        idtag = str(self.IPR) + '_' + str(self.IPI) + '_1'

        # set the HVDC line active
        active = bus1.active and bus2.active

        obj = dev.HvdcLine(bus_from=bus1,  # Rectifier as of PSSe
                           bus_to=bus2,  # inverter as of PSSe
                           active=active,
                           name=name1,
                           idtag=idtag,
                           Pset=specified_power,
                           Vset_f=Vset_f,
                           Vset_t=Vset_t,
                           rate=specified_power,
                           r=self.RDC,
                           min_firing_angle_f=np.deg2rad(self.ANMNR),
                           max_firing_angle_f=np.deg2rad(self.ANMXR),
                           min_firing_angle_t=np.deg2rad(self.ANMNI),
                           max_firing_angle_t=np.deg2rad(self.ANMXI))
        return obj


class PSSeVscDCLine(PSSeObject):

    def __init__(self):
        PSSeObject.__init__(self)

        self.O1 = ''
        self.F1 = ''
        self.O2 = ''
        self.F2 = ''
        self.O3 = ''
        self.F3 = ''
        self.O4 = ''
        self.F4 = ''

        self.NAME = ""
        self.MDC = 0
        self.RDC = 0

        self.IBUS1 = 0
        self.TYPE1 = 0
        self.MODE1 = 0
        self.DCSET1 = 0
        self.ACSET1 = 0
        self.ALOSS1 = 0
        self.BLOSS1 = 0
        self.MINLOSS1 = 0
        self.SMAX1 = 0
        self.IMAX1 = 0
        self.PWF1 = 0
        self.MAXQ1 = 0
        self.MINQ1 = 0
        self.REMOT1 = 0
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
        self.REMOT2 = 0
        self.RMPCT2 = 0

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        var = [self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4]

        if version >= 30:

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

        # Estimate power
        # P = dV^2 / R
        V1 = bus1.Vnom * Vset_f
        V2 = bus2.Vnom * Vset_t
        dV = (V1 - V2) * 1000.0  # in V
        P = dV * dV / self.RDC if self.RDC != 0 else 0  # power in W
        specified_power = P * 1e-6  # power in MW

        obj = dev.HvdcLine(bus_from=bus1,
                           bus_to=bus2,
                           name=name1,
                           idtag=idtag,
                           Pset=specified_power,
                           Vset_f=Vset_f,
                           Vset_t=Vset_t,
                           rate=rate)

        return obj


def get_psse_transformer_impedances(CW, CZ, CM, V1, V2, sbase, logger, code,
                                    MAG1, MAG2, WINDV1, WINDV2, ANG1, NOMV1, NOMV2,
                                    R1_2, X1_2, SBASE1_2):
    """

    CW	Winding I/O code
    1	Turns ratio (pu on bus base kV)
    2	Winding voltage kV
    3	Turns ratio (pu on nominal winding kV)

    CZ	Impedance I/O code
    1	Z pu (winding kV system MVA)
    2	Z pu (winding kV winding MVA)
    3	Load loss (W) & |Z| (pu)

    CM	Admittance I/O code
    1	Y pu (system base)
    2	No load loss (W) & Exciting I (pu)


    :param CW:
    :param CZ:
    :param CM:
    :return:
    """

    g = MAG1
    b = MAG2
    tap_mod = WINDV1 / WINDV2
    tap_angle = np.deg2rad(ANG1)

    # if self.CW == 2 or self.CW == 3:
    #     tap_mod *= bus_to.Vnom / bus_from.Vnom
    #
    # if self.CW == 3:
    #     tap_mod *= self.NOMV1 / self.NOMV2

    """
    CW	Winding I/O code
    1	Turns ratio (pu on bus base kV)
    2	Winding voltage kV
    3	Turns ratio (pu on nominal winding kV)        
    """

    if CW == 1:
        tap_mod = WINDV1 / WINDV2

    elif CW == 2:
        tap_mod = (WINDV1 / V1) / (WINDV2 / V2)

    elif CW == 3:
        tap_mod = (WINDV1 / WINDV2) * (NOMV1 / NOMV2)

    """
    CZ	Impedance I/O code
    1	Z pu (winding kV system MVA)
    2	Z pu (winding kV winding MVA)
    3	Load loss (W) & |Z| (pu)
    """
    r = 1e-20
    x = 1e-20
    if CZ == 1:
        # the transformer values are in system base
        r = R1_2
        x = X1_2

    elif CZ == 2:
        # pu on Winding 1 to 2 MVA base (SBASE1-2) and winding voltage base
        logger.add_warning('Transformer not in system base', code)

        if SBASE1_2 > 0:
            zb = sbase / SBASE1_2
            r = R1_2 * zb
            x = X1_2 * zb

        else:
            logger.add_error('Transformer SBASE1_2 is zero', code)

    elif CZ == 3:
        # R1-2 is the load loss in watts, and X1-2 is the impedance magnitude
        # in pu on Winding 1 to 2 MVA base (SBASE1-2) and winding voltage base
        r = R1_2 * 1e-6 / SBASE1_2 / sbase
        x = np.sqrt(X1_2 * X1_2 - r * r)
        logger.add_warning('Transformer not in system base', code)

    else:
        raise Exception('Unknown impedance combination CZ=' + str(CZ))

    return r, x, g, b, tap_mod, tap_angle


class PSSeTransformer(PSSeObject):

    def __init__(self):
        PSSeObject.__init__(self)

        self.windings = 0
        self.O1 = ''
        self.F1 = ''
        self.O2 = ''
        self.F2 = ''
        self.O3 = ''
        self.F3 = ''
        self.O4 = ''
        self.F4 = ''

        self.I = 0
        self.J = 0
        self.K = 0
        self.CKT = 0
        self.CW = 0
        self.CZ = 0
        self.CM = 0
        self.MAG1 = 0
        self.MAG2 = 0
        self.NMETR = 0
        self.NAME = ""
        self.STAT = 0
        self.VECGRP = ""
        self.ZCOD = 0

        self.WINDV1 = 0
        self.NOMV1 = 0
        self.ANG1 = 0
        self.RATA1 = 0
        self.RATB1 = 0
        self.RATC1 = 0
        self.COD1 = 0
        self.CONT1 = 0
        self.RMA1 = 0
        self.RMI1 = 0
        self.VMA1 = 0
        self.VMI1 = 0
        self.NTP1 = 0
        self.TAB1 = 0
        self.CR1 = 0
        self.CX1 = 0
        self.CNXA1 = 0

        self.WINDV2 = 0
        self.NOMV2 = 0

        # in case of 3 W
        self.ANG2 = 0
        self.RATA2 = 0
        self.RATB2 = 0
        self.RATC2 = 0
        self.COD2 = 0
        self.CONT2 = 0
        self.RMA2 = 0
        self.RMI2 = 0
        self.VMA2 = 0
        self.VMI2 = 0
        self.NTP2 = 0
        self.TAB2 = 0
        self.CR2 = 0
        self.CX2 = 0
        self.CNXA2 = 0

        self.WINDV3 = 0
        self.NOMV3 = 0
        self.ANG3 = 0
        self.RATA3 = 0
        self.RATB3 = 0
        self.RATC3 = 0
        self.COD3 = 0
        self.CONT3 = 0
        self.RMA3 = 0
        self.RMI3 = 0
        self.VMA3 = 0
        self.VMI3 = 0
        self.NTP3 = 0
        self.TAB3 = 0
        self.CR3 = 0
        self.CX3 = 0
        self.CNXA3 = 0

        self.NOD1 = 0
        self.NOD2 = 0
        self.NOD3 = 0

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
                @!   I,     J,     K,'CKT',CW,CZ,CM,    MAG1,       MAG2,NMETR,               'N A M E',               STAT,O1,  F1,    O2,  F2,    O3,  F3,    O4,  F4,     'VECGRP', ZCOD
                @!   R1-2,       X1-2,   SBASE1-2,     R2-3,       X2-3,   SBASE2-3,     R3-1,       X3-1,   SBASE3-1, VMSTAR,   ANSTAR
                @!WINDV1,  NOMV1,    ANG1,  RATE1-1,  RATE1-2,  RATE1-3,  RATE1-4,  RATE1-5,  RATE1-6,  RATE1-7,  RATE1-8,  RATE1-9, RATE1-10, RATE1-11, RATE1-12,COD1,CONT1,   NOD1,    RMA1,    RMI1,    VMA1,    VMI1, NTP1,TAB1,  CR1,     CX1,   CNXA1
                @!WINDV2,  NOMV2,    ANG2,  RATE2-1,  RATE2-2,  RATE2-3,  RATE2-4,  RATE2-5,  RATE2-6,  RATE2-7,  RATE2-8,  RATE2-9, RATE2-10, RATE2-11, RATE2-12,COD2,CONT2,   NOD2,    RMA2,    RMI2,    VMA2,    VMI2, NTP2,TAB2,  CR2,     CX2,   CNXA2
                @!WINDV3,  NOMV3,    ANG3,  RATE3-1,  RATE3-2,  RATE3-3,  RATE3-4,  RATE3-5,  RATE3-6,  RATE3-7,  RATE3-8,  RATE3-9, RATE3-10, RATE3-11, RATE3-12,COD3,CONT3,   NOD3,    RMA3,    RMI3,    VMA3,    VMI3, NTP3,TAB3,  CR3,     CX3,   CNXA3
                '''

                self.R1_2, self.X1_2, self.SBASE1_2 = data[1]

                self.WINDV1, self.NOMV1, self.ANG1, \
                    self.RATE1_1, self.RATE1_2, self.RATE1_3, self.RATE1_4, self.RATE1_5, self.RATE1_6, \
                    self.RATE1_7, self.RATE1_8, self.RATE1_9, self.RATE1_10, self.RATE1_11, self.RATE1_12, \
                    self.COD1, self.CONT1, self.NOD1, self.RMA1, \
                    self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1, self.CNXA1 = data[2]

                self.WINDV2, self.NOMV2 = data[3]

                self.RATA1 = self.RATE1_1

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
                    self.COD1, self.CONT1, self.NOD1, \
                    self.RMA1, self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1, self.CNXA1 = \
                    data[2]

                self.WINDV2, self.NOMV2, self.ANG2, \
                    self.RATE2_1, self.RATE2_2, self.RATE2_3, self.RATE2_4, self.RATE2_5, self.RATE2_6, \
                    self.RATE2_7, self.RATE2_8, self.RATE2_9, self.RATE2_10, self.RATE2_11, self.RATE2_12, \
                    self.COD2, self.CONT2, self.NOD2, \
                    self.RMA2, self.RMI2, self.VMA2, self.VMI2, self.NTP2, self.TAB2, self.CR2, self.CX2, self.CNXA2 = \
                    data[3]

                self.WINDV3, self.NOMV3, self.ANG3, \
                    self.RATE3_1, self.RATE3_2, self.RATE3_3, self.RATE3_4, self.RATE3_5, self.RATE3_6, \
                    self.RATE3_7, self.RATE3_8, self.RATE3_9, self.RATE3_10, self.RATE3_11, self.RATE3_12, \
                    self.COD3, self.CONT3, self.NOD3, \
                    self.RMA3, self.RMI3, self.VMA3, self.VMI3, self.NTP3, self.TAB3, self.CR3, self.CX3, self.CNXA3 = \
                    data[4]

                self.RATA1 = self.RATE1_1
                self.RATA2 = self.RATE2_1
                self.RATA3 = self.RATE3_1

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

                self.WINDV1, self.NOMV1, self.ANG1, self.RATA1, self.RATB1, self.RATC1, self.COD1, self.CONT1, self.RMA1, \
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

                self.WINDV1, self.NOMV1, self.ANG1, self.RATA1, self.RATB1, self.RATC1, self.COD1, self.CONT1, \
                    self.RMA1, self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1, self.CNXA1 = \
                    data[2]

                self.WINDV2, self.NOMV2, self.ANG2, self.RATA2, self.RATB2, self.RATC2, self.COD2, self.CONT2, \
                    self.RMA2, self.RMI2, self.VMA2, self.VMI2, self.NTP2, self.TAB2, self.CR2, self.CX2, self.CNXA2 = \
                    data[3]

                self.WINDV3, self.NOMV3, self.ANG3, self.RATA3, self.RATB3, self.RATC3, self.COD3, self.CONT3, \
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
                self.SBASE1_2 = 100  # MVA (the system base by default)
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

                self.WINDV1, self.NOMV1, self.ANG1, self.RATA1, self.RATB1, self.RATC1, self.COD1, self.CONT1, self.RMA1, \
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

        self.CKT = str(self.CKT).replace("'", "")

        self.NAME = self.NAME.replace("'", "").strip()

        if self.windings == 2:
            bus_from = psse_bus_dict[self.I]
            bus_to = psse_bus_dict[self.J]

            name = "{0}_{1}_{2}_{3}_{4}_{5}_{6}".format(self.I, bus_from.name, bus_from.Vnom,
                                                        self.J, bus_to.name, bus_to.Vnom, self.CKT)

            name = name.replace("'", "").replace(" ", "").strip()

            code = str(self.I) + '_' + str(self.J) + '_' + str(self.CKT)
            code = code.strip().replace("'", "")

            """            
            PSS/e's randomness:            
            """

            if self.NOMV1 == 0:
                V1 = bus_from.Vnom
            else:
                V1 = self.NOMV1

            if self.NOMV2 == 0:
                V2 = bus_to.Vnom
            else:
                V2 = self.NOMV2

            contingency_factor = self.RATB1 / self.RATA1 if self.RATA1 > 0.0 else 1.0

            r, x, g, b, tap_mod, tap_angle = get_psse_transformer_impedances(self.CW, self.CZ, self.CM,
                                                                             V1, V2,
                                                                             sbase, logger, code,
                                                                             self.MAG1, self.MAG2, self.WINDV1,
                                                                             self.WINDV2,
                                                                             self.ANG1, self.NOMV1, self.NOMV2,
                                                                             self.R1_2, self.X1_2, self.SBASE1_2)

            if V1 >= V2:
                HV = V1
                LV = V2
            else:
                HV = V2
                LV = V1

            elm = dev.Transformer2W(bus_from=bus_from,
                                    bus_to=bus_to,
                                    idtag=None,
                                    code=code,
                                    name=name,
                                    HV=HV,
                                    LV=LV,
                                    r=r,
                                    x=x,
                                    g=g,
                                    b=b,
                                    rate=self.RATA1,
                                    contingency_factor=round(contingency_factor, 6),
                                    tap_module=tap_mod,
                                    tap_phase=tap_angle,
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

            elm1 = dev.Transformer2W(bus_from=bus_1,
                                     bus_to=bus_2,
                                     idtag=code + '_12',
                                     name=self.NAME,
                                     HV=V1,
                                     LV=V2,
                                     r=r12,
                                     x=x12,
                                     rate=max(self.RATA1, self.RATA2, self.RATA3),
                                     tap_phase=self.ANG1,
                                     active=bool(self.STAT),
                                     mttf=0,
                                     mttr=0)

            elm2 = dev.Transformer2W(bus_from=bus_2,
                                     bus_to=bus_3,
                                     idtag=code + '_23',
                                     name=self.NAME,
                                     HV=V2,
                                     LV=V3,
                                     r=r23,
                                     x=x23,
                                     rate=max(self.RATB1, self.RATB2, self.RATB3),
                                     tap_phase=self.ANG2,
                                     active=bool(self.STAT),
                                     mttf=0,
                                     mttr=0)

            elm3 = dev.Transformer2W(bus_from=bus_3,
                                     bus_to=bus_1,
                                     idtag=code + '_31',
                                     name=self.NAME,
                                     HV=V1,
                                     LV=V3,
                                     r=r31,
                                     x=x31,
                                     rate=max(self.RATC1, self.RATC2, self.RATC3),
                                     tap_phase=self.ANG3,
                                     active=bool(self.STAT),
                                     mttf=0,
                                     mttr=0)

            return [elm1, elm2, elm3]

        else:
            raise Exception(str(self.windings) + ' number of windings!')


class PSSeFACTS(PSSeObject):

    def __init__(self):
        PSSeObject.__init__(self)

        self.NAME = ""
        self.I = 0
        self.J = 0
        self.MODE = 0
        self.PDES = 0
        self.QDES = 0
        self.VSET = 0
        self.SHMX = 0
        self.TRMX = 0
        self.VTMN = 0
        self.VTMX = 0
        self.VSMX = 0
        self.IMX = 0
        self.LINX = 0
        self.RMPCT = 0
        self.OWNER = 0
        self.SET1 = 0
        self.SET2 = 0
        self.VSREF = 0
        self.REMOT = 0
        self.MNAME = 0

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """
        if version in [35]:
            '''
            'NAME',I,J,MODE,PDES,QDES,VSET,SHMX,TRMX,VTMN,VTMX,VSMX,IMX,LINX,
            RMPCT,OWNER,SET1,SET2,VSREF,REMOT,'MNAME'
            '''

            self.NAME, self.I, self.J, self.MODE, self.PDES, self.QDES, self.VSET, self.SHMX, \
                self.TRMX, self.VTMN, self.VTMX, self.VSMX, self.IMX, self.LINX, self.RMPCT, self.OWNER, \
                self.SET1, self.SET2, self.VSREF, self.FCREG, self.NREG, self.MNAME = data[0]

        elif version in [32, 33, 34]:
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

    def is_connected(self):
        return self.I > 0 and self.J > 0

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

            elm = dev.UPFC(name=name1,
                           bus_from=bus1,
                           bus_to=bus2,
                           code=idtag,
                           rs=self.SET1,
                           xs=self.SET2 + self.LINX,
                           rp=0.0,
                           xp=1.0 / self.SHMX if self.SHMX > 0 else 0.0,
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


class PSSeInterArea(PSSeObject):

    def __init__(self):
        PSSeObject.__init__(self)

        self.I = -1
        self.ARNAME = ''
        self.ISW = 0
        self.PDES = 0
        self.PTOL = 0

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if version >= 29:
            # I, ISW, PDES, PTOL, 'ARNAME'
            self.I, self.ISW, self.PDES, self.PTOL, self.ARNAME = data[0]

            self.ARNAME = self.ARNAME.replace("'", "").strip()
        else:
            logger.add_warning('Areas not defined for version', str(version))


class PSSeArea(PSSeObject):

    def __init__(self):
        PSSeObject.__init__(self)

        self.I = -1
        self.ARNAME = ''
        self.ISW = 0
        self.PDES = 0
        self.PTOL = 0

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        self.I = -1

        self.ARNAME = ''

        if version >= 29:
            # I, ISW, PDES, PTOL, 'ARNAME'
            self.I, self.ISW, self.PDES, self.PTOL, self.ARNAME = data[0]

            self.ARNAME = self.ARNAME.replace("'", "").strip()
        else:
            logger.add_warning('Areas not defined for version', str(version))


class PSSeZone(PSSeObject):

    def __init__(self):
        PSSeObject.__init__(self)

        self.I = -1
        self.ZONAME = ''

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        if version >= 29:
            # I, 'ZONAME'
            self.I, self.ZONAME = data[0]

            self.ZONAME = self.ZONAME.replace("'", "").strip()
        else:
            logger.add_warning('Zones not defined for version', str(version))


def delete_comment(raw_line):
    lne = ""
    text_active = False
    for c in raw_line:

        if c == "'":
            text_active = not text_active

        if c == "/":
            if text_active:
                pass
            else:
                return lne

        lne += c

    return lne


def interpret_line(raw_line, splitter=','):
    """
    Split text into arguments and parse each of them to an appropriate format (int, float or string)
    Args:
        raw_line: text line
        splitter: value to split by
    Returns: list of arguments
    """
    raw_line = delete_comment(raw_line)

    # Remove the last useless comma if it is there:
    if raw_line[-1] == ",":
        lne = raw_line[:-1]
    else:
        lne = raw_line

    parsed = list()
    elms = lne.split(splitter)

    for elm in elms:

        if "'" in elm:
            el = elm.replace("'", "").strip()
        else:

            if "/" in elm:
                # the line might end with a comment "/ whatever" so we must remove the comment
                print("Comment detected:", elm, end="")
                ss = elm.split("/")
                elm = ss[0]
                print(" corrected to:", elm)

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

    def __init__(self, file_name, text_func=print, progress_func=None):
        """
        Parse PSSe file
        Args:
            file_name: file name or path
        """
        self.parsers = dict()
        self.versions = [35, 34, 33, 32, 30, 29]

        self.logger = Logger()

        self.file_name = file_name

        self.pss_grid, logs = self.parse_psse(text_func=text_func, progress_func=progress_func)

        self.logger += logs

        self.circuit = self.pss_grid.get_circuit(self.logger)

        self.circuit.comments = 'Converted from the PSS/e .raw file ' \
                                + os.path.basename(file_name) + '\n\n' + str(self.logger)

    def read_and_split_old(self, text_func=None, progress_func=None) -> (List[AnyStr], Dict[AnyStr, AnyStr]):
        """
        Read the text file and split it into sections
        :return: list of sections, dictionary of sections by type
        """

        if text_func is not None:
            text_func("Detecting raw file encoding...")

        if progress_func is not None:
            progress_func(0)

        # make a guess of the file encoding
        detection = chardet.detect(open(self.file_name, "rb").read())

        # open the text file into a variable

        if text_func is not None:
            text_func("Reading raw file...")

        txt = ''
        lines = list()
        with open(self.file_name, 'r', encoding=detection['encoding']) as my_file:
            for line in my_file:
                if line[0] != '@':
                    txt += line
                    lines.append(line)

        # split the text file into sections
        sections = txt.split(' /')
        # sections = txt.split(' 0 /')

        sections_dict = dict()

        if text_func is not None:
            text_func("Parsing the raw file information...")

        str_a = 'End of'.lower()
        str_b = 'data'.lower()
        n_sec = len(sections)
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

                if name.lower() == 'bus' and len(data2) > 1:
                    data2.pop(0)
                    data2.pop(0)

                sections_dict[name] = data2

            if progress_func is not None:
                progress_func((i / n_sec) * 100)

        return sections, sections_dict

    def read_and_split(self, text_func=None, progress_func=None) -> (List[AnyStr], Dict[AnyStr, AnyStr]):
        """
        Read the text file and split it into sections
        :return: list of sections, dictionary of sections by type
        """

        if text_func is not None:
            text_func("Detecting raw file encoding...")

        if progress_func is not None:
            progress_func(0)

        # make a guess of the file encoding
        detection = chardet.detect(open(self.file_name, "rb").read())

        # open the text file into a variable

        if text_func is not None:
            text_func("Reading raw file...")

        sections_dict: Dict[str, List[Union[str, float, int]]] = dict()
        sections_dict["bus"] = list()
        sep = ","
        with open(self.file_name, 'r', encoding=detection['encoding']) as my_file:
            i = 0
            block_category = "bus"
            for line_ in my_file:

                if line_[0] != '@':
                    # remove garbage
                    lne = line_.strip()

                    if lne.startswith("program"):
                        # common header
                        block_category = 'program'
                        sections_dict[block_category] = list()

                    if i == 0:
                        sections_dict['info'] = [interpret_line(lne, sep)]
                    elif i == 1:
                        sections_dict['comment'] = [lne]
                    elif i == 2:
                        sections_dict['comment2'] = [lne]
                    else:

                        if lne.startswith("0 /"):
                            # this is a category splitter
                            if lne.startswith("cards"):
                                # MISO file
                                pass
                            else:
                                # common header
                                s = lne.lower().split(", begin")
                                if len(s) == 2:
                                    block_category = s[1].replace("begin", "").replace("data", "").strip()
                                    sections_dict[block_category] = list()

                        elif lne.startswith("Q"):
                            pass
                        else:
                            if lne.strip() != '':
                                sections_dict[block_category].append(interpret_line(lne, sep))

                    i += 1
                else:
                    # it is a header
                    hdr = line_.strip()
                    pass

        return sections_dict

    def parse_psse(self, text_func=None, progress_func=None) -> (MultiCircuit, List[AnyStr]):
        """
        Parser implemented according to:
            - POM section 4.1.1 Power Flow Raw Data File Contents (v.29)
            - POM section 5.2.1                                   (v.33)
            - POM section 5.2.1                                   (v.32)

        Returns: MultiCircuit, List[str]
        """

        logger = Logger()

        if text_func is not None:
            text_func("Reading file...")

        sections_dict = self.read_and_split(text_func=text_func, progress_func=progress_func)

        # header -> new grid
        # grid = PSSeGrid(interpret_line(sections[0]))
        grid = PSSeGrid(sections_dict['info'][0])

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
        meta_data['fixed bus shunt'] = [grid.shunts, PSSeShunt, 1]
        meta_data['shunt'] = [grid.shunts, PSSeShunt, 1]
        meta_data['switched shunt'] = [grid.switched_shunts, PSSeSwitchedShunt, 1]
        meta_data['generator'] = [grid.generators, PSSeGenerator, 1]
        meta_data['induction machine'] = [grid.generators, PSSeInductionMachine, 3]
        meta_data['branch'] = [grid.branches, PSSeBranch, 1]
        meta_data['nontransformer branch'] = [grid.branches, PSSeBranch, 1]
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

        bus_set = {lne[0] for lne in sections_dict["bus"]}

        def is_3w(row):
            return row[0] in bus_set and row[1] in bus_set and row[2] in bus_set

        for key, lines in sections_dict.items():

            if key in meta_data:

                # get the parsers for the declared object type
                objects_list, ObjectT, lines_per_object = meta_data[key]

                if text_func is not None:
                    text_func("Converting {0}...".format(key))

                if key in sections_dict.keys():

                    # iterate ove the object's lines to pack them as expected
                    # (normally 1 per object except transformers...)
                    l_count = 0
                    while l_count < len(lines):

                        lines_per_object2 = lines_per_object

                        if version in self.versions and key == 'transformer':
                            # as you know the PSS/e raw format is nuts, that is why for v29 (onwards probably)
                            # the transformers may have 4 or 5 lines to define them
                            # so, to be able to know, we look at the line "l" and check if the first arguments
                            # are 2 or 3 buses
                            if is_3w(lines[l_count]):
                                # 3 - windings
                                lines_per_object2 = 5
                            else:
                                # 2-windings
                                lines_per_object2 = 4

                        data = list()
                        for k in range(lines_per_object2):
                            data.append(lines[l_count + k])

                        # pick the line that matches the object and split it by line returns \n
                        # object_lines = line.split('\n')

                        # interpret each line of the object and store into data.
                        # data is a vector of vectors with data definitions
                        # for the buses, Branches, loads etc. data contains 1 vector,
                        # for the transformers data contains 4 vectors
                        # data = [interpret_line(object_lines[k]) for k in range(lines_per_object)]

                        # pass the data to the according object to assign it to the matching variables
                        obj = ObjectT()
                        obj.parse(data, version, logger)
                        objects_list.append(obj)

                        # add lines
                        l_count += lines_per_object2

                        if progress_func is not None:
                            progress_func((l_count / len(lines)) * 100)

                else:
                    pass

            else:
                if len(lines) > 0 and key not in ['info', 'comment', 'comment2']:
                    # add logs for the non parsed objects
                    logger.add_warning('Not implemented in the parser', key)

        return grid, logger
