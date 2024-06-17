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
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.enumerations import BuildStatus, DeviceType
from GridCalEngine.basic_structures import CxVec
from GridCalEngine.Devices.profile import Profile
from GridCalEngine.Devices.Parents.injection_parent import InjectionParent


class GeneratorParent(InjectionParent):
    """
    Template for objects that behave like generators
    """

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 bus: Union[Bus, None],
                 cn: Union[ConnectivityNode, None],
                 control_bus: Union[Bus, None],
                 control_cn: Union[ConnectivityNode, None],
                 active: bool,
                 P: float,
                 Pmin: float,
                 Pmax: float,
                 Cost: float,
                 mttf: float,
                 mttr: float,
                 capex: float,
                 opex: float,
                 srap_enabled: bool,
                 build_status: BuildStatus,
                 device_type: DeviceType):
        """

        :param name: Name of the device
        :param idtag: unique id of the device (if None or "" a new one is generated)
        :param code: secondary code for compatibility
        :param bus: snapshot bus object
        :param cn: connectivity node
        :param active:active state
        :param P: active power (MW)
        :param Pmin: minimum active power (MW)
        :param Pmax: maximum active power (MW)
        :param Cost: cost associated with various actions (dispatch or shedding)
        :param mttf: mean time to failure (h)
        :param mttr: mean time to recovery (h)
        :param capex: capital expenditures (investment cost)
        :param opex: operational expenditures (maintainance cost)
        :param srap_enabled: Is the unit available for SRAP participation?
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

        self.control_bus = control_bus
        self._control_bus_prof = Profile(default_value=control_bus, data_type=DeviceType.BusDevice)

        self.control_cn = control_cn

        self.P = P
        self._P_prof = Profile(default_value=P, data_type=float)

        self.srap_enabled = srap_enabled
        self._srap_enabled_prof = Profile(default_value=srap_enabled, data_type=bool)

        # Minimum dispatched power in MW
        self.Pmin = Pmin

        # Maximum dispatched power in MW
        self.Pmax = Pmax

        self.register(key='control_bus', units='', tpe=DeviceType.BusDevice, definition='Control bus',
                      editable=True, profile_name="control_bus_prof")

        self.register(key='control_cn', units='', tpe=DeviceType.ConnectivityNodeDevice,
                      definition='Control connectivity node', editable=True)
        self.register(key='P', units='MW', tpe=float, definition='Active power', profile_name='P_prof')
        self.register(key='Pmin', units='MW', tpe=float, definition='Minimum active power. Used in OPF.')
        self.register(key='Pmax', units='MW', tpe=float, definition='Maximum active power. Used in OPF.')

        self.register(key='srap_enabled', units='', tpe=bool,
                      definition='Is the unit available for SRAP participation?',
                      editable=True, profile_name="srap_enabled_prof")

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

    @property
    def srap_enabled_prof(self) -> Profile:
        """
        Control bus profile
        :return: Profile
        """
        return self._srap_enabled_prof

    @srap_enabled_prof.setter
    def srap_enabled_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._srap_enabled_prof = val
        elif isinstance(val, np.ndarray):
            self._srap_enabled_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into srap_enabled_prof')

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
