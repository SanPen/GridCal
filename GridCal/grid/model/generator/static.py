from numpy import ones


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
