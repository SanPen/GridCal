from numpy import ones


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
