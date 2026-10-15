# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Union, List, TYPE_CHECKING, Tuple
import numpy as np

from VeraGridEngine.Devices.Parents.dynamic_parent import DynamicDevice
from VeraGridEngine.Devices.Associations.association import Associations
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.enumerations import (BuildStatus, DeviceType, SubObjectType, ShuntConnectionType, PrpCat,
                                         ParamPowerFlowReferenceType)
from VeraGridEngine.basic_structures import CxVec
from VeraGridEngine.Devices.Profiles import ProfileBool, ProfileFloat
from VeraGridEngine.Devices.Aggregation.facility import Facility
from VeraGridEngine.Devices.Parents.editable_device import get_at, GCProp

if TYPE_CHECKING:
    from VeraGridEngine.Devices.Associations.technology import Technology
    from VeraGridEngine.Devices.types import ALL_DEV_TYPES


class InjectionParent(DynamicDevice):
    """
    Parent class for Injections
    """

    __slots__ = (
        '_bus',
        '_active',
        '_active_prof',
        '_mttf',
        '_mttr',
        '_Cost',
        '_Cost_prof',
        '_capex',
        '_opex',
        'facility',
        'technologies',
        '_scalable',
        '_shift_key',
        '_longitude',
        '_latitude',
        '_shift_key_prof',
        '_use_kw',
        '_bus_pos',
        '_conn',
        "_phN",
        "_phA",
        "_phB",
        "_phC",
        'color',
    )

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(
            prop_name='bus',
            units='',
            tpe=DeviceType.BusDevice,
            definition='Connection bus',
            editable=False,
            cat=list([PrpCat.TP]),
        ),
        GCProp(
            prop_name='active',
            units='',
            tpe=bool,
            definition='Is the load active?',
            profile_name='active_prof',
            cat=[PrpCat.PF, PrpCat.OPF, PrpCat.CON],
            dyn_ref=ParamPowerFlowReferenceType.device_active,
        ),
        GCProp(
            prop_name='color',
            units='',
            tpe=str,
            definition='Color to paint the element in the map diagram',
            is_color=True,
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='mttf',
            units='h',
            tpe=float,
            definition='Mean time to failure',
            cat=[PrpCat.REL],
        ),
        GCProp(
            prop_name='mttr',
            units='h',
            tpe=float,
            definition='Mean time to recovery',
            cat=[PrpCat.REL],
        ),
        GCProp(
            prop_name='capex',
            units='e/MW',
            tpe=float,
            definition='Cost of investment. Used in expansion planning.',
            cat=[PrpCat.INV],
        ),
        GCProp(
            prop_name='opex',
            units='e/MWh',
            tpe=float,
            definition='Cost of operation. Used in expansion planning.',
            cat=[PrpCat.INV],
        ),
        GCProp(
            prop_name='Cost',
            units='e/MWh',
            tpe=float,
            definition='Cost of not served energy. Used in OPF.',
            profile_name='Cost_prof',
            cat=list([PrpCat.OPF, PrpCat.NTC]),
        ),
        GCProp(
            prop_name='facility',
            units='',
            tpe=DeviceType.FacilityDevice,
            definition='Facility where this is located',
            editable=True,
            cat=list([PrpCat.OPF, PrpCat.TP]),
        ),
        GCProp(
            prop_name='technologies',
            units='p.u.',
            tpe=SubObjectType.Associations,
            definition='Technologies associations to injections',
            display=False,
            cat=[PrpCat.OPF],
        ),
        GCProp(
            prop_name='scalable',
            units='',
            tpe=bool,
            definition='Is the injection scalable? (only for data compatibility)',
            cat=[PrpCat.OPF],
        ),
        GCProp(
            prop_name='shift_key',
            units='',
            tpe=float,
            definition='Shift key for net transfer capacity',
            profile_name="shift_key_prof",
            cat=[PrpCat.NTC],
        ),
        GCProp(
            prop_name='longitude',
            units='deg',
            tpe=float,
            definition='longitude of the injection.',
            profile_name='',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='latitude',
            units='deg',
            tpe=float,
            definition='latitude of the injection.',
            profile_name='',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='use_kw',
            units='',
            tpe=bool,
            definition='Consider the injections in kW and kVAr?',
            cat=list([PrpCat.PF, PrpCat.OPF, PrpCat.NTC]),
        ),
        GCProp(
            prop_name='conn',
            units='',
            tpe=ShuntConnectionType,
            definition='Connection type for 3-phase studies',
            cat=[PrpCat.SC, PrpCat.PF3],
            dyn_ref=ParamPowerFlowReferenceType.injection_connection_type,
        ),

        GCProp(
            prop_name='phN',
            units='',
            tpe=bool,
            definition='Is the neutral connected?',
            cat=[PrpCat.SC, PrpCat.PF3, PrpCat.EMT],
            display=False,
        ),

        GCProp(
            prop_name='phA',
            units='',
            tpe=bool,
            definition='Is phase A connected?',
            cat=[PrpCat.SC, PrpCat.PF3, PrpCat.EMT],
        ),

        GCProp(
            prop_name='phB',
            units='',
            tpe=bool,
            definition='Is phase B connected?',
            cat=[PrpCat.SC, PrpCat.PF3, PrpCat.EMT],
        ),

        GCProp(
            prop_name='phC',
            units='',
            tpe=bool,
            definition='Is phase C connected?',
            cat=[PrpCat.SC, PrpCat.PF3, PrpCat.EMT],
        ),

        GCProp(
            prop_name='bus_pos',
            units='',
            tpe=int,
            definition='Aid to locate devices on a busbar',
            display=False,
        ),
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
                 device_type: DeviceType,
                 longitude=0.0,
                 latitude=0.0,
                 color: str | None = None):
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

        DynamicDevice.__init__(self,
                               name=name,
                               idtag=idtag,
                               code=code,
                               device_type=device_type,
                               build_status=build_status)

        self._bus = bus

        self.active = bool(active)
        self._active_prof = ProfileBool(default_value=self.active)

        self.mttf = mttf

        self.mttr = mttr

        self.Cost = float(Cost)

        self._Cost_prof = ProfileFloat(default_value=self.Cost)

        self.capex = capex

        self.opex = opex

        self.facility: Facility | None = None

        self.technologies: Associations = Associations(device_type=DeviceType.Technology)

        self.scalable: bool = True

        self.shift_key: float = 1.0
        self._shift_key_prof = ProfileFloat(default_value=self.shift_key)

        self.longitude = float(longitude)
        self.latitude = float(latitude)

        self._use_kw: bool = False

        self._conn: ShuntConnectionType = ShuntConnectionType.GroundedStar

        self._phN: bool = False
        self._phA: bool = True
        self._phB: bool = True
        self._phC: bool = True

        self.bus_pos: int = 0

        self.color = color if color is not None else "#909090"  # light gray

    @property
    def bus(self) -> Bus | None:
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
    def active_prof(self) -> ProfileBool:
        """
        Cost profile
        :return: Profile
        """
        return self._active_prof

    @active_prof.setter
    def active_prof(self, val: Union[ProfileBool, np.ndarray]):
        if isinstance(val, ProfileBool):
            self._active_prof = val
        elif isinstance(val, np.ndarray):
            self._active_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a active_prof')

    def get_active_at(self, t: int | None) -> float:
        """
        :param t:
        :return:
        """
        return get_at(self.active, self.active_prof, t)

    @property
    def Cost_prof(self) -> ProfileFloat:
        """
        Cost profile
        :return: Profile
        """
        return self._Cost_prof

    @Cost_prof.setter
    def Cost_prof(self, val: Union[ProfileFloat, np.ndarray]):
        if isinstance(val, ProfileFloat):
            self._Cost_prof = val
        elif isinstance(val, np.ndarray):
            self._Cost_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Cost_prof')

    def get_Cost_at(self, t: int | None) -> float:
        """
        :param t:
        :return:
        """
        return get_at(self.Cost, self.Cost_prof, t)

    @property
    def shift_key_prof(self) -> ProfileFloat:
        """
        Cost profile
        :return: Profile
        """
        return self._shift_key_prof

    @shift_key_prof.setter
    def shift_key_prof(self, val: Union[ProfileFloat, np.ndarray]):
        if isinstance(val, ProfileFloat):
            self._shift_key_prof = val
        elif isinstance(val, np.ndarray):
            self._shift_key_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a shift_key_prof')

    def get_shift_key_at(self, t: int | None) -> float:
        """
        :param t:
        :return:
        """
        return get_at(self.shift_key, self.shift_key_prof, t)

    @property
    def use_kw(self):
        """

        :return:
        """
        return self._use_kw

    @use_kw.setter
    def use_kw(self, val: bool):
        """
        Setter
        :param val: bool
        """
        val = bool(val)
        if self.auto_update_enabled:
            if val != self._use_kw:
                self._use_kw = val
            else:
                pass
        else:
            self._use_kw = val

    @property
    def conn(self) -> ShuntConnectionType:
        """

        :return:
        """
        return self._conn

    @conn.setter
    def conn(self, val: ShuntConnectionType):
        if isinstance(val, ShuntConnectionType):
            self._conn = val

            if self.auto_update_enabled:
                if self._conn == ShuntConnectionType.NeutralStar:
                    self.phN = True
                else:
                    self.phN = False

    def get_S_with_sign(self) -> complex:
        """

        :return:
        """
        return complex(0.0, 0.0)

    def get_Sprof_with_sign(self) -> CxVec:
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

    def get_first_technology(self) -> Technology | None:
        """
        Get the first technology available
        :return: Technology
        """
        for key, association in self.technologies.data.items():
            return association.api_object
        return None

    def get_bus_pos(self, bus: Bus | None = None) -> int:
        """
        Get the bus position
        NOTE: don't remove the void bus argument
        :param bus: Bus
        :return: bus_pos
        """
        return self.bus_pos

    def try_to_find_coordinates(self) -> Tuple[float, float]:
        """
        Get the latitude and
        :return: longitude, latitude
        """
        if self.latitude == 0.0 and self.longitude == 0.0:
            lon, lat = self.bus.get_coordinates()

            if lon == 0.0 and lat == 0.0:
                lon, lat = self.bus.try_to_find_coordinates()

                return lon, lat
            else:
                return lon, lat
        else:
            return self.longitude, self.latitude

    def color_by_main_technology(self):
        """
        Set the color of the dominant technology
        """
        mx = 0.0
        col = self.color
        for _, val in self.technologies.data.items():
            if val.value > mx:
                col = val.api_object.color
        self.color = col

    def color_by_main_owner(self):
        """
        Set the color of the dominant owner
        """
        mx = 0.0
        col = self.color
        for _, val in self.owners.data.items():
            if val.value > mx:
                col = val.api_object.color
        self.color = col

    # Scalar property accessors coerce assignments to the declared schema types.

    @property
    def active(self) -> bool:
        """
        Get ``active``.

        :return: bool
        """
        return self._active

    @active.setter
    def active(self, val: bool) -> None:
        """
        Set ``active``.

        :param val: Value to assign.
        :return: None
        """
        self._active = bool(val)

    @property
    def mttf(self) -> float:
        """
        Get ``mttf``.

        :return: float
        """
        return self._mttf

    @mttf.setter
    def mttf(self, val: float) -> None:
        """
        Set ``mttf``.

        :param val: Value to assign.
        :return: None
        """
        self._mttf = float(val)

    @property
    def mttr(self) -> float:
        """
        Get ``mttr``.

        :return: float
        """
        return self._mttr

    @mttr.setter
    def mttr(self, val: float) -> None:
        """
        Set ``mttr``.

        :param val: Value to assign.
        :return: None
        """
        self._mttr = float(val)

    @property
    def capex(self) -> float:
        """
        Get ``capex``.

        :return: float
        """
        return self._capex

    @capex.setter
    def capex(self, val: float) -> None:
        """
        Set ``capex``.

        :param val: Value to assign.
        :return: None
        """
        self._capex = float(val)

    @property
    def opex(self) -> float:
        """
        Get ``opex``.

        :return: float
        """
        return self._opex

    @opex.setter
    def opex(self, val: float) -> None:
        """
        Set ``opex``.

        :param val: Value to assign.
        :return: None
        """
        self._opex = float(val)

    @property
    def Cost(self) -> float:
        """
        Get ``Cost``.

        :return: float
        """
        return self._Cost

    @Cost.setter
    def Cost(self, val: float) -> None:
        """
        Set ``Cost``.

        :param val: Value to assign.
        :return: None
        """
        self._Cost = float(val)

    @property
    def scalable(self) -> bool:
        """
        Get ``scalable``.

        :return: bool
        """
        return self._scalable

    @scalable.setter
    def scalable(self, val: bool) -> None:
        """
        Set ``scalable``.

        :param val: Value to assign.
        :return: None
        """
        self._scalable = bool(val)

    @property
    def shift_key(self) -> float:
        """
        Get ``shift_key``.

        :return: float
        """
        return self._shift_key

    @shift_key.setter
    def shift_key(self, val: float) -> None:
        """
        Set ``shift_key``.

        :param val: Value to assign.
        :return: None
        """
        self._shift_key = float(val)

    @property
    def longitude(self) -> float:
        """
        Get ``longitude``.

        :return: float
        """
        return self._longitude

    @longitude.setter
    def longitude(self, val: float) -> None:
        """
        Set ``longitude``.

        :param val: Value to assign.
        :return: None
        """
        self._longitude = float(val)

    @property
    def latitude(self) -> float:
        """
        Get ``latitude``.

        :return: float
        """
        return self._latitude

    @latitude.setter
    def latitude(self, val: float) -> None:
        """
        Set ``latitude``.

        :param val: Value to assign.
        :return: None
        """
        self._latitude = float(val)

    @property
    def bus_pos(self) -> int:
        """
        Get ``bus_pos``.

        :return: int
        """
        return self._bus_pos

    @bus_pos.setter
    def bus_pos(self, val: int) -> None:
        """
        Set ``bus_pos``.

        :param val: Value to assign.
        :return: None
        """
        self._bus_pos = int(val)

    @property
    def phN(self) -> bool:
        """
        :return:
        """
        return self._phN

    @phN.setter
    def phN(self, val: bool):
        if isinstance(val, bool):
            self._phN = val
        else:
            raise ValueError(f'{val} is not an bool.')

    @property
    def phA(self) -> bool:
        """
        :return:
        """
        return self._phA

    @phA.setter
    def phA(self, val: bool):
        if isinstance(val, bool):
            self._phA = val
        else:
            raise ValueError(f'{val} is not an bool.')

    @property
    def phB(self) -> bool:
        """
        :return:
        """
        return self._phB

    @phB.setter
    def phB(self, val: bool):
        if isinstance(val, bool):
            self._phB = val
        else:
            raise ValueError(f'{val} is not an bool.')

    @property
    def phC(self) -> bool:
        """
        :return:
        """
        return self._phC

    @phC.setter
    def phC(self, val: bool):
        if isinstance(val, bool):
            self._phC = val
        else:
            raise ValueError(f'{val} is not an bool.')
