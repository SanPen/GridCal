# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Union
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from GridCalEngine.enumerations import DeviceType, BuildStatus, ExternalGridMode
from GridCalEngine.Devices.Parents.load_parent import LoadParent
from GridCalEngine.Devices.profile import Profile


class ExternalGrid(LoadParent):
    __slots__ = (
        'mode',
        'substituted_device_id',
        'Vm',
        'Va',
        '_Vm_prof',
        '_Va_prof',
    )

    def __init__(self, name='External grid', idtag=None, code='', active=True, substituted_device_id: str = '',
                 Vm=1.0, Va=0.0, P=0.0, Q=0.0,
                 P1=0.0, P2=0.0, P3=0.0, Q1=0.0, Q2=0.0, Q3=0.0,
                 mttf=0.0, mttr=0.0, mode: ExternalGridMode = ExternalGridMode.PQ,
                 capex=0, opex=0, build_status: BuildStatus = BuildStatus.Commissioned):
        """
        External grid device
        In essence, this is a slack-enforcer device
        :param name:
        :param idtag:
        :param code:
        :param active:
        :param substituted_device_id:
        :param Vm:
        :param Va:
        :param P:
        :param Q:
        :param mttf:
        :param mttr:
        :param mode:
        :param capex:
        :param opex:
        :param build_status:
        """

        LoadParent.__init__(self,
                            name=name,
                            idtag=idtag,
                            code=code,
                            bus=None,
                            active=active,
                            P=P,
                            P1=P1,
                            P2=P2,
                            P3=P3,
                            Q=Q,
                            Q1=Q1,
                            Q2=Q2,
                            Q3=Q3,
                            Cost=0,
                            mttf=mttf,
                            mttr=mttr,
                            capex=capex,
                            opex=opex,
                            build_status=build_status,
                            device_type=DeviceType.ExternalGridDevice)

        self.mode: ExternalGridMode = mode

        self.substituted_device_id: str = str(substituted_device_id)

        # Impedance in equivalent MVA
        self.Vm = float(Vm)
        self.Va = float(Va)
        self._Vm_prof = Profile(default_value=self.Vm, data_type=float)
        self._Va_prof = Profile(default_value=self.Va, data_type=float)

        self.register(key='mode', units='', tpe=ExternalGridMode,
                      definition='Operation mode of the external grid (voltage or load)')
        self.register(key='substituted_device_id', units='', tpe=str,
                      definition='idtag of the device that was substituted by this external grid equivalent')
        self.register(key='Vm', units='p.u.', tpe=float, definition='Active power', profile_name='Vm_prof')
        self.register(key='Va', units='radians', tpe=float, definition='Reactive power', profile_name='Va_prof')

    @property
    def Vm_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Vm_prof

    @Vm_prof.setter
    def Vm_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Vm_prof = val
        elif isinstance(val, np.ndarray):
            self._Vm_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Vm_prof')

    @property
    def Va_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Va_prof

    @Va_prof.setter
    def Va_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Va_prof = val
        elif isinstance(val, np.ndarray):
            self._Va_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Va_prof')

    def plot_profiles(self, time=None, show_fig=True):
        """
        Plot the time series results of this object
        :param time: array of time values
        :param show_fig: Show the figure?
        """

        if time is not None:
            fig = plt.figure(figsize=(12, 8))

            ax_1 = fig.add_subplot(211)
            ax_2 = fig.add_subplot(212)

            if self.mode == ExternalGridMode.VD:
                y1 = self.Vm_prof.toarray()
                title_1 = 'Voltage module'
                units_1 = 'p.u'

                y2 = self.Va_prof.toarray()
                title_2 = 'Voltage angle'
                units_2 = 'radians'

            elif self.mode == ExternalGridMode.PQ:
                y1 = self.P_prof.toarray()
                title_1 = 'Active Power'
                units_1 = 'MW'

                y2 = self.Q_prof.toarray()
                title_2 = 'Reactive power'
                units_2 = 'MVAr'

            else:
                raise Exception('Unrecognised external grid mode: ' + str(self.mode))

            ax_1.set_title(title_1, fontsize=14)
            ax_1.set_ylabel(units_1, fontsize=11)
            df = pd.DataFrame(data=y1, index=time, columns=[self.name])
            df.plot(ax=ax_1)

            df = pd.DataFrame(data=y2, index=time, columns=[self.name])
            ax_2.set_title(title_2, fontsize=14)
            ax_2.set_ylabel(units_2, fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

            if show_fig:
                plt.show()
