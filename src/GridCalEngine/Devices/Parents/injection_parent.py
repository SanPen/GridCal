# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Union, List, TYPE_CHECKING
import numpy as np

from GridCalEngine.Devices.Parents.physical_device import PhysicalDevice
from GridCalEngine.Devices.Associations.association import Associations
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.enumerations import BuildStatus, DeviceType, SubObjectType
from GridCalEngine.basic_structures import CxVec
from GridCalEngine.Devices.profile import Profile
from GridCalEngine.Devices.Aggregation.facility import Facility

if TYPE_CHECKING:
    from GridCalEngine.Devices import Technology
    from GridCalEngine.Devices.types import ALL_DEV_TYPES


class InjectionParent(PhysicalDevice):
    """
    Parent class for Injections
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
        InjectionTemplate
        :param name: Name of the device
        :param idtag: unique id of the device (if None or "" a new one is generated)
        :param code: secondary code for compatibility
        :param bus: snapshot bus object
        :param cn: connectivity node
        :param active:active state
        :param Cost: cost associated with various actions (dispatch or shedding)
        :param mttf: mean time to failure (h)
        :param mttr: mean time to recovery (h)
        :param capex: capital expenditures (investment cost)
        :param opex: operational expenditures (maintainance cost)
        :param build_status: BuildStatus
        :param device_type: DeviceType
        """

        PhysicalDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=device_type)

        self._bus = bus
        self._bus_prof = Profile(default_value=bus, data_type=DeviceType.BusDevice)

        self.cn = cn

        self.active = bool(active)
        self._active_prof = Profile(default_value=self.active, data_type=bool)

        self.mttf = mttf

        self.mttr = mttr

        self.Cost = float(Cost)

        self._Cost_prof = Profile(default_value=self.Cost, data_type=float)

        self.capex = capex

        self.opex = opex

        self.build_status = build_status

        self.facility: Facility | None = None

        self.technologies: Associations = Associations(device_type=DeviceType.Technology)

        self.scalable: bool = True

        self.register(key='bus', units='', tpe=DeviceType.BusDevice, definition='Connection bus',
                      editable=False, profile_name="bus_prof")

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

        self.register(key='facility', units='', tpe=DeviceType.FacilityDevice,
                      definition='Facility where this is located', editable=True)

        self.register(key='technologies', units='p.u.', tpe=SubObjectType.Associations,
                      definition='List of technologies', display=False)

        self.register(key='scalable', units='', tpe=bool, definition='Is the load scalable?', editable=False,
                      display=False)

    @property
    def bus(self) -> Bus:
        """
        Bus
        :return: Bus
        """
        return self._bus

    @bus.setter
    def bus(self, val: Bus):
        if val is None:
            self._bus = val
            self._bus_prof.fill(value=val)
        else:
            if isinstance(val, Bus):
                self._bus = val
                self._bus_prof.fill(value=val)
            else:
                raise Exception(str(type(val)) + 'not supported to be set into a bus')

    @property
    def bus_prof(self) -> Profile:
        """
        Bus profile
        :return: Profile
        """
        return self._bus_prof

    @bus_prof.setter
    def bus_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._bus_prof = val
        elif isinstance(val, np.ndarray):
            self._bus_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a bus_prof')

    def get_bus_at(self, t_idx: Union[None, int]) -> Bus:
        """
        Returns the bus at a particular point in time
        :param t_idx: time index (None for snapshot, int for profile values)
        :return: Bus device
        """
        if t_idx is None:
            return self.bus
        else:
            return self._bus_prof[t_idx]

    def set_bus_at(self, t_idx: Union[None, int], val: Bus):
        """
        Returns the bus at a particular point in time
        :param t_idx: time index (None for snapshot, int for profile values)
        :param val: Bus object to set
        :return: Bus device
        """
        if t_idx is None:
            self.bus = val
        else:
            self._bus_prof[t_idx] = val

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
        """

        :return:
        """
        return complex(0.0, 0.0)

    def get_Sprof(self) -> CxVec:
        """

        :return:
        """
        return np.zeros(self.active_prof.size(), dtype=complex)

    def associate_technology(self, tech: Technology, val=1.0):
        """
        Associate a technology with this injection device
        :param tech:
        :param val:
        :return:
        """
        self.technologies.add_object(tech, val=val)

    @property
    def tech_list(self) -> List[ALL_DEV_TYPES]:
        """
        Bus
        :return: Bus
        """
        return self.technologies.to_list()
