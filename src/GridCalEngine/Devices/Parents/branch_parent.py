# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import numpy as np
from typing import Tuple, Union, TYPE_CHECKING

from GridCalEngine import SubObjectType
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.Substation.substation import Substation
from GridCalEngine.Devices.Substation.voltage_level import VoltageLevel
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.enumerations import BuildStatus, DeviceType
from GridCalEngine.Devices.Parents.physical_device import PhysicalDevice
from GridCalEngine.Devices.Aggregation.branch_group import BranchGroup
from GridCalEngine.Devices.profile import Profile
from GridCalEngine.Devices.admittance_matrix import AdmittanceMatrix

if TYPE_CHECKING:
    from GridCalEngine.Devices.types import CONNECTION_TYPE


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


class BranchParent(PhysicalDevice):
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
                 reducible: bool,
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
                 cost: float,
                 device_type: DeviceType,
                 color: str | None = None):
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
        :param cost: Cost of overloads. Used in OPF (e/MWh)
        :param device_type: device_type (passed on)
        :param color: Color of the branch
        """

        PhysicalDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=device_type)

        # connectivity
        self._bus_from, self._cn_from = set_bus(bus_from, cn_from)
        self._bus_to, self._cn_to = set_bus(bus_to, cn_to)

        self.active = bool(active)
        self._active_prof = Profile(default_value=self.active, data_type=bool)

        self.reducible = bool(reducible)

        self.contingency_enabled: bool = contingency_enabled

        self.monitor_loading: bool = monitor_loading

        self.mttf = mttf

        self.mttr = mttr

        self.Cost = cost

        self._Cost_prof = Profile(default_value=cost, data_type=float)

        self.capex = capex

        self.opex = opex

        self.build_status = build_status

        self._ys = AdmittanceMatrix()
        self._ysh = AdmittanceMatrix()

        # line rating in MVA
        if not isinstance(rate, Union[float, int]):
            raise ValueError("Rate must be a float")
        self._rate = float(rate)
        self._rate_prof = Profile(default_value=rate, data_type=float)

        # TODO define additional rates if needed, plus register property (only here, not in init)

        if not isinstance(contingency_factor, Union[float, int]):
            raise ValueError("contingency_factor must be a float")
        self._contingency_factor = float(contingency_factor)
        self._contingency_factor_prof = Profile(default_value=contingency_factor, data_type=float)

        if not isinstance(protection_rating_factor, Union[float, int]):
            raise ValueError("protection_rating_factor must be a float")
        self._protection_rating_factor = float(protection_rating_factor)
        self._protection_rating_factor_prof = Profile(default_value=protection_rating_factor, data_type=float)

        self.color = color if color is not None else "#909090" # light gray

        # group of this branch
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

        self.register('reducible', units="", tpe=bool,
                      definition='Is the branch to be reduced by the topology preprocessor?')

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
        self.register('ys', units="p.u.", tpe=SubObjectType.AdmittanceMatrix,
                      definition='Series admittance matrix of the branch', editable=False, display=False)

        self.register('ysh', units="p.u.", tpe=SubObjectType.AdmittanceMatrix,
                      definition='Shunt admittance matrix of the branch', editable=False, display=False)
        self.register(key='color', units='', tpe=str, definition='Color to paint the element in the map diagram')

    @property
    def bus_from(self) -> Bus:
        """
        Bus
        :return: Bus
        """
        return self._bus_from

    @bus_from.setter
    def bus_from(self, val: Bus):
        if val is None:
            self._bus_from = val
        else:
            if isinstance(val, Bus):
                self._bus_from = val
            else:
                raise Exception(str(type(val)) + 'not supported to be set into a _bus_from')

    @property
    def bus_to(self) -> Bus:
        """
        Bus
        :return: Bus
        """
        return self._bus_to

    @bus_to.setter
    def bus_to(self, val: Bus):
        if val is None:
            self._bus_to = val
        else:
            if isinstance(val, Bus):
                self._bus_to = val
            else:
                raise Exception(str(type(val)) + 'not supported to be set into a _bus_to')

    @property
    def cn_from(self) -> ConnectivityNode:
        """
        Bus
        :return: Bus
        """
        return self._cn_from

    @cn_from.setter
    def cn_from(self, val: ConnectivityNode):
        if val is None:
            self._cn_from = val
        else:
            if isinstance(val, ConnectivityNode):
                self._cn_from = val

                if self.bus_from is None:
                    self.bus_from = self._cn_from.bus
            else:
                raise Exception(str(type(val)) + 'not supported to be set into a connectivity node from')

    @property
    def cn_to(self) -> ConnectivityNode:
        """
        Bus
        :return: Bus
        """
        return self._cn_to

    @cn_to.setter
    def cn_to(self, val: ConnectivityNode):
        if val is None:
            self._cn_to = val
        else:
            if isinstance(val, ConnectivityNode):
                self._cn_to = val

                if self.bus_to is None:
                    self.bus_to = self._cn_to.bus
            else:
                raise Exception(str(type(val)) + 'not supported to be set into a connectivity node to')

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

    @property
    def rate(self):
        """
        Rate (MVA)
        :return:
        """
        return self._rate

    @rate.setter
    def rate(self, val: float):
        if isinstance(val, float):
            self._rate = val
        else:
            raise ValueError(f'{val} is not a float')

    @property
    def contingency_factor(self):
        """
        Rate (MVA)
        :return:
        """
        return self._contingency_factor

    @contingency_factor.setter
    def contingency_factor(self, val: float):
        if isinstance(val, float):
            self._contingency_factor = val
        else:
            raise ValueError(f'{val} is not a float')

    @property
    def protection_rating_factor(self):
        """
        Rate (MVA)
        :return:
        """
        return self._protection_rating_factor

    @protection_rating_factor.setter
    def protection_rating_factor(self, val: float):
        if isinstance(val, float):
            self._protection_rating_factor = val
        else:
            raise ValueError(f'{val} is not a float')

    @property
    def ys(self) -> AdmittanceMatrix:
        return self._ys

    @ys.setter
    def ys(self, val: AdmittanceMatrix):
        if isinstance(val, AdmittanceMatrix):
            self._ys = val
        else:
            raise ValueError(f'{val} is not a AdmittanceMatrix')

    @property
    def ysh(self) -> AdmittanceMatrix:
        return self._ysh

    @ysh.setter
    def ysh(self, val: AdmittanceMatrix):
        if isinstance(val, AdmittanceMatrix):
            self._ysh = val
        else:
            raise ValueError(f'{val} is not a AdmittanceMatrix')

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

    def should_this_be_a_transformer(self, branch_connection_voltage_tolerance: float = 0.1,
                                     logger: Logger | None = None) -> bool:
        """
        Check if this line should be a transformer
        :param branch_connection_voltage_tolerance:
        :param logger: Logger
        :return: should this be a transformer?
        """
        if self.bus_to is not None and self.bus_from is not None:
            V1 = min(self.bus_to.Vnom, self.bus_from.Vnom)
            V2 = max(self.bus_to.Vnom, self.bus_from.Vnom)
            if V2 > 0:
                per = V1 / V2

                if per < (1.0 - branch_connection_voltage_tolerance):
                    if logger is not None:
                        logger.add_warning(
                            msg="Converted line to transformer due to excessive nominal voltage difference",
                            device=self.idtag,
                            value=per)
                    return True
                else:
                    return False
            else:
                return V1 != V2
        else:
            return False

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

    def get_from_and_to_objects(self,
                                logger: Logger = Logger(),
                                prefer_node_breaker: bool = True) -> Tuple[CONNECTION_TYPE, CONNECTION_TYPE, bool]:
        """
        Get the from and to connection objects of the branch
        :param logger: Logger object
        :param prefer_node_breaker: If true the connectivity nodes are examined first,
                                    otherwise the buses are returned right away
        :return: Object from, Object to, is it ok?
        """

        # Pick the right bus
        bus_from = self.bus_from
        bus_to = self.bus_to

        if not prefer_node_breaker:
            # if we're not preferrig node breaker, return the bus-branch buses whatever they may be
            ok = bus_from is not None and bus_to is not None
            return bus_from, bus_to, ok

        else:
            # Helper function to handle errors and return consistent output
            def handle_error(message: str) -> Tuple[CONNECTION_TYPE, CONNECTION_TYPE, bool]:
                """

                :param message:
                :return:
                """
                logger.add_error(msg=message, device=self.name)
                return None, None, False

            # Both cn_from and cn_to are provided
            if self.cn_from is not None and self.cn_to is not None:
                f = self.cn_from
                t = self.cn_to
                return f, t, True

            # cn_from is provided, cn_to is not
            if self.cn_from is not None:
                f = self.cn_from
                if bus_to is not None:
                    t = bus_to
                    return f, t, True
                return handle_error("No to connection provided!")

            # cn_to is provided, cn_from is not
            if self.cn_to is not None:
                t = self.cn_to
                if bus_from is not None:
                    f = bus_from
                    return f, t, True
                return handle_error("No from connection provided!")

            # Both cn_from and cn_to are not provided
            if bus_from is not None and bus_to is not None:
                f = bus_from
                t = bus_to
                return f, t, True

            return handle_error("Isolated branch!")
