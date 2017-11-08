from numpy import ones


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
