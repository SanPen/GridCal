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
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.enumerations import BuildStatus, DeviceType
from GridCalEngine.Devices.profile import Profile
from GridCalEngine.Devices.Parents.injection_parent import InjectionParent


class ShuntParent(InjectionParent):
    """
    Template for objects that behave like shunts
    """

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 bus: Union[Bus, None],
                 cn: Union[ConnectivityNode, None],
                 active: bool,
                 G: float,
                 B: float,
                 G0: float,
                 B0: float,
                 Cost: float,
                 mttf: float,
                 mttr: float,
                 capex: float,
                 opex: float,
                 build_status: BuildStatus,
                 device_type: DeviceType):
        """
        ShuntLikeTemplate
        :param name: Name of the device
        :param idtag: unique id of the device (if None or "" a new one is generated)
        :param code: secondary code for compatibility
        :param bus: snapshot bus object
        :param cn: connectivity node
        :param active:active state
        :param G: positive conductance (MW @ v=1 p.u.)
        :param B: positive conductance (MVAr @ v=1 p.u.)
        :param G0: zero-sequence conductance (MW @ v=1 p.u.)
        :param B0: zero-sequence conductance (MVAr @ v=1 p.u.)
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

        self.G = G
        self._G_prof = Profile(default_value=G, data_type=float)

        self.B = B
        self._B_prof = Profile(default_value=B, data_type=float)

        self.G0 = G0
        self._G0_prof = Profile(default_value=G0, data_type=float)

        self.B0 = B0
        self._B0_prof = Profile(default_value=B0, data_type=float)

        self.register(key='G', units='MW', tpe=float, definition='Active power', profile_name='G_prof')
        self.register(key='B', units='MVAr', tpe=float, definition='Reactive power', profile_name='B_prof')
        self.register(key='G0', units='MW', tpe=float,
                      definition='Zero sequence active power of the impedance component at V=1.0 p.u.',
                      profile_name='G0_prof')
        self.register(key='B0', units='MVAr', tpe=float,
                      definition='Zero sequence reactive power of the impedance component at V=1.0 p.u.',
                      profile_name='B0_prof')

    @property
    def G_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._G_prof

    @G_prof.setter
    def G_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._G_prof = val
        elif isinstance(val, np.ndarray):
            self._G_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a G_prof')

    @property
    def B_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._B_prof

    @B_prof.setter
    def B_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._B_prof = val
        elif isinstance(val, np.ndarray):
            self._B_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a B_prof')

    @property
    def G0_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._G0_prof

    @G0_prof.setter
    def G0_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._G0_prof = val
        elif isinstance(val, np.ndarray):
            self._G0_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a G_prof')

    @property
    def B0_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._B0_prof

    @B0_prof.setter
    def B0_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._B0_prof = val
        elif isinstance(val, np.ndarray):
            self._B0_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a B_prof')

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

            # G
            y = self.G_prof.toarray()
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_1.set_title('Conductance power', fontsize=14)
            ax_1.set_ylabel('MW', fontsize=11)
            df.plot(ax=ax_1)

            # B
            y = self.B_prof.toarray()
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_2.set_title('Susceptance power', fontsize=14)
            ax_2.set_ylabel('MVAr', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

            if show_fig:
                plt.show()
