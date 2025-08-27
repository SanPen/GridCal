# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.enumerations import BuildStatus, DeviceType
from VeraGridEngine.basic_structures import CxVec
from VeraGridEngine.Devices.profile import Profile
from VeraGridEngine.Devices.Parents.injection_parent import InjectionParent


class LoadParent(InjectionParent):
    """
    Template for objects that behave like loads
    """

    __slots__ = (
        'P',
        '_P_prof',
        'Q',
        '_Q_prof',

        'Pa',
        '_Pa_prof',
        'Qa',
        '_Qa_prof',

        'Pb',
        '_Pb_prof',
        'Qb',
        '_Qb_prof',

        'Pc',
        '_Pc_prof',
        'Qc',
        '_Qc_prof',
    )

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 bus: Union[Bus, None],
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

        self.Pa = float(P1)
        self._Pa_prof = Profile(default_value=self.Pa, data_type=float)

        self.Pb = float(P2)
        self._Pb_prof = Profile(default_value=self.Pb, data_type=float)

        self.Pc = float(P3)
        self._Pc_prof = Profile(default_value=self.Pc, data_type=float)

        self.Q = float(Q)
        self._Q_prof = Profile(default_value=self.Q, data_type=float)

        self.Qa = float(Q1)
        self._Qa_prof = Profile(default_value=self.Qa, data_type=float)

        self.Qb = float(Q2)
        self._Qb_prof = Profile(default_value=self.Qb, data_type=float)

        self.Qc = float(Q3)
        self._Qc_prof = Profile(default_value=self.Qc, data_type=float)

        self.register(key='P', units='MW', tpe=float, definition='Active power', profile_name='P_prof')
        self.register(key='Pa', units='MW', tpe=float, definition='Phase A active power', profile_name='Pa_prof')
        self.register(key='Pb', units='MW', tpe=float, definition='Phase B active power', profile_name='Pb_prof')
        self.register(key='Pc', units='MW', tpe=float, definition='Phase C active power', profile_name='Pc_prof')
        self.register(key='Q', units='MVAr', tpe=float, definition='Reactive power', profile_name='Q_prof')
        self.register(key='Qa', units='MVAr', tpe=float, definition='Phase A reactive power', profile_name='Qa_prof')
        self.register(key='Qb', units='MVAr', tpe=float, definition='Phase B reactive power', profile_name='Qb_prof')
        self.register(key='Qc', units='MVAr', tpe=float, definition='Phase C reactive power', profile_name='Qc_prof')

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
    def Pa_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Pa_prof

    @Pa_prof.setter
    def Pa_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Pa_prof = val
        elif isinstance(val, np.ndarray):
            self._Pa_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a pofile')

    @property
    def Pb_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Pb_prof

    @Pb_prof.setter
    def Pb_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Pb_prof = val
        elif isinstance(val, np.ndarray):
            self._Pb_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a pofile')

    @property
    def Pc_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Pc_prof

    @Pc_prof.setter
    def Pc_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Pc_prof = val
        elif isinstance(val, np.ndarray):
            self._Pc_prof.set(arr=val)
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
    def Qa_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Qa_prof

    @Qa_prof.setter
    def Qa_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Qa_prof = val
        elif isinstance(val, np.ndarray):
            self._Qa_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Q1_prof')

    @property
    def Qb_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Qb_prof

    @Qb_prof.setter
    def Qb_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Qb_prof = val
        elif isinstance(val, np.ndarray):
            self._Qb_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Q2_prof')

    @property
    def Qc_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Qc_prof

    @Qc_prof.setter
    def Qc_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Qc_prof = val
        elif isinstance(val, np.ndarray):
            self._Qc_prof.set(arr=val)
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

    def split_sequence_load_in_3_phase(self, share_a=1.0, share_b=1.0, share_c=1.0):
        """
        Initializes the 3-phase properties using the positive sequence ones
        """
        self.Pa = self.P * share_a
        self.Pb = self.P * share_b
        self.Pc = self.P * share_c

        self.Qa = self.Q * share_a
        self.Qb = self.Q * share_b
        self.Qc = self.Q * share_c

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
