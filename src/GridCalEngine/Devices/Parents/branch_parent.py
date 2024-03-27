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

import numpy as np
from typing import Tuple, Union

from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.Substation.substation import Substation
from GridCalEngine.Devices.Substation.voltage_level import VoltageLevel
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.enumerations import BuildStatus
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType
from GridCalEngine.Devices.Aggregation.branch_group import BranchGroup
from GridCalEngine.Devices.profile import Profile


class BranchParent(EditableDevice):
    """
    This class serves to represent the basic branch
    All other branches inherit from this one
    """

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 bus_from: Union[Bus, None],
                 bus_to: Union[Bus, None],
                 cn_from: Union[ConnectivityNode, None],
                 cn_to: Union[ConnectivityNode, None],
                 active: bool,
                 rate: float,
                 contingency_factor: float,
                 protection_rating_factor: float,
                 contingency_enabled: bool,
                 monitor_loading: bool,
                 mttf: float,
                 mttr: float,
                 build_status: BuildStatus,
                 capex: float,
                 opex: float,
                 Cost: float,
                 device_type: DeviceType):
        """

        :param name: name of the branch
        :param idtag: UUID code
        :param code: secondary id
        :param bus_from: Name of the bus at the "from" side
        :param bus_to: Name of the bus at the "to" side
        :param cn_from: Name of the connectivity node at the "from" side
        :param cn_to: Name of the connectivity node at the "to" side
        :param active: Is active?
        :param rate: Branch rating (MVA)
        :param contingency_factor: Factor to multiply the rating in case of contingency
        :param contingency_enabled: Enabled contingency (Legacy, better use contingency objects)
        :param monitor_loading: Monitor loading (Legacy)
        :param mttf: Mean time to failure
        :param mttr: Mean time to repair
        :param build_status: Branch build status. Used in expansion planning.
        :param capex: Cost of investment. (e/MW)
        :param opex: Cost of operation. (e/MWh)
        :param Cost: Cost of overloads. Used in OPF (e/MWh)
        :param device_type: device_type (passed on)
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=device_type)

        # connectivity
        self.bus_from = bus_from
        self._bus_from_prof = Profile(default_value=bus_from)

        self.bus_to = bus_to
        self._bus_to_prof = Profile(default_value=bus_to)

        self.cn_from = cn_from
        self.cn_to = cn_to

        self.active = active
        self._active_prof = Profile(default_value=active)

        self.contingency_enabled: bool = contingency_enabled

        self.monitor_loading: bool = monitor_loading

        self.mttf = mttf

        self.mttr = mttr

        self.Cost = Cost

        self._Cost_prof = Profile(default_value=Cost)

        self.capex = capex

        self.opex = opex

        self.build_status = build_status

        # line rating in MVA
        self.rate = rate
        self._rate_prof = Profile(default_value=rate)

        self.contingency_factor = contingency_factor
        self._contingency_factor_prof = Profile(default_value=contingency_factor)

        self.protection_rating_factor = protection_rating_factor
        self._protection_rating_factor_prof = Profile(default_value=protection_rating_factor)

        # List of measurements
        self.group: Union[BranchGroup, None] = None

        self.register('bus_from', units="", tpe=DeviceType.BusDevice,
                      definition='Name of the bus at the "from" side', editable=False)

        self.register('bus_to', units="", tpe=DeviceType.BusDevice,
                      definition='Name of the bus at the "to" side', editable=False)

        self.register('cn_from', units="", tpe=DeviceType.ConnectivityNodeDevice,
                      definition='Name of the connectivity node at the "from" side', editable=False)

        self.register('cn_to', units="", tpe=DeviceType.ConnectivityNodeDevice,
                      definition='Name of the connectivity node at the "to" side', editable=False)

        self.register('active', units="", tpe=bool, definition='Is active?', profile_name="active_prof")

        self.register('rate', units="MVA", tpe=float, definition='Thermal rating power', profile_name="rate_prof")
        self.register('contingency_factor', units="p.u.", tpe=float,
                      definition='Rating multiplier for contingencies', profile_name="contingency_factor_prof")

        self.register('protection_rating_factor', units="p.u.", tpe=float,
                      definition='Rating multiplier that indicates the maximum flow before the protections tripping',
                      profile_name="protection_rating_factor_prof")

        self.register('monitor_loading', units="", tpe=bool,
                      definition="Monitor this device loading for OPF, NTC or contingency studies.")
        self.register('mttf', units="h", tpe=float, definition="Mean time to failure")
        self.register('mttr', units="h", tpe=float, definition="Mean time to repair")

        self.register('Cost', units="e/MWh", tpe=float,
                      definition="Cost of overloads. Used in OPF", profile_name="Cost_prof")

        self.register('build_status', units="", tpe=BuildStatus,
                      definition="Branch build status. Used in expansion planning.")
        self.register('capex', units="e/MW", tpe=float, definition="Cost of investment. Used in expansion planning.")
        self.register('opex', units="e/MWh", tpe=float, definition="Cost of operation. Used in expansion planning.")
        self.register('group', units="", tpe=DeviceType.BranchGroupDevice,
                      definition="Group where this branch belongs")

    @property
    def bus_from_prof(self) -> Profile:
        """
        Bus profile
        :return: Profile
        """
        return self._bus_from_prof

    @bus_from_prof.setter
    def bus_from_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._bus_from_prof = val
        elif isinstance(val, np.ndarray):
            self._bus_from_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a bus_from_prof')

    @property
    def bus_to_prof(self) -> Profile:
        """
        Bus profile
        :return: Profile
        """
        return self._bus_to_prof

    @bus_to_prof.setter
    def bus_to_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._bus_to_prof = val
        elif isinstance(val, np.ndarray):
            self._bus_to_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a bus_to_prof')

    def get_bus_from_at(self, t_idx: Union[None, int]) -> Bus:
        """
        Returns the bus_from at a particular point in time
        :param t_idx: time index (None for snapshot, int for profile values)
        :return: Bus device
        """
        if t_idx is None:
            return self.bus_from
        else:
            return self._bus_from_prof[t_idx]

    def set_bus_from_at(self, t_idx: Union[None, int], val: Bus):
        """
        Returns the bus from at a particular point in time
        :param t_idx: time index (None for snapshot, int for profile values)
        :param val: Bus object to set
        :return: Bus device
        """
        if t_idx is None:
            self.bus_from = val
        else:
            self._bus_from_prof[t_idx] = val

    def get_bus_to_at(self, t_idx: Union[None, int]) -> Bus:
        """
        Returns the bus_to at a particular point in time
        :param t_idx: time index (None for snapshot, int for profile values)
        :return: Bus device
        """
        if t_idx is None:
            return self.bus_to
        else:
            return self._bus_to_prof[t_idx]

    def set_bus_to_at(self, t_idx: Union[None, int], val: Bus):
        """
        Returns the bus to at a particular point in time
        :param t_idx: time index (None for snapshot, int for profile values)
        :param val: Bus object to set
        :return: Bus device
        """
        if t_idx is None:
            self.bus_to = val
        else:
            self._bus_to_prof[t_idx] = val

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
    def rate_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._rate_prof

    @rate_prof.setter
    def rate_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._rate_prof = val
        elif isinstance(val, np.ndarray):
            self._rate_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a rate_prof')

    @property
    def contingency_factor_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._contingency_factor_prof

    @contingency_factor_prof.setter
    def contingency_factor_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._contingency_factor_prof = val
        elif isinstance(val, np.ndarray):
            self._contingency_factor_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a contingency_factor_prof')

    @property
    def protection_rating_factor_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._protection_rating_factor_prof

    @protection_rating_factor_prof.setter
    def protection_rating_factor_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._protection_rating_factor_prof = val
        elif isinstance(val, np.ndarray):
            self._protection_rating_factor_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a protection_rating_factor_prof')

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

    def get_max_bus_nominal_voltage(self):
        """
        GEt the maximum nominal voltage
        :return:
        """
        return max(self.bus_from.Vnom, self.bus_to.Vnom)

    def get_min_bus_nominal_voltage(self):
        """
        Get the minimum nominal voltage
        :return:
        """
        return min(self.bus_from.Vnom, self.bus_to.Vnom)

    def get_sorted_buses_voltages(self):
        """
        Get the sorted bus voltages
        :return: high voltage, low voltage
        """
        bus_f_v = self.bus_from.Vnom
        bus_t_v = self.bus_to.Vnom
        if bus_f_v > bus_t_v:
            return bus_f_v, bus_t_v
        else:
            return bus_t_v, bus_f_v

    def get_virtual_taps(self) -> Tuple[float, float]:
        """
        Get the branch virtual taps

        The virtual taps generate when a line nominal voltage ate the two connection buses differ

        Returns:

            **tap_f** (float, 1.0): Virtual tap at the *from* side

            **tap_t** (float, 1.0): Virtual tap at the *to* side

        """
        # resolve how the transformer is actually connected and set the virtual taps
        bus_f_v = self.bus_from.Vnom
        bus_t_v = self.bus_to.Vnom

        if bus_f_v == bus_t_v:
            return 1.0, 1.0
        else:
            if bus_f_v > 0.0 and bus_t_v > 0.0:
                return 1.0, bus_f_v / bus_t_v
            else:
                return 1.0, 1.0

    def get_coordinates(self):
        """
        Get the line defining coordinates
        """
        return [self.bus_from.get_coordinates(), self.bus_to.get_coordinates()]

    def convertible_to_vsc(self):
        """
        Is this line convertible to VSC?
        :return:
        """
        if self.bus_to is not None and self.bus_from is not None:
            # connectivity:
            # for the later primitives to make sense, the "bus from" must be AC and the "bus to" must be DC
            if self.bus_from.is_dc and not self.bus_to.is_dc:  # this is the correct sense
                return True
            elif not self.bus_from.is_dc and self.bus_to.is_dc:  # opposite sense, revert
                return True
            else:
                return False
        else:
            return False

    @property
    def Vf(self) -> float:
        """
        Get the voltage "from" (kV)
        :return: get the nominal voltage from
        """
        return self.bus_from.Vnom

    @property
    def Vt(self) -> float:
        """
        Get the voltage "to" (kV)
        :return: get the nominal voltage to
        """
        return self.bus_to.Vnom

    def should_this_be_a_transformer(self, branch_connection_voltage_tolerance: float = 0.1) -> bool:
        """

        :param branch_connection_voltage_tolerance:
        :return:
        """
        if self.bus_to is not None and self.bus_from is not None:
            V1 = min(self.bus_to.Vnom, self.bus_from.Vnom)
            V2 = max(self.bus_to.Vnom, self.bus_from.Vnom)
            if V2 > 0:
                per = V1 / V2
                return per < (1.0 - branch_connection_voltage_tolerance)
            else:
                return V1 != V2
        else:
            return False

    def apply_template(self, obj, Sbase, logger: Logger):
        """
        Virtual function to apply template
        :param obj:
        :param Sbase
        :param logger
        :return:
        """
        pass

    def get_substation_from(self) -> Union[Substation, None]:
        """
        Try to get the substation at the From side
        :return: Union[Substation, None]
        """
        if self.bus_from is not None:
            return self.bus_from.substation
        else:
            return None

    def get_substation_to(self) -> Union[Substation, None]:
        """
        Try to get the substation at the To side
        :return: Union[Substation, None]
        """
        if self.bus_to is not None:
            return self.bus_to.substation
        else:
            return None

    def get_voltage_level_from(self) -> Union[VoltageLevel, None]:
        """
        Try to get the voltage level at the From side
        :return: Union[VoltageLevel, None]
        """
        if self.bus_from is not None:
            return self.bus_from.voltage_level
        else:
            return None

    def get_voltage_level_to(self) -> Union[VoltageLevel, None]:
        """
        Try to get the voltage level at the To side
        :return: Union[VoltageLevel, None]
        """
        if self.bus_to is not None:
            return self.bus_to.voltage_level
        else:
            return None
