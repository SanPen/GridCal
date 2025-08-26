# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import pandas as pd
import numpy as np
from typing import Tuple, Union
from matplotlib import pyplot as plt

from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.enumerations import DeviceType, BuildStatus, SubObjectType
from GridCalEngine.Devices.Parents.branch_parent import BranchParent
from GridCalEngine.enumerations import HvdcControlType
from GridCalEngine.Devices.profile import Profile
from GridCalEngine.Devices.Branches.line_locations import LineLocations


def firing_angles_to_reactive_limits(P: float, alphamin: float, alphamax: float) -> Tuple[float, float]:
    """
    Convert firing angles to reactive power limits
    :param P: Active power (MW)
    :param alphamin: minimum firing angle (rad)
    :param alphamax: Maximum firing angle (rad)
    :return: Qmin (MVAr), Qmax (MVAr)
    """
    # minimum reactive power calculated under assumption of no overlap angle
    # i.e. power factor equals to tan(alpha)
    Qmin = P * np.tan(alphamin)

    # maximum reactive power calculated when overlap angle reaches max
    # value (60 deg). I.e.
    #      cos(phi) = 1/2*(cos(alpha)+cos(delta))
    #      Q = P*tan(phi)
    phi = np.arccos(0.5 * (np.cos(alphamax) + np.cos(np.deg2rad(60))))
    Qmax = P * np.tan(phi)
    # if Qmin < 0:
    #     Qmin = -Qmin
    #
    # if Qmax < 0:
    #     Qmax = -Qmax

    return Qmin, Qmax


def getFromAndToPowerAt(Pset: float, theta_f: float, theta_t: float,
                        Vnf: float, Vnt: float, v_set_f: float, v_set_t: float,
                        Sbase: float, r1: float, angle_droop: float, rate: float,
                        free: bool, in_pu: bool = False):
    """
    Compute the power and losses
    :param Pset: set power in MW
    :param theta_f: angle from (rad)
    :param theta_t: angle to (rad)
    :param Vnf: nominal voltage from (kV)
    :param Vnt: nominal voltage to (kV)
    :param v_set_f: control voltage from (p.u.)
    :param v_set_t: control voltage to (p.u.)
    :param Sbase: base power MVA
    :param r1: line resistance (ohm)
    :param angle_droop: angle droop control (MW/deg)
    :param rate: Rate (MW)
    :param free: is free to use the angle droop?
    :param in_pu: return power in per unit? otherwise the power comes in MW
    :return: Pf, Pt, losses (in MW or p.u. depending on `in_pu`)
    """

    if not free:

        # simply copy the set power value
        Pcalc = Pset

    elif free:

        # compute the angular difference in degrees (0.017453292f -> pi/180)
        # theta_f and theta_t are in rad
        # for the control not to be oscillatory, the angle difference must be the opposite (to - from)
        dtheta = np.rad2deg(theta_t - theta_f)

        # compute the desired control power flow
        Pcalc = Pset + angle_droop * dtheta  # this is in MW

        # rate truncation
        if Pcalc > rate:
            Pcalc = rate

        elif Pcalc < -rate:
            Pcalc = -rate

    else:
        Pcalc = 0

    # depending on the value of Pcalc, assign the from and to values
    if Pcalc > 0:
        # from ->  to
        I = Pcalc / (Vnf * v_set_f)  # current in kA
        loss = r1 * I * I  # losses in MW
        Pf = - Pcalc
        Pt = Pcalc - loss

    elif Pcalc < 0:
        # to -> from
        I = Pcalc / (Vnt * v_set_t)  # current in kA
        loss = r1 * I * I  # losses in MW
        Pf = - Pcalc - loss
        Pt = Pcalc  # is negative

    else:
        Pf = 0
        Pt = 0
        loss = 0

    # convert to p.u.
    if in_pu:
        Pf /= Sbase
        Pt /= Sbase
        loss /= Sbase

    return Pf, Pt, loss


class HvdcLine(BranchParent):
    """
    HvdcLine
    """
    __slots__ = (
        '_length',
        'dispatchable',
        'Pset',
        'r',
        'dc_link_voltage',
        'angle_droop',
        'loss_factor',
        'mttf',
        'mttr',
        'Vset_f',
        'Vset_t',
        'min_firing_angle_f',
        'max_firing_angle_f',
        'min_firing_angle_t',
        'max_firing_angle_t',
        'capex',
        'opex',
        'build_status',
        'control_mode',
        '_Pset_prof',
        '_active_prof',
        '_Vset_f_prof',
        '_Vset_t_prof',
        '_angle_droop_prof',
        '_locations',
    )


    def __init__(self,
                 bus_from: Bus = None,
                 bus_to: Bus = None,
                 name='HVDC Line',
                 idtag=None,
                 active=True,
                 code='',
                 rate=1.0,
                 Pset=0.0,
                 r=1e-20,
                 loss_factor=0.0,
                 Vset_f=1.0,
                 Vset_t=1.0,
                 length=1.0,
                 mttf=0.0,
                 mttr=0.0,
                 overload_cost=1000.0,
                 min_firing_angle_f=-1.0, max_firing_angle_f=1.0,
                 min_firing_angle_t=-1.0, max_firing_angle_t=1.0,
                 contingency_factor=1.0, protection_rating_factor: float = 1.4,
                 control_mode: HvdcControlType = HvdcControlType.type_1_Pset,
                 dispatchable=True, angle_droop=0,
                 capex=0, opex=0,
                 build_status: BuildStatus = BuildStatus.Commissioned,
                 dc_link_voltage: float = 200.0):
        """
        HVDC Line model
        :param bus_from: Bus from
        :param bus_to:  Bus to
        :param name: name of the line
        :param idtag:  id tag of the line
        :param active:  Is the line active?
        :param code: Secondary code for compatibility
        :param rate:  Line rate in MVA
        :param Pset:  Active power set point
        :param r: Line resistance (Ohm)
        :param loss_factor:  Losses factor (p.u.)
        :param Vset_f: Voltage set point at the "from" side
        :param Vset_t: Voltage set point at the "to" side
        :param length: line length in km
        :param mttf: Mean time to failure in hours
        :param mttr: Mean time to recovery in hours
        :param overload_cost: cost of a line overload in EUR/MW
        :param min_firing_angle_f: minimum firing angle at the "from" side
        :param max_firing_angle_f: maximum firing angle at the "from" side
        :param min_firing_angle_t: minimum firing angle at the "to" side
        :param max_firing_angle_t: maximum firing angle at the "to" side
        :param contingency_factor: factor used for contingency studies
        :param protection_rating_factor: Rating used for protection tripping limit
        :param control_mode: HvdcControlType
        :param dispatchable: is this line dispatchable?
        :param angle_droop: INELFE angle-droop constant
        :param capex: Capital expenditures (€)
        :param opex: Operational expenditures (€)
        :param build_status: BuildStatus
        :param dc_link_voltage: line voltage (only for compatibility, not used in calcs.) (kV)
        """

        BranchParent.__init__(self,
                              name=name,
                              idtag=idtag,
                              code=code,
                              bus_from=bus_from,
                              bus_to=bus_to,
                              active=active,
                              reducible=False,
                              rate=rate,
                              contingency_factor=contingency_factor,
                              protection_rating_factor=protection_rating_factor,
                              contingency_enabled=True,
                              monitor_loading=True,
                              mttf=mttf,
                              mttr=mttr,
                              build_status=build_status,
                              capex=capex,
                              opex=opex,
                              cost=overload_cost,
                              device_type=DeviceType.HVDCLineDevice)

        # line length in km
        self._length = float(length)

        self.dispatchable = bool(dispatchable)

        self.Pset = float(Pset)

        self.r = float(r)

        self.dc_link_voltage = float(dc_link_voltage)

        self.angle_droop = float(angle_droop)

        self.loss_factor = float(loss_factor)

        self.mttf = float(mttf)

        self.mttr = float(mttr)

        self.Vset_f = float(Vset_f)
        self.Vset_t = float(Vset_t)

        # converter / inverter firing angles
        self.min_firing_angle_f = float(min_firing_angle_f)
        self.max_firing_angle_f = float(max_firing_angle_f)
        self.min_firing_angle_t = float(min_firing_angle_t)
        self.max_firing_angle_t = float(max_firing_angle_t)

        self.capex = float(capex)

        self.opex = float(opex)

        self.build_status = build_status

        self.control_mode: HvdcControlType = control_mode

        self._Pset_prof: Profile = Profile(default_value=Pset, data_type=float)
        self._active_prof: Profile = Profile(default_value=active, data_type=bool)
        self._Vset_f_prof: Profile = Profile(default_value=Vset_f, data_type=float)
        self._Vset_t_prof: Profile = Profile(default_value=Vset_t, data_type=float)
        self._angle_droop_prof: Profile = Profile(default_value=angle_droop, data_type=float)

        # Line locations
        self._locations: LineLocations = LineLocations()

        self.register(key='dispatchable', units='', tpe=bool, definition='Is the line power optimizable?')

        self.register(key='control_mode', units='-', tpe=HvdcControlType, definition='Control type.')
        self.register(key='Pset', units='MW', tpe=float, definition='Set power flow.', profile_name='Pset_prof')
        self.register(key='r', units='Ohm', tpe=float, definition='line resistance.')
        self.register(key='dc_link_voltage', units='kV', tpe=float,
                      definition='line voltage (only for compatibility, not used in calcs.)')

        self.register(key='angle_droop', units='MW/deg', tpe=float, definition='Power/angle rate control',
                      profile_name='angle_droop_prof')

        self.register(key='Vset_f', units='p.u.', tpe=float, definition='Set voltage at the from side',
                      profile_name='Vset_f_prof')
        self.register(key='Vset_t', units='p.u.', tpe=float, definition='Set voltage at the to side',
                      profile_name='Vset_t_prof')

        self.register(key='min_firing_angle_f', units='rad', tpe=float,
                      definition='minimum firing angle at the "from" side.')
        self.register(key='max_firing_angle_f', units='rad', tpe=float,
                      definition='maximum firing angle at the "from" side.')
        self.register(key='min_firing_angle_t', units='rad', tpe=float,
                      definition='minimum firing angle at the "to" side.')
        self.register(key='max_firing_angle_t', units='rad', tpe=float,
                      definition='maximum firing angle at the "to" side.')

        self.register(key='length', units='km', tpe=float, definition='Length of the branch (not used for calculation)')

        self.register(key='locations', units='', tpe=SubObjectType.LineLocations, definition='', editable=False)

        self.registered_properties['Cost'].old_names.append('overload_cost')

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
    def Pset_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Pset_prof

    @Pset_prof.setter
    def Pset_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Pset_prof = val
        elif isinstance(val, np.ndarray):
            self._Pset_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Pset_prof')

    @property
    def angle_droop_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._angle_droop_prof

    @angle_droop_prof.setter
    def angle_droop_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._angle_droop_prof = val
        elif isinstance(val, np.ndarray):
            self._angle_droop_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a angle_droop_prof')

    @property
    def Vset_f_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Vset_f_prof

    @Vset_f_prof.setter
    def Vset_f_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Vset_f_prof = val
        elif isinstance(val, np.ndarray):
            self._Vset_f_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Vset_f_prof')

    @property
    def Vset_t_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Vset_t_prof

    @Vset_t_prof.setter
    def Vset_t_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Vset_t_prof = val
        elif isinstance(val, np.ndarray):
            self._Vset_t_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Vset_t_prof')

    @property
    def locations(self) -> LineLocations:
        """
        Cost profile
        :return: Profile
        """
        return self._locations

    @locations.setter
    def locations(self, val: Union[LineLocations, np.ndarray]):
        if isinstance(val, LineLocations):
            self._locations = val
        elif isinstance(val, np.ndarray):
            self._locations.set(data=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a locations')

    @property
    def length(self) -> float:
        """
        Line length in km
        :return: float
        """
        return self._length

    @length.setter
    def length(self, val: float):
        if isinstance(val, float):
            if val > 0.0:

                if self._length != 0:
                    factor = np.round(val / self._length, 6)  # new length / old length

                    self.r *= factor

                self._length = val
            else:
                # print('The length cannot be zero, ignoring value')
                pass
        else:
            raise Exception('The length must be a float value')

    def get_from_and_to_power(self, theta_f, theta_t, Sbase, in_pu=False):
        """
        Get the power set at both ends accounting for meaningful losses
        :return: power from, power to
        """
        if self.active:
            Pf, Pt, losses = getFromAndToPowerAt(Pset=self.Pset,
                                                 theta_f=theta_f,
                                                 theta_t=theta_t,
                                                 Vnf=self.bus_from.Vnom,
                                                 Vnt=self.bus_to.Vnom,
                                                 v_set_f=self.Vset_f,
                                                 v_set_t=self.Vset_t,
                                                 Sbase=Sbase,
                                                 r1=self.r,
                                                 angle_droop=self.angle_droop,
                                                 rate=self.rate,
                                                 free=self.control_mode == HvdcControlType.type_0_free,
                                                 in_pu=in_pu)

            return Pf, Pt, losses
        else:
            return 0, 0, 0

    def get_from_and_to_power_at(self, t, theta_f, theta_t, Sbase, in_pu=False):
        """
        Get the power set at both ends accounting for meaningful losses
        :return: power from, power to
        """
        if self.active_prof[t]:
            Pf, Pt, losses = getFromAndToPowerAt(Pset=self.Pset_prof[t],
                                                 theta_f=theta_f,
                                                 theta_t=theta_t,
                                                 Vnf=self.bus_from.Vnom,
                                                 Vnt=self.bus_to.Vnom,
                                                 v_set_f=self.Vset_f_prof[t],
                                                 v_set_t=self.Vset_t_prof[t],
                                                 Sbase=Sbase,
                                                 r1=self.r,
                                                 angle_droop=self.angle_droop,
                                                 rate=self.rate_prof[t],
                                                 free=self.control_mode == HvdcControlType.type_0_free,
                                                 in_pu=in_pu)

            return Pf, Pt, losses
        else:
            return 0, 0, 0

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        data = list()
        for name, properties in self.registered_properties.items():
            obj = getattr(self, name)

            if properties.tpe == DeviceType.BusDevice:
                obj = obj.idtag

            elif properties.tpe not in [str, float, int, bool]:
                obj = str(obj)

            data.append(obj)
        return data

    def get_max_bus_nominal_voltage(self):
        return max(self.bus_from.Vnom, self.bus_to.Vnom)

    def get_min_bus_nominal_voltage(self):
        return min(self.bus_from.Vnom, self.bus_to.Vnom)

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
            y = self.Pset_prof.toarray() / (self.rate_prof.toarray() + 1e-9) * 100.0
            df = pd.DataFrame(data=y, index=x, columns=[self.name])
            ax_1.set_title('Loading', fontsize=14)
            ax_1.set_ylabel('Loading [%]', fontsize=11)
            df.plot(ax=ax_1)

            # losses
            y = self.Pset_prof.toarray() * self.loss_factor
            df = pd.DataFrame(data=y, index=x, columns=[self.name])
            ax_2.set_title('Losses', fontsize=14)
            ax_2.set_ylabel('Losses [MVA]', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

        if show_fig:
            plt.show()

    def get_coordinates(self):
        """
        Get the branch defining coordinates
        """
        return [self.bus_from.get_coordinates(), self.bus_to.get_coordinates()]

    def get_q_limits(self, P: float) -> Tuple[float, float, float, float]:
        """
        Get reactive power limits
        :param P: Pset value
        :return: Qmin_f, Qmax_f, Qmin_t, Qmax_t
        """
        Qmin_f, Qmax_f = firing_angles_to_reactive_limits(P, self.min_firing_angle_f, self.max_firing_angle_f)

        Qmin_t, Qmax_t = firing_angles_to_reactive_limits(P, self.min_firing_angle_t, self.max_firing_angle_t)

        return Qmin_f, Qmax_f, Qmin_t, Qmax_t
