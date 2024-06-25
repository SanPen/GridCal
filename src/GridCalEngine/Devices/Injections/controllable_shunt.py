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
from GridCalEngine.enumerations import DeviceType, BuildStatus, SubObjectType
from GridCalEngine.Devices.Parents.shunt_parent import ShuntParent
from GridCalEngine.Devices.profile import Profile


class ControllableShunt(ShuntParent):
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
                 G: float = 1e-20,
                 B: float = 1e-20,
                 G0: float = 1e-20,
                 B0: float = 1e-20,
                 vset: float = 1.0,
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
        ShuntParent.__init__(self,
                             name=name,
                             idtag=idtag,
                             code=code,
                             bus=None,
                             cn=None,
                             active=active,
                             G=G,
                             B=B,
                             G0=G0,
                             B0=B0,
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

        self._step = step
        self._step_prof = Profile(default_value=step, data_type=int)

        # Voltage module set point (p.u.)
        self.Vset = vset

        # voltage set profile for this load in p.u.
        self._Vset_prof = Profile(default_value=vset, data_type=float)

        self.register(key='is_nonlinear', units='', tpe=bool, definition='Is non-linear?')
        self.register(key='g_steps', units='', tpe=SubObjectType.Array,
                      definition='Conductance incremental steps')
        self.register(key='b_steps', units='', tpe=SubObjectType.Array,
                      definition='Susceptance incremental steps')

        self.register(key='step', units='', tpe=int, definition='Device tap step', profile_name='step_prof')

        self.register(key='Vset', units='p.u.', tpe=float,
                      definition='Set voltage. This is used for controlled shunts.', profile_name='Vset_prof')

    @property
    def step(self):
        """
        Step
        :return:
        """
        return self._step

    @step.setter
    def step(self, value: int):

        if 0 <= value < len(self._b_steps):

            self._step = int(value)

            # override value on change
            self.B = self._b_steps[self._step]
            self.G = self._g_steps[self._step]


    @property
    def Bmin(self):
        """

        :return:
        """
        return self._b_steps[0]

    @property
    def Bmax(self):
        """

        :return:
        """
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

    def set_blocks(self, n_list: list[int], b_list: list[float]):
        """
        Initialize the steps from block data
        :param n_list: list of number of blocks per step
        :param b_list: list of unit impedance block at each step
        """
        assert len(n_list) == len(b_list)
        nn = len(n_list)
        self._b_steps = np.zeros(nn)
        self._g_steps = np.zeros(nn)

        if nn > 0:
            self._b_steps[0] = n_list[0] * b_list[0]
            if nn > 1:
                for i in range(1, nn):
                    self._b_steps[i] = self._b_steps[i - 1] + n_list[i] * b_list[i]

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
    def Vset_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Vset_prof

    @Vset_prof.setter
    def Vset_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Vset_prof = val
        elif isinstance(val, np.ndarray):
            self._Vset_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Vset_prof')

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
