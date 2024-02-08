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
from GridCalEngine.Core.Devices.Substation.bus import Bus
from GridCalEngine.Core.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.enumerations import BuildStatus, DeviceType
from GridCalEngine.basic_structures import CxVec
from GridCalEngine.Core.Devices.profile import Profile
from GridCalEngine.Core.Devices.Templates.injection_template import InjectionTemplate


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
        :param build_status: BuildStatus
        :param device_type: DeviceType
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
