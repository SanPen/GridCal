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
from GridCalEngine.Core.Devices.editable_device import EditableDevice
from GridCalEngine.Core.Devices.Substation.bus import Bus
from GridCalEngine.Core.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.enumerations import BuildStatus, DeviceType
from GridCalEngine.basic_structures import CxVec
from GridCalEngine.Core.Devices.profile import Profile


class InjectionTemplate(EditableDevice):
    """
    The load object implements the so-called ZIP model, in which the load can be
    represented by a combination of power (P), current(I), and impedance (Z).

    The sign convention is: Positive to act as a load, negative to act as a generator.

    Arguments:

        **name** (str, "Load"): Name of the load

        **G** (float, 0.0): Conductance in equivalent MW

        **B** (float, 0.0): Susceptance in equivalent MVAr

        **Ir** (float, 0.0): Real current in equivalent MW

        **Ii** (float, 0.0): Imaginary current in equivalent MVAr

        **P** (float, 0.0): Active power in MW

        **Q** (float, 0.0): Reactive power in MVAr

        **G_prof** (DataFrame, None): Pandas DataFrame with the conductance profile in equivalent MW

        **B_prof** (DataFrame, None): Pandas DataFrame with the susceptance profile in equivalent MVAr

        **Ir_prof** (DataFrame, None): Pandas DataFrame with the real current profile in equivalent MW

        **Ii_prof** (DataFrame, None): Pandas DataFrame with the imaginary current profile in equivalent MVAr

        **P_prof** (DataFrame, None): Pandas DataFrame with the active power profile in equivalent MW

        **Q_prof** (DataFrame, None): Pandas DataFrame with the reactive power profile in equivalent MVAr

        **active** (bool, True): Is the load active?

        **mttf** (float, 0.0): Mean time to failure in hours

        **mttr** (float, 0.0): Mean time to recovery in hours

    """

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 bus: Union[Bus, None],
                 cn: Union[ConnectivityNode, None],
                 active: bool,
                 Cost: float,
                 mttf: float,
                 mttr: float,
                 capex: float,
                 opex: float,
                 build_status: BuildStatus,
                 device_type: DeviceType):
        """

        :param name:
        :param idtag:
        :param code:
        :param bus:
        :param cn:
        :param active:
        :param Cost:
        :param mttf:
        :param mttr:
        :param capex:
        :param opex:
        :param build_status:
        :param device_type:
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=device_type)

        self.bus = bus

        self.cn = cn

        self.active = active
        self._active_prof = Profile(default_value=active)

        self.mttf = mttf

        self.mttr = mttr

        self.Cost = Cost

        self._Cost_prof = Profile(default_value=Cost)

        self.capex = capex

        self.opex = opex

        self.build_status = build_status

        self.register(key='bus', units='', tpe=DeviceType.BusDevice, definition='Connection bus', editable=False)
        self.register(key='cn', units='', tpe=DeviceType.ConnectivityNodeDevice,
                      definition='Connection connectivity node', editable=False)

        self.register(key='active', units='', tpe=bool, definition='Is the load active?', profile_name='active_prof')

        self.register(key='mttf', units='h', tpe=float, definition='Mean time to failure')
        self.register(key='mttr', units='h', tpe=float, definition='Mean time to recovery')

        self.register(key='capex', units='e/MW', tpe=float,
                      definition='Cost of investment. Used in expansion planning.')
        self.register(key='opex', units='e/MWh', tpe=float, definition='Cost of operation. Used in expansion planning.')

        self.register(key='build_status', units='', tpe=BuildStatus,
                      definition='Branch build status. Used in expansion planning.')

        self.register(key='Cost', units='e/MWh', tpe=float, definition='Cost of not served energy. Used in OPF.',
                      profile_name='Cost_prof')

    @property
    def active_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._active_prof

    @active_prof.setter
    def active_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._active_prof = val
        elif isinstance(val, np.ndarray):
            self._active_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a active_prof')

    @property
    def Cost_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Cost_prof

    @Cost_prof.setter
    def Cost_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Cost_prof = val
        elif isinstance(val, np.ndarray):
            self._Cost_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Cost_prof')

    def get_S(self) -> complex:
        return complex(0.0, 0.0)

    def get_Sprof(self) -> CxVec:
        return np.zeros(self.active_prof.size(), dtype=complex)


class LoadLikeTemplate(InjectionTemplate):
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
                 Q: float,
                 Cost: float,
                 mttf: float,
                 mttr: float,
                 capex: float,
                 opex: float,
                 build_status: BuildStatus,
                 device_type: DeviceType):
        """

        :param name:
        :param idtag:
        :param code:
        :param bus:
        :param cn:
        :param active:
        :param Cost:
        :param mttf:
        :param mttr:
        :param capex:
        :param opex:
        :param build_status:
        :param device_type:
        """

        InjectionTemplate.__init__(self,
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

        self.P = P
        self._P_prof = Profile(default_value=P)

        self.Q = Q
        self._Q_prof = Profile(default_value=Q)

        self.register(key='P', units='MW', tpe=float, definition='Active power', profile_name='P_prof')
        self.register(key='Q', units='MVAr', tpe=float, definition='Reactive power', profile_name='Q_prof')

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

    def get_S(self) -> complex:
        """

        :return:
        """
        return complex(self.P, self.Q)

    def get_Sprof(self) -> CxVec:
        """

        :return:
        """
        return self.P_prof.toarray() + 1j * self.Q_prof.toarray()

    def get_properties_dict(self, version=3):
        """
        Get json dictionary
        :return:
        """
        if version in [2, 3]:
            return {'id': self.idtag,
                    'type': 'load',
                    'phases': 'ps',
                    'name': self.name,
                    'name_code': self.code,
                    'bus': self.bus.idtag,
                    'active': bool(self.active),
                    'p': self.P,
                    'q': self.Q,
                    'shedding_cost': self.Cost
                    }
        else:
            return dict()

    def get_profiles_dict(self, version=3):
        """

        :return:
        """

        if self.active_prof is not None:
            active_profile = self.active_prof.tolist()
            P_prof = self.P_prof.tolist()
            Q_prof = self.Q_prof.tolist()

        else:
            active_profile = list()
            P_prof = list()
            Q_prof = list()

        return {'id': self.idtag,
                'active': active_profile,
                'p': P_prof,
                'q': Q_prof}

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


class GeneratorLikeTemplate(InjectionTemplate):
    """
    Template for objects that behave like generators
    """

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 bus: Union[Bus, None],
                 cn: Union[ConnectivityNode, None],
                 active: bool,
                 P: float,
                 Pmin: float,
                 Pmax: float,
                 Cost: float,
                 mttf: float,
                 mttr: float,
                 capex: float,
                 opex: float,
                 build_status: BuildStatus,
                 device_type: DeviceType):
        """

        :param name:
        :param idtag:
        :param code:
        :param bus:
        :param cn:
        :param active:
        :param Cost:
        :param mttf:
        :param mttr:
        :param capex:
        :param opex:
        :param build_status:
        :param device_type:
        """

        InjectionTemplate.__init__(self,
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

        self.P = P
        self._P_prof = Profile(default_value=P)

        # Minimum dispatched power in MW
        self.Pmin = Pmin

        # Maximum dispatched power in MW
        self.Pmax = Pmax

        self.register(key='P', units='MW', tpe=float, definition='Active power', profile_name='P_prof')
        self.register(key='Pmin', units='MW', tpe=float, definition='Minimum active power. Used in OPF.')
        self.register(key='Pmax', units='MW', tpe=float, definition='Maximum active power. Used in OPF.')

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
            raise Exception(str(type(val)) + 'not supported to be set into a P_prof')

    def get_properties_dict(self, version=3):
        """
        Get json dictionary
        :return:
        """
        if version in [2, 3]:
            return {'id': self.idtag,
                    'type': 'load',
                    'phases': 'ps',
                    'name': self.name,
                    'name_code': self.code,
                    'bus': self.bus.idtag,
                    'active': bool(self.active),
                    'p': self.P,
                    'shedding_cost': self.Cost
                    }
        else:
            return dict()

    def get_profiles_dict(self, version=3):
        """

        :return:
        """

        if self.active_prof is not None:
            active_profile = self.active_prof.tolist()
            P_prof = self.P_prof.tolist()

        else:
            active_profile = list()
            P_prof = list()

        return {'id': self.idtag,
                'active': active_profile,
                'p': P_prof}

    def get_S(self) -> complex:
        """

        :return:
        """
        return complex(self.P, 0.0)

    def get_Sprof(self) -> CxVec:
        """

        :return:
        """
        return self.P_prof.toarray().astype(complex)


class ShuntLikeTemplate(InjectionTemplate):
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

        :param name:
        :param idtag:
        :param code:
        :param bus:
        :param cn:
        :param active:
        :param Cost:
        :param mttf:
        :param mttr:
        :param capex:
        :param opex:
        :param build_status:
        :param device_type:
        """

        InjectionTemplate.__init__(self,
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
        self._G_prof = Profile(default_value=G)

        self.B = B
        self._B_prof = Profile(default_value=B)

        self.G0 = G0
        self._G0_prof = Profile(default_value=G0)

        self.B0 = B0
        self._B0_prof = Profile(default_value=B0)

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

    def get_properties_dict(self, version=3):
        """
        Get json dictionary
        :return:
        """
        if version in [2, 3]:
            return {'id': self.idtag,
                    'type': 'load',
                    'phases': 'ps',
                    'name': self.name,
                    'name_code': self.code,
                    'bus': self.bus.idtag,
                    'active': bool(self.active),
                    'g': self.G,
                    'b': self.B,
                    'shedding_cost': self.Cost
                    }
        else:
            return dict()

    def get_profiles_dict(self, version=3):
        """

        :return:
        """

        if self.active_prof is not None:
            active_profile = self.active_prof.tolist()
            G_prof = self.G_prof.tolist()
            B_prof = self.B_prof.tolist()

        else:
            active_profile = list()
            G_prof = list()
            B_prof = list()

        return {'id': self.idtag,
                'active': active_profile,
                'g': G_prof,
                'b': B_prof}

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
