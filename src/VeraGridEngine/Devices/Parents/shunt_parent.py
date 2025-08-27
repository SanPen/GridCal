# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.enumerations import BuildStatus, DeviceType, SubObjectType
from VeraGridEngine.Devices.profile import Profile
from VeraGridEngine.Devices.Parents.injection_parent import InjectionParent
from VeraGridEngine.Devices.admittance_matrix import AdmittanceMatrix


class ShuntParent(InjectionParent):
    """
    Template for objects that behave like shunts
    """

    __slots__ = (
        'G',
        '_G_prof',
        'B',
        '_B_prof',

        'G0',
        '_G0_prof',
        'B0',
        '_B0_prof',

        'Ga',
        '_Ga_prof',
        'Ba',
        '_Ba_prof',

        'Gb',
        '_Gb_prof',
        'Bb',
        '_Bb_prof',

        'Gc',
        '_Gc_prof',
        'Bc',
        '_Bc_prof',

        '_ysh'
    )

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 bus: Union[Bus, None],
                 active: bool,
                 G: float,
                 G1: float,
                 G2: float,
                 G3: float,
                 B: float,
                 B1: float,
                 B2: float,
                 B3: float,
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
        :param active:active state
        :param G: positive conductance (MW @ v=1 p.u.)
        :param G1: positive conductance (MW @ v=1 p.u.)
        :param G2: positive conductance (MW @ v=1 p.u.)
        :param G3: positive conductance (MW @ v=1 p.u.)
        :param B: positive conductance (MVAr @ v=1 p.u.)
        :param B1: positive conductance (MVAr @ v=1 p.u.)
        :param B2: positive conductance (MVAr @ v=1 p.u.)
        :param B3: positive conductance (MVAr @ v=1 p.u.)
        :param G0: zero-sequence conductance (MW @ v=1 p.u.)
        :param B0: zero-sequence conductance (MVAr @ v=1 p.u.)
        :param Cost: cost associated with various actions (dispatch or shedding)
        :param mttf: mean time to failure (h)
        :param mttr: mean time to recovery (h)
        :param capex: capital expenditures (investment cost)
        :param opex: operational expenditures (maintenance cost)
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

        self.G = float(G)
        self._G_prof = Profile(default_value=self.G, data_type=float)

        self.B = float(B)
        self._B_prof = Profile(default_value=self.B, data_type=float)

        self.G0 = float(G0)
        self._G0_prof = Profile(default_value=self.G0, data_type=float)

        self.B0 = float(B0)
        self._B0_prof = Profile(default_value=self.B0, data_type=float)

        self.Ga = float(G1)
        self._Ga_prof = Profile(default_value=self.Ga, data_type=float)

        self.Gb = float(G2)
        self._Gb_prof = Profile(default_value=self.Gb, data_type=float)

        self.Gc = float(G3)
        self._Gc_prof = Profile(default_value=self.Gc, data_type=float)

        self.Ba = float(B1)
        self._Ba_prof = Profile(default_value=self.Ba, data_type=float)

        self.Bb = float(B2)
        self._Bb_prof = Profile(default_value=self.Bb, data_type=float)

        self.Bc = float(B3)
        self._Bc_prof = Profile(default_value=self.Bc, data_type=float)

        self._ysh = AdmittanceMatrix()

        self.register(key='G', units='MW', tpe=float, definition='Active power', profile_name='G_prof')
        self.register(key='G0', units='MW', tpe=float,
                      definition='Zero sequence active power of the impedance component at V=1.0 p.u.',
                      profile_name='G0_prof')
        self.register(key='Ga', units='MW', tpe=float, definition='Active power', profile_name='Ga_prof')
        self.register(key='Gb', units='MW', tpe=float, definition='Active power', profile_name='Gb_prof')
        self.register(key='Gc', units='MW', tpe=float, definition='Active power', profile_name='Gc_prof')

        self.register(key='B', units='MVAr', tpe=float, definition='Reactive power', profile_name='B_prof')
        self.register(key='B0', units='MVAr', tpe=float,
                      definition='Zero sequence reactive power of the impedance component at V=1.0 p.u.',
                      profile_name='B0_prof')
        self.register(key='Ba', units='MVAr', tpe=float, definition='Reactive power', profile_name='Ba_prof')
        self.register(key='Bb', units='MVAr', tpe=float, definition='Reactive power', profile_name='Bb_prof')
        self.register(key='Bc', units='MVAr', tpe=float, definition='Reactive power', profile_name='Bc_prof')

        self.register('ysh', units="p.u.", tpe=SubObjectType.AdmittanceMatrix,
                      definition='Shunt admittance matrix of the branch', editable=False, display=False)

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
    def Ga_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Ga_prof

    @Ga_prof.setter
    def Ga_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Ga_prof = val
        elif isinstance(val, np.ndarray):
            self._Ga_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Ga_prof')

    @property
    def Gb_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Gb_prof

    @Gb_prof.setter
    def Gb_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Gb_prof = val
        elif isinstance(val, np.ndarray):
            self._Gb_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Gb_prof')

    @property
    def Gc_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Gc_prof

    @Gc_prof.setter
    def Gc_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Gc_prof = val
        elif isinstance(val, np.ndarray):
            self._Gc_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Gc_prof')

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
    def Ba_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Ba_prof

    @Ba_prof.setter
    def Ba_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Ba_prof = val
        elif isinstance(val, np.ndarray):
            self._Ba_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Ba_prof')

    @property
    def Bb_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Bb_prof

    @Bb_prof.setter
    def Bb_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Bb_prof = val
        elif isinstance(val, np.ndarray):
            self._Bb_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Bb_prof')

    @property
    def Bc_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Bc_prof

    @Bc_prof.setter
    def Bc_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Bc_prof = val
        elif isinstance(val, np.ndarray):
            self._Bc_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Bc_prof')

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

    @property
    def ysh(self) -> AdmittanceMatrix:
        if self._ysh.size == 0:
            self.fill_3_phase_from_sequence()

        return self._ysh

    @ysh.setter
    def ysh(self, val: AdmittanceMatrix):
        if isinstance(val, AdmittanceMatrix):
            self._ysh = val
        else:
            raise ValueError(f'{val} is not a AdmittanceMatrix')

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

    def fill_3_phase_from_sequence(self):
        """
        Fill the admittance
        :return:
        """
        self.ysh = AdmittanceMatrix(3)

        y1 = self.G + 1j * self.B
        y0 = self.G0 + 1j * self.B0

        diag = (2.0 * y1 + y0) / 3.0
        off_diag = (y0 - y1) / 3.0

        yabc = np.full((3, 3), off_diag)
        np.fill_diagonal(yabc, diag)

        self.ysh.values = yabc
        self.ysh.phA = 1
        self.ysh.phB = 1
        self.ysh.phC = 1
