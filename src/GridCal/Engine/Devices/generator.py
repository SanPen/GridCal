# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
from matplotlib import pyplot as plt
from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Devices.editable_device import EditableDevice, GCProp
from GridCal.Engine.Devices.enumerations import DeviceType, GeneratorTechnologyType


def make_default_q_curve(Snom, Qmin, Qmax, n=3):
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


def get_q_limits(q_points, p):
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
    """
    Voltage controlled generator. This generators supports several reactive power
    control modes (see
    :class:`GridCal.Engine.Simulations.PowerFlowDriver.power_flow_driver.ReactivePowerControlMode`)
    to regulate the voltage on its :ref:`bus` during
    :ref:`power flow simulations<gridcal_engine_simulations_PowerFlow>`.

    Arguments:

        **name** (str, "gen"): Name of the generator

        **active_power** (float, 0.0): Active power in MW

        **power_factor** (float, 0.8): Power factor

        **voltage_module** (float, 1.0): Voltage setpoint in per unit

        **is_controlled** (bool, True): Is the generator voltage controlled?

        **Qmin** (float, -9999): Minimum reactive power in MVAr

        **Qmax** (float, 9999): Maximum reactive power in MVAr

        **Snom** (float, 9999): Nominal apparent power in MVA

        **power_prof** (DataFrame, None): Pandas DataFrame with the active power profile in MW

        **power_factor_prof** (DataFrame, None): Pandas DataFrame with the power factor profile

        **vset_prof** (DataFrame, None): Pandas DataFrame with the voltage setpoint profile in per unit

        **active** (bool, True): Is the generator active?

        **p_min** (float, 0.0): Minimum dispatchable power in MW

        **p_max** (float, 9999): Maximum dispatchable power in MW

        **op_cost** (float, 1.0): Operational cost in Eur (or other currency) per MW

        **Sbase** (float, 100): Nominal apparent power in MVA

        **enabled_dispatch** (bool, True): Is the generator enabled for OPF?

        **mttf** (float, 0.0): Mean time to failure in hours

        **mttr** (float, 0.0): Mean time to recovery in hours

        **technology** (GeneratorTechnologyType): Instance of technology to use

        **q_points**: list of reactive capability curve points [(P1, Qmin1, Qmax1), (P2, Qmin2, Qmax2), ...]

        **use_reactive_power_curve**: Use the reactive power curve? otherwise use the plain old limits
    """

    def __init__(self, name='gen', idtag=None, code='', active_power=0.0, power_factor=0.8, voltage_module=1.0, is_controlled=True,
                 Qmin=-9999, Qmax=9999, Snom=9999, power_prof=None, power_factor_prof=None, vset_prof=None,
                 Cost_prof=None, active=True,  p_min=0.0, p_max=9999.0, op_cost=1.0, Sbase=100, enabled_dispatch=True,
                 mttf=0.0, mttr=0.0, technology: GeneratorTechnologyType = GeneratorTechnologyType.CombinedCycle,
                 q_points=None, use_reactive_power_curve=False):

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                active=active,
                                device_type=DeviceType.GeneratorDevice,
                                editable_headers={'name': GCProp('', str, 'Name of the generator'),
                                                  'idtag': GCProp('', str, 'Unique ID'),
                                                  'code': GCProp('', str, 'Secondary ID'),
                                                  'bus': GCProp('', DeviceType.BusDevice, 'Connection bus name'),
                                                  'active': GCProp('', bool, 'Is the generator active?'),
                                                  'is_controlled': GCProp('', bool,
                                                                          'Is this generator voltage-controlled?'),
                                                  'P': GCProp('MW', float, 'Active power'),
                                                  'Pf': GCProp('', float,
                                                               'Power factor (cos(fi)). '
                                                               'This is used for non-controlled generators.'),
                                                  'Vset': GCProp('p.u.', float,
                                                                 'Set voltage. '
                                                                 'This is used for controlled generators.'),
                                                  'Snom': GCProp('MVA', float, 'Nomnial power.'),
                                                  'Qmin': GCProp('MVAr', float, 'Minimum reactive power.'),
                                                  'Qmax': GCProp('MVAr', float, 'Maximum reactive power.'),
                                                  'use_reactive_power_curve': GCProp('', bool, 'Use the reactive power capability curve?'),
                                                  'Pmin': GCProp('MW', float, 'Minimum active power. Used in OPF.'),
                                                  'Pmax': GCProp('MW', float, 'Maximum active power. Used in OPF.'),
                                                  'Cost': GCProp('e/MWh', float, 'Generation unitary cost. Used in OPF.'),
                                                  'enabled_dispatch': GCProp('', bool,
                                                                             'Enabled for dispatch? Used in OPF.'),
                                                  'mttf': GCProp('h', float, 'Mean time to failure'),
                                                  'mttr': GCProp('h', float, 'Mean time to recovery'),
                                                  'technology': GCProp('', GeneratorTechnologyType, 'Generator technology')},
                                non_editable_attributes=['bus', 'idtag'],
                                properties_with_profile={'active': 'active_prof',
                                                         'P': 'P_prof',
                                                         'Pf': 'Pf_prof',
                                                         'Vset': 'Vset_prof',
                                                         'Cost': 'Cost_prof'})

        self.bus = None

        self.active_prof = None

        self.mttf = mttf

        self.mttr = mttr

        self.technology = technology

        # is the device active active power dispatch?
        self.enabled_dispatch = enabled_dispatch

        # Power (MVA)
        self.P = active_power

        # Power factor
        self.Pf = power_factor

        # voltage set profile for this load in p.u.
        self.Pf_prof = power_factor_prof

        # If this generator is voltage controlled it produces a PV node, otherwise the node remains as PQ
        self.is_controlled = is_controlled

        # Nominal power in MVA (also the machine base)
        self._Snom = Snom

        # Minimum dispatched power in MW
        self.Pmin = p_min

        # Maximum dispatched power in MW
        self.Pmax = p_max

        # power profile for this load in MW
        self.P_prof = power_prof

        # Voltage module set point (p.u.)
        self.Vset = voltage_module

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

        # Cost of operation €/MW
        self.Cost = op_cost

        self.Cost_prof = Cost_prof

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
                    'cost': self.Cost,
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
