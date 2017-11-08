from GridCal.grid.model.bus import Bus
from GridCal.grid.model.node_type import NodeType


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
            self.I, self.NAME, self.BASKV, self.IDE, self.AREA, self.ZONE, \
             self.OWNER, self.VM, self.VA, self.NVHI, self.NVLO, self.EVHI, self.EVLO = data[0]

            # create bus
            self.bus = Bus(name=self.NAME, vnom=self.BASKV, vmin=self.EVLO, vmax=self.EVHI, xpos=0, ypos=0, active=True)

        elif version == 32:

            self.I, self.NAME, self.BASKV, self.IDE, self.AREA, self.ZONE, self.OWNER, self.VM, self.VA = data[0]

            # create bus
            self.bus = Bus(name=self.NAME, vnom=self.BASKV, vmin=0.9, vmax=1.1, xpos=0, ypos=0,
                           active=True)

        elif version == 30:

            self.I, self.NAME, self.BASKV, self.IDE, self.GL, self.BL, \
             self.AREA, self.ZONE, self.VM, self.VA, self.OWNER = data[0]

            # create bus
            self.bus = Bus(name=self.NAME, vnom=self.BASKV, vmin=0.9, vmax=1.1, xpos=0, ypos=0,
                           active=True)

        # set type
        self.bus.type = bustype[self.IDE]

        if self.bus.type == NodeType.REF:
            self.bus.is_slack = True

        self.bus.name = self.bus.name.replace("'", "").strip()
