# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
from typing import Union
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from GridCalEngine.enumerations import DeviceType, BuildStatus
from GridCalEngine.Devices.Parents.load_parent import InjectionParent
from GridCalEngine.Devices.profile import Profile


class ControllableShunt(InjectionParent):
    """
    Controllable Shunt
    """

    def __init__(self,
                 name='Controllable Shunt',
                 idtag: Union[None, str] = None,
                 code: str = '',
                 is_nonlinear: bool = False,
                 number_of_steps: int = 1,
                 step: int = 1,
                 g_per_step: float = 0.0,
                 b_per_step: float = 0.0,
                 Cost: float = 1200.0,
                 active: bool = True,
                 mttf: float = 0.0,
                 mttr: float = 0.0,
                 capex: float = 0.0,
                 opex: float = 0.0,
                 is_controlled: bool = True,
                 build_status: BuildStatus = BuildStatus.Commissioned):
        """
        The controllable shunt object implements the so-called ZIP model, in which the load can be
        represented by a combination of power (P), current(I), and impedance (Z).
        The sign convention is: Positive to act as a load, negative to act as a generator.
        :param name: Name of the load
        :param idtag: UUID code
        :param code: secondary ID code
        :param Cost: Cost of load shedding
        :param active: Is the load active?
        :param mttf: Mean time to failure in hours
        :param mttr: Mean time to recovery in hours
        """
        InjectionParent.__init__(self,
                                 name=name,
                                 idtag=idtag,
                                 code=code,
                                 bus=None,
                                 cn=None,
                                 active=active,
                                 Cost=Cost,
                                 mttf=mttf,
                                 mttr=mttr,
                                 capex=capex,
                                 opex=opex,
                                 build_status=build_status,
                                 device_type=DeviceType.ControllableShuntDevice)

        self.is_controlled = is_controlled
        self.is_nonlinear = is_nonlinear
        self._g_steps = np.zeros(number_of_steps)
        self._b_steps = np.zeros(number_of_steps)

        # regardless of the linear / nonlinear type, we always store
        # the cumulative values because the query is faster
        for i in range(number_of_steps):
            self._g_steps[i] = g_per_step * (i + 1)
            self._b_steps[i] = b_per_step * (i + 1)

        self.step = step
        self._step_prof = Profile(default_value=step)

        self.register(key='step', units='', tpe=int, definition='Device tap step', profile_name='step_prof')
        self.register(key='is_nonlinear', units='', tpe=bool, definition='Is non-linear?')
        self.register(key='is_controlled', units='', tpe=bool, definition='Is controlled?')

    @property
    def Bmin(self):
        return self._b_steps[0]

    @property
    def Bmax(self):
        return self._b_steps[-1]

    @property
    def g_steps(self):
        """
        G steps
        :return:
        """
        return self._g_steps

    @g_steps.setter
    def g_steps(self, value: np.ndarray):
        assert isinstance(value, np.ndarray)
        self._g_steps = value

    @property
    def b_steps(self):
        """
        B steps
        :return:
        """
        return self._b_steps

    @b_steps.setter
    def b_steps(self, value: np.ndarray):
        assert isinstance(value, np.ndarray)
        self._b_steps = value

    @property
    def G(self):
        """

        :return:
        """
        return self._g_steps[self.step - 1]

    @property
    def B(self):
        """

        :return:
        """
        return self._b_steps[self.step - 1]

    def G_at(self, t_idx):
        """

        :return:
        """
        return self._g_steps[self.step_prof[t_idx] - 1]

    def B_at(self, t_idx):
        """

        :return:
        """
        return self._b_steps[self.step_prof[t_idx] - 1]

    @property
    def step_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._step_prof

    def get_linear_g_steps(self):
        """

        :return:
        """
        return np.diff(self._g_steps)

    def get_linear_b_steps(self):
        """

        :return:
        """
        return np.diff(self._b_steps)

    @step_prof.setter
    def step_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._step_prof = val
        elif isinstance(val, np.ndarray):
            self._step_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a step_prof')

    def plot_profiles(self, time=None, show_fig=True):
        """
        Plot the time series results of this object
        :param time: array of time values
        :param show_fig: Show the figure?
        """

        if time is not None:
            fig = plt.figure(figsize=(12, 8))

            ax_1 = fig.add_subplot(211)
            # ax_2 = fig.add_subplot(212, sharex=ax_1)

            # P
            y = self.step_prof.toarray()
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_1.set_title('Steps', fontsize=14)
            ax_1.set_ylabel('', fontsize=11)
            df.plot(ax=ax_1)

            # Q
            # y = self.B_prof.toarray()
            # df = pd.DataFrame(data=y, index=time, columns=[self.name])
            # ax_2.set_title('Reactive power susceptance', fontsize=14)
            # ax_2.set_ylabel('MVAr', fontsize=11)
            # df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

            if show_fig:
                plt.show()
