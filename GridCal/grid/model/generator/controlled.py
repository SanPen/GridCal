from numpy import ones


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
