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
