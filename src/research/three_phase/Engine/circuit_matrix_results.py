

class CircuitMatrixResults:

    def __init__(self):
        """
        Class to store grid calculated values from Power flow ans State estimation
        """

        # node voltages vector (p.u.)
        self.V = None

        # node power injections (p.u.)
        self.Sbus = None

        # branch power injected at the from side (p.u.)
        self.Sf = None

        # branch power injected at the to side (p.u.)
        self.St = None

        # branch current injected at the from side (p.u.)
        self.If = None

        # branch current injected at the to side (p.u.)
        self.It = None

        # power flowing through the branch (p.u.)
        self.Sbranch = None

        # current flowing through the branch (p.u.)
        self.Ibranch = None

        # losses of the branch (p.u.)
        self.losses = None

        # did this solution converge?
        self.converged = False

        # power mismatch of this solution (p.u.)
        self.error = None
