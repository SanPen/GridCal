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
import pandas as pd
from typing import Union
from matplotlib import pyplot as plt
from GridCalEngine.basic_structures import Logger
from GridCalEngine.enumerations import DeviceType, BuildStatus, SubObjectType
from GridCalEngine.Devices.Associations.association import Associations
from GridCalEngine.Devices.Parents.generator_parent import GeneratorParent
from GridCalEngine.Devices.Injections.generator_q_curve import GeneratorQCurve
from GridCalEngine.Devices.profile import Profile


class Generator(GeneratorParent):

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
                 active: bool = True,
                 Pmin: float = 0.0,
                 Pmax: float = 9999.0,
                 Cost: float = 1.0,
                 Cost2: float = 0.0,
                 Cost0: float = 0.0,
                 Sbase: float = 100,
                 enabled_dispatch=True,
                 mttf: float = 0.0,
                 mttr: float = 0.0,
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
                 srap_enabled: bool = True,
                 build_status: BuildStatus = BuildStatus.Commissioned):
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
        :param active: Is the generator active?
        :param Pmin:
        :param Pmax:
        :param Cost:
        :param Sbase: Nominal apparent power in MVA
        :param enabled_dispatch: Is the generator enabled for OPF?
        :param mttf: Mean time to failure in hours
        :param mttr: Mean time to recovery in hours
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
        """
        GeneratorParent.__init__(self,
                                 name=name,
                                 idtag=idtag,
                                 code=code,
                                 bus=None,
                                 cn=None,
                                 control_bus=None,
                                 control_cn=None,
                                 active=active,
                                 P=P,
                                 Pmin=Pmin,
                                 Pmax=Pmax,
                                 Cost=Cost,
                                 mttf=mttf,
                                 mttr=mttr,
                                 capex=capex,
                                 opex=opex,
                                 srap_enabled=srap_enabled,
                                 build_status=build_status,
                                 device_type=DeviceType.GeneratorDevice)

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

        # Power factor
        self.Pf = power_factor

        # voltage set profile for this load in p.u.
        self._Pf_prof = Profile(default_value=power_factor, data_type=float)

        # If this generator is voltage controlled it produces a PV node, otherwise the node remains as PQ
        self.is_controlled = is_controlled

        # Nominal power in MVA (also the machine base)
        self._Snom = Snom

        # Voltage module set point (p.u.)
        self.Vset = vset

        # voltage set profile for this load in p.u.
        self._Vset_prof = Profile(default_value=vset, data_type=float)

        self.use_reactive_power_curve = use_reactive_power_curve

        # minimum reactive power in MVAr
        self.qmin_set = Qmin

        # Maximum reactive power in MVAr
        self.qmax_set = Qmax

        # declare the generation curve
        self.q_curve = GeneratorQCurve()

        if q_points is not None:
            self.q_curve.set(np.array(q_points))
            self.custom_q_points = True
        else:
            self.q_curve.make_default_q_curve(self.Snom, self.qmin_set, self.qmax_set, n=1)
            self.custom_q_points = False

        self.Cost2 = Cost2  # Cost of operation e/MW²
        self.Cost0 = Cost0  # Cost of operation e

        self.StartupCost = 0.0
        self.ShutdownCost = 0.0
        self.MinTimeUp = 0.0
        self.MinTimeDown = 0.0
        self.RampUp = 1e20
        self.RampDown = 1e20

        self._Cost2_prof = Profile(default_value=Cost2, data_type=float)
        self._Cost0_prof = Profile(default_value=Cost0, data_type=float)

        self.emissions: Associations = Associations(device_type=DeviceType.EmissionGasDevice)
        self.fuels: Associations = Associations(device_type=DeviceType.FuelDevice)

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

        self.register(key='is_controlled', units='', tpe=bool, definition='Is this generator voltage-controlled?')

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
        self.register(key='q_curve', units='MVAr', tpe=SubObjectType.GeneratorQCurve,
                      definition='Capability curve data (double click on the generator to edit)',
                      editable=False, display=False)

        self.register(key='R1', units='p.u.', tpe=float, definition='Total positive sequence resistance.')
        self.register(key='X1', units='p.u.', tpe=float, definition='Total positive sequence reactance.')
        self.register(key='R0', units='p.u.', tpe=float, definition='Total zero sequence resistance.')
        self.register(key='X0', units='p.u.', tpe=float, definition='Total zero sequence reactance.')
        self.register(key='R2', units='p.u.', tpe=float, definition='Total negative sequence resistance.')
        self.register(key='X2', units='p.u.', tpe=float, definition='Total negative sequence reactance.')
        self.register(key='Cost2', units='e/MWh²', tpe=float, definition='Generation quadratic cost. Used in OPF.',
                      profile_name='Cost2_prof')

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

        self.register(key='enabled_dispatch', units='', tpe=bool, definition='Enabled for dispatch? Used in OPF.')

        self.register(key='emissions', units='t/MWh', tpe=SubObjectType.Associations,
                      definition='List of emissions', display=False)

        self.register(key='fuels', units='t/MWh', tpe=SubObjectType.Associations,
                      definition='List of fuels', display=False)

    @property
    def Pf_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Pf_prof

    @Pf_prof.setter
    def Pf_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Pf_prof = val
        elif isinstance(val, np.ndarray):
            self._Pf_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Pf_prof')

    @property
    def Vset_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Vset_prof

    @Vset_prof.setter
    def Vset_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Vset_prof = val
        elif isinstance(val, np.ndarray):
            self._Vset_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Vset_prof')

    @property
    def Cost2_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Cost2_prof

    @Cost2_prof.setter
    def Cost2_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Cost2_prof = val
        elif isinstance(val, np.ndarray):
            self._Cost2_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Cost2_prof')

    @property
    def Cost0_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Cost0_prof

    @Cost0_prof.setter
    def Cost0_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Cost0_prof = val
        elif isinstance(val, np.ndarray):
            self._Cost0_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Cost0_prof')

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
            y = self.P_prof.toarray()
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_1.set_title('Active power', fontsize=14)
            ax_1.set_ylabel('MW', fontsize=11)
            df.plot(ax=ax_1)

            # V
            y = self.Vset_prof.toarray()
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
        # if not self.custom_q_points:
        #     self.q_curve.make_default_q_curve(self._Snom, self.qmin_set, self.qmax_set)
