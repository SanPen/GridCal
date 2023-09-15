# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
import pandas as pd
from typing import Union, List, Tuple
from matplotlib import pyplot as plt
from GridCalEngine.basic_structures import Logger, Vec, IntVec, Mat
from GridCalEngine.Core.Devices.editable_device import EditableDevice, GCProp
from GridCalEngine.Core.Devices.enumerations import DeviceType, BuildStatus
from GridCalEngine.Core.Devices.Aggregation.technology import Technology


def make_default_q_curve(Snom: float, Qmin: float, Qmax: float, n: int = 3) -> Mat:
    """
    Compute the generator capability curve
    :param Snom: Nominal power
    :param Qmin: Minimum reactive power
    :param Qmax: Maximum reactive power
    :param n: number of points, at least 3
    :return: Array of points [(P1, Qmin1, Qmax1), (P2, Qmin2, Qmax2), ...]
    """
    assert (n > 2)
    pts = np.zeros((n, 3))
    s2 = Snom * Snom

    Qmax2 = Qmax if Qmax < Snom else Snom
    Qmin2 = Qmin if Qmin > -Snom else -Snom

    # Compute the intersections of the Qlimits with the natural curve
    p0_max = np.sqrt(s2 - Qmax2 * Qmax2)
    p0_min = np.sqrt(s2 - Qmin2 * Qmin2)
    p0 = min(p0_max, p0_min)  # pick the lower limit as the starting point for sampling

    pts[1:, 0] = np.linspace(p0, Snom, n - 1)
    pts[0, 0] = 0
    pts[0, 1] = Qmin2
    pts[0, 2] = Qmax2

    for i in range(1, n):
        p2 = pts[i, 0] * pts[i, 0]  # P^2
        q = np.sqrt(s2 - p2)  # point that naturally matches Q = sqrt(S^2 - P^2)

        # assign the natural point if it does not violates the limits imposes, else set the limit
        qmin = -q if -q > Qmin2 else Qmin2
        qmax = q if q < Qmax2 else Qmax2

        # Enforce that Qmax > Qmin
        if qmax < qmin:
            qmax = qmin
        if qmin > qmax:
            qmin = qmax

        # Assign the points
        pts[i, 1] = qmin
        pts[i, 2] = qmax

    return pts


def get_q_limits(q_points: Mat, p: Vec) -> Tuple[Vec, Vec]:
    """
    Get the reactive power limits
    :param q_points: Array of points [(P1, Qmin1, Qmax1), (P2, Qmin2, Qmax2), ...]
    :param p: active power value (or array)
    :return:
    """
    all_p = q_points[:, 0]
    all_qmin = q_points[:, 1]
    all_qmax = q_points[:, 2]

    qmin = np.interp(p, all_p, all_qmin)
    qmax = np.interp(p, all_p, all_qmax)

    return qmin, qmax


class Generator(EditableDevice):

    def __init__(self,
                 name='gen',
                 idtag: Union[str, None] = None,
                 code: str = '',
                 P: float = 0.0,
                 power_factor: float = 0.8,
                 vset: float = 1.0,
                 is_controlled=True,
                 Qmin: float = -9999,
                 Qmax: float = 9999,
                 Snom: float = 9999,
                 power_prof: Union[Vec, None] = None,
                 power_factor_prof: Union[Vec, None] = None,
                 vset_prof: Union[Vec, None] = None,
                 active_prof: Union[Vec, None] = None,
                 active: bool = True,
                 Pmin: float = 0.0,
                 Pmax: float = 9999.0,
                 Cost: float = 1.0,
                 Sbase: float = 100,
                 enabled_dispatch=True,
                 mttf: float = 0.0,
                 mttr: float = 0.0,
                 technology: Technology = None,
                 q_points=None,
                 use_reactive_power_curve=False,
                 r1: float = 1e-20,
                 x1: float = 1e-20,
                 r0: float = 1e-20,
                 x0: float = 1e-20,
                 r2: float = 1e-20,
                 x2: float = 1e-20,
                 capex: float = 0,
                 opex: float = 0,
                 build_status: BuildStatus = BuildStatus.Commissioned,
                 Cost_prof: Union[Vec, None] = None,
                 Cost2_prof: Union[Vec, None] = None,
                 Cost0_prof: Union[Vec, None] = None):
        """
        Voltage controlled generator. This generators supports several reactive power
        :param name: Name of the generator
        :param idtag: UUID code
        :param code: secondary code
        :param P: Active power in MW
        :param power_factor: Power factor
        :param vset: Voltage setpoint in per unit
        :param is_controlled: Is the generator voltage controlled?
        :param Qmin: Minimum reactive power in MVAr
        :param Qmax: Maximum reactive power in MVAr
        :param Snom: Nominal apparent power in MVA
        :param power_prof: active power profile in MW (array)
        :param power_factor_prof: power factor profile (array)
        :param vset_prof: voltage setpoint profile in per unit
        :param active_prof:
        :param active: Is the generator active?
        :param Pmin:
        :param Pmax:
        :param Cost:
        :param Sbase: Nominal apparent power in MVA
        :param enabled_dispatch: Is the generator enabled for OPF?
        :param mttf: Mean time to failure in hours
        :param mttr: Mean time to recovery in hours
        :param technology:  Instance of technology to use
        :param q_points: list of reactive capability curve points [(P1, Qmin1, Qmax1), (P2, Qmin2, Qmax2), ...]
        :param use_reactive_power_curve: Use the reactive power curve? otherwise use the plain old limits
        :param r1:
        :param x1:
        :param r0:
        :param x0:
        :param r2:
        :param x2:
        :param capex:
        :param opex:
        :param build_status:
        :param Cost_prof:
        :param Cost2_prof:
        :param Cost0_prof:
        """
        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                active=active,
                                device_type=DeviceType.GeneratorDevice)

        self.bus: "Bus" = None

        self.active_prof = active_prof

        self.mttf = mttf

        self.mttr = mttr

        self.technology = technology

        # is the device active for active power dispatch?
        self.enabled_dispatch = enabled_dispatch

        # positive sequence resistance
        self.R1 = r1

        # positive sequence reactance
        self.X1 = x1

        # zero sequence resistance
        self.R0 = r0

        # zero sequence reactance
        self.X0 = x0

        # negative sequence resistance
        self.R2 = r2

        # negative sequence reactance
        self.X2 = x2

        # Power (MVA)
        self.P = P

        # Power factor
        self.Pf = power_factor

        # voltage set profile for this load in p.u.
        self.Pf_prof = power_factor_prof

        # If this generator is voltage controlled it produces a PV node, otherwise the node remains as PQ
        self.is_controlled = is_controlled

        # Nominal power in MVA (also the machine base)
        self._Snom = Snom

        # Minimum dispatched power in MW
        self.Pmin = Pmin

        # Maximum dispatched power in MW
        self.Pmax = Pmax

        # power profile for this load in MW
        self.P_prof = power_prof

        # Voltage module set point (p.u.)
        self.Vset = vset

        # voltage set profile for this load in p.u.
        self.Vset_prof = vset_prof

        self.use_reactive_power_curve = use_reactive_power_curve

        # minimum reactive power in MVAr
        self.qmin_set = Qmin

        # Maximum reactive power in MVAr
        self.qmax_set = Qmax

        if q_points is not None:
            self.q_points = np.array(q_points)
            self.custom_q_points = True
        else:
            self.q_points = make_default_q_curve(self.Snom, self.qmin_set, self.qmax_set)
            self.custom_q_points = False

        self.Cost2 = 0.0  # Cost of operation €/MW²
        self.Cost = Cost  # Cost of operation €/MW
        self.Cost0 = 0.0  # Cost of operation €/MW

        self.StartupCost = 0.0
        self.ShutdownCost = 0.0
        self.MinTimeUp = 0.0
        self.MinTimeDown = 0.0
        self.RampUp = 1e20
        self.RampDown = 1e20

        self.Cost2_prof = Cost2_prof
        self.Cost_prof = Cost_prof
        self.Cost0_prof = Cost0_prof

        self.capex = capex

        self.opex = opex

        self.build_status = build_status

        # Dynamic vars
        # self.Ra = Ra
        # self.Xa = Xa
        # self.Xd = Xd
        # self.Xq = Xq
        # self.Xdp = Xdp
        # self.Xqp = Xqp
        # self.Xdpp = Xdpp
        # self.Xqpp = Xqpp
        # self.Td0p = Td0p
        # self.Tq0p = Tq0p
        # self.Td0pp = Td0pp
        # self.Tq0pp = Tq0pp
        # self.H = H
        # self.speed_volt = speed_volt
        # self.base_mva = base_mva  # machine base MVA

        # system base power MVA
        self.Sbase = Sbase

        self.register(key='name', units='', tpe=str, definition='Name of the generator')
        self.register(key='idtag', units='', tpe=str, definition='Unique ID', )
        self.register(key='code', units='', tpe=str, definition='Secondary ID')
        self.register(key='bus', units='', tpe=DeviceType.BusDevice, definition='Connection bus name')
        self.register(key='active', units='', tpe=bool, definition='Is the generator active?',
                      profile_name='active_prof')
        self.register(key='is_controlled', units='', tpe=bool, definition='Is this generator voltage-controlled?')
        self.register(key='P', units='MW', tpe=float, definition='Active power', profile_name='P_prof')
        self.register(key='Pf', units='', tpe=float,
                      definition='Power factor (cos(fi)). This is used for non-controlled generators.',
                      profile_name='Pf_prof')
        self.register(key='Vset', units='p.u.', tpe=float,
                      definition='Set voltage. This is used for controlled generators.', profile_name='Vset_prof')
        self.register(key='Snom', units='MVA', tpe=float, definition='Nomnial power.')
        self.register(key='Qmin', units='MVAr', tpe=float, definition='Minimum reactive power.')
        self.register(key='Qmax', units='MVAr', tpe=float, definition='Maximum reactive power.')
        self.register(key='use_reactive_power_curve', units='', tpe=bool,
                      definition='Use the reactive power capability curve?')
        self.register(key='Pmin', units='MW', tpe=float, definition='Minimum active power. Used in OPF.')
        self.register(key='Pmax', units='MW', tpe=float, definition='Maximum active power. Used in OPF.')
        self.register(key='R1', units='p.u.', tpe=float, definition='Total positive sequence resistance.')
        self.register(key='X1', units='p.u.', tpe=float, definition='Total positive sequence reactance.')
        self.register(key='R0', units='p.u.', tpe=float, definition='Total zero sequence resistance.')
        self.register(key='X0', units='p.u.', tpe=float, definition='Total zero sequence reactance.')
        self.register(key='R2', units='p.u.', tpe=float, definition='Total negative sequence resistance.')
        self.register(key='X2', units='p.u.', tpe=float, definition='Total negative sequence reactance.')
        self.register(key='Cost2', units='e/MWh²', tpe=float, definition='Generation quadratic cost. Used in OPF.',
                      profile_name='Cost2_prof')
        self.register(key='Cost', units='e/MWh', tpe=float, definition='Generation linear cost. Used in OPF.',
                      profile_name='Cost_prof')
        self.register(key='Cost0', units='e/h', tpe=float, definition='Generation constant cost. Used in OPF.',
                      profile_name='Cost0_prof')
        self.register(key='StartupCost', units='e/h', tpe=float, definition='Generation start-up cost. Used in OPF.')
        self.register(key='ShutdownCost', units='e/h', tpe=float, definition='Generation shut-down cost. Used in OPF.')
        self.register(key='MinTimeUp', units='h', tpe=float,
                      definition='Minimum time that the generator has to be on when started. Used in OPF.')
        self.register(key='MinTimeDown', units='h', tpe=float,
                      definition='Minimum time that the generator has to be off when shut down. Used in OPF.')
        self.register(key='RampUp', units='MW/h', tpe=float,
                      definition='Maximum amount of generation increase per hour.')
        self.register(key='RampDown', units='MW/h', tpe=float,
                      definition='Maximum amount of generation decrease per hour.')
        self.register(key='capex', units='e/MW', tpe=float,
                      definition='Cost of investment. Used in expansion planning.')
        self.register(key='opex', units='e/MWh', tpe=float,
                      definition='Cost of maintenance. Used in expansion planning.')
        self.register(key='build_status', units='', tpe=BuildStatus,
                      definition='Branch build status. Used in expansion planning.')
        self.register(key='enabled_dispatch', units='', tpe=bool, definition='Enabled for dispatch? Used in OPF.')
        self.register(key='mttf', units='h', tpe=float, definition='Mean time to failure')
        self.register(key='mttr', units='h', tpe=float, definition='Mean time to recovery')

    def copy(self):
        """
        Make a deep copy of this object
        :return: Copy of this object
        """

        # make a new instance (separated object in memory)
        gen = Generator()

        gen.name = self.name

        # Power (MVA), MVA = kV * kA
        gen.P = self.P

        # is the generator active?
        gen.active = self.active

        # r0, r1, r2, x0, x1, x2
        gen.R0 = self.R0
        gen.R1 = self.R1
        gen.R2 = self.R2

        gen.X0 = self.X0
        gen.X1 = self.X1
        gen.X2 = self.X2

        # active profile
        gen.active_prof = self.active_prof

        # power profile for this load
        gen.P_prof = self.P_prof

        # Power factor profile
        gen.Pf_prof = self.Pf_prof

        # Voltage module set point (p.u.)
        gen.Vset = self.Vset

        # voltage set profile for this load
        gen.Vset_prof = self.Vset_prof

        # minimum reactive power in per unit
        gen.Qmin = self.Qmin

        # Maximum reactive power in per unit
        gen.Qmax = self.Qmax

        # Nominal power
        gen.Snom = self.Snom

        # is the generator enabled for dispatch?
        gen.enabled_dispatch = self.enabled_dispatch

        gen.mttf = self.mttf

        gen.mttr = self.mttr

        gen.technology = self.technology

        gen.opex = self.opex
        gen.capex = self.capex

        return gen

    def get_properties_dict(self, version=3):
        """
        Get json dictionary
        :return: json-compatible dictionary
        """
        if version == 2:
            return {'id': self.idtag,
                    'type': 'generator',
                    'phases': 'ps',
                    'name': self.name,
                    'name_code': self.code,
                    'bus': self.bus.idtag,
                    'active': self.active,
                    'is_controlled': self.is_controlled,
                    'p': self.P,
                    'pf': self.Pf,
                    'vset': self.Vset,
                    'snom': self.Snom,
                    'qmin': self.Qmin,
                    'qmax': self.Qmax,
                    'pmin': self.Pmin,
                    'pmax': self.Pmax,
                    'cost': self.Cost,
                    'technology': "",
                    }
        elif version == 3:
            return {'id': self.idtag,
                    'type': 'generator',
                    'phases': 'ps',
                    'name': self.name,
                    'name_code': self.code,
                    'bus': self.bus.idtag,
                    'active': self.active,
                    'is_controlled': self.is_controlled,
                    'p': self.P,
                    'pf': self.Pf,
                    'vset': self.Vset,
                    'snom': self.Snom,
                    'qmin': self.Qmin,
                    'qmax': self.Qmax,
                    'pmin': self.Pmin,
                    'pmax': self.Pmax,
                    'cost2': self.Cost2,
                    'cost1': self.Cost,
                    'cost0': self.Cost0,

                    'startup_cost': self.StartupCost,
                    'shutdown_cost': self.ShutdownCost,
                    'min_time_up': self.MinTimeUp,
                    'min_time_down': self.MinTimeDown,
                    'ramp_up': self.RampUp,
                    'ramp_down': self.RampDown,

                    'capex': self.capex,
                    'opex': self.opex,
                    'build_status': str(self.build_status.value).lower(),
                    'technology': "",
                    }
        else:
            return dict()

    def get_profiles_dict(self, version=3):
        """

        :return:
        """

        if self.active_prof is None:
            active_prof = list()
        else:
            active_prof = self.active_prof.tolist()

        if self.P_prof is None:
            P_prof = list()
        else:
            P_prof = self.P_prof.tolist()

        if self.Pf_prof is None:
            Pf_prof = list()
        else:
            Pf_prof = self.Pf_prof.tolist()

        if self.Vset_prof is None:
            Vset_prof = list()
        else:
            Vset_prof = self.Vset_prof.tolist()

        return {'id': self.idtag,
                'active': active_prof,
                'p': P_prof,
                'v': Vset_prof,
                'pf': Pf_prof}

    def get_units_dict(self, version=3):
        """
        Get units of the values
        """
        return {'p': 'MW',
                'vset': 'p.u.',
                'pf': 'p.u.',
                'snom': 'MVA',
                'enom': 'MWh',
                'qmin': 'MVAr',
                'qmax': 'MVAr',
                'pmin': 'MW',
                'pmax': 'MW',
                'cost': '€/MWh'}

    def plot_profiles(self, time=None, show_fig=True):
        """
        Plot the time series results of this object
        :param time: array of time values
        :param show_fig: Show the figure?
        """

        if time is not None:
            fig = plt.figure(figsize=(12, 8))

            ax_1 = fig.add_subplot(211)
            ax_2 = fig.add_subplot(212, sharex=ax_1)

            # P
            y = self.P_prof
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_1.set_title('Active power', fontsize=14)
            ax_1.set_ylabel('MW', fontsize=11)
            df.plot(ax=ax_1)

            # V
            y = self.Vset_prof
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_2.set_title('Voltage Set point', fontsize=14)
            ax_2.set_ylabel('p.u.', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

            if show_fig:
                plt.show()

    def fix_inconsistencies(self, logger: Logger, min_vset=0.98, max_vset=1.02):
        """
        Correct the voltage set points
        :param logger: logger to store the events
        :param min_vset: minimum voltage set point (p.u.)
        :param max_vset: maximum voltage set point (p.u.)
        :return: True if any correction happened
        """
        errors = False

        if self.Vset > max_vset:
            logger.add_warning("Corrected generator set point", self.name, self.Vset, max_vset)
            self.Vset = max_vset
            errors = True

        elif self.Vset < min_vset:
            logger.add_warning("Corrected generator set point", self.name, self.Vset, min_vset)
            self.Vset = min_vset
            errors = True

        return errors

    @property
    def Qmax(self):
        """
        Return the reactive power upper limit
        :return: value
        """
        if self.use_reactive_power_curve:
            all_p = self.q_points[:, 0]
            all_qmax = self.q_points[:, 2]
            return np.interp(self.P, all_p, all_qmax)
        else:
            return self.qmax_set

    @Qmax.setter
    def Qmax(self, val):
        self.qmax_set = val

    @property
    def Qmin(self):
        """
        Return the reactive power lower limit
        :return: value
        """
        if self.use_reactive_power_curve:
            all_p = self.q_points[:, 0]
            all_qmin = self.q_points[:, 1]
            return np.interp(self.P, all_p, all_qmin)
        else:
            return self.qmin_set

    @Qmin.setter
    def Qmin(self, val):
        self.qmin_set = val

    @property
    def Snom(self):
        """
        Return the reactive power lower limit
        :return: value
        """
        return self._Snom

    @Snom.setter
    def Snom(self, val):
        """
        Set the generator nominal power
        if the reactive power curve was generated automatically, then it is refreshed
        :param val: float value
        """
        self._Snom = val
        if not self.custom_q_points:
            self.q_points = make_default_q_curve(self._Snom, self.qmin_set, self.qmax_set)
