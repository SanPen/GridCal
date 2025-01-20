# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Union, List, Tuple, TYPE_CHECKING
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


def set_bus(bus: Bus, cn: ConnectivityNode) -> Tuple[Bus | None, ConnectivityNode | None]:
    """

    :param bus:
    :param cn:
    :return:
    """
    if bus is None:
        if cn is None:
            return None, None
        else:
            return cn.bus, cn
    else:
        return bus, cn


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

        self._bus, self._cn = set_bus(bus, cn)

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

        self._use_kw: bool = False

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

        self.register(key='facility', units='', tpe=DeviceType.FacilityDevice,
                      definition='Facility where this is located', editable=True)

        self.register(key='technologies', units='p.u.', tpe=SubObjectType.Associations,
                      definition='List of technologies', display=False)

        self.register(key='scalable', units='', tpe=bool, definition='Is the injection scalable?', editable=False,
                      display=False)

        self.register(key='use_kw', units='', tpe=bool, definition='Consider the injections in kW and kVAr?')

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
        else:
            if isinstance(val, Bus):
                self._bus = val
            else:
                raise Exception(str(type(val)) + 'not supported to be set into a bus')

    @property
    def cn(self) -> ConnectivityNode:
        """
        Bus
        :return: Bus
        """
        return self._cn

    @cn.setter
    def cn(self, val: ConnectivityNode):
        if val is None:
            self._cn = val
        else:
            if isinstance(val, ConnectivityNode):
                self._cn = val

                if self.bus is None:
                    self.bus = self._cn.bus
            else:
                raise Exception(str(type(val)) + 'not supported to be set into a connectivity node')

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

    @property
    def use_kw(self):
        return self._use_kw

    @use_kw.setter
    def use_kw(self, val: bool):
        """
        Setter
        :param val: bool
        """
        if self.auto_update_enabled:
            if val != self._use_kw:
                self._use_kw = val

                if val:
                    # is in kW, replace MW by kW
                    for key, prp in self.registered_properties.items():
                        prp.units = (prp.units.replace("MW", "kW")
                                     .replace("MVAr", "kVAr")
                                     .replace("MVA", "kVA"))
                else:
                    # is in MW, replace kW by MW
                    for key, prp in self.registered_properties.items():
                        prp.units = (prp.units.replace( "kW", "MW")
                                     .replace( "kVAr", "MVAr")
                                     .replace( "kVA", "MVA"))
        else:
            self._use_kw = val

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
