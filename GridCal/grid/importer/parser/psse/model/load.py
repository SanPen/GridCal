from _warnings import warn

from GridCal.grid.model.bus import Bus
from GridCal.grid.model.load import Load


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
            self.I, self.ID, self.STATUS, self.AREA, self.ZONE, self.PL, self.QL, \
             self.IP, self.IQ, self.YP, self.YQ, self.OWNER, self.SCALE, self.INTRPT = data[0]

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
