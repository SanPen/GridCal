# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from typing import Union
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from VeraGridEngine.enumerations import DeviceType, BuildStatus
from VeraGridEngine.Devices.Parents.load_parent import InjectionParent
from VeraGridEngine.Devices.profile import Profile


class CurrentInjection(InjectionParent):
    """
    CurrentInjection
    """
    __slots__ = (
        'Ir',
        'Ii',
        '_Ir_prof',
        '_Ii_prof',

        'Ir1',
        'Ii1',
        '_Ir1_prof',
        '_Ii1_prof',

        'Ir2',
        'Ii2',
        '_Ir2_prof',
        '_Ii2_prof',

        'Ir3',
        'Ii3',
        '_Ir3_prof',
        '_Ii3_prof',

    )

    def __init__(self, name='CurrentInjection', idtag=None, code='', Ir=0.0, Ii=0.0, Cost=1200.0,
                 Ir1=0.0, Ir2=0.0, Ir3=0.0, Ii1=0.0, Ii2=0.0, Ii3=0.0,
                 active=True, mttf=0.0, mttr=0.0, capex=0, opex=0,
                 build_status: BuildStatus = BuildStatus.Commissioned):
        """
        The load object implements the so-called ZIP model, in which the load can be
        represented by a combination of power (P), current(I), and impedance (Z).
        The sign convention is: Positive to act as a load, negative to act as a generator.
        :param name: Name of the device
        :param idtag: UUID code
        :param code: secondary ID code
        :param Ir: Real current in equivalent MW
        :param Ir1: Real phase 1 current in equivalent MW
        :param Ir2: Real phase 2 current in equivalent MW
        :param Ir3: Real phase 3 current in equivalent MW
        :param Ii: Imaginary current in equivalent MVAr
        :param Ii1: Imaginary phase 1 current in equivalent MVAr
        :param Ii2: Imaginary phase 2 current in equivalent MVAr
        :param Ii3: Imaginary phase 3 current in equivalent MVAr
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
                                 active=active,
                                 Cost=Cost,
                                 mttf=mttf,
                                 mttr=mttr,
                                 capex=capex,
                                 opex=opex,
                                 build_status=build_status,
                                 device_type=DeviceType.CurrentInjectionDevice)

        self.Ir = float(Ir)
        self.Ir1 = float(Ir1)
        self.Ir2 = float(Ir2)
        self.Ir3 = float(Ir3)
        self.Ii = float(Ii)
        self.Ii1 = float(Ii1)
        self.Ii2 = float(Ii2)
        self.Ii3 = float(Ii3)

        self._Ir_prof = Profile(default_value=self.Ir, data_type=float)
        self._Ir1_prof = Profile(default_value=self.Ir1, data_type=float)
        self._Ir2_prof = Profile(default_value=self.Ir2, data_type=float)
        self._Ir3_prof = Profile(default_value=self.Ir3, data_type=float)
        self._Ii_prof = Profile(default_value=self.Ii, data_type=float)
        self._Ii1_prof = Profile(default_value=self.Ii1, data_type=float)
        self._Ii2_prof = Profile(default_value=self.Ii2, data_type=float)
        self._Ii3_prof = Profile(default_value=self.Ii3, data_type=float)

        self.register(key='Ir', units='MW', tpe=float,
                      definition='Active power of the current component at V=1.0 p.u.',
                      profile_name='Ir_prof')
        self.register(key='Ir1', units='MW', tpe=float,
                      definition='Active power of the current component at V=1.0 p.u.',
                      profile_name='Ir1_prof')
        self.register(key='Ir2', units='MW', tpe=float,
                      definition='Active power of the current component at V=1.0 p.u.',
                      profile_name='Ir2_prof')
        self.register(key='Ir3', units='MW', tpe=float,
                      definition='Active power of the current component at V=1.0 p.u.',
                      profile_name='Ir3_prof')
        self.register(key='Ii', units='MVAr', tpe=float,
                      definition='Reactive power of the current component at V=1.0 p.u.',
                      profile_name='Ii_prof')
        self.register(key='Ii1', units='MVAr', tpe=float,
                      definition='Reactive power of the current component at V=1.0 p.u.',
                      profile_name='Ii1_prof')
        self.register(key='Ii2', units='MVAr', tpe=float,
                      definition='Reactive power of the current component at V=1.0 p.u.',
                      profile_name='Ii2_prof')
        self.register(key='Ii3', units='MVAr', tpe=float,
                      definition='Reactive power of the current component at V=1.0 p.u.',
                      profile_name='Ii3_prof')

    @property
    def Ir_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Ir_prof

    @Ir_prof.setter
    def Ir_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Ir_prof = val
        elif isinstance(val, np.ndarray):
            self._Ir_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Ir_prof')

    @property
    def Ir1_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Ir1_prof

    @Ir1_prof.setter
    def Ir1_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Ir1_prof = val
        elif isinstance(val, np.ndarray):
            self._Ir1_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Ir1_prof')

    @property
    def Ir2_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Ir2_prof

    @Ir2_prof.setter
    def Ir2_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Ir2_prof = val
        elif isinstance(val, np.ndarray):
            self._Ir2_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Ir2_prof')

    @property
    def Ir3_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Ir3_prof

    @Ir3_prof.setter
    def Ir3_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Ir3_prof = val
        elif isinstance(val, np.ndarray):
            self._Ir3_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Ir3_prof')

    @property
    def Ii_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Ii_prof

    @Ii_prof.setter
    def Ii_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Ii_prof = val
        elif isinstance(val, np.ndarray):
            self._Ii_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Ii_prof')

    @property
    def Ii1_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Ii1_prof

    @Ii1_prof.setter
    def Ii1_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Ii1_prof = val
        elif isinstance(val, np.ndarray):
            self._Ii1_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Ii1_prof')

    @property
    def Ii2_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Ii2_prof

    @Ii2_prof.setter
    def Ii2_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Ii2_prof = val
        elif isinstance(val, np.ndarray):
            self._Ii2_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Ii2_prof')

    @property
    def Ii3_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Ii3_prof

    @Ii3_prof.setter
    def Ii3_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Ii3_prof = val
        elif isinstance(val, np.ndarray):
            self._Ii3_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Ii3_prof')

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
            y = self.Ir_prof.toarray()
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_1.set_title('Active power', fontsize=14)
            ax_1.set_ylabel('MW', fontsize=11)
            df.plot(ax=ax_1)

            # Q
            y = self.Ii_prof.toarray()
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_2.set_title('Reactive power', fontsize=14)
            ax_2.set_ylabel('MVAr', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

            if show_fig:
                plt.show()
