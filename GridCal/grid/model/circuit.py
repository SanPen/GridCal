import os
from datetime import datetime, timedelta
from warnings import warn

from matplotlib import pyplot as plt
from numpy import ones, nan, r_, delete, argwhere, c_

from GridCal.grid.model.node_type import NodeType
from GridCal.grid.statistics.statistics import CDF, load_from_xls
from GridCal.grid.calculate.power_flow.power_flow import PowerFlowInput


class TransformerType:

    def __init__(self, HV_nominal_voltage, LV_nominal_voltage, Nominal_power, Copper_losses, Iron_losses,
                 No_load_current, Short_circuit_voltage, GR_hv1, GX_hv1, name='TransformerType'):
        """
        Constructor
        @param HV_nominal_voltage: High voltage side nominal voltage (kV)
        @param LV_nominal_voltage: Low voltage side nominal voltage (kV)
        @param Nominal_power: Transformer nominal power (MVA)
        @param Copper_losses: Copper losses (kW)
        @param Iron_losses: Iron Losses (kW)
        @param No_load_current: No load current (%)
        @param Short_circuit_voltage: Short circuit voltage (%)
        @param GR_hv1:
        @param GX_hv1:
        """

        self.name = name

        self.type_name = 'TransformerType'

        self.properties_with_profile = None

        self.HV_nominal_voltage = HV_nominal_voltage

        self.LV_nominal_voltage = LV_nominal_voltage

        self.Nominal_power = Nominal_power

        self.Copper_losses = Copper_losses

        self.Iron_losses = Iron_losses

        self.No_load_current = No_load_current

        self.Short_circuit_voltage = Short_circuit_voltage

        self.GR_hv1 = GR_hv1

        self.GX_hv1 = GX_hv1

    def get_impedances(self):
        """
        Compute the branch parameters of a transformer from the short circuit
        test values
        @return:
            leakage_impedance: Series impedance
            magnetizing_impedance: Shunt impedance
        """
        Uhv = self.HV_nominal_voltage

        Ulv = self.LV_nominal_voltage

        Sn = self.Nominal_power

        Pcu = self.Copper_losses

        Pfe = self.Iron_losses

        I0 = self.No_load_current

        Usc = self.Short_circuit_voltage

        # Nominal impedance HV (Ohm)
        Zn_hv = Uhv * Uhv / Sn

        # Nominal impedance LV (Ohm)
        Zn_lv = Ulv * Ulv / Sn

        # Short circuit impedance (p.u.)
        zsc = Usc / 100

        # Short circuit resistance (p.u.)
        rsc = (Pcu / 1000) / Sn

        # Short circuit reactance (p.u.)
        xsc = sqrt(zsc * zsc - rsc * rsc)

        # HV resistance (p.u.)
        rcu_hv = rsc * self.GR_hv1

        # LV resistance (p.u.)
        rcu_lv = rsc * (1 - self.GR_hv1)

        # HV shunt reactance (p.u.)
        xs_hv = xsc * self.GX_hv1

        # LV shunt reactance (p.u.)
        xs_lv = xsc * (1 - self.GX_hv1)

        # Shunt resistance (p.u.)
        rfe = Sn / (Pfe / 1000)

        # Magnetization impedance (p.u.)
        zm = 1 / (I0 / 100)

        # Magnetization reactance (p.u.)
        if rfe > zm:
            xm = 1 / sqrt(1 / (zm * zm) - 1 / (rfe * rfe))
        else:
            xm = 0  # the square root cannot be computed

        # Calculated parameters in per unit
        leakage_impedance = rsc + 1j * xsc
        magnetizing_impedance = rfe + 1j * xm

        return leakage_impedance, magnetizing_impedance


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


class Load:

    def __init__(self, name='Load', impedance=complex(0, 0), current=complex(0, 0), power=complex(0, 0),
                 impedance_prof=None, current_prof=None, power_prof=None, active=True):
        """
        Load model constructor
        This model implements the so-called ZIP model
        composed of an impedance value, a current value and a power value
        @param impedance: Impedance complex (Ohm)
        @param current: Current complex (kA)
        @param power: Power complex (MVA)
        """

        self.name = name

        self.active = active

        self.type_name = 'Load'

        self.properties_with_profile = (['S', 'I', 'Z'], [complex, complex, complex])

        self.graphic_obj = None

        # The bus this element is attached to: Not necessary for calculations
        self.bus = None

        # Impedance (Ohm)
        # Z * I = V -> Ohm * kA = kV
        self.Z = impedance

        # Current (kA)
        self.I = current

        # Power (MVA)
        # MVA = kV * kA
        self.S = power

        # impedances profile for this load
        self.Zprof = impedance_prof

        # Current profiles for this load
        self.Iprof = current_prof

        # power profile for this load
        self.Sprof = power_prof

        self.graphic_obj = None

        self.edit_headers = ['name', 'bus', 'Z', 'I', 'S']

        self.units = ['', '', 'MVA', 'MVA', 'MVA']  # ['', '', 'Ohm', 'kA', 'MVA']

        self.edit_types = {'name': str, 'bus': None, 'Z': complex, 'I': complex, 'S': complex}

    def create_profiles(self, index):
        """
        Create the load object default profiles
        Args:
            index:
            steps:

        Returns:

        """

        self.create_S_profile(index)
        self.create_I_profile(index)
        self.create_Z_profile(index)

    def create_S_profile(self, index):
        """
        Create power profile based on index
        Args:
            index:

        Returns:

        """
        steps = len(index)
        self.Sprof = pd.DataFrame(data=ones(steps), index=index, columns=[self.name]) * self.S

    def create_I_profile(self, index):
        """
        Create current profile based on index
        Args:
            index:

        Returns:

        """
        steps = len(index)
        self.Iprof = pd.DataFrame(data=ones(steps), index=index, columns=[self.name]) * self.I

    def create_Z_profile(self, index):
        """
        Create impedance profile based on index
        Args:
            index:

        Returns:

        """
        steps = len(index)
        self.Zprof = pd.DataFrame(data=ones(steps), index=index, columns=[self.name]) * self.Z

    def get_profiles(self, index=None):
        """
        Get profiles and if the index is passed, create the profiles if needed
        Args:
            index: index of the Pandas DataFrame

        Returns:
            Power, Current and Impedance profiles
        """
        if index is not None:
            if self.Sprof is None:
                self.create_S_profile(index)
            if self.Iprof is None:
                self.create_I_profile(index)
            if self.Zprof is None:
                self.create_Z_profile(index)
        return self.Sprof, self.Iprof, self.Zprof

    def copy(self):

        load = Load()

        load.name = self.name

        # Impedance (Ohm)
        # Z * I = V -> Ohm * kA = kV
        load.Z = self.Z

        # Current (kA)
        load.I = self.I

        # Power (MVA)
        # MVA = kV * kA
        load.S = self.S

        # impedances profile for this load
        load.Zprof = self.Zprof

        # Current profiles for this load
        load.Iprof = self.Iprof

        # power profile for this load
        load.Sprof = self.Sprof

        return load

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        return [self.name, self.bus.name, str(self.Z), str(self.I), str(self.S)]


class StaticGenerator:

    def __init__(self, name='StaticGen', power=complex(0, 0), power_prof=None, active=True):
        """

        @param power:
        """

        self.name = name

        self.active = active

        self.type_name = 'StaticGenerator'

        self.properties_with_profile = (['S'], [complex])

        self.graphic_obj = None

        # The bus this element is attached to: Not necessary for calculations
        self.bus = None

        # Power (MVA)
        # MVA = kV * kA
        self.S = power

        # power profile for this load
        self.Sprof = power_prof

        self.edit_headers = ['name', 'bus', 'S']

        self.units = ['', '', 'MVA']

        self.edit_types = {'name': str,  'bus': None,  'S': complex}

    def copy(self):
        """

        :return:
        """
        return StaticGenerator(name=self.name, power=self.S, power_prof=self.Sprof)

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        return [self.name, self.bus.name, str(self.S)]

    def create_profiles(self, index):
        """
        Create the load object default profiles
        Args:
            index:
            steps:

        Returns:

        """
        self.create_S_profile(index)

    def create_S_profile(self, index):
        """
        Create power profile based on index
        Args:
            index:

        Returns:

        """
        steps = len(index)
        self.Sprof = pd.DataFrame(data=ones(steps), index=index, columns=[self.name]) * self.S

    def get_profiles(self, index=None):
        """
        Get profiles and if the index is passed, create the profiles if needed
        Args:
            index: index of the Pandas DataFrame

        Returns:
            Power, Current and Impedance profiles
        """
        if index is not None:
            if self.Sprof is None:
                self.create_S_profile(index)
        return self.Sprof


class Battery:

    def __init__(self, name='batt', active_power=0.0, voltage_module=1.0, Qmin=-9999, Qmax=9999, Snom=9999, Enom=9999,
                 power_prof=None, vset_prof=None, active=True):
        """
        Batery (Voltage controlled and dispatchable)
        @param name:
        @param active_power:
        @param voltage_module:
        @param Qmin:
        @param Qmax:
        @param Snom:
        @param Enom:
        @param power_prof:
        @param vset_prof:
        @param active:
        """

        self.name = name

        self.active = active

        self.type_name = 'Battery'

        self.properties_with_profile = (['P', 'Vset'], [float, float])

        self.graphic_obj = None

        # The bus this element is attached to: Not necessary for calculations
        self.bus = None

        # Power (MVA)
        # MVA = kV * kA
        self.P = active_power

        # power profile for this load
        self.Pprof = power_prof

        # Voltage module set point (p.u.)
        self.Vset = voltage_module

        # voltage set profile for this load
        self.Vsetprof = vset_prof

        # minimum reactive power in per unit
        self.Qmin = Qmin

        # Maximum reactive power in per unit
        self.Qmax = Qmax

        # Nominal power MVA
        self.Snom = Snom

        # Nominal energy MWh
        self.Enom = Enom

        self.edit_headers = ['name', 'bus', 'P', 'Vset', 'Snom', 'Enom', 'Qmin', 'Qmax']

        self.units = ['', '', 'MW', 'p.u.', 'MVA', 'kV', 'p.u.', 'p.u.']

        self.edit_types = {'name': str,
                           'bus': None,
                           'P': float,
                           'Vset': float,
                           'Snom': float,
                           'Enom': float,
                           'Qmin': float,
                           'Qmax': float}

    def copy(self):

        batt = Battery()

        batt.name = self.name

        # Power (MVA)
        # MVA = kV * kA
        batt.P = self.P

        # power profile for this load
        batt.Pprof = self.Pprof

        # Voltage module set point (p.u.)
        batt.Vset = self.Vset

        # voltage set profile for this load
        batt.Vsetprof = self.Vsetprof

        # minimum reactive power in per unit
        batt.Qmin = self.Qmin

        # Maximum reactive power in per unit
        batt.Qmax = self.Qmax

        # Nominal power MVA
        batt.Snom = self.Snom

        # Nominal energy MWh
        batt.Enom = self.Enom

        return batt

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        return [self.name, self.bus.name, self.P, self.Vset, self.Snom, self.Enom, self.Qmin, self.Qmax]

    def create_profiles(self, index):
        """
        Create the load object default profiles
        Args:
            index:
            steps:

        Returns:

        """
        self.create_P_profile(index)

        self.create_Vset_profile(index)

    def create_P_profile(self, index):
        """
        Create power profile based on index
        Args:
            index:

        Returns:

        """
        steps = len(index)
        self.Pprof = pd.DataFrame(data=ones(steps), index=index, columns=[self.name]) * self.P

    def create_Vset_profile(self, index):
        """
        Create power profile based on index
        Args:
            index:

        Returns:

        """
        steps = len(index)
        self.Vsetprof = pd.DataFrame(data=ones(steps), index=index, columns=[self.name]) * self.Vset

    def get_profiles(self, index=None):
        """
        Get profiles and if the index is passed, create the profiles if needed
        Args:
            index: index of the Pandas DataFrame

        Returns:
            Power, Current and Impedance profiles
        """
        if index is not None:
            if self.Pprof is None:
                self.create_P_profile(index)
            if self.Vsetprof is None:
                self.create_vset_profile(index)
        return self.Pprof, self.Vsetprof


class ControlledGenerator:

    def __init__(self, name='gen', active_power=0.0, voltage_module=1.0, Qmin=-9999, Qmax=9999, Snom=9999,
                 power_prof=None, vset_prof=None, active=True):
        """
        Voltage controlled generator
        @param name:
        @param active_power: Active power (MW)
        @param voltage_module: Voltage set point (p.u.)
        @param Qmin:
        @param Qmax:
        @param Snom:
        @param power_prof:
        @param vset_prof
        @param active
        """

        self.name = name

        self.active = active

        self.type_name = 'ControlledGenerator'

        self.graphic_obj = None

        self.properties_with_profile = (['P', 'Vset'], [float, float])

        # The bus this element is attached to: Not necessary for calculations
        self.bus = None

        # Power (MVA)
        # MVA = kV * kA
        self.P = active_power

        # power profile for this load
        self.Pprof = power_prof

        # Voltage module set point (p.u.)
        self.Vset = voltage_module

        # voltage set profile for this load
        self.Vsetprof = vset_prof

        # minimum reactive power in per unit
        self.Qmin = Qmin

        # Maximum reactive power in per unit
        self.Qmax = Qmax

        # Nominal power
        self.Snom = Snom

        self.edit_headers = ['name', 'bus', 'P', 'Vset', 'Snom', 'Qmin', 'Qmax']

        self.units = ['', '', 'MW', 'p.u.', 'MVA', 'p.u.', 'p.u.']

        self.edit_types = {'name': str,
                           'bus': None,
                           'P': float,
                           'Vset': float,
                           'Snom': float,
                           'Qmin': float,
                           'Qmax': float}

    def copy(self):

        gen = ControlledGenerator()

        gen.name = self.name

        # Power (MVA)
        # MVA = kV * kA
        gen.P = self.P

        # power profile for this load
        gen.Pprof = self.Pprof

        # Voltage module set point (p.u.)
        gen.Vset = self.Vset

        # voltage set profile for this load
        gen.Vsetprof = self.Vsetprof

        # minimum reactive power in per unit
        gen.Qmin = self.Qmin

        # Maximum reactive power in per unit
        gen.Qmax = self.Qmax

        # Nominal power
        gen.Snom = self.Snom

        return gen

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        return [self.name, self.bus.name, self.P, self.Vset, self.Snom, self.Qmin, self.Qmax]

    def create_profiles(self, index):
        """
        Create the load object default profiles
        Args:
            index:
            steps:

        Returns:

        """
        self.create_P_profile(index)

        self.create_Vset_profile(index)

    def create_P_profile(self, index):
        """
        Create power profile based on index
        Args:
            index:

        Returns:

        """
        steps = len(index)
        self.Pprof = pd.DataFrame(data=ones(steps), index=index, columns=[self.name]) * self.P

    def create_Vset_profile(self, index):
        """
        Create power profile based on index
        Args:
            index:

        Returns:

        """
        steps = len(index)
        self.Vsetprof = pd.DataFrame(data=ones(steps), index=index, columns=[self.name]) * self.Vset

    def get_profiles(self, index=None):
        """
        Get profiles and if the index is passed, create the profiles if needed
        Args:
            index: index of the Pandas DataFrame

        Returns:
            Power, Current and Impedance profiles
        """
        if index is not None:
            if self.Pprof is None:
                self.create_P_profile(index)
            if self.Vsetprof is None:
                self.create_vset_profile(index)
        return self.Pprof, self.Vsetprof


class Shunt:

    def __init__(self, name='shunt', admittance=complex(0, 0), admittance_prof=None, active=True):
        """
        Shunt object
        Args:
            name:
            admittance: Admittance in MVA at 1 p.u. voltage
            admittance_prof: Admittance profile in MVA at 1 p.u. voltage
            active: Is active True or False
        """
        self.name = name

        self.active = active

        self.type_name = 'Shunt'

        self.properties_with_profile = (['Y'], [complex])

        self.graphic_obj = None

        # The bus this element is attached to: Not necessary for calculations
        self.bus = None

        # Impedance (Ohm)
        # Z * I = V -> Ohm * kA = kV
        self.Y = admittance

        # admittance profile
        self.Yprof = admittance_prof

        self.edit_headers = ['name', 'bus', 'Y']

        self.units = ['', '', 'MVA']  # MVA at 1 p.u.

        self.edit_types = {'name': str,   'bus': None, 'Y': complex}

    def copy(self):

        shu = Shunt()

        shu.name = self.name

        # Impedance (Ohm)
        # Z * I = V -> Ohm * kA = kV
        shu.Y = self.Y

        # admittance profile
        shu.Yprof = self.Yprof

        return shu

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        return [self.name, self.bus.name, str(self.Y)]

    def create_profiles(self, index):
        """
        Create the load object default profiles
        Args:
            index:
            steps:

        Returns:

        """
        self.create_Y_profile(index)

    def create_Y_profile(self, index):
        """
        Create power profile based on index
        Args:
            index:

        Returns:

        """
        steps = len(index)
        self.Yprof = pd.DataFrame(data=ones(steps), index=index, columns=[self.name]) * self.Y

    def get_profiles(self, index=None):
        """
        Get profiles and if the index is passed, create the profiles if needed
        Args:
            index: index of the Pandas DataFrame

        Returns:
            Power, Current and Impedance profiles
        """
        if index is not None:
            if self.Yprof is None:
                self.create_Y_profile(index)
        return self.Yprof


class Circuit:

    def __init__(self, name='Circuit'):
        """
        Circuit constructor
        @param name: Name of the circuit
        """

        self.name = name

        # Base power (MVA)
        self.Sbase = 100

        # Should be able to accept Branches, Lines and Transformers alike
        self.branches = list()

        # array of branch indices in the master circuit
        self.branch_original_idx = list()

        # Should accept buses
        self.buses = list()

        # array of bus indices in the master circuit
        self.bus_original_idx = list()

        # Object with the necessary inputs for a power flow study
        self.power_flow_input = None

        #  containing the power flow results
        self.power_flow_results = None

        # containing the short circuit results
        self.short_circuit_results = None

        # Object with the necessary inputs for th time series simulation
        self.time_series_input = None

        # Object with the time series simulation results
        self.time_series_results = None

        # Monte Carlo input object
        self.monte_carlo_input = None

        # Monte Carlo time series batch
        self.mc_time_series = None

        # Bus-Branch graph
        self.graph = None

    def clear(self):
        """
        Delete the Circuit content
        @return:
        """
        self.Sbase = 100
        self.branches = list()
        self.branch_original_idx = list()
        self.buses = list()
        self.bus_original_idx = list()

    def compile(self):
        """
        Compile the circuit into all the needed arrays:
            - Ybus matrix
            - Sbus vector
            - Vbus vector
            - etc...
        """
        n = len(self.buses)
        m = len(self.branches)

        self.graph = nx.Graph()

        # declare power flow results
        power_flow_input = PowerFlowInput(n, m)

        # time series inputs
        Sprofile = pd.DataFrame()
        Iprofile = pd.DataFrame()
        Yprofile = pd.DataFrame()
        Scdf_ = [None] * n
        Icdf_ = [None] * n
        Ycdf_ = [None] * n
        time_series_input = None
        monte_carlo_input = None

        are_cdfs = False

        # Dictionary that helps referencing the nodes
        buses_dict = dict()

        # declare the square root of 3 to do it only once
        sqrt3 = sqrt(3.0)

        # Compile the buses
        for i in range(n):

            # Add buses dictionary entry
            buses_dict[self.buses[i]] = i

            # set the name
            power_flow_input.bus_names[i] = self.buses[i].name

            # assign the nominal voltage value
            power_flow_input.Vnom[i] = self.buses[i].Vnom

            # Determine the bus type
            self.buses[i].determine_bus_type()

            # compute the bus magnitudes
            Y, I, S, V, Yprof, Iprof, Sprof, Ycdf, Icdf, Scdf = self.buses[i].get_YISV()
            power_flow_input.Vbus[i] = V  # set the bus voltages
            power_flow_input.Sbus[i] += S  # set the bus power
            power_flow_input.Ibus[i] += I  # set the bus currents

            power_flow_input.Ybus[i, i] += Y  # set the bus shunt impedance in per unit
            power_flow_input.Yshunt[i] += Y  # copy the shunt impedance

            power_flow_input.types[i] = self.buses[i].type.value[0]  # set type

            power_flow_input.Vmin[i] = self.buses[i].Vmin
            power_flow_input.Vmax[i] = self.buses[i].Vmax
            power_flow_input.Qmin[i] = self.buses[i].Qmin_sum
            power_flow_input.Qmax[i] = self.buses[i].Qmax_sum

            # compute the time series arrays  ##############################################

            # merge the individual profiles. The profiles are Pandas DataFrames
            # ttt, nnn = Sprof.shape
            if Sprof is not None:
                k = where(Sprof.values == nan)
                Sprofile = pd.concat([Sprofile, Sprof], axis=1)
            else:
                nn = len(Sprofile)
                Sprofile['Sprof@Bus' + str(i)] = pd.Series(ones(nn) * S, index=Sprofile.index)  # append column of zeros

            if Iprof is not None:
                Iprofile = pd.concat([Iprofile, Iprof], axis=1)
            else:
                Iprofile['Iprof@Bus' + str(i)] = pd.Series(ones(len(Iprofile)) * I, index=Iprofile.index)

            if Yprof is not None:
                Yprofile = pd.concat([Yprofile, Yprof], axis=1)
            else:
                Yprofile['Iprof@Bus' + str(i)] = pd.Series(ones(len(Yprofile)) * Y, index=Yprofile.index)

            # Store the CDF's form Monte Carlo ##############################################

            if Scdf is None and S != complex(0, 0):
                Scdf = CDF(array([S]))

            if Icdf is None and I != complex(0, 0):
                Icdf = CDF(array([I]))

            if Ycdf is None and Y != complex(0, 0):
                Ycdf = CDF(array([Y]))

            if Scdf is not None or Icdf is not None or Ycdf is not None:
                are_cdfs = True

            Scdf_[i] = Scdf
            Icdf_[i] = Icdf
            Ycdf_[i] = Ycdf

        # normalize the power array
        power_flow_input.Sbus /= self.Sbase

        # normalize the currents array (I was given in MVA at v=1 p.u.)
        power_flow_input.Ibus /= self.Sbase

        # normalize the admittances array (Y was given in MVA at v=1 p.u.)
        power_flow_input.Ybus /= self.Sbase
        power_flow_input.Yshunt /= self.Sbase

        # normalize the reactive power limits array (Q was given in MVAr)
        power_flow_input.Qmax /= self.Sbase
        power_flow_input.Qmin /= self.Sbase

        if Sprofile is not None:
            Sprofile /= self.Sbase
            Sprofile.columns = ['Sprof@Bus' + str(i) for i in range(Sprofile.shape[1])]

        if Iprofile is not None:
            Iprofile /= self.Sbase
            Iprofile.columns = ['Iprof@Bus' + str(i) for i in range(Iprofile.shape[1])]

        if Yprofile is not None:
            Yprofile /= self.Sbase
            Yprofile.columns = ['Yprof@Bus' + str(i) for i in range(Yprofile.shape[1])]

        time_series_input = TimeSeriesInput(Sprofile, Iprofile, Yprofile)
        time_series_input.compile()

        if are_cdfs:
            monte_carlo_input = MonteCarloInput(n, Scdf_, Icdf_, Ycdf_)

        # Compile the branches
        for i in range(m):

            if self.branches[i].active:
                # Set the branch impedance

                f = buses_dict[self.branches[i].bus_from]
                t = buses_dict[self.branches[i].bus_to]

                f, t = self.branches[i].apply_to(Ybus=power_flow_input.Ybus,
                                                 Yseries=power_flow_input.Yseries,
                                                 Yshunt=power_flow_input.Yshunt,
                                                 Yf=power_flow_input.Yf,
                                                 Yt=power_flow_input.Yt,
                                                 B1=power_flow_input.B1,
                                                 B2=power_flow_input.B2,
                                                 i=i, f=f, t=t)
                # add the bus shunts
                # power_flow_input.Yf[i, f] += power_flow_input.Yshunt[f, f]
                # power_flow_input.Yt[i, t] += power_flow_input.Yshunt[t, t]

                # Add graph edge (automatically adds the vertices)
                self.graph.add_edge(f, t)

                # Set the active flag in the active branches array
                power_flow_input.active_branches[i] = 1

                # Arrays with the from and to indices per bus
                power_flow_input.F[i] = f
                power_flow_input.T[i] = t

            # fill rate
            if self.branches[i].rate > 0:
                power_flow_input.branch_rates[i] = self.branches[i].rate
            else:
                power_flow_input.branch_rates[i] = 1e-6
                warn('The branch ' + str(i) + ' has no rate. Setting 1e-6 to avoid zero division.')

        # Assign the power flow inputs  button
        power_flow_input.compile()
        self.power_flow_input = power_flow_input
        self.time_series_input = time_series_input
        self.monte_carlo_input = monte_carlo_input

    def set_at(self, t, mc=False):
        """
        Set the current values given by the profile step of index t
        @param t: index of the profiles
        @param mc: Is this being run from MonteCarlo?
        @return: Nothing
        """
        if self.time_series_input is not None:
            if mc:

                if self.mc_time_series is None:
                    warn('No monte carlo inputs in island!!!')
                else:
                    self.power_flow_input.Sbus = self.mc_time_series.S[t, :] / self.Sbase
            else:
                self.power_flow_input.Sbus = self.time_series_input.S[t, :] / self.Sbase
        else:
            warn('No time series values')

    def sample_monte_carlo_batch(self, batch_size, use_latin_hypercube=False):
        """
        Samples a monte carlo batch as a time series object
        @param batch_size: size of the batch (integer)
        @return:
        """
        self.mc_time_series = self.monte_carlo_input(batch_size, use_latin_hypercube)

    def sample_at(self, x):
        """
        Get samples at x
        Args:
            x: values in [0, 1+ to sample the CDF

        Returns:

        """
        self.mc_time_series = self.monte_carlo_input.get_at(x)

    def get_loads(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.loads:
                elm.bus = bus
            lst = lst + bus.loads
        return lst

    def get_static_generators(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.static_generators:
                elm.bus = bus
            lst = lst + bus.static_generators
        return lst

    def get_shunts(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.shunts:
                elm.bus = bus
            lst = lst + bus.shunts
        return lst

    def get_controlled_generators(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.controlled_generators:
                elm.bus = bus
            lst = lst + bus.controlled_generators
        return lst

    def get_batteries(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.batteries:
                elm.bus = bus
            lst = lst + bus.batteries
        return lst

    def get_Jacobian(self, sparse=False):
        """
        Returns the Grid Jacobian matrix
        Returns:
            Grid Jacobian Matrix in CSR sparse format or as full matrix
        """

        # Initial magnitudes
        pvpq = r_[self.power_flow_input.pv, self.power_flow_input.pq]

        J = Jacobian(Ybus=self.power_flow_input.Ybus,
                     V=self.power_flow_input.Vbus,
                     Ibus=self.power_flow_input.Ibus,
                     pq=self.power_flow_input.pq,
                     pvpq=pvpq)

        if sparse:
            return J
        else:
            return J.todense()


class MultiCircuit(Circuit):

    def __init__(self):
        """
        Multi Circuit Constructor
        """
        Circuit.__init__(self)

        self.name = 'Grid'

        # List of circuits contained within this circuit
        self.circuits = list()

        # self.power_flow_results = PowerFlowResults()

        self.bus_dictionary = dict()

        self.branch_dictionary = dict()

        self.has_time_series = False

        self.bus_names = None

        self.branch_names = None

        self.objects_with_profiles = [Load(), StaticGenerator(), ControlledGenerator(), Battery(), Shunt()]

        self.time_profile = None

        self.profile_magnitudes = dict()

        '''
        self.type_name = 'Shunt'

        self.properties_with_profile = ['Y']
        '''
        for dev in self.objects_with_profiles:
            if dev.properties_with_profile is not None:
                self.profile_magnitudes[dev.type_name] = dev.properties_with_profile

    def load_file(self, filename):
        """
        Load GridCal compatible file
        @param filename:
        @return:
        """
        if os.path.exists(filename):
            name, file_extension = os.path.splitext(filename)
            print(name, file_extension)
            if file_extension == '.xls' or file_extension == '.xlsx':
                ppc = load_from_xls(filename)

                # Pass the table-like data dictionary to objects in this circuit
                if 'version' not in ppc.keys():
                    from GridCal.grid.ImportParsers.matpower_parser import interpret_data_v1
                    interpret_data_v1(self, ppc)
                    return True
                elif ppc['version'] == 2.0:
                    self.interpret_data_v2(ppc)
                    return True
                else:
                    warn('The file could not be processed')
                    return False

            elif file_extension == '.dgs':
                from GridCal.grid.ImportParsers.DGS_Parser import dgs_to_circuit
                circ = dgs_to_circuit(filename)
                self.buses = circ.buses
                self.branches = circ.branches

            elif file_extension == '.m':
                from GridCal.grid.ImportParsers.matpower_parser import parse_matpower_file
                circ = parse_matpower_file(filename)
                self.buses = circ.buses
                self.branches = circ.branches

            elif file_extension in ['.raw', '.RAW', '.Raw']:
                from GridCal.grid.ImportParsers.PSS_Parser import PSSeParser
                parser = PSSeParser(filename)
                circ = parser.circuit
                self.buses = circ.buses
                self.branches = circ.branches

        else:
            warn('The file does not exist.')
            return False

    def interpret_data_v2(self, data):
        """
        Interpret the new file version
        Args:
            data: Dictionary with the excel file sheet labels and the corresponding DataFrame

        Returns: Nothing, just applies the loaded data to this MultiCircuit instance

        """
        print('Interpreting V2 data...')

        # clear all the data
        self.clear()

        self.name = data['name']

        # set the base magnitudes
        self.Sbase = data['baseMVA']

        self.time_profile = None

        # common function
        def set_object_attributes(obj_, attr_list, values):
            for a, attr in enumerate(attr_list):

                # Hack to change the enabled by active...
                if attr == 'is_enabled':
                    attr = 'active'

                conv = obj.edit_types[attr]  # get the type converter
                if conv is None:
                    setattr(obj_, attr, values[a])
                else:
                    setattr(obj_, attr, conv(values[a]))

        # Add the buses
        lst = data['bus']
        hdr = lst.columns.values
        vals = lst.values
        bus_dict = dict()
        for i in range(len(lst)):
            obj = Bus()
            set_object_attributes(obj, hdr, vals[i, :])
            bus_dict[obj.name] = obj
            self.add_bus(obj)

        # Add the branches
        lst = data['branch']
        bus_from = lst['bus_from'].values
        bus_to = lst['bus_to'].values
        hdr = lst.columns.values
        hdr = delete(hdr, argwhere(hdr == 'bus_from'))
        hdr = delete(hdr, argwhere(hdr == 'bus_to'))
        vals = lst[hdr].values
        for i in range(len(lst)):
            obj = Branch(bus_from=bus_dict[bus_from[i]], bus_to=bus_dict[bus_to[i]])
            set_object_attributes(obj, hdr, vals[i, :])
            self.add_branch(obj)

        # add the loads
        lst = data['load']
        bus_from = lst['bus'].values
        hdr = lst.columns.values
        hdr = delete(hdr, argwhere(hdr == 'bus'))
        vals = lst[hdr].values
        for i in range(len(lst)):
            obj = Load()
            set_object_attributes(obj, hdr, vals[i, :])

            if 'load_Sprof' in data.keys():
                val = [complex(v) for v in data['load_Sprof'].values[:, i]]
                idx = data['load_Sprof'].index
                obj.Sprof = pd.DataFrame(data=val, index=idx)

                if self.time_profile is None:
                    self.time_profile = idx

            if 'load_Iprof' in data.keys():
                val = [complex(v) for v in data['load_Iprof'].values[:, i]]
                idx = data['load_Iprof'].index
                obj.Iprof = pd.DataFrame(data=val, index=idx)

                if self.time_profile is None:
                    self.time_profile = idx

            if 'load_Zprof' in data.keys():
                val = [complex(v) for v in data['load_Zprof'].values[:, i]]
                idx = data['load_Zprof'].index
                obj.Zprof = pd.DataFrame(data=val, index=idx)

                if self.time_profile is None:
                    self.time_profile = idx

            bus = bus_dict[bus_from[i]]

            if obj.name == 'Load':
                obj.name += str(len(bus.loads)+1) + '@' + bus.name

            obj.bus = bus
            bus.loads.append(obj)

        # add the controlled generators
        lst = data['controlled_generator']
        bus_from = lst['bus'].values
        hdr = lst.columns.values
        hdr = delete(hdr, argwhere(hdr == 'bus'))
        vals = lst[hdr].values
        for i in range(len(lst)):
            obj = ControlledGenerator()
            set_object_attributes(obj, hdr, vals[i, :])

            if 'CtrlGen_P_profiles' in data.keys():
                val = data['CtrlGen_P_profiles'].values[:, i]
                idx = data['CtrlGen_P_profiles'].index
                obj.Pprof = pd.DataFrame(data=val, index=idx)

            if 'CtrlGen_Vset_profiles' in data.keys():
                val = data['CtrlGen_Vset_profiles'].values[:, i]
                idx = data['CtrlGen_Vset_profiles'].index
                obj.Vsetprof = pd.DataFrame(data=val, index=idx)

            bus = bus_dict[bus_from[i]]

            if obj.name == 'gen':
                obj.name += str(len(bus.controlled_generators)+1) + '@' + bus.name

            obj.bus = bus
            bus.controlled_generators.append(obj)

        # add the batteries
        lst = data['battery']
        bus_from = lst['bus'].values
        hdr = lst.columns.values
        hdr = delete(hdr, argwhere(hdr == 'bus'))
        vals = lst[hdr].values
        for i in range(len(lst)):
            obj = Battery()
            set_object_attributes(obj, hdr, vals[i, :])

            if 'battery_P_profiles' in data.keys():
                val = data['battery_P_profiles'].values[:, i]
                idx = data['battery_P_profiles'].index
                obj.Pprof = pd.DataFrame(data=val, index=idx)

            if 'battery_Vset_profiles' in data.keys():
                val = data['battery_Vset_profiles'].values[:, i]
                idx = data['battery_Vset_profiles'].index
                obj.Vsetprof = pd.DataFrame(data=val, index=idx)

            bus = bus_dict[bus_from[i]]

            if obj.name == 'batt':
                obj.name += str(len(bus.batteries)+1) + '@' + bus.name

            obj.bus = bus
            bus.batteries.append(obj)

        # add the static generators
        lst = data['static_generator']
        bus_from = lst['bus'].values
        hdr = lst.columns.values
        hdr = delete(hdr, argwhere(hdr == 'bus'))
        vals = lst[hdr].values
        for i in range(len(lst)):
            obj = StaticGenerator()
            set_object_attributes(obj, hdr, vals[i, :])

            if 'static_generator_Sprof' in data.keys():
                val = data['static_generator_Sprof'].values[:, i]
                idx = data['static_generator_Sprof'].index
                obj.Sprof = pd.DataFrame(data=val, index=idx)

            bus = bus_dict[bus_from[i]]

            if obj.name == 'StaticGen':
                obj.name += str(len(bus.static_generators)+1) + '@' + bus.name

            obj.bus = bus
            bus.static_generators.append(obj)

        # add the shunts
        lst = data['shunt']
        bus_from = lst['bus'].values
        hdr = lst.columns.values
        hdr = delete(hdr, argwhere(hdr == 'bus'))
        vals = lst[hdr].values
        for i in range(len(lst)):
            obj = Shunt()
            set_object_attributes(obj, hdr, vals[i, :])

            if 'shunt_Y_profiles' in data.keys():
                val = data['shunt_Y_profiles'].values[:, i]
                idx = data['shunt_Y_profiles'].index
                obj.Yprof = pd.DataFrame(data=val, index=idx)

            bus = bus_dict[bus_from[i]]

            if obj.name == 'shunt':
                obj.name += str(len(bus.shunts)+1) + '@' + bus.name

            obj.bus = bus
            bus.shunts.append(obj)

        print('Done!')

        # ['branch', 'load_Zprof', 'version', 'CtrlGen_Vset_profiles', 'CtrlGen_P_profiles', 'basekA',
        #                   'baseMVA', 'load_Iprof', 'battery', 'load', 'bus', 'shunt', 'controlled_generator',
        #                   'load_Sprof', 'static_generator']

    def save_file(self, file_path):
        """
        Save the circuit information
        :param file_path: file path to save
        :return:
        """
        dfs = dict()

        # configuration ################################################################################################
        obj = list()
        obj.append(['BaseMVA', self.Sbase])
        obj.append(['Version', 2])
        obj.append(['Name', self.name])
        dfs['config'] = pd.DataFrame(data=obj, columns=['Property', 'Value'])

        # get the master time profile
        T = self.time_profile

        # buses ########################################################################################################
        obj = list()
        names_count = dict()
        for elm in self.buses:

            # check name: if the name is repeated, change it so that it is not
            if elm.name in names_count.keys():
                names_count[elm.name] += 1
                elm.name = elm.name + '_' + str(names_count[elm.name])
            else:
                names_count[elm.name] = 1

            obj.append(elm.get_save_data())
        dfs['bus'] = pd.DataFrame(data=array(obj).astype('str'), columns=Bus().edit_headers)

        # branches #####################################################################################################
        obj = list()
        for elm in self.branches:
            obj.append(elm.get_save_data())
        dfs['branch'] = pd.DataFrame(data=obj, columns=Branch(None, None).edit_headers)

        # loads ########################################################################################################
        obj = list()
        s_profiles = None
        i_profiles = None
        z_profiles = None
        hdr = list()
        for elm in self.get_loads():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None:
                if s_profiles is None and elm.Sprof is not None:
                    s_profiles = elm.Sprof.values
                    i_profiles = elm.Iprof.values
                    z_profiles = elm.Zprof.values
                else:
                    s_profiles = c_[s_profiles, elm.Sprof.values]
                    i_profiles = c_[i_profiles, elm.Iprof.values]
                    z_profiles = c_[z_profiles, elm.Zprof.values]

        dfs['load'] = pd.DataFrame(data=obj, columns=Load().edit_headers)

        if s_profiles is not None:
            dfs['load_Sprof'] = pd.DataFrame(data=s_profiles.astype('str'), columns=hdr, index=T)
            dfs['load_Iprof'] = pd.DataFrame(data=i_profiles.astype('str'), columns=hdr, index=T)
            dfs['load_Zprof'] = pd.DataFrame(data=z_profiles.astype('str'), columns=hdr, index=T)

        # static generators ############################################################################################
        obj = list()
        hdr = list()
        s_profiles = None
        for elm in self.get_static_generators():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None:
                if s_profiles is None and elm.Sprof is not None:
                    s_profiles = elm.Sprof.values
                else:
                    s_profiles = c_[s_profiles, elm.Sprof.values]

        dfs['static_generator'] = pd.DataFrame(data=obj, columns=StaticGenerator().edit_headers)

        if s_profiles is not None:
            dfs['static_generator_Sprof'] = pd.DataFrame(data=s_profiles.astype('str'), columns=hdr, index=T)

        # battery ######################################################################################################
        obj = list()
        hdr = list()
        v_set_profiles = None
        p_profiles = None
        for elm in self.get_batteries():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None:
                if p_profiles is None and elm.Pprof is not None:
                    p_profiles = elm.Pprof.values
                    v_set_profiles = elm.Vsetprof.values
                else:
                    p_profiles = c_[p_profiles, elm.Pprof.values]
                    v_set_profiles = c_[v_set_profiles, elm.Vsetprof.values]
        dfs['battery'] = pd.DataFrame(data=obj, columns=Battery().edit_headers)

        if p_profiles is not None:
            dfs['battery_Vset_profiles'] = pd.DataFrame(data=v_set_profiles, columns=hdr, index=T)
            dfs['battery_P_profiles'] = pd.DataFrame(data=p_profiles, columns=hdr, index=T)

        # controlled generator
        obj = list()
        hdr = list()
        v_set_profiles = None
        p_profiles = None
        for elm in self.get_controlled_generators():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None and elm.Pprof is not None:
                if p_profiles is None:
                    p_profiles = elm.Pprof.values
                    v_set_profiles = elm.Vsetprof.values
                else:
                    p_profiles = c_[p_profiles, elm.Pprof.values]
                    v_set_profiles = c_[v_set_profiles, elm.Vsetprof.values]
        dfs['controlled_generator'] = pd.DataFrame(data=obj, columns=ControlledGenerator().edit_headers)
        if p_profiles is not None:
            dfs['CtrlGen_Vset_profiles'] = pd.DataFrame(data=v_set_profiles, columns=hdr, index=T)
            dfs['CtrlGen_P_profiles'] = pd.DataFrame(data=p_profiles, columns=hdr, index=T)

        # shunt
        obj = list()
        hdr = list()
        y_profiles = None
        for elm in self.get_shunts():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None:
                if y_profiles is None and elm.Yprof.values is not None:
                    y_profiles = elm.Yprof.values
                else:
                    y_profiles = c_[y_profiles, elm.Yprof.values]

        dfs['shunt'] = pd.DataFrame(data=obj, columns=Shunt().edit_headers)

        if y_profiles is not None:
            dfs['shunt_Y_profiles'] = pd.DataFrame(data=y_profiles, columns=hdr, index=T)

        # flush-save
        writer = pd.ExcelWriter(file_path)
        for key in dfs.keys():
            dfs[key].to_excel(writer, key)

        writer.save()

    def compile(self):
        """
        Divide the grid into the different possible grids
        @return:
        """

        n = len(self.buses)
        m = len(self.branches)
        self.power_flow_input = PowerFlowInput(n, m)

        self.time_series_input = TimeSeriesInput()

        self.graph = nx.Graph()

        self.circuits = list()

        self.has_time_series = True

        self.bus_names = zeros(n, dtype=object)
        self.branch_names = zeros(m, dtype=object)

        # create bus dictionary
        for i in range(n):
            self.bus_dictionary[self.buses[i]] = i
            self.bus_names[i] = self.buses[i].name

        # Compile the branches
        for i in range(m):
            self.branch_names[i] = self.branches[i].name
            if self.branches[i].active:
                if self.branches[i].bus_from.active and self.branches[i].bus_to.active:
                    f = self.bus_dictionary[self.branches[i].bus_from]
                    t = self.bus_dictionary[self.branches[i].bus_to]
                    # Add graph edge (automatically adds the vertices)
                    self.graph.add_edge(f, t, length=self.branches[i].R)
                    self.branch_dictionary[self.branches[i]] = i

        # Split the graph into islands
        islands = [list(isl) for isl in connected_components(self.graph)]

        isl_idx = 0
        for island in islands:

            # Convert island to dictionary
            isl_dict = dict()
            for idx in range(len(island)):
                isl_dict[island[idx]] = idx

            # create circuit of the island
            circuit = Circuit(name='Island ' + str(isl_idx))

            # Set buses of the island
            circuit.buses = [self.buses[b] for b in island]
            circuit.bus_original_idx = island

            # set branches of the island
            for i in range(m):
                f = self.bus_dictionary[self.branches[i].bus_from]
                t = self.bus_dictionary[self.branches[i].bus_to]
                if f in island and t in island:
                    # Copy the branch into a new
                    branch = self.branches[i].copy()
                    # Add the branch to the circuit
                    circuit.branches.append(branch)
                    circuit.branch_original_idx.append(i)

            circuit.compile()
            self.power_flow_input.set_from(circuit.power_flow_input,
                                           circuit.bus_original_idx,
                                           circuit.branch_original_idx)

            self.time_series_input.apply_from_island(circuit.time_series_input,
                                                     circuit.bus_original_idx,
                                                     circuit.branch_original_idx,
                                                     n, m)

            self.circuits.append(circuit)

            self.has_time_series = self.has_time_series and circuit.time_series_input.valid

            isl_idx += 1

        print(islands)

    def create_profiles(self, steps, step_length, step_unit, time_base: datetime=datetime.now()):
        """
        Set the default profiles in all the objects enabled to have profiles
        Args:
            steps: Number of time steps
            step_length: time length (1, 2, 15, ...)
            step_unit: unit of the time step
            time_base: Date to start from
        """

        index = [None] * steps
        for i in range(steps):
            if step_unit == 'h':
                index[i] = time_base + timedelta(hours=i*step_length)
            elif step_unit == 'm':
                index[i] = time_base + timedelta(minutes=i*step_length)
            elif step_unit == 's':
                index[i] = time_base + timedelta(seconds=i*step_length)

        self.format_profiles(index)

    def format_profiles(self, index):
        """
        Format the pandas profiles in place using a time index
        Args:
            index: Time profile
        """

        self.time_profile = array(index)

        for bus in self.buses:

            for elm in bus.loads:
                elm.create_profiles(index)

            for elm in bus.static_generators:
                elm.create_profiles(index)

            for elm in bus.controlled_generators:
                elm.create_profiles(index)

            for elm in bus.batteries:
                elm.create_profiles(index)

            for elm in bus.shunts:
                elm.create_profiles(index)

    def get_node_elements_by_type(self, element_type):
        """
        Get set of elements and their parent nodes
        Args:
            element_type: String {'Load', 'StaticGenerator', 'ControlledGenerator', 'Battery', 'Shunt'}

        Returns: List of elements, list of matching parent buses
        """
        elements = list()
        parent_buses = list()

        if element_type == 'Load':
            for bus in self.buses:
                for elm in bus.loads:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == 'StaticGenerator':
            for bus in self.buses:
                for elm in bus.static_generators:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == 'ControlledGenerator':
            for bus in self.buses:
                for elm in bus.controlled_generators:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == 'Battery':
            for bus in self.buses:
                for elm in bus.batteries:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == 'Shunt':
            for bus in self.buses:
                for elm in bus.shunts:
                    elements.append(elm)
                    parent_buses.append(bus)

        return elements, parent_buses

    def set_power(self, S):
        """
        Set the power array in the circuits
        @param S: Array of power values in MVA for all the nodes in all the islands
        """
        for circuit_island in self.circuits:
            idx = circuit_island.bus_original_idx  # get the buses original indexing in the island
            circuit_island.power_flow_input.Sbus = S[idx]  # set the values

    def add_bus(self, obj: Bus):
        """
        Add bus keeping track of it as object
        @param obj:
        """
        self.buses.append(obj)

    def delete_bus(self, obj: Bus):
        """
        Remove bus
        @param obj: Bus object
        """

        # remove associated branches in reverse order
        for i in range(len(self.branches) - 1, -1, -1):
            if self.branches[i].bus_from == obj or self.branches[i].bus_to == obj:
                self.branches.pop(i)

        # remove the bus itself
        self.buses.remove(obj)

    def add_branch(self, obj: Branch):
        """
        Add a branch object to the circuit
        @param obj: Branch object
        """
        self.branches.append(obj)

    def delete_branch(self, obj: Branch):
        """
        Delete a branch object from the circuit
        @param obj:
        """
        self.branches.remove(obj)

    def add_load(self, bus: Bus, api_obj=None):
        """
        Add load object to a bus
        Args:
            bus: Bus object
            api_obj: Load object
        """
        if api_obj is None:
            api_obj = Load()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        if api_obj.name == 'Load':
            api_obj.name += '@' + bus.name

        bus.loads.append(api_obj)

        return api_obj

    def add_controlled_generator(self, bus: Bus, api_obj=None):
        """
        Add controlled generator to a bus
        Args:
            bus: Bus object
            api_obj: ControlledGenerator object
        """
        if api_obj is None:
            api_obj = ControlledGenerator()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.controlled_generators.append(api_obj)

        return api_obj

    def add_static_generator(self, bus: Bus, api_obj=None):
        """
        Add a static generator object to a bus
        Args:
            bus: Bus object to add it to
            api_obj: StaticGenerator object
        """
        if api_obj is None:
            api_obj = StaticGenerator()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.static_generators.append(api_obj)

        return api_obj

    def add_battery(self, bus: Bus, api_obj=None):
        """
        Add battery object to a bus
        Args:
            bus: Bus object to add it to
            api_obj: Battery object to add it to
        """
        if api_obj is None:
            api_obj = Battery()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.batteries.append(api_obj)

        return api_obj

    def add_shunt(self, bus: Bus, api_obj=None):
        """
        Add shunt object to a bus
        Args:
            bus: Bus object to add it to
            api_obj: Shunt object
        """
        if api_obj is None:
            api_obj = Shunt()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.shunts.append(api_obj)

        return api_obj

    def plot_graph(self, ax=None):
        """
        Plot the grid
        @param ax: Matplotlib axis object
        @return: Nothing
        """
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        nx.draw_spring(self.graph, ax=ax)

    def copy(self):
        """
        Returns a deep (true) copy of this circuit
        @return:
        """

        cpy = MultiCircuit()

        cpy.name = self.name

        bus_dict = dict()
        for bus in self.buses:
            bus_cpy = bus.copy()
            bus_dict[bus] = bus_cpy
            cpy.add_bus(bus_cpy)

        for branch in self.branches:
            cpy.add_branch(branch.copy(bus_dict))

        return cpy

    def dispatch(self):
        """
        Dispatch either load or generation using a simple equalised share rule of the shedding to be done
        @return: Nothing
        """
        if self.power_flow_input is not None:

            # get the total power balance
            balance = abs(self.power_flow_input.Sbus.sum())

            if balance > 0:  # more generation than load, dispatch generation
                Gmax = 0
                Lt = 0
                for bus in self.buses:
                    for load in bus.loads:
                        Lt += abs(load.S)
                    for gen in bus.controlled_generators:
                        Gmax += abs(gen.Snom)

                # reassign load
                factor = Lt / Gmax
                print('Decreasing generation by ', factor * 100, '%')
                for bus in self.buses:
                    for gen in bus.controlled_generators:
                        gen.P *= factor

            elif balance < 0:  # more load than generation, dispatch load

                Gmax = 0
                Lt = 0
                for bus in self.buses:
                    for load in bus.loads:
                        Lt += abs(load.S)
                    for gen in bus.controlled_generators:
                        Gmax += abs(gen.P + 1j * gen.Qmax)

                # reassign load
                factor = Gmax / Lt
                print('Decreasing load by ', factor * 100, '%')
                for bus in self.buses:
                    for load in bus.loads:
                        load.S *= factor

            else:  # nothing to do
                pass

        else:
            warn('The grid must be compiled before dispatching it')

    def set_state(self, t):
        """
        Set the profiles state at the index t as the default values
        :param t:
        :return:
        """
        for bus in self.buses:
            bus.set_state(t)


class Bus:

    def __init__(self, name="Bus", vnom=10, vmin=0.9, vmax=1.1, xpos=0, ypos=0, active=True):
        """
        Bus  constructor
        """

        self.name = name

        self.type_name = 'Bus'

        self.properties_with_profile = None

        # Nominal voltage (kV)
        self.Vnom = vnom

        self.Vmin = vmin

        self.Vmax = vmax

        self.Qmin_sum = 0

        self.Qmax_sum = 0

        self.Zf = 0

        self.active = active

        # List of load s attached to this bus
        self.loads = list()

        # List of Controlled generators attached to this bus
        self.controlled_generators = list()

        # List of shunt s attached to this bus
        self.shunts = list()

        # List of batteries attached to this bus
        self.batteries = list()

        # List of static generators attached tot this bus
        self.static_generators = list()

        # Bus type
        self.type = NodeType.NONE

        # Flag to determine if the bus is a slack bus or not
        self.is_slack = False

        # if true, the presence of storage devices turn the bus into a Reference bus in practice
        # So that P +jQ are computed
        self.dispatch_storage = False

        self.x = xpos

        self.y = ypos

        self.graphic_obj = None

        self.edit_headers = ['name', 'active', 'is_slack', 'Vnom', 'Vmin', 'Vmax', 'Zf', 'x', 'y']

        self.units = ['', '', '', 'kV', 'p.u.', 'p.u.', 'p.u.', '', '']

        self.edit_types = {'name': str,
                           'active': bool,
                           'is_slack': bool,
                           'Vnom': float,
                           'Vmin': float,
                           'Vmax': float,
                           'Zf': complex,
                           'x': float,
                           'y': float}

    def determine_bus_type(self):
        """
        Infer the bus type from the devices attached to it
        @return: Nothing
        """
        if len(self.controlled_generators) > 0:

            if self.is_slack:  # If contains generators and is marked as REF, then set it as REF
                self.type = NodeType.REF
            else:  # Otherwise set as PV
                self.type = NodeType.PV

        elif len(self.batteries) > 0:

            if self.dispatch_storage:
                # If there are storage devices and the dispatchable flag is on, set the bus as dispatchable
                self.type = NodeType.STO_DISPATCH
            else:
                # Otherwise a storage device shall be marked as a voltage controlld bus
                self.type = NodeType.PV
        else:
            if self.is_slack:  # If there is no device but still is marked as REF, then set as REF
                self.type = NodeType.REF
            else:
                # Nothing special; set it as PQ
                self.type = NodeType.PQ

    def get_YISV(self, index=None):
        """
        Compose the
            - Z: Impedance attached to the bus
            - I: Current attached to the bus
            - S: Power attached to the bus
            - V: Voltage of the bus
        All in complex values
        @return: Y, I, S, V, Yprof, Iprof, Sprof
        """
        Y = complex(0, 0)
        I = complex(0, 0)  # Positive Generates, negative consumes
        S = complex(0, 0)  # Positive Generates, negative consumes
        V = complex(1, 0)

        y_profile = None
        i_profile = None  # Positive Generates, negative consumes
        s_profile = None  # Positive Generates, negative consumes

        y_cdf = None
        i_cdf = None   # Positive Generates, negative consumes
        s_cdf = None   # Positive Generates, negative consumes

        self.Qmin_sum = 0
        self.Qmax_sum = 0

        is_v_controlled = False

        # Loads
        for elm in self.loads:

            if elm.active:

                if elm.Z != 0:
                    Y += 1 / elm.Z
                I -= elm.I  # Reverse sign convention in the load
                S -= elm.S  # Reverse sign convention in the load

                # Add the profiles
                elm_s_prof, elm_i_prof, elm_z_prof = elm.get_profiles(index)
                if elm_z_prof is not None:
                    if elm_z_prof.values.sum(axis=0) != complex(0):
                        if y_profile is None:
                            y_profile = 1 / elm_z_prof
                            y_cdf = CDF(y_profile)
                        else:
                            pr = 1 / elm_z_prof
                            y_profile = y_profile.add(pr, fill_value=0)
                            y_cdf = y_cdf + CDF(pr)

                if elm_i_prof is not None:
                    if elm_i_prof.values.sum(axis=0) != complex(0):
                        if i_profile is None:
                            i_profile = -elm_i_prof  # Reverse sign convention in the load
                            i_cdf = CDF(i_profile)
                        else:
                            pr = -elm_i_prof
                            i_profile = i_profile.add(pr, fill_value=0)  # Reverse sign convention in the load
                            i_cdf = i_cdf + CDF(pr)

                if elm_s_prof is not None:
                    if elm_s_prof.values.sum(axis=0) != complex(0):
                        if s_profile is None:
                            s_profile = -elm_s_prof  # Reverse sign convention in the load
                            s_cdf = CDF(s_profile)
                        else:
                            pr = -elm_s_prof
                            s_profile = s_profile.add(pr, fill_value=0)  # Reverse sign convention in the load
                            s_cdf = s_cdf + CDF(pr)
            else:
                warn(elm.name + ' is not active')

        # controlled gen and batteries
        for elm in self.controlled_generators + self.batteries:

            if elm.active:
                # Add the generator active power
                S = complex(S.real + elm.P, S.imag)

                self.Qmin_sum += elm.Qmin
                self.Qmax_sum += elm.Qmax

                # Voltage of the bus
                if not is_v_controlled:
                    V = complex(elm.Vset, 0)
                    is_v_controlled = True
                else:
                    if elm.Vset != V.real:
                        raise Exception("Different voltage controlled generators try to control " +
                                        "the same bus with different voltage set points")
                    else:
                        pass

                # add the power profile
                elm_p_prof, elm_vset_prof = elm.get_profiles(index)
                if elm_p_prof is not None:
                    if s_profile is None:
                        s_profile = elm_p_prof  # Reverse sign convention in the load
                        s_cdf = CDF(s_profile)
                    else:
                        s_profile = s_profile.add(elm_p_prof, fill_value=0)
                        s_cdf = s_cdf + CDF(elm_p_prof)
            else:
                warn(elm.name + ' is not active')

        # set maximum reactive power limits
        if self.Qmin_sum == 0:
            self.Qmin_sum = -999900
        if self.Qmax_sum == 0:
            self.Qmax_sum = 999900

        # Shunts
        for elm in self.shunts:
            if elm.active:
                Y += elm.Y
            else:
                warn(elm.name + ' is not active')

        # Static generators
        for elm in self.static_generators:

            if elm.active:
                S += elm.S

                if elm.Sprof is not None:
                    if s_profile is None:
                        s_profile = elm.Sprof  # Reverse sign convention in the load
                        s_cdf = CDF(s_profile)
                    else:
                        s_profile = s_profile.add(elm.Sprof, fill_value=0)
                        s_cdf = s_cdf + CDF(elm.Pprof)
            else:
                warn(elm.name + ' is not active')

        # Align profiles into a common column sum based on the time axis
        if s_profile is not None:
            s_profile = s_profile.sum(axis=1)

        if i_profile is not None:
            i_profile = i_profile.sum(axis=1)

        if y_profile is not None:
            y_profile = y_profile.sum(axis=1)

        return Y, I, S, V, y_profile, i_profile, s_profile, y_cdf, i_cdf, s_cdf

    def plot_profiles(self, ax=None):
        """

        @param time_idx: Master time profile: usually stored in the circuit
        @param ax: Figure axis, if not provided one will be created
        @return:
        """

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)
            show_fig = True
        else:
            show_fig = False

        for elm in self.loads:
            ax.plot(elm.Sprof.index, elm.Sprof.values.real, label=elm.name)

        for elm in self.controlled_generators + self.batteries:
            ax.plot(elm.Pprof.index, elm.Pprof.values, label=elm.name)

        for elm in self.static_generators:
            ax.plot(elm.Sprof.index, elm.Sprof.values.real, label=elm.name)

        plt.legend()
        plt.title(self.name)
        plt.ylabel('MW')
        if show_fig:
            plt.show()

    def copy(self):
        """

        :return:
        """
        bus = Bus()
        bus.name = self.name

        # Nominal voltage (kV)
        bus.Vnom = self.Vnom

        bus.vmin = self.Vmin

        bus.Vmax = self.Vmax

        bus.Zf = self.Zf

        bus.Qmin_sum = self.Qmin_sum

        bus.Qmax_sum = self.Qmax_sum

        bus.active = self.active

        # List of load s attached to this bus
        for elm in self.loads:
            bus.loads.append(elm.copy())

        # List of Controlled generators attached to this bus
        for elm in self.controlled_generators:
            bus.controlled_generators.append(elm.copy())

        # List of shunt s attached to this bus
        for elm in self.shunts:
            bus.shunts.append(elm.copy())

        # List of batteries attached to this bus
        for elm in self.batteries:
            bus.batteries.append(elm.copy())

        # List of static generators attached tot this bus
        for g in self.static_generators:
            bus.static_generators.append(g.copy())

        # Bus type
        bus.type = self.type

        # Flag to determine if the bus is a slack bus or not
        bus.is_slack = self.is_slack

        # if true, the presence of storage devices turn the bus into a Reference bus in practice
        # So that P +jQ are computed
        bus.dispatch_storage = self.dispatch_storage

        bus.x = self.x

        bus.y = self.y

        # self.graphic_obj = None

        return bus

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        self.retrieve_graphic_position()
        return [self.name, self.active, self.is_slack, self.Vnom, self.Vmin, self.Vmax, self.Zf, self.x, self.y]

    def set_state(self, t):
        """
        Set the profiles state of the objects in this bus to the value given in the profiles at the index t
        :param t: index of the profile
        :return:
        """
        for elm in self.loads:
            elm.S = elm.Sprof.values[t, 0]
            elm.I = elm.Iprof.values[t, 0]
            elm.Z = elm.Zprof.values[t, 0]

        for elm in self.static_generators:
            elm.S = elm.Sprof.values[t, 0]

        for elm in self.batteries:
            elm.P = elm.Pprof.values[t, 0]
            elm.Vset = elm.Vsetprof.values[t, 0]

        for elm in self.controlled_generators:
            elm.P = elm.Pprof.values[t, 0]
            elm.Vset = elm.Vsetprof.values[t, 0]

        for elm in self.shunts:
            elm.Y = elm.Yprof.values[t, 0]

    def retrieve_graphic_position(self):
        """
        Get the position set by the graphic object
        :return:
        """
        if self.graphic_obj is not None:
            self.x = self.graphic_obj.pos().x()
            self.y = self.graphic_obj.pos().y()


