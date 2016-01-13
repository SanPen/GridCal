import numpy as np
import pandas as pd
from PyQt4.QtCore import QThread, SIGNAL

# try:
#     from power_flow import *
# except:
#     from .power_flow import *


class TimeSeries(QThread):
    """
    This class includes the necessary routines to run a time series power flow simulation
    """
    def __init__(self, power_flow_object):
        """
        Constructor
        @param power_flow_object:
        @return:
        """
        QThread.__init__(self)
        # self.pf = PowerFlow()
        self.pf = power_flow_object

        # Master time
        self.time = None

        # profiles (input)
        self.load_profiles = None
        self.gen_profiles = None

        # profiles (output)
        self.voltages = None
        self.currents = None
        self.loadings = None
        self.losses = None

        # run options
        self.auto_repeat = True
        self.tolerance = 1e-3
        self.max_iterations = 20
        self.enforce_reactive_power_limits = True

        self.cancel = False

    def set_master_time(self, time_profile):
        """
        Sets the master time profile
        @param time_profile: Array of time stamps
        @return: Nothing
        """

        '''
        The master time can simply change because the load and generation profiles will auto-repeat or curtail
        according to the master time length on the simulation routine
        '''
        self.time = time_profile

        if self.voltages is None:
            self.format_profiles()

    def set_profile(self, profiles, destination, device_type, master_structure):
        """
        Set the profiles into the destination array based on some contour conditions
        @param profiles: Input profiles
        @param destination: Array where to set the profiles
        @return: the modified destination
        """
        profile_len, profile_dev = np.shape(profiles)  # number of time steps, number of devices
        gen_len = len(master_structure)  # number of generators

        if profile_dev == gen_len:
            if self.time is not None:

                time_len = len(self.time)  # number of time steps

                if profile_len == time_len:
                    # if we reach here, the time steps and the number of devices match: Assign the profiles
                    destination = profiles.copy()
                else:
                    if profile_len > time_len:
                        # trim the profile to make it match
                        raise Warning("The generation profile is longer than the time profile. It'll be trimmed.")
                        destination = profiles[0:time_len, :].copy()

                    elif profile_len < time_len:
                        print('The profile will be repeated automatically')
                        # repeat the profile to make it match
                        # that will be done automatically
                        destination = profiles.copy()
            else:
                raise Exception('The master time profile is empty...')
        else:
            raise Exception('The profile has a different number of ' + device_type + ' than the actual ' + device_type + ' list.')


        if self.voltages is None:
            self.format_profiles()

        return destination

    def is_ready(self):
        """
        Returns if the Time series object is ready to simulate
        @return:
        """
        return not (self.time is None)

    def has_results(self):
        return not (self.voltages  is None)

    def format_profiles(self):
        tT = len(self.time)
        nbus = len(self.pf.bus)
        nbranch = len(self.pf.branch)
        self.voltages = np.zeros((tT, nbus), dtype=np.complex128)
        self.currents = np.zeros((tT, nbranch), dtype=np.complex128)
        self.loadings = np.zeros((tT, nbranch), dtype=np.complex128)
        self.losses = np.zeros((tT, nbranch), dtype=np.complex128)

    def set_loads_profile(self, profiles):
        """
        Set the load profiles
        @param profiles: input profiles as a table
        @return:
        """
        print('set_loads_profile')
        self.load_profiles = self.set_profile(profiles, self.load_profiles, 'loads', self.pf.bus)

    def set_generators_profile(self, profiles):
        """
        Setting generators profile
        @param profiles: input profiles as a table
        @return:
        """
        print('set_generators_profile')
        self.gen_profiles = self.set_profile(profiles, self.gen_profiles, 'generators', self.pf.gen)

    def get_loads_dataframe(self, columns=None):
        """
        Returns the load profile as a data frame
        Args:
            columns: names of the columns

        Returns:

        """
        if self.is_ready():
            return pd.DataFrame(data=self.load_profiles, index=self.time, columns=columns)
        else:
            return None

    def get_gen_dataframe(self, columns=None):
        """
        Returns the generation profile as a data frame
        Args:
            columns: names of the columns

        Returns:

        """
        if self.is_ready():
            return pd.DataFrame(data=self.gen_profiles, index=self.time, columns=columns)
        else:
            return None

    def end_process(self):
        self.cancel = True

    def set_run_options(self, auto_repeat=True, tol=1e-3, max_it=10, enforce_reactive_power_limits=True):
        self.auto_repeat = auto_repeat
        self.tolerance = tol
        self.max_iterations = max_it
        self.enforce_reactive_power_limits = enforce_reactive_power_limits

    def run(self):
        """
        Perform a time series run
        @param auto_repeat: Parameter that controls whether a profile is automatically repeated or not
        @return:
        """
        print('Time series: run')

        if self.time is None:
            raise Warning('The time series time profile is empty')
            return

        self.cancel = False

        tT = len(self.time)

        nbus = len(self.pf.bus)
        nbranch = len(self.pf.branch)

        # format output profiles
        self.format_profiles()

        # determine if to set every time a profile type on the condition that the profile exists
        if self.gen_profiles is None:
            setG = False
        else:
            tG, nG = np.shape(self.gen_profiles)
            setG = True

        if self.load_profiles is None:
            setL = False
        else:
            tL, nL = np.shape(self.load_profiles)
            setL = True

        # set the run options
        self.pf.set_run_options(self.pf.solver_type, self.tolerance, self.max_iterations, self.enforce_reactive_power_limits, False)

        # se the profile time indices
        t_g = 0  # generators profiles index
        t_l = 0  # loads profiles index
        self.emit(SIGNAL('progress(float)'), 0.0)
        for t in range(tT):

            # Setting the states
            if setG:
                Pgen = self.gen_profiles[t_g, :]  # this is a simple double value
                self.pf.set_generators(Pgen)

            if setL:
                S = self.load_profiles[t_l, :]  # this is a complex number
                self.pf.set_loads(np.real(S), np.imag(S))

            # run the power flow
            # tol=1e-3, max_it=10, enforce_q_limits=True, remember_last_solution
            self.pf.run()

            # gather the results (the results are ensured to have the same length as the time master)
            self.voltages[t, :] = self.pf.voltage
            self.currents[t, :] = self.pf.current
            self.loadings[t, :] = self.pf.loading
            self.losses[t, :] = self.pf.losses

            # Auto-repeating of the profiles
            if setG:
                if t_g == tG-1:
                    if not self.auto_repeat:
                        setG = False
                    t_g = 0  # reset the generators time index
                t_g += 1  # increase the profile index

            if setL:
                if t_l == tL-1:
                    if not self.auto_repeat:
                        setL = False
                    t_l = 0  # reset the loads time index
                t_l += 1  # increase the profile index

            print(t+1, ' / ', tT)

            # emmit the progress signal
            prog = ((t+1)/tT)*100
            self.emit(SIGNAL('progress(float)'), prog)

            if self.cancel:
                break

        # send the finnish signal
        self.emit(SIGNAL('done()'))


class MonteCarlo(QThread):

    def __init__(self, time_series_object):
        """
        Class constructor
        Args:
            time_series_object: TimeSeries object from which to take the data

        Returns:

        """
        self.time_series = time_series_object

    def group_data(self):
        print()