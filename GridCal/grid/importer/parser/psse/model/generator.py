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
                                     Qmin=-self.QB,
                                     Qmax=self.QT,
                                     Snom=self.MBASE,
                                     power_prof=None,
                                     vset_prof=None,
                                     active=bool(self.STAT))

        return object
