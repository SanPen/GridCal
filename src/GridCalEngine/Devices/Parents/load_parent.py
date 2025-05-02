# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.enumerations import BuildStatus, DeviceType
from GridCalEngine.basic_structures import CxVec
from GridCalEngine.Devices.profile import Profile
from GridCalEngine.Devices.Parents.injection_parent import InjectionParent


class LoadParent(InjectionParent):
    """
    Template for objects that behave like loads
    """

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 bus: Union[Bus, None],
                 cn: Union[ConnectivityNode, None],
                 active: bool,
                 P: float,
                 P1: float,
                 P2: float,
                 P3: float,
                 Q: float,
                 Q1: float,
                 Q2: float,
                 Q3: float,
                 Cost: float,
                 mttf: float,
                 mttr: float,
                 capex: float,
                 opex: float,
                 build_status: BuildStatus,
                 device_type: DeviceType):
        """
        LoadLikeTemplate
        :param name: Name of the device
        :param idtag: unique id of the device (if None or "" a new one is generated)
        :param code: secondary code for compatibility
        :param bus: snapshot bus object
        :param cn: connectivity node
        :param active:active state
        :param P: active power (MW)
        :param P1: phase 1 active power (MW)
        :param P2: phase 2 active power (MW)
        :param P3: phase 3 active power (MW)
        :param Q: reactive power (MVAr)
        :param Q1: phase 1 reactive power (MVAr)
        :param Q2: phase 2 reactive power (MVAr)
        :param Q3: phase 3 reactive power (MVAr)
        :param Cost: cost associated with various actions (dispatch or shedding)
        :param mttf: mean time to failure (h)
        :param mttr: mean time to recovery (h)
        :param capex: capital expenditures (investment cost)
        :param opex: operational expenditures (maintainance cost)
        :param build_status: BuildStatus
        :param device_type: DeviceType
        """

        InjectionParent.__init__(self,
                                 name=name,
                                 idtag=idtag,
                                 code=code,
                                 bus=bus,
                                 cn=cn,
                                 active=active,
                                 Cost=Cost,
                                 mttf=mttf,
                                 mttr=mttr,
                                 capex=capex,
                                 opex=opex,
                                 build_status=build_status,
                                 device_type=device_type)

        self.P = float(P)
        self._P_prof = Profile(default_value=self.P, data_type=float)

        self.P1 = float(P1)
        self._P1_prof = Profile(default_value=self.P1, data_type=float)

        self.P2 = float(P2)
        self._P2_prof = Profile(default_value=self.P2, data_type=float)

        self.P3 = float(P3)
        self._P3_prof = Profile(default_value=self.P3, data_type=float)

        self.Q = float(Q)
        self._Q_prof = Profile(default_value=self.Q, data_type=float)

        self.Q1 = float(Q1)
        self._Q1_prof = Profile(default_value=self.Q1, data_type=float)

        self.Q2 = float(Q2)
        self._Q2_prof = Profile(default_value=self.Q2, data_type=float)

        self.Q3 = float(Q3)
        self._Q3_prof = Profile(default_value=self.Q3, data_type=float)

        self.register(key='P', units='MW', tpe=float, definition='Active power', profile_name='P_prof')
        self.register(key='P1', units='MW', tpe=float, definition='Phase 1 active power', profile_name='P1_prof')
        self.register(key='P2', units='MW', tpe=float, definition='Phase 2 active power', profile_name='P2_prof')
        self.register(key='P3', units='MW', tpe=float, definition='Phase 3 active power', profile_name='P3_prof')
        self.register(key='Q', units='MVAr', tpe=float, definition='Reactive power', profile_name='Q_prof')
        self.register(key='Q1', units='MVAr', tpe=float, definition='Phase 1 reactive power', profile_name='Q1_prof')
        self.register(key='Q2', units='MVAr', tpe=float, definition='Phase 2 reactive power', profile_name='Q2_prof')
        self.register(key='Q3', units='MVAr', tpe=float, definition='Phase 3 reactive power', profile_name='Q3_prof')

    @property
    def P_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._P_prof

    @P_prof.setter
    def P_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._P_prof = val
        elif isinstance(val, np.ndarray):
            self._P_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a pofile')

    @property
    def P1_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._P1_prof

    @P1_prof.setter
    def P1_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._P1_prof = val
        elif isinstance(val, np.ndarray):
            self._P1_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a pofile')

    @property
    def P2_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._P2_prof

    @P2_prof.setter
    def P2_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._P2_prof = val
        elif isinstance(val, np.ndarray):
            self._P2_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a pofile')

    @property
    def P3_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._P3_prof

    @P3_prof.setter
    def P3_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._P3_prof = val
        elif isinstance(val, np.ndarray):
            self._P3_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a pofile')

    @property
    def Q_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Q_prof

    @Q_prof.setter
    def Q_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Q_prof = val
        elif isinstance(val, np.ndarray):
            self._Q_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Q_prof')

    @property
    def Q1_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Q1_prof

    @Q1_prof.setter
    def Q1_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Q1_prof = val
        elif isinstance(val, np.ndarray):
            self._Q1_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Q1_prof')

    @property
    def Q2_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Q2_prof

    @Q2_prof.setter
    def Q2_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Q2_prof = val
        elif isinstance(val, np.ndarray):
            self._Q2_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Q2_prof')

    @property
    def Q3_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Q3_prof

    @Q3_prof.setter
    def Q3_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Q3_prof = val
        elif isinstance(val, np.ndarray):
            self._Q3_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Q3_prof')

    def get_S(self) -> complex:
        """

        :return:
        """
        return complex(-self.P, -self.Q)

    def get_Sprof(self) -> CxVec:
        """

        :return:
        """
        return -self.P_prof.toarray() - 1j * self.Q_prof.toarray()

    def plot_profiles(self, time=None, show_fig=True):
        """
        Plot the time series results of this object
        :param time: array of time values
        :param show_fig: Show the figure?
        """

        if time is not None:
            fig = plt.figure(figsize=(12, 8))

            ax_1 = fig.add_subplot(211)
            ax_2 = fig.add_subplot(212, sharex=ax_1)

            # P
            y = self.P_prof.toarray()
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_1.set_title('Active power', fontsize=14)
            ax_1.set_ylabel('MW', fontsize=11)
            df.plot(ax=ax_1)

            # Q
            y = self.Q_prof.toarray()
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_2.set_title('Reactive power', fontsize=14)
            ax_2.set_ylabel('MVAr', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

            if show_fig:
                plt.show()
