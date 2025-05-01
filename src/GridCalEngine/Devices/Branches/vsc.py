# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
from typing import List, Tuple, TYPE_CHECKING, Union
from GridCalEngine.Devices.profile import Profile
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.Devices.Parents.physical_device import PhysicalDevice
from GridCalEngine.enumerations import BuildStatus, ConverterControlType
from GridCalEngine.Devices.Parents.branch_parent import BranchParent
from GridCalEngine.Devices.Parents.editable_device import DeviceType

if TYPE_CHECKING:
    from GridCalEngine.Devices.types import BRANCH_TYPES


class VSC(PhysicalDevice):

    def __init__(self,
                 bus_dc_p: Bus | None = None,
                 bus_dc_n: Bus | None = None,
                 bus_ac: Bus | None = None,
                 cn_dc_p: ConnectivityNode | None = None,
                 cn_dc_n: ConnectivityNode | None = None,
                 cn_ac: ConnectivityNode | None = None,
                 name='VSC',
                 idtag: str | None = None,
                 code='',
                 active=True,
                 rate:float = 100.0,
                 kdp=-0.05,
                 alpha1=0.0001,
                 alpha2=0.015,
                 alpha3=0.2,
                 mttf=0.0,
                 mttr=0.0,
                 cost=100,
                 contingency_factor:float = 1.0,
                 protection_rating_factor: float = 1.4,
                 contingency_enabled=True,
                 monitor_loading=True,
                 capex=0.0,
                 opex=0.0,
                 build_status: BuildStatus = BuildStatus.Commissioned,
                 control1: ConverterControlType = ConverterControlType.Vm_dc,
                 control2: ConverterControlType = ConverterControlType.Pac,
                 control1_val: float = 1.0,
                 control2_val: float = 0.0,
                 control1_dev: Bus | BRANCH_TYPES | None = None,
                 control2_dev: Bus | BRANCH_TYPES | None = None):
        """
        Voltage source converter (VSC) with 3 terminals
        :param bus_dc_p:
        :param bus_dc_n:
        :param bus_ac:
        :param cn_dc_p:
        :param cn_dc_n:
        :param cn_ac:
        :param name:
        :param idtag:
        :param code:
        :param active:
        :param rate:
        :param kdp:
        :param k:
        :param alpha1:
        :param alpha2:
        :param alpha3:
        :param mttf:
        :param mttr:
        :param cost:
        :param contingency_factor:
        :param protection_rating_factor:
        :param contingency_enabled:
        :param monitor_loading:
        :param capex:
        :param opex:
        :param build_status:
        :param control1:
        :param control2:
        """

        PhysicalDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=DeviceType.VscDevice)

        if bus_dc_p.is_dc and bus_dc_n.is_dc and not bus_ac.is_dc:
            self._bus_dc_p = bus_dc_p
            self._bus_dc_n = bus_dc_n
            self._bus_ac = bus_ac

            self._cn_dc_p = cn_dc_p
            self._cn_dc_n = cn_dc_n
            self._cn_ac = cn_ac
        else:
            raise Exception('Impossible connecting a VSC device here. '
                            'VSC devices must be connected between 1 AC and 2 DC buses')

        self.active = bool(active)
        self._active_prof = Profile(default_value=self.active, data_type=bool)

        self.contingency_enabled: bool = contingency_enabled

        self.monitor_loading: bool = monitor_loading

        self.mttf = mttf
        self.mttr = mttr

        self.Cost = cost
        self._Cost_prof = Profile(default_value=cost, data_type=float)
        self.capex = capex
        self.opex = opex

        self.build_status = build_status

        self._rate = rate
        self._rate_prof = Profile(default_value=rate, data_type=float)

        self._contingency_factor = float(contingency_factor)
        self._contingency_factor_prof = Profile(default_value=contingency_factor, data_type=float)

        self._protection_rating_factor = float(protection_rating_factor)
        self._protection_rating_factor_prof = Profile(default_value=protection_rating_factor, data_type=float)

        self.kdp = float(kdp)
        self.alpha1 = float(alpha1)
        self.alpha2 = float(alpha2)
        self.alpha3 = float(alpha3)

        self._control1: ConverterControlType = control1
        self._control1_prof: Profile = Profile(default_value=control1, data_type=ConverterControlType)

        self._control2: ConverterControlType = control2
        self._control2_prof: Profile = Profile(default_value=control2, data_type=ConverterControlType)

        self._control1_dev: Bus | BRANCH_TYPES | None = control1_dev
        self._control1_dev_prof: Profile = Profile(default_value=control1_dev, data_type=DeviceType.BusOrBranch)

        self._control2_dev: Bus | BRANCH_TYPES | None = control2_dev
        self._control2_dev_prof: Profile = Profile(default_value=control2_dev, data_type=DeviceType.BusOrBranch)

        self._control1_val = float(control1_val)
        self._control1_val_prof: Profile = Profile(default_value=self._control1_val, data_type=float)

        self._control2_val = float(control2_val)
        self._control2_val_prof: Profile = Profile(default_value=self._control2_val, data_type=float)

        self.register(key='bus_dc_p', units="", tpe=DeviceType.BusDevice, 
                      definition='DC positive bus', editable=False)
        self.register(key='bus_dc_n', units="", tpe=DeviceType.BusDevice, 
                      definition='DC negative bus', editable=False)
        self.register(key='bus_ac', units="", tpe=DeviceType.BusDevice,
                      definition='AC bus', editable=False)

        self.register(key='cn_dc_p', units="", tpe=DeviceType.ConnectivityNodeDevice, 
                      definition='DC positive connectivity node', editable=False)
        self.register(key='cn_dc_n', units="", tpe=DeviceType.ConnectivityNodeDevice, 
                      definition='DC negative connectivity node', editable=False)
        self.register(key='cn_ac', units="", tpe=DeviceType.ConnectivityNodeDevice, 
                      definition='AC connectivity node', editable=False)

        self.register(key='active', units="", definition='Is active?', profile_name="active_prof")

        self.register(key='rate', units='MVA', definition='Nominal power', 
                      tpe=float, definition='Rating', profile_name="rate_prof")

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

        self.register(key='alpha1', units='', tpe=float,
                      definition='Losses constant parameter (IEC 62751-2 loss Correction).')
        self.register(key='alpha2', units='', tpe=float,
                      definition='Losses linear parameter (IEC 62751-2 loss Correction).')
        self.register(key='alpha3', units='', tpe=float,
                      definition='Losses quadratic parameter (IEC 62751-2 loss Correction).')

        self.register(key='kdp', units='p.u./p.u.', tpe=float, definition='Droop Power/Voltage slope.')

        self.register(key='control1', units='', tpe=ConverterControlType, profile_name="control1_prof",
                      definition='Control mode 1.')

        self.register(key='control2', units='', tpe=ConverterControlType, profile_name="control2_prof",
                      definition='Control mode 2.')

        self.register(key='control1_val', units='', tpe=float, profile_name="control1_val_prof",
                      definition='Control value 1.'
                                 'p.u. for voltage\n'
                                 'rad for angles\n'
                                 'MW for P\n'
                                 'MVAr for Q')
        self.register(key='control2_val', units='', tpe=float, profile_name="control2_val_prof",
                      definition='Control value 2.'
                                 'p.u. for voltage\n'
                                 'rad for angles\n'
                                 'MW for P\n'
                                 'MVAr for Q')

        self.register(key='control1_dev', units="", tpe=DeviceType.BusOrBranch, profile_name="control1_dev_prof",
                      definition='Controlled device, None to apply to this converter', editable=False)

        self.register(key='control2_dev', units="", tpe=DeviceType.BusOrBranch, profile_name="control2_dev_prof",
                      definition='Controlled device, None to apply to this converter', editable=False)

    @property
    def bus_dc_p(self) -> Bus:
        """
        Get the DC positive bus
        """
        return self._bus_dc_p

    @bus_dc_p.setter
    def bus_dc_p(self, value: Bus):
        if value is None:
            self._bus_dc_p = value
        else:
            if isinstance(value, Bus):
                if value.is_dc:
                    self._bus_dc_p = value
                else:
                    raise Exception('This should be a DC bus')
            else:
                raise Exception(str(type(value)) + 'not supported to be set into a _bus_dc_p')

    @property
    def bus_dc_n(self) -> Bus:
        """
        Get the DC negative bus
        """
        return self._bus_dc_n

    @bus_dc_n.setter
    def bus_dc_n(self, value: Bus):
        if value is None:
            self._bus_dc_n = value
        else:
            if isinstance(value, Bus):
                if value.is_dc:
                    self._bus_dc_n = value
                else:
                    raise Exception('This should be a DC bus')
            else:
                raise Exception(str(type(value)) + 'not supported to be set into a _bus_dc_n')

    @property
    def bus_ac(self) -> Bus:
        """
        Get the AC bus
        """
        return self._bus_ac

    @bus_ac.setter
    def bus_ac(self, value: Bus):
        if value is None:
            self._bus_ac = value
        else:
            if isinstance(value, Bus):
                if not value.is_dc:
                    self._bus_ac = value
                else:
                    raise Exception('This should be an AC bus')
            else:
                raise Exception(str(type(value)) + 'not supported to be set into a _bus_ac')

    @property
    def cn_dc_p(self) -> ConnectivityNode:
        """
        Get the DC positive connectivity node
        """
        return self._cn_dc_p

    @cn_dc_p.setter
    def cn_dc_p(self, val: ConnectivityNode):
        if val is None:
            self._cn_dc_p = val
        else:
            if isinstance(val, ConnectivityNode):
                self._cn_dc_p = val

                if self.bus_dc_p is None:
                    self.bus_dc_p = self._cn_dc_p.bus
            else:
                raise Exception(str(type(val)) + 'not supported to be set into a connectivity node from')

    @property
    def cn_dc_n(self) -> ConnectivityNode:
        """
        Get the DC negative connectivity node
        """
        return self._cn_dc_n

    @cn_dc_n.setter
    def cn_dc_n(self, val: ConnectivityNode):
        if val is None:
            self._cn_dc_n = val
        else:
            if isinstance(val, ConnectivityNode):
                self._cn_dc_n = val

                if self.bus_dc_n is None:
                    self.bus_dc_n = self._cn_dc_n.bus
            else:
                raise Exception(str(type(val)) + 'not supported to be set into a connectivity node from')

    @property
    def cn_ac(self) -> ConnectivityNode:
        """
        Get the AC connectivity node
        """
        return self._cn_ac

    @cn_ac.setter
    def cn_ac(self, val: ConnectivityNode):
        if val is None:
            self._cn_ac = val
        else:
            if isinstance(val, ConnectivityNode):
                self._cn_ac = val

                if self.bus_ac is None:
                    self.bus_ac = self._cn_ac.bus
            else:
                raise Exception(str(type(val)) + 'not supported to be set into a connectivity node from')

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
    def control1(self):
        """

        :return:
        """
        return self._control1

    @control1.setter
    def control1(self, value: ConverterControlType):
        if self.auto_update_enabled:
            if value != self.control2:
                self._control1 = value

                # Revert the control in range
                if (value in (ConverterControlType.Vm_dc, ConverterControlType.Vm_ac) and
                        not (0.9 < self.control1_val <= 1.1)):
                    self.control1_val = 1.0
        else:
            self._control1 = value

    @property
    def control1_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._control1_prof

    @control1_prof.setter
    def control1_prof(self, val: Profile | np.ndarray):
        if isinstance(val, Profile):
            self._control1_prof = val
        elif isinstance(val, np.ndarray):
            self._control1_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a profile')

    @property
    def control2(self):
        """

        :return:
        """
        return self._control2

    @control2.setter
    def control2(self, value: ConverterControlType):
        if self.auto_update_enabled:
            if value != self.control1:
                self._control2 = value

                # Revert the control in range
                if (value in (ConverterControlType.Vm_dc, ConverterControlType.Vm_ac) and
                        not (0.9 < self.control2_val <= 1.1)):
                    self.control2_val = 1.0
        else:
            self._control2 = value

    @property
    def control2_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._control2_prof

    @control2_prof.setter
    def control2_prof(self, val: Profile | np.ndarray):
        if isinstance(val, Profile):
            self._control2_prof = val
        elif isinstance(val, np.ndarray):
            self._control2_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a profile')

    @property
    def control1_val(self):
        """

        :return:
        """
        return self._control1_val

    @control1_val.setter
    def control1_val(self, value: float):
        self._control1_val = value

    @property
    def control1_val_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._control1_val_prof

    @control1_val_prof.setter
    def control1_val_prof(self, val: Profile | np.ndarray):
        if isinstance(val, Profile):
            self._control1_val_prof = val
        elif isinstance(val, np.ndarray):
            self._control1_val_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a profile')

    @property
    def control2_val(self):
        """

        :return:
        """
        return self._control2_val

    @control2_val.setter
    def control2_val(self, value: float):
        self._control2_val = value

    @property
    def control2_val_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._control2_val_prof

    @control2_val_prof.setter
    def control2_val_prof(self, val: Profile | np.ndarray):
        if isinstance(val, Profile):
            self._control2_val_prof = val
        elif isinstance(val, np.ndarray):
            self._control2_val_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a profile')

    @property
    def control1_dev(self):
        """

        :return:
        """
        return self._control1_dev

    @control1_dev.setter
    def control1_dev(self, value: Bus | BranchParent | None = None):
        self._control1_dev = value

    @property
    def control1_dev_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._control1_dev_prof

    @control1_dev_prof.setter
    def control1_dev_prof(self, val: Profile | np.ndarray):
        if isinstance(val, Profile):
            self._control1_dev_prof = val
        elif isinstance(val, np.ndarray):
            self._control1_dev_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a profile')

    @property
    def control2_dev(self):
        """

        :return:
        """
        return self._control2_dev

    @control2_dev.setter
    def control2_dev(self, value: Bus | BranchParent | None = None):
        self._control2_dev = value

    @property
    def control2_dev_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._control2_dev_prof

    @control2_dev_prof.setter
    def control2_dev_prof(self, val: Profile | np.ndarray):
        if isinstance(val, Profile):
            self._control2_dev_prof = val
        elif isinstance(val, np.ndarray):
            self._control2_dev_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a profile')

    def get_coordinates(self) -> List[Tuple[float, float, float]]:
        """
        Get the line defining coordinates
        """
        return [self.bus_dc_p.get_coordinates(), self.bus_dc_n.get_coordinates(), self.bus_ac.get_coordinates()]

    # def correct_buses_connection(self) -> None:
    #     """
    #     Fix the buses connection (from: DC, To: AC)
    #     """
    #     # the VSC must only connect from an DC to a AC bus
    #     # this connectivity sense is done to keep track with the articles that set it
    #     # from -> DC
    #     # to   -> AC
    #     # assert(bus_from.is_dc != bus_to.is_dc)
    #     if self.bus_to is not None and self.bus_from is not None:
    #         # connectivity:
    #         # for the later primitives to make sense, the "bus from" must be AC and the "bus to" must be DC
    #         if self.bus_from.is_dc and not self.bus_to.is_dc:  # correct sense
    #             pass
    #         elif not self.bus_from.is_dc and self.bus_to.is_dc:  # opposite sense, revert
    #             self.bus_from, self.bus_to = self.bus_to, self.bus_from
    #             print('Corrected the connection direction of the VSC device:', self.name)
    #         else:
    #             raise Exception('Impossible connecting a VSC device here. '
    #                             'VSC devices must be connected between AC and DC buses')
    #     else:
    #         self.bus_from = None
    #         self.bus_to = None

    def plot_profiles(self, time_series=None, my_index=0, show_fig=True):
        """
        Plot the time series results of this object
        :param time_series: TimeSeries Instance
        :param my_index: index of this object in the simulation
        :param show_fig: Show the figure?
        """

        if time_series is not None:
            fig = plt.figure(figsize=(12, 8))

            ax_1 = fig.add_subplot(211)
            ax_2 = fig.add_subplot(212, sharex=ax_1)

            x = time_series.results.time_array

            # loading
            y = time_series.results.loading.real * 100.0
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            ax_1.set_title('Loading', fontsize=14)
            ax_1.set_ylabel('Loading [%]', fontsize=11)
            df.plot(ax=ax_1)

            # losses
            y = np.abs(time_series.results.losses)
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            ax_2.set_title('Losses', fontsize=14)
            ax_2.set_ylabel('Losses [MVA]', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

        if show_fig:
            plt.show()
