# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Union, List, TYPE_CHECKING
import numpy as np

from VeraGridEngine.Devices.Parents.physical_device import PhysicalDevice
from VeraGridEngine.Devices.Associations.association import Associations
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.enumerations import BuildStatus, DeviceType, SubObjectType, ShuntConnectionType
from VeraGridEngine.basic_structures import CxVec
from VeraGridEngine.Devices.profile import Profile
from VeraGridEngine.Devices.Aggregation.facility import Facility
from VeraGridEngine.Devices.Dynamic.dynamic_model_host import DynamicModelHost

if TYPE_CHECKING:
    from VeraGridEngine.Devices import Technology
    from VeraGridEngine.Devices.types import ALL_DEV_TYPES


class InjectionParent(PhysicalDevice):
    """
    Parent class for Injections
    """

    __slots__ = (
        '_bus',
        'active',
        '_active_prof',
        'mttf',
        'mttr',
        'Cost',
        '_Cost_prof',
        'capex',
        'opex',
        'build_status',
        'facility',
        'technologies',
        'scalable',
        'shift_key',
        '_shift_key_prof',
        '_use_kw',
        '_conn',
        '_rms_model'
    )

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 bus: Union[Bus, None],
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

        self.shift_key: float = 1.0
        self._shift_key_prof = Profile(default_value=self.shift_key, data_type=float)

        self._use_kw: bool = False

        self._conn: ShuntConnectionType = ShuntConnectionType.Star

        self._rms_model: DynamicModelHost = DynamicModelHost()

        self.register(key='bus', units='', tpe=DeviceType.BusDevice, definition='Connection bus', editable=False)

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

        self.register(key='scalable', units='', tpe=bool, definition='Is the injection scalable?')

        self.register(key='shift_key', units='', tpe=float, definition='Shift key for net transfer capacity',
                      profile_name="shift_key_prof")

        self.register(key='use_kw', units='', tpe=bool, definition='Consider the injections in kW and kVAr?')

        self.register(key='conn', units='', tpe=ShuntConnectionType,
                      definition='Connection type for 3-phase studies')

        self.register(key='rms_model', units='', tpe=SubObjectType.DynamicModelHostType,
                      definition='RMS dynamic model', display=False)

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
    def shift_key_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._shift_key_prof

    @shift_key_prof.setter
    def shift_key_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._shift_key_prof = val
        elif isinstance(val, np.ndarray):
            self._shift_key_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a shift_key_prof')

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

    @property
    def conn(self) -> ShuntConnectionType:
        return self._conn

    @conn.setter
    def conn(self, val: ShuntConnectionType):
        if isinstance(val, ShuntConnectionType):
            self._conn = val

    @property
    def rms_model(self) -> DynamicModelHost:
        return self._rms_model

    @rms_model.setter
    def rms_model(self, value: DynamicModelHost):
        if isinstance(value, DynamicModelHost):
            self._rms_model = value

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
