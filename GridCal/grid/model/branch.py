from GridCal.grid.model.bus import Bus
from GridCal.grid.model.circuit import TransformerType


class Branch:

    def __init__(self, bus_from: Bus, bus_to: Bus, name='Branch', r=1e-20, x=1e-20, g=1e-20, b=1e-20,
                 rate=1, tap=1, shift_angle=0, active=True, mttf=0, mttr=0):
        """
        Branch model constructor
        @param bus_from: Bus Object
        @param bus_to: Bus Object
        @param name: name of the branch
        @param zserie: branch series impedance (complex)
        @param yshunt: branch shunt admittance (complex)
        @param rate: branch rate in MVA
        @param tap: tap module
        @param shift_angle: tap shift angle in radians
        @param mttf: Mean time to failure
        @param mttr: Mean time to repair
        """

        self.name = name

        self.type_name = 'Branch'

        self.properties_with_profile = None

        self.bus_from = bus_from
        self.bus_to = bus_to

        self.active = active

        # self.z_series = zserie  # R + jX
        # self.y_shunt = yshunt  # G + jB

        self.R = r
        self.X = x
        self.G = g
        self.B = b

        if tap != 0:
            self.tap_module = tap
        else:
            self.tap_module = 1

        self.angle = shift_angle

        self.rate = rate

        self.mttf = mttf

        self.mttr = mttr

        self.type_obj = None

        self.edit_headers = ['name', 'bus_from', 'bus_to', 'active', 'rate', 'mttf', 'mttr', 'R', 'X', 'G', 'B', 'tap_module', 'angle']

        self.units = ['', '', '', '', 'MVA', 'h', 'h', 'p.u.', 'p.u.', 'p.u.', 'p.u.',
                             'p.u.', 'rad']

        self.edit_types = {'name': str,
                           'bus_from': None,
                           'bus_to': None,
                           'active': bool,
                           'rate': float,
                           'mttf': float,
                           'mttr': float,
                           'R': float,
                           'X': float,
                           'G': float,
                           'B': float,
                           'tap_module': float,
                           'angle': float}

    def copy(self, bus_dict=None):
        """
        Returns a copy of the branch
        @return: A new  with the same content as this
        """

        if bus_dict is None:
            f = self.bus_from
            t = self.bus_to
        else:
            f = bus_dict[self.bus_from]
            t = bus_dict[self.bus_to]

        # z_series = complex(self.R, self.X)
        # y_shunt = complex(self.G, self.B)
        b = Branch(bus_from=f,
                   bus_to=t,
                   name=self.name,
                   r=self.R,
                   x=self.X,
                   g=self.G,
                   b=self.B,
                   rate=self.rate,
                   tap=self.tap_module,
                   shift_angle=self.angle,
                   active=self.active,
                   mttf=self.mttf,
                   mttr=self.mttr)

        return b

    def get_tap(self):
        """
        Get the complex tap value
        @return:
        """
        return self.tap_module * exp(-1j * self.angle)

    def apply_to(self, Ybus, Yseries, Yshunt, Yf, Yt, B1, B2, i, f, t):
        """

        Modify the circuit admittance matrices with the admittances of this branch
        @param Ybus: Complete Admittance matrix
        @param Yseries: Admittance matrix of the series elements
        @param Yshunt: Admittance matrix of the shunt elements
        @param Yf: Admittance matrix of the branches with the from buses
        @param Yt: Admittance matrix of the branches with the to buses
        @param B1: Jacobian 1 for the fast-decoupled power flow
        @param B1: Jacobian 2 for the fast-decoupled power flow
        @param i: index of the branch in the circuit
        @return: Nothing, the inputs are implicitly modified
        """
        z_series = complex(self.R, self.X)
        y_shunt = complex(self.G, self.B)
        tap = self.get_tap()
        Ysh = y_shunt / 2
        if abs(z_series) > 0:
            Ys = 1 / z_series
        else:
            raise ValueError("The impedance at " + self.name + " is zero")

        Ytt = Ys + Ysh
        Yff = Ytt / (tap * conj(tap))
        Yft = - Ys / conj(tap)
        Ytf = - Ys / tap

        Yff_sh = Ysh
        Ytt_sh = Yff_sh / (tap * conj(tap))

        # Full admittance matrix
        Ybus[f, f] += Yff
        Ybus[f, t] += Yft
        Ybus[t, f] += Ytf
        Ybus[t, t] += Ytt

        # Y-from and Y-to for the lines power flow computation
        Yf[i, f] += Yff
        Yf[i, t] += Yft
        Yt[i, f] += Ytf
        Yt[i, t] += Ytt

        # Y shunt for HELM
        Yshunt[f] += Yff_sh
        Yshunt[t] += Ytt_sh

        # Y series for HELM
        Yseries[f, f] += Ys / (tap * conj(tap))
        Yseries[f, t] += Yft
        Yseries[t, f] += Ytf
        Yseries[t, t] += Ys

        # B1 for FDPF (no shunts, no resistance, no tap module)
        z_series = complex(0, self.X)
        y_shunt = complex(0, 0)
        tap = exp(-1j * self.angle)  # self.tap_module * exp(-1j * self.angle)
        Ysh = y_shunt / 2
        Ys = 1 / z_series

        Ytt = Ys + Ysh
        Yff = Ytt / (tap * conj(tap))
        Yft = - Ys / conj(tap)
        Ytf = - Ys / tap

        B1[f, f] -= Yff.imag
        B1[f, t] -= Yft.imag
        B1[t, f] -= Ytf.imag
        B1[t, t] -= Ytt.imag

        # B2 for FDPF (with shunts, only the tap module)
        z_series = complex(self.R, self.X)
        y_shunt = complex(self.G, self.B)
        tap = self.tap_module  # self.tap_module * exp(-1j * self.angle)
        Ysh = y_shunt / 2
        Ys = 1 / z_series

        Ytt = Ys + Ysh
        Yff = Ytt / (tap * conj(tap))
        Yft = - Ys / conj(tap)
        Ytf = - Ys / tap

        B2[f, f] -= Yff.imag
        B2[f, t] -= Yft.imag
        B2[t, f] -= Ytf.imag
        B2[t, t] -= Ytt.imag

        return f, t

    def apply_transformer_type(self, obj: TransformerType):
        """
        Apply a transformer type definition to this object
        Args:
            obj:

        Returns:

        """
        leakage_impedance, magnetizing_impedance = obj.get_impedances()

        z_series = magnetizing_impedance
        y_shunt = 1 / leakage_impedance

        self.R = z_series.real
        self.X = z_series.imag
        self.G = y_shunt.real
        self.B = y_shunt.imag

        self.type_obj = obj

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        return [self.name, self.bus_from.name, self.bus_to.name, self.active, self.rate, self.mttf, self.mttr,
                self.R, self.X, self.G, self.B, self.tap_module, self.angle]
