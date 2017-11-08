class VoltageCollapseInput:
    def __init__(self, Sbase, Vbase, Starget):
        """
        VoltageCollapseInput constructor
        @param Sbase: Initial power array
        @param Vbase: Initial voltage array
        @param Starget: Final power array
        """
        self.Sbase = Sbase

        self.Starget = Starget

        self.Vbase = Vbase
