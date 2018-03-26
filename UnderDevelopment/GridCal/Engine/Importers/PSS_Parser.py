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

from GridCal.Engine.CalculationEngine import *
import math
import chardet
import numpy as np
import pandas as pd
from numpy import array
from pandas import DataFrame as df
from warnings import warn


class PSSeGrid:

    def __init__(self, data):
        """
        IC
            New Case Flag:
            0 for base case input (i.e., clear the working case before adding data to it)
            1 to add data to the working case
            IC = 0 by default.
        SBASE System MVA base. SBASE = 100.0 by default.
        REV = current revision (32) by default.
        XFRRAT Units of transformer ratings (refer to Transformer Data). The transformer percent
            loading units program option setting (refer to Saved Case Specific Option Settings) is
            set according to this data value.
            XFRRAT < 0 for MVA
            XFRRAT > 0 for current expressed as MVA
            XFRRAT = present transformer percent loading program option setting by default
            (refer to activity OPTN).
        NXFRAT
            Units of ratings of non-transformer branches (refer to Non-Transformer Branch
            Data ). The non-transformer branch percent loading units program option setting
            (refer to Saved Case Specific Option Settings) is set according to this data value.
            NXFRAT < 0 for MVA
            NXFRAT > 0 for current expressed as MVA
            NXFRAT = present non-transformer branch percent loading program option setting
            by default (refer to activity OPTN).
        BASFRQ
            System base frequency in Hertz. The base frequency program option setting (refer to
            Saved Case Specific Option Settings) is set to this data value. BASFRQ = present
            base frequency program option setting value by default (refer to activity OPTN).
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
        self.generators = list()
        self.branches = list()
        self.transformers = list()

    def get_circuit(self):
        """
        Return GridCal circuit
        Returns:

        """

        circuit = MultiCircuit()
        circuit.Sbase = self.SBASE

        # ---------------------------------------------------------------------
        # Bus related
        # ---------------------------------------------------------------------
        psse_bus_dict = dict()
        for psse_bus in self.buses:

            # relate each PSS bus index with a GridCal bus object
            psse_bus_dict[psse_bus.I] = psse_bus.bus

            # add the bus to the circuit
            circuit.add_bus(psse_bus.bus)

        # Go through loads
        for psse_load in self.loads:

            bus = psse_bus_dict[psse_load.I]
            api_obj = psse_load.get_object(bus)

            circuit.add_load(bus, api_obj)

        # Go through shunts
        for psse_shunt in self.shunts:

            bus = psse_bus_dict[psse_shunt.I]
            api_obj = psse_shunt.get_object(bus)

            circuit.add_shunt(bus, api_obj)

        # Go through generators
        for psse_gen in self.generators:

            bus = psse_bus_dict[psse_gen.I]
            api_obj = psse_gen.get_object()

            circuit.add_controlled_generator(bus, api_obj)

        # ---------------------------------------------------------------------
        # Branches
        # ---------------------------------------------------------------------
        # Go through Branches
        for psse_banch in self.branches:
            # get the object
            branch = psse_banch.get_object(psse_bus_dict)

            # Add to the circuit
            circuit.add_branch(branch)

        # Go through Transformers
        for psse_banch in self.transformers:
            # get the object
            branches = psse_banch.get_object(psse_bus_dict)

            # Add to the circuit
            for branch in branches:
                circuit.add_branch(branch)

        return circuit


class PSSeBus:

    def __init__(self, data, version):
        """
        I: Bus number (1 through 999997). No default allowed.
        NAME Alphanumeric identifier assigned to bus I. NAME may be up to twelve characters
            and may contain any combination of blanks, uppercase letters, numbers and
            special characters, but the first character must not be a minus sign. NAME must
            be enclosed in single or double quotes if it contains any blanks or special char-
            acters. NAME is twelve blanks by default.
        BASKV: Bus base voltage; entered in kV. BASKV = 0.0 by default.
        IDE: Bus type code:
            1 -> for a load bus or passive node (no generator boundary condition) 
            2 -> for a generator or plant bus (either voltage regulating or fixed Mvar) 
            3 -> for a swing bus 
            4 -> for a disconnected (isolated) bus
            IDE = 1 by default.
        AREA: Area number (1 through 9999). AREA = 1 by default.
        ZONE: Zone number (1 through 9999). ZONE = 1 by default.
        OWNER: Owner number (1 through 9999). OWNER = 1 by default.
        VM: Bus voltage magnitude; entered in pu. VM = 1.0 by default.
        VA: Bus voltage phase angle; entered in degrees. VA = 0.0 by default.
        NVHI: Normal voltage magnitude high limit; entered in pu. NVHI=1.1 by default
        NVLO: Normal voltage magnitude low limit, entered in pu. NVLO=0.9 by default
        EVHI: Emergency voltage magnitude high limit; entered in pu. EVHI=1.1 by default
        EVLO: Emergency voltage magnitude low limit; entered in pu. EVLO=0.9 by default
        Args:
            data:
        """

        bustype = {1: NodeType.PQ, 2: NodeType.PV, 3: NodeType.REF, 4: NodeType.PQ}

        if version == 33:
            n = len(data[0])
            dta = zeros(13, dtype=object)
            dta[0:n] = data[0]

            self.I, self.NAME, self.BASKV, self.IDE, self.AREA, self.ZONE, \
             self.OWNER, self.VM, self.VA, self.NVHI, self.NVLO, self.EVHI, self.EVLO = dta

            # create bus
            name = self.NAME
            # name = str(self.I) + '_' + self.NAME
            self.bus = Bus(name=name, vnom=self.BASKV, vmin=self.EVLO, vmax=self.EVHI, xpos=0, ypos=0, active=True)

        elif version == 32:

            self.I, self.NAME, self.BASKV, self.IDE, self.AREA, self.ZONE, self.OWNER, self.VM, self.VA = data[0]

            # create bus
            name = self.NAME
            # name = str(self.I) + '_' + self.NAME
            self.bus = Bus(name=name, vnom=self.BASKV, vmin=0.9, vmax=1.1, xpos=0, ypos=0,
                           active=True)

        elif version == 30:

            self.I, self.NAME, self.BASKV, self.IDE, self.GL, self.BL, \
             self.AREA, self.ZONE, self.VM, self.VA, self.OWNER = data[0]

            # create bus
            name = self.NAME
            # name = str(self.I) + '_' + self.NAME
            self.bus = Bus(name=name, vnom=self.BASKV, vmin=0.9, vmax=1.1, xpos=0, ypos=0,
                           active=True)

            if self.GL > 0 or self.BL > 0:
                sh = Shunt(name='Shunt_' + self.ID,
                           admittance=complex(self.GL, self.BL),
                           admittance_prof=None,
                           active=True)

                self.bus.shunts.append(sh)

        # set type
        self.bus.type = bustype[self.IDE]

        if self.bus.type == NodeType.REF:
            self.bus.is_slack = True

        self.bus.name = self.bus.name.replace("'", "").strip()


class PSSeLoad:

    def __init__(self, data, version):
        """
        I: Bus number, or extended bus name enclosed in single quotes (refer to Extended Bus
            Names). No default allowed.
        ID: One- or two-character uppercase non-blank alphanumeric load identifier used to
            distinguish among multiple loads at bus I. It is recommended that, at buses for which
            a single load is present, the load be designated as having the load identifier 1. ID = 1
            by default.
        STATUS: Load status of one for in-service and zero for out-of-service. STATUS = 1 by default.
        AREA: Area to which the load is assigned (1 through 9999). By default, AREA is the area to
            which bus I is assigned (refer to Bus Data).
        ZONE: Zone to which the load is assigned (1 through 9999). By default, ZONE is the zone to
            which bus I is assigned (refer to Bus Data).
        PL: Active power component of constant MVA load; entered in MW. PL = 0.0 by default.
        QL: Reactive power component of constant MVA load; entered in Mvar. QL = 0.0 by
            default.
        IP: Active power component of constant current load; entered in MW at one per unit
            voltage. IP = 0.0 by default.
        IQ: Reactive power component of constant current load; entered in Mvar at one per unit
            voltage. IQ = 0.0 by default.
        YP: Active power component of constant admittance load; entered in MW at one per unit
            voltage. YP = 0.0 by default.
        YQ: Reactive power component of constant admittance load; entered in Mvar at one per
            unit voltage. YQ is a negative quantity for an inductive load and positive for a capacitive load.
            YQ = 0.0 by default.
        OWNER: Owner to which the load is assigned (1 through 9999). By default, OWNER is the
            owner to which bus I is assigned (refer to Bus Data).
        SCALE: Load scaling flag of one for a scalable load and zero for a fixed load (refer to SCAL).
            SCALE = 1 by default.
        INTRPT: Interruptible load flag of one for an interruptible load for zero for a non interruptible
            load. INTRPT=0 by default.
        Args:
            data:
        """

        if version == 33:

            n = len(data[0])
            dta = zeros(14, dtype=object)
            dta[0:n] = data[0]

            self.I, self.ID, self.STATUS, self.AREA, self.ZONE, self.PL, self.QL, \
             self.IP, self.IQ, self.YP, self.YQ, self.OWNER, self.SCALE, self.INTRPT = dta

        elif version == 32:

            self.I, self.ID, self.STATUS, self.AREA, self.ZONE, self.PL, self.QL, \
             self.IP, self.IQ, self.YP, self.YQ, self.OWNER, self.SCALE = data[0]

        elif version == 30:

            self.I, self.ID, self.STATUS, self.AREA, self.ZONE, self.PL, \
             self.QL, self.IP, self.IQ, self.YP, self.YQ, self.OWNER = data[0]

    def get_object(self, bus: Bus):
        """
        Return GridCal Load object
        Returns:
            Gridcal Load object
        """

        # GL and BL come in MW and MVAr
        # THey must be in siemens
        vv = bus.Vnom ** 2.0

        if vv == 0:
            warn('Voltage equal to zero in shunt conversion!!!')

        g, b = self.YP, self.YQ
        ir, ii = self.IP, self.IQ
        p, q = self.PL, self.QL

        object = Load(name='Load ' + self.ID,
                      impedance=complex(g, b),
                      current=complex(ir, ii),
                      power=complex(p, q),
                      impedance_prof=None,
                      current_prof=None,
                      power_prof=None)

        return object


class PSSeShunt:

    def __init__(self, data, version):
        """
        I: Bus number, or extended bus name enclosed in single quotes (refer to Extended
            Bus Names). No default allowed.
        ID: One- or two-character uppercase non-blank alphanumeric shunt identifier used to
            distinguish among multiple shunts at bus I. It is recommended that, at buses for
            which a single shunt is present, the shunt be designated as having the shunt identi-
            fier 1. ID = 1 by default.
        STATUS: Shunt status of one for in-service and zero for out-of-service. STATUS = 1 by
            default.
        GL: Active component of shunt admittance to ground; entered in MW at one per unit
            voltage. GL should not include any resistive impedance load, which is entered as
            part of load data. GL = 0.0 by default.
        BL: Reactive component of shunt admittance to ground; entered in Mvar at one per unit
            voltage. BL should not include any reactive impedance load, which is entered as
            part of load data; line charging and line connected shunts, which are entered as part
            of non-transformer branch data; transformer magnetizing admittance, which is
            entered as part of transformer data; or switched shunt admittance, which is entered
            as part of switched shunt data. BL is positive for a capacitor, and negative for a
            reactor or an inductive load. BL = 0.0 by default.
        Args:
            data:
        """
        if version == 33:
            self.I, self.ID, self.STATUS, self.GL, self.BL = data[0]

        elif version == 32:

            self.I, self.ID, self.STATUS, self.GL, self.BL = data[0]

    def get_object(self, bus: Bus):
        """
        Return GridCal Load object
        Returns:
            Gridcal Load object
        """

        # GL and BL come in MW and MVAr
        # THey must be in siemens
        vv = bus.Vnom**2.0

        if vv == 0:
            warn('Voltage equal to zero in shunt conversion!!!')

        g = self.GL
        b = self.BL

        object = Shunt(name='Shunt' + self.ID,
                       admittance=complex(g, b),
                       admittance_prof=None,
                       active=bool(self.STATUS))

        return object


class PSSeGenerator:

    def __init__(self, data, version):
        """
        I: Bus number, or extended bus name enclosed in single quotes (refer to Extended
            Bus Names). No default allowed.
        ID: One- or two-character uppercase non-blank alphanumeric machine identifier used
            to distinguish among multiple machines at bus I. It is recommended that, at buses
            for which a single machine is present, the machine be designated as having the
            machine identifier 1. ID = 1 by default.
        PG: Generator active power output; entered in MW. PG = 0.0 by default.
        QG: Generator reactive power output; entered in Mvar. QG needs to be entered only if
            the case, as read in, is to be treated as a solved case. QG = 0.0 by default.
        QT: Maximum generator reactive power output; entered in Mvar. For fixed output generators
            (i.e., nonregulating), QT must be equal to the fixed Mvar output. QT = 9999.0
            by default.
        QB: Minimum generator reactive power output; entered in Mvar. For fixed output generators,
            QB must be equal to the fixed Mvar output. QB = -9999.0 by default.
        VS: Regulated voltage setpoint; entered in pu. VS = 1.0 by default.
        IREG: Bus number, or extended bus name enclosed in single quotes, of a remote Type 1
            or 2 bus for which voltage is to be regulated by this plant to the value specified by
            VS. If bus IREG is other than a Type 1 or 2 bus, bus I regulates its own voltage to
            the value specified by VS. IREG is entered as zero if the plant is to regulate its own
            voltage and must be zero for a Type 3 (swing) bus. IREG = 0 by default.
        MBASE: Total MVA base of the units represented by this machine; entered in MVA. This
            quantity is not needed in normal power flow and equivalent construction work, but is
            required for switching studies, fault analysis, and dynamic simulation.
            MBASE = system base MVA by default.
        ZR,ZX: Complex machine impedance, ZSORCE; entered in pu on MBASE base. This data
            is not needed in normal power flow and equivalent construction work, but is required
            for switching studies, fault analysis, and dynamic simulation. For dynamic simula-
            tion, this impedance must be set equal to the unsaturated subtransient impedance
            for those generators to be modeled by subtransient level machine models, and to
            unsaturated transient impedance for those to be modeled by classical or transient
            level models. For short-circuit studies, the saturated subtransient or transient
            impedance should be used. ZR = 0.0 and ZX = 1.0 by default.
        RT,XT: Step-up transformer impedance, XTRAN; entered in pu on MBASE base. XTRAN
            should be entered as zero if the step-up transformer is explicitly modeled as a
            network branch and bus I is the terminal bus. RT+jXT = 0.0 by default.
        GTAP: Step-up transformer off-nominal turns ratio; entered in pu on a system base. GTAP
            is used only if XTRAN is non-zero. GTAP = 1.0 by default.
        STAT: Machine status of one for in-service and zero for out-of-service; STAT = 1 by
            default.
        RMPCT: Percent of the total Mvar required to hold the voltage at the bus controlled by bus I
            that are to be contributed by the generation at bus I; RMPCT must be positive.
        RMPCT: is needed only if IREG specifies a valid remote bus and there is more than
            one local or remote voltage controlling device (plant, switched shunt, FACTS device
            shunt element, or VSC dc line converter) controlling the voltage at bus IREG to a
            setpoint, or IREG is zero but bus I is the controlled bus, local or remote, of one or
            more other setpoint mode voltage controlling devices. RMPCT = 100.0 by default.
        PT: Maximum generator active power output; entered in MW. PT = 9999.0 by default.
        PB: Minimum generator active power output; entered in MW. PB = -9999.0 by default.
        Oi: Owner number (1 through 9999). Each machine may have up to four owners. By
            default, O1 is the owner to which bus I is assigned (refer to Bus Data) and O2, O3,
            and O4 are zero.
        Fi: Fraction of total ownership assigned to owner Oi; each Fi must be positive. The Fi
            values are normalized such that they sum to 1.0 before they are placed in the
            working case. By default, each Fi is 1.0.
        WMOD: Wind machine control mode; WMOD is used to indicate whether a machine is a
            wind machine, and, if it is, the type of reactive power limits to be imposed.
            0 for a machine that is not a wind machine.
            1 for a wind machine for which reactive power limits are specified 
            by QT and QB.
            2 for a wind machine for which reactive power limits are determined from 
            the machine’s active power output and WPF; limits are of equal 
            magnitude and opposite sign
            3 for a wind machine with a fixed reactive power setting determined from 
            the machine’s active power output and WPF; when WPF is positive, 
            the machine’s reactive power has the same sign as its active power; 
            when WPF is negative, the machine’s reactive power has the opposite 
            sign of its active power.
            WMOD = 0 by default.
        WPF: Power factor used in calculating reactive power limits or output when WMOD is 2 or 3.
            WPF = 1.0 by default.
        Args:
            data:
            version:
        """

        length = len(data[0])

        if version in [33, 32, 30]:

            if length == 28:
                self.I, self.ID, self.PG, self.QG, self.QT, self.QB, self.VS, self.IREG, self.MBASE, \
                 self.ZR, self.ZX, self.RT, self.XT, self.GTAP, self.STAT, self.RMPCT, self.PT, self.PB, \
                 self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4, self.WMOD, self.WPF = data[0]

            elif length == 26:
                self.I, self.ID, self.PG, self.QG, self.QT, self.QB, self.VS, self.IREG, self.MBASE, \
                 self.ZR, self.ZX, self.RT, self.XT, self.GTAP, self.STAT, self.RMPCT, self.PT, self.PB, \
                 self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.WMOD, self.WPF = data[0]

            elif length == 24:
                self.I, self.ID, self.PG, self.QG, self.QT, self.QB, self.VS, self.IREG, self.MBASE, \
                 self.ZR, self.ZX, self.RT, self.XT, self.GTAP, self.STAT, self.RMPCT, self.PT, self.PB, \
                 self.O1, self.F1, self.O2, self.F2, self.WMOD, self.WPF = data[0]

            elif length == 22:
                self.I, self.ID, self.PG, self.QG, self.QT, self.QB, self.VS, self.IREG, self.MBASE, \
                 self.ZR, self.ZX, self.RT, self.XT, self.GTAP, self.STAT, self.RMPCT, self.PT, self.PB, \
                 self.O1, self.F1, self.WMOD, self.WPF = data[0]

            elif length == 20:
                self.I, self.ID, self.PG, self.QG, self.QT, self.QB, self.VS, self.IREG, self.MBASE, \
                 self.ZR, self.ZX, self.RT, self.XT, self.GTAP, self.STAT, self.RMPCT, self.PT, self.PB, \
                 self.WMOD, self.WPF = data[0]

            else:
                raise Exception('Wrong data length in generator' + str(length))

    def get_object(self):
        """
        Return GridCal Load object
        Returns:
            Gridcal Load object
        """

        object = ControlledGenerator(name='Gen_' + str(self.ID),
                                     active_power=self.PG,
                                     voltage_module=self.VS,
                                     Qmin=self.QB,
                                     Qmax=self.QT,
                                     Snom=self.MBASE,
                                     power_prof=None,
                                     vset_prof=None,
                                     active=bool(self.STAT))

        return object


class PSSeBranch:

    def __init__(self, data, version):
        """
        I: Branch from bus number, or extended bus name enclosed in single quotes (refer to
            Extended Bus Names). No default allowed.
        J: Branch to bus number, or extended bus name enclosed in single quotes.
        CKT: One- or two-character uppercase non-blank alphanumeric branch circuit identifier;
            the first character of CKT must not be an ampersand ( & ); refer to Multi-Section
            Line Grouping Data. If the first character of CKT is an at sign ( @ ), the branch is
            treated as a breaker; if it is an asterisk ( * ), it is treated as a switch (see Section
            6.17.2, Outage Statistics Data File Contents). Unless it is a breaker or switch, it is
            recommended that single circuit branches be designated as having the circuit identifier 1.
            CKT = 1 by default.
        R: Branch resistance; entered in pu. A value of R must be entered for each branch.
        X: Branch reactance; entered in pu. A non-zero value of X must be entered for each
            branch. Refer to Zero Impedance Lines for details on the treatment of branches as
            zero impedance lines.
        B: Total branch charging susceptance; entered in pu. B = 0.0 by default.
        RATEA: First rating; entered in either MVA or current expressed as MVA, according to the
            value specified for NXFRAT specified on the first data record (refer to Case Identification Data).
            RATEA = 0.0 (bypass check for this branch; this branch will not be included in any
            examination of circuit loading) by default. Refer to activity RATE.
        RATEB: Second rating; entered in either MVA or current expressed as MVA, according to
            the value specified for NXFRAT specified on the first data record (refer to Case
            Identification Data). RATEB = 0.0 by default.
        RATEC: Third rating; entered in either MVA or current expressed as MVA, according to the
            value specified for NXFRAT specified on the first data record (refer to Case Identification Data).
            RATEC = 0.0 by default.
            When specified in units of current expressed as MVA, ratings are entered as:
            MVArated = sqrt(3) x Ebase x Irated x 10-6
            where:
                Ebase is the base line-to-line voltage in volts of the buses to which the terminal of the branch
                    is connected
                Irated is the branch rated phase current in amperes.
        GI,BI: Complex admittance of the line shunt at the bus I end of the branch; entered in pu.
            BI is negative for a line connected reactor and positive for line connected capacitor.
            GI + jBI = 0.0 by default.
        GJ,BJ: Complex admittance of the line shunt at the bus J end of the branch; entered in pu.
            BJ is negative for a line connected reactor nd positive for line connected capacitor.
            GJ + jBJ = 0.0 by default.
        ST: Branch status of one for in-service and zero for out-of-service; ST = 1 by default.
        MET: Metered end flag;
            <1 to designate bus I as the metered end
            >2 to designate bus J as the metered end.
            MET = 1 by default.
        LEN: Line length; entered in user-selected units. LEN = 0.0 by default.
        Oi: Owner number (1 through 9999). Each branch may have up to four owners. By
            default, O1 is the owner to which bus I is assigned (refer to Bus Data) and O2, O3,
            and O4 are zero.
        Fi: Fraction of total ownership assigned to owner Oi; each Fi must be positive. The Fi
            values are normalized such that they sum to 1.0 before they are placed in the
            working case. By default, each Fi is 1.0.
        Args:
            data:
            version:
        """

        length = len(data[0])

        if version in [33, 32]:

            if length == 24:
                self.I, self.J, self.CKT, self.R, self.X, self.B, self.RATEA, self.RATEB, self.RATEC, \
                 self.GI, self.BI, self.GJ, self.BJ, self.ST, self.MET, self.LEN, \
                 self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4 = data[0]
            elif length == 22:
                self.I, self.J, self.CKT, self.R, self.X, self.B, self.RATEA, self.RATEB, self.RATEC, \
                 self.GI, self.BI, self.GJ, self.BJ, self.ST, self.MET, self.LEN, \
                 self.O1, self.F1, self.O2, self.F2, self.O3, self.F3 = data[0]
            elif length == 20:
                self.I, self.J, self.CKT, self.R, self.X, self.B, self.RATEA, self.RATEB, self.RATEC, \
                 self.GI, self.BI, self.GJ, self.BJ, self.ST, self.MET, self.LEN, \
                 self.O1, self.F1, self.O2, self.F2 = data[0]
            elif length == 18:
                self.I, self.J, self.CKT, self.R, self.X, self.B, self.RATEA, self.RATEB, self.RATEC, \
                 self.GI, self.BI, self.GJ, self.BJ, self.ST, self.MET, self.LEN, \
                 self.O1, self.F1 = data[0]
            elif length == 16:
                self.I, self.J, self.CKT, self.R, self.X, self.B, self.RATEA, self.RATEB, self.RATEC, \
                 self.GI, self.BI, self.GJ, self.BJ, self.ST, self.MET, self.LEN = data[0]

            else:
                raise Exception('Wrong data length in branch' + str(length))

        elif version == 30:
            """
            I,J,CKT,R,X,B,RATEA,RATEB,RATEC,GI,BI,GJ,BJ,ST,LEN,01,F1, ,04,F4
            """
            if length == 24:
                self.I, self.J, self.CKT, self.R, self.X, self.B, self.RATEA, self.RATEB, self.RATEC, \
                 self.GI, self.BI, self.GJ, self.BJ, self.ST, self.LEN, \
                 self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4 = data[0]
            elif length == 22:
                self.I, self.J, self.CKT, self.R, self.X, self.B, self.RATEA, self.RATEB, self.RATEC, \
                 self.GI, self.BI, self.GJ, self.BJ, self.ST, self.LEN, \
                 self.O1, self.F1, self.O2, self.F2, self.O3, self.F3 = data[0]
            elif length == 20:
                self.I, self.J, self.CKT, self.R, self.X, self.B, self.RATEA, self.RATEB, self.RATEC, \
                 self.GI, self.BI, self.GJ, self.BJ, self.ST, self.LEN, \
                 self.O1, self.F1, self.O2, self.F2 = data[0]
            elif length == 18:
                self.I, self.J, self.CKT, self.R, self.X, self.B, self.RATEA, self.RATEB, self.RATEC, \
                 self.GI, self.BI, self.GJ, self.BJ, self.ST, self.LEN, \
                 self.O1, self.F1 = data[0]
            elif length == 16:
                self.I, self.J, self.CKT, self.R, self.X, self.B, self.RATEA, self.RATEB, self.RATEC, \
                 self.GI, self.BI, self.GJ, self.BJ, self.ST, self.LEN = data[0]

            else:
                raise Exception('Wrong data length in branch' + str(length))

        else:

            warn('Invalid Branch version')

    def get_object(self, psse_bus_dict):
        """
        Return GridCal branch object
        Args:
            psse_bus_dict: Dictionary that relates PSSe bus indices with GridCal Bus objects

        Returns:
            Gridcal Branch object
        """
        bus_from = psse_bus_dict[self.I]
        bus_to = psse_bus_dict[self.J]

        if self.LEN > 0:
            r = self.R * self.LEN
            x = self.X * self.LEN
            b = self.B * self.LEN
        else:
            r = self.R
            x = self.X
            b = self.B

        object = Branch(bus_from=bus_from, bus_to=bus_to,
                        name='Branch',
                        r=r,
                        x=x,
                        g=1e-20,
                        b=b,
                        rate=max(self.RATEA, self.RATEB, self.RATEC),
                        tap=1,
                        shift_angle=0,
                        active=True,
                        mttf=0,
                        mttr=0,
                        is_transformer=False)
        return object


class PSSeTransformer:

    def __init__(self, data, version):
        """
        I The bus number, or extended bus name enclosed in single quotes (refer to
            Extended Bus Names), of the bus to which Winding 1 is connected. The trans-
            former’s magnetizing admittance is modeled on Winding 1. Winding 1 is the only
            winding of a two-winding transformer for which tap ratio or phase shift angle may be
            adjusted by the power flow solution activities; any winding(s) of a three-winding
            transformer may be adjusted. No default is allowed.
        J The bus number, or extended bus name enclosed in single quotes, of the bus to
            which Winding 2 is connected. No default is allowed.
        K The bus number, or extended bus name enclosed in single quotes, of the bus to
            which Winding 3 is connected. Zero is used to indicate that no third winding is
            present (i.e., that a two-winding rather than a three-winding transformer is being
            specified). K = 0 by default.
        CKT One- or two-character uppercase non-blank alphanumeric transformer circuit identi-
            fier; the first character of CKT must not be an ampersand ( & ), at sign ( @ ), or
            asterisk ( * ); refer to Multi-Section Line Grouping Data and Section 6.17.2, Outage
            Statistics Data File Contents. CKT = 1 by default.
        CW The winding data I/O code defines the units in which the turns ratios WINDV1,
            WINDV2 and WINDV3 are specified (the units of RMAn and RMIn are also
            governed by CW when |CODn| is 1 or 2):
            1 for off-nominal turns ratio in pu of winding bus base voltage
            2 for winding voltage in kV
            3 for off-nominal turns ratio in pu of nominal winding voltage, 
            NOMV1, NOMV2 and NOMV3.
            CW = 1 by default.
        CZ  The impedance data I/O code defines the units in which the winding impedances
            R1-2, X1-2, R2-3, X2-3, R3-1 and X3-1 are specified:

            1 for resistance and reactance in pu on system MVA base and  winding voltage base

            2 for resistance and reactance in pu on a specified MVA base and winding voltage base

            3 for transformer load loss in watts and impedance magnitude in pu on a specified
              MVA base and winding voltage base.

            In specifying transformer leakage impedances, the base voltage values are always
            the nominal winding voltages that are specified on the third, fourth and fifth records
            of the transformer data block (NOMV1, NOMV2 and NOMV3). If the default NOMVn
            is not specified, it is assumed to be identical to the winding n bus base voltage.
            CZ = 1 by default.
        CM The magnetizing admittance I/O code defines the units in which MAG1 and MAG2 are specified:
            1 for complex admittance in pu on system MVA base and Winding 1 
            bus voltage base
            2 for no load loss in watts and exciting current in pu on Winding 1 to 
            two MVA base (SBASE1-2) and nominal Winding 1 voltage, NOMV1.
            CM = 1 by default.
        MAG1, MAG2: The transformer magnetizing admittance connected to ground at bus I.
            When CM is 1, MAG1 and MAG2 are the magnetizing conductance and suscep-
            tance, respectively, in pu on system MVA base and Winding 1 bus voltage base.
            When a non-zero MAG2 is specified, it should be entered as a negative quantity.
            When CM is 2, MAG1 is the no load loss in watts and MAG2 is the exciting current
            in pu on Winding 1 to two MVA base (SBASE1-2) and nominal Winding 1 voltage
            (NOMV1). For three-phase transformers or three-phase banks of single phase
            transformers, MAG1 should specify the three-phase no-load loss. When a non-zero
            MAG2 is specified, it should be entered as a positive quantity.
            MAG1 = 0.0 and MAG2 = 0.0 by default.
        NMETR The non-metered end code of either 1 (for the Winding 1 bus) or 2 (for the Winding 2 bus).
            In addition, for a three-winding transformer, 3 (for the Winding 3 bus) is a valid
            specification of NMETR. NMETR = 2 by default.
        NAME Alphanumeric identifier assigned to the transformer. NAME may be up to twelve
            characters and may contain any combination of blanks, uppercase letters, numbers
            and special characters. NAME must be enclosed in single or double quotes if it
            contains any blanks or special characters. NAME is twelve blanks by default.
        STAT Transformer status of one for in-service and zero for out-of-service.
            In addition, for a three-winding transformer, the following values of STAT provide for
            one winding out-of-service with the remaining windings in-service:
            2 -> for only Winding 2 out-of-service
            3 -> for only Winding 3 out-of-service
            4 -> for only Winding 1 out-of-service
            STAT = 1 by default.
        Oi: An owner number (1 through 9999). Each transformer may have up to four owners.
            By default, O1 is the owner to which bus I is assigned and O2, O3, and O4 are zero.
        Fi: The fraction of total ownership assigned to owner Oi; each Fi must be positive. The
            Fi values are normalized such that they sum to 1.0 before they are placed in the
            working case. By default, each Fi is 1.0.
        VECGRP: Alphanumeric identifier specifying vector group based on transformer winding
            connections and phase angles. VECGRP value is used for information purpose
            only. VECGRP is 12 blanks by default

        ----------------------------------------------------------------------------------------------
        The first three data items on the second record are read for both two- and three-winding trans-
        formers; the remaining data items are used only for three-winding transformers:

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
        SBASE1-2 The Winding 1 to 2 three-phase base MVA of the transformer. SBASE1-2 = SBASE
            (the system base MVA) by default.
        R2-3, X2-3 The measured impedance of a three-winding transformer between the buses to
            which its second and third windings are connected; ignored for a two-winding
            transformer.
            When CZ is 1, they are the resistance and reactance, respectively, in pu on system
            MVA base and winding voltage base.
            When CZ is 2, they are the resistance and reactance, respectively, in pu on Winding
            2 to 3 MVA base (SBASE2-3) and winding voltage base.
            When CZ is 3, R2-3 is the load loss in watts, and X2-3 is the impedance magnitude
            in pu on Winding 2 to 3 MVA base (SBASE2-3) and winding voltage base. For
            three-phase transformers or three-phase banks of single phase transformers, R2-3
            should specify the three-phase load loss.
            R2-3 = 0.0 by default, but no default is allowed for X2-3.
        SBASE2-3 The Winding 2 to 3 three-phase base MVA of a three-winding transformer; ignored
            for a two-winding transformer. SBASE2-3 = SBASE (the system base MVA) by
            default.
        R3-1, X3-1 The measured impedance of a three-winding transformer between the buses to
            which its third and first windings are connected; ignored for a two-winding
            transformer.
            When CZ is 1, they are the resistance and reactance, respectively, in pu on system
            MVA base and winding voltage base.
            When CZ is 2, they are the resistance and reactance, respectively, in pu on Winding
            3 to 1 MVA base (SBASE3-1) and winding voltage base.
            When CZ is 3, R3-1 is the load loss in watts, and X3-1 is the impedance magnitude
            in pu on Winding 3 to 1 MVA base (SBASE3-1) and winding voltage base. For
            three-phase transformers or three-phase banks of single phase transformers, R3-1
            should specify the three-phase load loss.
            R3-1 = 0.0 by default, but no default is allowed for X3-1.
        SBASE3-1 The Winding 3 to 1 three-phase base MVA of a three-winding transformer; ignored
            for a two-winding transformer. SBASE3-1 = SBASE (the system base MVA) by

        VMSTAR The voltage magnitude at the hidden star point bus; entered in pu. VMSTAR = 1.0
            by default.
        ANSTAR The bus voltage phase angle at the hidden star point bus; entered in degrees.
            ANSTAR = 0.0 by default.

        ----------------------------------------------------------------------------------------------
        All data items on the third record are read for both two- and three-winding transformers:

        WINDV1: When CW is 1, WINDV1 is the Winding 1 off-nominal turns ratio in pu of Winding 1
            bus base voltage; WINDV1 = 1.0 by default.
            When CW is 2, WINDV1 is the actual Winding 1 voltage in kV; WINDV1 is equal to
            the base voltage of bus I by default.
            When CW is 3, WINDV1 is the Winding 1 off-nominal turns ratio in pu of nominal
            Winding 1 voltage, NOMV1; WINDV1 = 1.0 by default.
        NOMV1 The nominal (rated) Winding 1 voltage base in kV, or zero to indicate that nominal
            Winding 1 voltage is assumed to be identical to the base voltage of bus I. NOMV1 is
            used in converting magnetizing data between physical units and per unit admittance
            values when CM is 2. NOMV1 is used in converting tap ratio data between values in
            per unit of nominal Winding 1 voltage and values in per unit of Winding 1 bus base
            voltage when CW is 3. NOMV1 = 0.0 by default.
        ANG1 The winding one phase shift angle in degrees. For a two-winding transformer,
            ANG1 is positive when the winding one bus voltage leads the winding two bus
            voltage; for a three-winding transformer, ANG1 is positive when the winding one
            bus voltage leads the T (or star) point bus voltage. ANG1 must be greater than -
            180.0o and less than or equal to +180.0o. ANG1 = 0.0 by default.
        RATA1, RATB1, RATC1: Winding 1’s three three-phase ratings, entered in either MVA or current expressed
            as MVA, according to the value specified for XFRRAT specified on the first data
            record (refer to Case Identification Data). RATA1 = 0.0, RATB1 = 0.0 and
            RATC1 = 0.0 (bypass loading limit check for this transformer winding) by default.
        COD1 The transformer control mode for automatic adjustments of the Winding 1 tap or
            phase shift angle during power flow solutions:
                0 for no control (fixed tap and fixed phase shift)
                ±1  for voltage control
                ±2  for reactive power flow control
                ±3  for active power flow control
                ±4  for control of a dc line quantity (valid only for two-winding  transformers)
                ±5  for asymmetric active power flow control.
            If the control mode is entered as a positive number, automatic adjustment of this
            transformer winding is enabled when the corresponding adjustment is activated
            during power flow solutions; a negative control mode suppresses the automatic
            adjustment of this transformer winding. COD1 = 0 by default.

        CONT1: The bus number, or extended bus name enclosed in single quotes (refer to
            Extended Bus Names), of the bus for which voltage is to be controlled by the trans-
            former turns ratio adjustment option of the power flow solution activities when
            COD1 is 1. CONT1 should be non-zero only for voltage controlling transformer
            windings.
            CONT1 may specify a bus other than I, J, or K; in this case, the sign of CONT1
            defines the location of the controlled bus relative to the transformer winding. If
            CONT1 is entered as a positive number, or a quoted extended bus name, the ratio
            is adjusted as if bus CONT1 is on the Winding 2 or Winding 3 side of the trans-
            former; if CONT1 is entered as a negative number, or a quoted extended bus name
            with a minus sign preceding the first character, the ratio is adjusted as if bus
            |CONT1| is on the Winding 1 side of the transformer. CONT1 = 0 by default.
        RMA1, RMI1:  When |COD1| is 1, 2 or 3, the upper and lower limits, respectively, of one of the
            following:
            • Off-nominal turns ratio in pu of Winding 1 bus base voltage when |COD1| is
            1 or 2 and CW is 1; RMA1 = 1.1 and RMI1 = 0.9 by default.
            • Actual Winding 1 vo ltage in kV when |COD1| is 1 o r 2 and CW is 2 . No
            default is allowed.
            • Off-nominal turns ratio in pu of nominal Winding 1 voltage (NOMV1) when
            |COD1| is 1 or 2 and CW is 3; RMA1 = 1.1 and RMI1 = 0.9 by default.
            • Phase shift angle in degrees when |COD1| is 3. No default is allowed.
            Not used when |COD1| is 0 or 4; RMA1 = 1.1 and RMI1 = 0.9 by default.
        VMA1, VMI1:  When |COD1| is 1, 2 or 3, the upper and lower limits, respectively, of one of the
            following:
            • Voltage at the controlled bus (bus |CONT1|) in pu when |COD1| is 1. 
            VMA1 = 1.1 and VMI1 = 0.9 by default.
            • Reactive power flow into the transformer at the Winding 1 bus end in Mvar
            when |COD1| is 2. No default is allowed.
            • Active power flow into the transformer at the Winding 1 bus end in MW when
            |COD1| is 3. No default is allowed.
            Not used when |COD1| is 0 or 4; VMA1 = 1.1 and VMI1 = 0.9 by default.
        NTP1: The number of tap positions available; used when COD1 is 1 or 2. NTP1 must be
            between 2 and 9999. NTP1 = 33 by default.
        TAB1: The number of a transformer impedance correction table if this transformer
            winding’s impedance is to be a function of either off-nominal turns ratio or phase
            shift angle (refer to Transformer Impedance Correction Tables), or 0 if no trans-
            former impedance correction is to be applied to this transformer winding. TAB1 = 0
            by default.
        CR1, CX1: The load drop compensation impedance for voltage controlling transformers
            entered in pu on system base quantities; used when COD1 is 1. CR1 + j CX1 = 0.0
            by default.
        CNXA1: Winding connection angle in degrees; used when COD1 is 5. There are no restrictions
            on the value specified for CNXA1; if it is outside of the range from -90.0 to
            +90.0, CNXA1 is normalized to within this range. CNXA1 = 0.0 by default.

        ----------------------------------------------------------------------------------------------
        The first two data items on the fourth record are read for both two- and three-winding transformers;
        the remaining data items are used only for three-winding transformers:

        WINDV2:  When CW is 1, WINDV2 is the Winding 2 off-nominal turns ratio in pu of Winding 2
            bus base voltage; WINDV2 = 1.0 by default.
            When CW is 2, WINDV2 is the actual Winding 2 voltage in kV; WINDV2 is equal to
            the base voltage of bus J by default.
            When CW is 3, WINDV2 is the Winding 2 off-nominal turns ratio in pu of nominal
            Winding 2 voltage, NOMV2; WINDV2 = 1.0 by default.
        NOMV2 The nominal (rated) Winding 2 voltage base in kV, or zero to indicate that nominal
            Winding 2 voltage is assumed to be identical to the base voltage of bus J. NOMV2
            is used in converting tap ratio data between values in per unit of nominal Winding 2
            voltage and values in per unit of Winding 2 bus base voltage when CW is 3.
            NOMV2 = 0.0 by default.
        ANG2 The winding two phase shift angle in degrees. ANG2 is ignored for a two-winding
            transformer. For a three-winding transformer, ANG2 is positive when the winding
            two bus voltage leads the T (or star) point bus voltage. ANG2 must be greater than
            -180.0o and less than or equal to +180.0o. ANG2 = 0.0 by default.
        RATA2, RATB2, RATC2: Winding 2’s three three-phase ratings, entered in either MVA or current expressed
            as MVA, according to the value specified for XFRRAT specified on the first data
            record (refer to Case Identification Data). RATA2 = 0.0, RATB2 = 0.0 and
            RATC2 = 0.0 (bypass loading limit check for this transformer winding) by default.
        COD2: The transformer control mode for automatic adjustments of the Winding 2 tap or
            phase shift angle during power flow solutions:
                0    for no control (fixed tap and fixed phase shift)
                ±1   for voltage control
                ±2   for reactive power flow control
                ±3   for active power flow control
                ±5   for asymmetric active power flow control
            If the control mode is entered as a positive number, automatic adjustment of this
            transformer winding is enabled when the corresponding adjustment is activated
            during power flow solutions; a negative control mode suppresses the automatic
            adjustment of this transformer winding. COD2 = 0 by default.
        CONT2:  The bus number, or extended bus name enclosed in single quotes (refer to
            Extended Bus Names), of the bus for which voltage is to be controlled by the trans-
            former turns ratio adjustment option of the power flow solution activities when
            COD2 is 1. CONT2 should be non-zero only for voltage controlling transformer
            windings.
            CONT2 may specify a bus other than I, J, or K; in this case, the sign of CONT2
            defines the location of the controlled bus relative to the transformer winding. If
            CONT2 is entered as a positive number, or a quoted extended bus name, the ratio
            is adjusted as if bus CONT2 is on the Winding 1 or Winding 3 side of the trans-
            former; if CONT2 is entered as a negative number, or a quoted extended bus name
            with a minus sign preceding the first character, the ratio is adjusted as if bus
            |CONT2| is on the Winding 2 side of the transformer. CONT2 = 0 by default.

        RMA2, RMI2:  When |COD2| is 1, 2 or 3, the upper and lower limits, respectively, of one of the
            following:
            • Off-nominal turns ratio in pu of Winding 2 bus base voltage when |COD2| is
            1 or 2 and CW is 1; RMA2 = 1.1 and RMI2 = 0.9 by default.
            • Actual Winding 2 voltage in kV when |COD2| is 1 or 2 and CW is 2. No default
            is allowed.
            • Off-nominal turns ratio in pu o f nominal Winding 2 voltage (NOMV2) when
            |COD2| is 1 or 2 and CW is 3; RMA2 = 1.1 and RMI2 = 0.9 by default.
            • Phase shift angle in degrees when |COD2| is 3. No default is allowed.
            Not used when |COD2| is 0; RMA2 = 1.1 and RMI2 = 0.9 by default.
        VMA2, VMI2:   When |COD2| is 1, 2 or 3, the upper and lower limits, respectively, of one of the
            following:
            • Voltage at the controlled bus (bus |CONT2|) in pu when |COD2| is 1.
            VMA2 = 1.1 and VMI2 = 0.9 by default.
            • Reactive power flow into the transformer at the Winding 2 bus end in Mvar
            when |COD2| is 2. No default is allowed.
            • Active power flow into the transformer at the Winding 2 bus end in MW when
            |COD2| is 3. No default is allowed.
            Not used when |COD2| is 0; VMA2 = 1.1 and VMI2 = 0.9 by default.
        NTP2 The number of tap positions available; used when COD2 is 1 or 2. NTP2 must be
            between 2 and 9999. NTP2 = 33 by default.
        TAB2 The number of a transformer impedance correction table if this transformer
            winding’s impedance is to be a function of either off-nominal turns ratio or phase
            shift angle (refer to Transformer Impedance Correction Tables), or 0 if no trans-
            former impedance correction is to be applied to this transformer winding. TAB2 = 0
            by default.
        CR2, CX2 The load drop compensation impedance for voltage controlling transformers
            entered in pu on system base quantities; used when COD2 is 1. CR2 + j CX2 = 0.0
            by default.
        CNXA2 Winding connection angle in degrees; used when COD2 is 5. There are no restrictions
            on the value specified for CNXA2; if it is outside of the range from -90.0 to
            +90.0, CNXA2 is normalized to within this range. CNXA2 = 0.0 by default.
            The fifth data record is specified only for three-winding transformers:
        WINDV3: When CW is 1, WINDV3 is the Winding 3 off-nominal turns ratio in pu of Winding 3
            bus base voltage; WINDV3 = 1.0 by default.
            When CW is 2, WINDV3 is the actual Winding 3 voltage in kV; WINDV3 is equal to
            the base voltage of bus K by default.
            When CW is 3, WINDV3 is the Winding 3 off-nominal turns ratio in pu of nominal
            Winding 3 voltage, NOMV3; WINDV3 = 1.0 by default.

        NOMV3 The nominal (rated) Winding 3 voltage base in kV, or zero to indicate that nominal
            Winding 3 voltage is assumed to be identical to the base voltage of bus K. NOMV3
            is used in converting tap ratio data between values in per unit of nominal Winding 3
            voltage and values in per unit of Winding 3 bus base voltage when CW is 3. NOMV3
            = 0.0 by default.
        ANG3 The winding three phase shift angle in degrees. ANG3 is positive when the winding
            three bus voltage leads the T (or star) point bus voltage. ANG3 must be greater
            than -180.0o and less than or equal to +180.0o. ANG3 = 0.0 by default.
        RATA3, RATB3, RATC3 Winding 3’s three three-phase ratings, entered in either MVA or current expressed
            as MVA, according to the value specified for XFRRAT specified on the first data
            record (refer to Case Identification Data). RATA3 = 0.0, RATB3 = 0.0 and
            RATC3 = 0.0 (bypass loading limit check for this transformer winding) by default.
        COD3 The transformer control mode for automatic adjustments of the Winding 3 tap or
            phase shift angle during power flow solutions:
            0    for no control (fixed tap and fixed phase shift)
            ±1   for voltage control
            ±2   for reactive power flow control
            ±3   for active power flow control
            ±5   for asymmetric active power flow control.

            If the control mode is entered as a positive number, automatic adjustment of this
            transformer winding is enabled when the corresponding adjustment is activated
            during power flow solutions; a negative control mode suppresses the automatic
            adjustment of this transformer winding. COD3 = 0 by default.
        CONT3:   The bus number, or extended bus name enclosed in single quotes (refer to
            Extended Bus Names), of the bus for which voltage is to be controlled by the trans-
            former turns ratio adjustment option of the power flow solution activities when
            COD3 is 1. CONT3 should be non-zero only for voltage controlling transformer
            windings.
            CONT3 may specify a bus other than I, J, or K; in this case, the sign of CONT3
            defines the location of the controlled bus relative to the transformer winding. If
            CONT3 is entered as a positive number, or a quoted extended bus name, the ratio
            is adjusted as if bus CONT3 is on the Winding 1 or Winding 2 side of the trans-
            former; if CONT3 is entered as a negative number, or a quoted extended bus name
            with a minus sign preceding the first character, the ratio is adjusted as if bus
            |CONT3| is on the Winding 3 side of the transformer. CONT3 = 0 by default.
        RMA3, RMI3:   When |COD3| is 1, 2 or 3, the upper and lower limits, respectively, of one of the
            following:
            • Off-nominal turns ratio in pu of Winding 3 bus base voltage when |COD3| is
            1 or 2 and CW is 1; RMA3 = 1.1 and RMI3 = 0.9 by default.
            • Actual Winding 3 voltage in kV when |COD3| is 1 or 2 and CW is 2. No default
            is allowed.
            • Off-nominal turns ratio in pu o f nominal Winding 3 voltage (NOMV3) when
            |COD3| is 1 or 2 and CW is 3; RMA3 = 1.1 and RMI3 = 0.9 by default.
            • Phase shift angle in degrees when |COD3| is 3. No default is allowed.
            Not used when |COD3| is 0; RMA3 = 1.1 and RMI3 = 0.9 by default.

        VMA3, VMI3:  When |COD3| is 1, 2 or 3, the upper and lower limits, respectively, of one of the
            following:
            • Voltage at the co ntrolled b us (bus |C ONT3|) in pu when |COD3| is 1.
            VMA3 = 1.1 and VMI3 = 0.9 by default.
            • Reactive power flow into the transformer at the Winding 3 bus end in Mvar
            when |COD3| is 2. No default is allowed.
            • Active power flow into the transformer at the Winding 3 bus end in MW when
            |COD3| is 3. No default is allowed.
            Not used when |COD3| is 0; VMA3 = 1.1 and VMI3 = 0.9 by default.
        NTP3 The number of tap positions available; used when COD3 is 1 or 2. NTP3 must be
            between 2 and 9999. NTP3 = 33 by default.
        TAB3 The number of a transformer impedance correction table if this transformer
            winding’s impedance is to be a function of either off-nominal turns ratio or phase
            shift angle (refer to Transformer Impedance Correction Tables), or 0 if no trans-
            former impedance correction is to be applied to this transformer winding. TAB3 = 0
            by default.
        CR3, CX3 The load drop compensation impedance for voltage controlling transformers
            entered in pu on system base quantities; used when COD3 is 1. CR3 + j CX3 = 0.0
            by default.
        CNXA3 Winding connection angle in degrees; used when COD3 is 5. There are no restrictions
            on the value specified for CNXA3; if it is outside of the range from -90.0 to
            +90.0, CNXA3 is normalized to within this range. CNXA3 = 0.0 by default.

        default.
            Args:
        data:
        version:
        """

        self.windings = 0

        if version == 33:

            # Line 1: for both types

            if len(data[0]) == 20:

                n = len(data[0])
                dta = zeros(21, dtype=object)
                dta[0:n] = data[0]

                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT, self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4, \
                 self.VECGRP = dta

            elif len(data[0]) == 18:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT, self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.VECGRP = data[0]
            elif len(data[0]) == 16:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT, self.O1, self.F1, self.O2, self.F2, self.VECGRP = data[0]
            elif len(data[0]) == 14:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT, self.O1, self.F1, self.VECGRP = data[0]
            elif len(data[0]) == 12:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT, self.VECGRP = data[0]

            # line 2
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
            dta = zeros(17, dtype=object)
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

        elif version == 32:

            '''
            I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,’NAME’,STAT,O1,F1,...,O4,F4

            R1-2,X1-2,SBASE1-2,R2-3,X2-3,SBASE2-3,R3-1,X3-1,SBASE3-1,VMSTAR,ANSTAR

            WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD1,CONT1,RMA1,RMI1,VMA1,VMI1,NTP1,TAB1,CR1,CX1,CNXA1

            WINDV2,NOMV2,ANG2,RATA2,RATB2,RATC2,COD2,CONT2,RMA2,RMI2,VMA2,VMI2,NTP2,TAB2,CR2,CX2,CNXA2
            WINDV3,NOMV3,ANG3,RATA3,RATB3,RATC3,COD3,CONT3,RMA3,RMI3,VMA3,VMI3,NTP3,TAB3,CR3,CX3,CNXA3
            '''

            # Line 1: for both types

            n = len(data[0])
            dta = zeros(20, dtype=object)
            dta[0:n] = data[0]

            # if len(data[0]) == 20:
            self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
             self.NAME, self.STAT, self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4 = dta

            # elif len(data[0]) == 18:
            #     self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
            #      self.NAME, self.STAT, self.O1, self.F1, self.O2, self.F2, self.O3, self.F3 = data[0]
            # elif len(data[0]) == 16:
            #     self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
            #      self.NAME, self.STAT, self.O1, self.F1, self.O2, self.F2 = data[0]
            # elif len(data[0]) == 14:
            #     self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
            #      self.NAME, self.STAT, self.O1, self.F1 = data[0]
            # elif len(data[0]) == 12:
            #     self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
            #      self.NAME, self.STAT = data[0]

            # line 2
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
            dta = zeros(17, dtype=object)
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

            # Line 1: for both types
            if len(data[0]) == 20:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT, self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4 = data[0]
            elif len(data[0]) == 18:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT, self.O1, self.F1, self.O2, self.F2, self.O3, self.F3 = data[0]
            elif len(data[0]) == 16:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT, self.O1, self.F1, self.O2, self.F2 = data[0]
            elif len(data[0]) == 14:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT, self.O1, self.F1 = data[0]
            elif len(data[0]) == 12:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT = data[0]

            # line 2
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

    def get_object(self, psse_bus_dict):
        """
        Return GridCal branch object
        Args:
            psse_bus_dict: Dictionary that relates PSSe bus indices with GridCal Bus objects

        Returns:
            Gridcal Branch object
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

        if self.windings == 2:
            bus_from = psse_bus_dict[self.I]
            bus_to = psse_bus_dict[self.J]

            if self.CZ == 1:
                r = self.R1_2
                x = self.X1_2
                g = self.MAG1
                b = self.MAG2

            else:
                r = self.R1_2
                x = self.X1_2
                g = self.MAG1
                b = self.MAG2

                warn('Transformer impedance is not in p.u.')

            object = Branch(bus_from=bus_from, bus_to=bus_to,
                            name=self.NAME.replace("'", "").strip(),
                            r=r,
                            x=x,
                            g=g,
                            b=b,
                            rate=max(self.RATA1, self.RATB1, self.RATC1),
                            tap=1,
                            shift_angle=0,
                            active=True,
                            mttf=0,
                            mttr=0,
                            is_transformer=True)

            return [object]

        elif self.windings == 3:

            bus_1 = psse_bus_dict[self.I]
            bus_2 = psse_bus_dict[self.J]
            bus_3 = psse_bus_dict[self.k]

            r = self.R1_2
            x = self.X1_2
            g = self.MAG1
            b = self.MAG2

            object1 = Branch(bus_from=bus_1, bus_to=bus_2,
                             name=self.NAME.replace("'", "").strip() + '_1_2',
                             r=r,
                             x=x,
                             g=g,
                             b=b,
                             rate=max(self.RATA1, self.RATB1, self.RATC1),
                             tap=1,
                             shift_angle=0,
                             active=True,
                             mttf=0,
                             mttr=0,
                             is_transformer=True)

            r = self.R2_3
            x = self.X2_3
            g = self.MAG1
            b = self.MAG2

            object2 = Branch(bus_from=bus_2, bus_to=bus_3,
                             name=self.NAME.replace("'", "").strip() + '_2_3',
                             r=r,
                             x=x,
                             g=g,
                             b=b,
                             rate=max(self.RATA1, self.RATB1, self.RATC1),
                             tap=1,
                             shift_angle=0,
                             active=True,
                             mttf=0,
                             mttr=0,
                             is_transformer=True)

            r = self.R3_1
            x = self.X3_1
            g = self.MAG1
            b = self.MAG2

            object3 = Branch(bus_from=bus_3, bus_to=bus_1,
                             name=self.NAME.replace("'", "").strip() + '_3_1',
                             r=r,
                             x=x,
                             g=g,
                             b=b,
                             rate=max(self.RATA1, self.RATB1, self.RATC1),
                             tap=1,
                             shift_angle=0,
                             active=True,
                             mttf=0,
                             mttr=0,
                             is_transformer=True)

            return [object1, object2, object3]


def interpret_line(line, splitter=','):
    """
    Split text into arguments and parse each of them to an appropriate format (int, float or string)
    Args:
        line:
        splitter:
    Returns: list of arguments
    """
    parsed = list()
    elms = line.split(splitter)

    for elm in elms:
        try:
            # try int
            el = int(elm)
        except Exception as ex1:
            try:
                # try float
                el = float(elm)
            except Exception as ex2:
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
        self.versions = [33, 32, 30]

        self.pss_grid = self.parse_psse(file_name)

        self.circuit = self.pss_grid.get_circuit()

    def parse_psse(self, file_name):
        """
        Parser implemented according to:
            - POM section 5.2.1 (v.33)
            - POM section 5.2.1 (v.32)

        Args:
            file_name:

        Returns:

        """
        print('Parsing ', file_name)

        # make a guess of the file encoding
        detection = chardet.detect(open(file_name, "rb").read())

        # open the text file into a variable
        with open(file_name, 'r', encoding=detection['encoding']) as my_file:
            txt = my_file.read()

        # split the text file into sections
        sections = txt.split(' /')

        # header -> new grid
        grid = PSSeGrid(interpret_line(sections[0]))

        if grid.REV not in self.versions:
            raise Exception('The PSSe version is not compatible. Compatible versions are:', self.versions)
        else:
            version = grid.REV

        meta_data = list()
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
        # 14: Interarea Transfer Data
        # 15: Owner Data
        # 16: FACTS Device Data
        # 17: Switched Shunt Data
        # 18: GNE Device Data
        # 19: Induction Machine Data
        # 20: Q Record

        meta_data.append([1, grid.buses, PSSeBus, 1])
        meta_data.append([2, grid.loads, PSSeLoad, 1])
        meta_data.append([3, grid.shunts, PSSeShunt, 1])
        meta_data.append([4, grid.generators, PSSeGenerator, 1])
        meta_data.append([5, grid.branches, PSSeBranch, 1])
        meta_data.append([6, grid.transformers, PSSeTransformer, 4])

        for section_idx, objects_list, ObjectT, lines_per_object in meta_data:

            # split the section lines by object declaration: '\n  ' delimits each object start.
            lines = sections[section_idx].split('\n  ')

            # this removes the useless header
            lines.pop(0)

            # iterate ove the object's lines
            for line in lines:
                # pick the line that matches the object and split it by line returns \n
                object_lines = line.split('\n')

                # interpret each line of the object and store into data
                # data is a vector of vectors with data definitions
                # for the buses, branches, loads etc. data contains 1 vector,
                # for the transformers data contains 4 vectors
                data = [interpret_line(object_lines[k]) for k in range(lines_per_object)]

                # pass the data to the according object to assign it to the matching variables
                objects_list.append(ObjectT(data, version))

        return grid


if __name__ == '__main__':
    # fname = 'raw/ExampleGrid_PSSEver32.raw'
    fname = 'raw/ExampleGrid_PSSEver33.raw'

    parser = PSSeParser(fname)
    pass