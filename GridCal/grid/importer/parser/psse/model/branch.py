from _warnings import warn


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
                        mttr=0)
        return object
