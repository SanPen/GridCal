# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Union, Tuple
import numpy as np

from GridCalEngine.enumerations import DeviceType, BuildStatus, SubObjectType
from GridCalEngine.Devices.Parents.shunt_parent import ShuntParent
from GridCalEngine.Devices.profile import Profile
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.basic_structures import Vec


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
                 Bmin: float = -9999.0,
                 Bmax: float = 9999.0,
                 Gmin: float = -9999.0,
                 Gmax: float = 9999.0,
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
                 control_bus: Bus = None,
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

        self.is_controlled = bool(is_controlled)
        self.is_nonlinear = bool(is_nonlinear)

        self.Bmin = Bmin
        self.Bmax = Bmax

        self.Gmin = Gmin
        self.Gmax = Gmax

        if number_of_steps > 0:
            self.g_per_step = (self.Gmin + self.Gmax) / number_of_steps
            self.b_per_step = (self.Bmin + self.Bmax) / number_of_steps
            self._active_steps = np.ones(number_of_steps, dtype=int)

        else:
            self.g_per_step = 0
            self.b_per_step = 0
            self._active_steps = np.ones(0, dtype=int)

        self._g_steps = np.full(number_of_steps, g_per_step)
        self._b_steps = np.full(number_of_steps, b_per_step)

        self._step = int(step)
        self._step_prof = Profile(default_value=self._step, data_type=int)

        self.control_bus = control_bus
        self._control_bus_prof = Profile(default_value=control_bus, data_type=DeviceType.BusDevice)

        # Voltage module set point (p.u.)
        self.Vset = float(vset)

        # voltage set profile for this load in p.u.
        self._Vset_prof = Profile(default_value=self.Vset, data_type=float)

        self.register(key='is_nonlinear', units='', tpe=bool, definition='Is non-linear?')

        self.register(key='g_steps', units='MW@v=1p.u.', tpe=SubObjectType.Array,
                      definition='Conductance steps', editable=False)

        self.register(key='b_steps', units='MVAr@v=1p.u.', tpe=SubObjectType.Array,
                      definition='Susceptance steps', editable=False)

        self.register(key='Gmax', units='MW', tpe=float,
                      definition='Maximum conductance', editable=True)

        self.register(key='Gmin', units='MW', tpe=float,
                      definition='Minimum conductance', editable=True)

        self.register(key='Bmax', units='MVAr', tpe=float,
                      definition='Maximum susceptance', editable=True)

        self.register(key='Bmin', units='MVAr', tpe=float,
                      definition='Minimum susceptance', editable=True)

        self.register(key='active_steps', units='', tpe=SubObjectType.Array,
                      definition='steps active?', editable=False)

        self.register(key='step', units='', tpe=int,
                      definition='Device step position (0~N-1)',
                      profile_name='step_prof')

        self.register(key='Vset', units='p.u.', tpe=float,
                      definition='Set voltage. This is used for controlled shunts.',
                      profile_name='Vset_prof')

    @property
    def step(self):
        """
        Step
        :return:
        """
        return self._step

    @step.setter
    def step(self, value: int):

        if self.auto_update_enabled:

            if 0 <= value < len(self._b_steps):
                self._step = int(value)

                # override value on change
                self.B = np.sum(self._b_steps[:self._step + 1] * self._active_steps[:self._step + 1])
                self.G = np.sum(self._g_steps[:self._step + 1] * self._active_steps[:self._step + 1])
        else:

            self._step = int(value)

    # @property
    # def Bmin(self):
    #     """
    #
    #     :return:
    #     """
    #     if len(self._b_steps):
    #         return self._b_steps[0] * self._active_steps[0]
    #     else:
    #         return -9999.0
    #
    # @property
    # def Bmax(self):
    #     """
    #
    #     :return:
    #     """
    #     if len(self._b_steps):
    #         return np.sum(self._b_steps * self._active_steps)
    #     else:
    #         return 9999.0

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
        # self.Gmax = value.max()
        # self.Gmin = value.min()

    @property
    def active_steps(self):
        """
        G steps
        :return:
        """
        return self._active_steps

    @active_steps.setter
    def active_steps(self, value: np.ndarray):
        assert isinstance(value, np.ndarray)
        self._active_steps = value.astype(int)

    def set_blocks(self, n_list: list[int], b_list: list[float]):
        """
        Initialize the steps from block data
        :param n_list: list of number of blocks per step
        :param b_list: list of unit impedance block at each step
        """
        assert len(n_list) == len(b_list)
        nn = len(n_list)
        self._active_steps = np.ones(nn, dtype=int)
        self._b_steps = np.zeros(nn)
        self._g_steps = np.zeros(nn)

        for i in range(nn):
            self._b_steps[i] = n_list[i] * b_list[i]

    def get_block_points(self):
        """
        Get B points for CGMES export.
        :return:
        :rtype:
        """
        return self._b_steps, self._g_steps

    def get_cumulative_b(self) -> Vec:
        """
        Get the cumulative B values
        :return:
        """
        return np.cumsum(self._b_steps * self._active_steps).astype(float)

    def get_cumulative_g(self) -> Vec:
        """
        Get the cumulative G values
        :return:
        """
        return np.cumsum(self._g_steps * self._active_steps).astype(float)

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
        # self.Bmax = value.max()
        # self.Bmin = value.min()

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
        if len(self._g_steps) == 1:
            return self._g_steps
        else:
            return np.diff(self._g_steps)

    def get_linear_b_steps(self):
        """

        :return:
        """
        if len(self._b_steps) == 1:
            return self._b_steps
        else:
            return np.diff(self._b_steps)

    @step_prof.setter
    def step_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._step_prof = val
        elif isinstance(val, np.ndarray):
            self._step_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a step_prof')

    @property
    def control_bus_prof(self) -> Profile:
        """
        Control bus profile
        :return: Profile
        """
        return self._control_bus_prof

    @control_bus_prof.setter
    def control_bus_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._control_bus_prof = val
        elif isinstance(val, np.ndarray):
            self._control_bus_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into control_bus_prof')
