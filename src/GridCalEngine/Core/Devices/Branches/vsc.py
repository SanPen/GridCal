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

import pandas as pd
import numpy as np
from matplotlib import pyplot as plt

from GridCalEngine.Core.Devices.Substation.bus import Bus
from GridCalEngine.Core.Devices.enumerations import BranchType, ConverterControlType, BuildStatus
from GridCalEngine.Core.Devices.Branches.templates.parent_branch import ParentBranch
from GridCalEngine.Core.Devices.editable_device import DeviceType


class VSC(ParentBranch):

    def __init__(self, bus_from: Bus = None, bus_to: Bus = None, name='VSC', idtag=None, code='', active=True,
                 r1=0.0001, x1=0.05,
                 m=1.0, m_max=1.1, m_min=0.8,
                 theta=0.1, theta_max=6.28, theta_min=-6.28,
                 Beq=0.001, Beq_min=-0.1, Beq_max=0.1,
                 G0sw=1e-5, rate=1e-9, kdp=-0.05, k=1.0,
                 control_mode: ConverterControlType = ConverterControlType.type_0_free,
                 Pfset = 0.0, Qfset=0.0, Vac_set=1.0, Vdc_set=1.0,
                 alpha1=0.0001, alpha2=0.015, alpha3=0.2,
                 mttf=0, mttr=0, cost=100, cost_prof=None, rate_prof=None, active_prof=None, contingency_factor=1.0,
                 contingency_enabled=True, monitor_loading=True, contingency_factor_prof=None,
                 r0=0.0001, x0=0.05, r2=0.0001, x2=0.05,
                 capex=0, opex=0, build_status: BuildStatus = BuildStatus.Commissioned):
        """
        Voltage source converter (VSC)
        :param bus_from:
        :param bus_to:
        :param name:
        :param idtag:
        :param active:
        :param r1:
        :param x1:
        :param m:
        :param m_max:
        :param m_min:
        :param theta:
        :param theta_max:
        :param theta_min:
        :param G0sw:
        :param Beq:
        :param Beq_min:
        :param Beq_max:
        :param rate:
        :param kdp:
        :param control_mode:
        :param Pfset:
        :param Vac_set:
        :param Vdc_set:
        :param Qfset:
        :param alpha1:
        :param alpha2:
        :param alpha3:
        :param mttf:
        :param mttr:
        :param cost:
        :param cost_prof:
        :param rate_prof:
        :param active_prof:
        """

        ParentBranch.__init__(self,
                              name=name,
                              idtag=idtag,
                              code=code,
                              bus_from=bus_from,
                              bus_to=bus_to,
                              active=active,
                              active_prof=active_prof,
                              rate=rate,
                              rate_prof=rate_prof,
                              contingency_factor=contingency_factor,
                              contingency_factor_prof=contingency_factor_prof,
                              contingency_enabled=contingency_enabled,
                              monitor_loading=monitor_loading,
                              mttf=mttf,
                              mttr=mttr,
                              build_status=build_status,
                              capex=capex,
                              opex=opex,
                              Cost=cost,
                              Cost_prof=cost_prof,
                              device_type=DeviceType.VscDevice,
                              branch_type=BranchType.VSC)

        # the VSC must only connect from an DC to a AC bus
        # this connectivity sense is done to keep track with the articles that set it
        # from -> DC
        # to   -> AC
        # assert(bus_from.is_dc != bus_to.is_dc)
        if bus_to is not None and bus_from is not None:
            # connectivity:
            # for the later primitives to make sense, the "bus from" must be AC and the "bus to" must be DC
            if bus_from.is_dc and not bus_to.is_dc:  # this is the correct sense
                self.bus_from = bus_from
                self.bus_to = bus_to
            elif not bus_from.is_dc and bus_to.is_dc:  # opposite sense, revert
                self.bus_from = bus_to
                self.bus_to = bus_from
                print('Corrected the connection direction of the VSC device:', self.name)
            else:
                raise Exception('Impossible connecting a VSC device here. '
                                'VSC devices must be connected between AC and DC buses')
        else:
            self.bus_from = None
            self.bus_to = None

        # List of measurements
        self.measurements = list()

        # total impedance and admittance in p.u.
        self.R1 = r1
        self.X1 = x1

        self.R0 = r0
        self.X0 = x0

        self.R2 = r2
        self.X2 = x2

        self.G0sw = G0sw
        self.Beq = Beq
        self.m = m
        self.theta = theta
        self.k = k
        self.m_max = m_max
        self.m_min = m_min
        self.theta_max = theta_max
        self.theta_min = theta_min
        self.Beq_min = Beq_min
        self.Beq_max = Beq_max

        self.Pdc_set = Pfset
        self.Qac_set = Qfset
        self.Vac_set = Vac_set
        self.Vdc_set = Vdc_set
        self.control_mode = control_mode

        self.kdp = kdp
        self.alpha1 = alpha1
        self.alpha2 = alpha2
        self.alpha3 = alpha3

        # branch type: Line, Transformer, etc...
        self.branch_type = BranchType.VSC

        self.register(key='R1', units='p.u.', tpe=float, definition='Resistive positive sequence losses.')
        self.register(key='X1', units='p.u.', tpe=float, definition='Magnetic positive sequence losses.')
        self.register(key='R0', units='p.u.', tpe=float, definition='Resistive zero sequence losses.')
        self.register(key='X0', units='p.u.', tpe=float, definition='Magnetic zero sequence losses.')
        self.register(key='R2', units='p.u.', tpe=float, definition='Resistive negative sequence losses.')
        self.register(key='X2', units='p.u.', tpe=float, definition='Magnetic negative sequence losses.')
        self.register(key='G0sw', units='p.u.', tpe=float, definition='Inverter losses.')
        self.register(key='Beq', units='p.u.', tpe=float, definition='Total shunt susceptance.')
        self.register(key='Beq_max', units='p.u.', tpe=float, definition='Max total shunt susceptance.')
        self.register(key='Beq_min', units='p.u.', tpe=float, definition='Min total shunt susceptance.')
        self.register(key='m', units='', tpe=float, definition='Tap changer module, it a value close to 1.0')
        self.register(key='m_max', units='', tpe=float, definition='Max tap changer module')
        self.register(key='m_min', units='', tpe=float, definition='Min tap changer module')
        self.register(key='theta', units='rad', tpe=float, definition='Converter firing angle.')
        self.register(key='theta_max', units='rad', tpe=float, definition='Max converter firing angle.')
        self.register(key='theta_min', units='rad', tpe=float, definition='Min converter firing angle.')
        self.register(key='alpha1', units='', tpe=float,
                      definition='Converter losses curve parameter (IEC 62751-2 loss Correction).')
        self.register(key='alpha2', units='', tpe=float,
                      definition='Converter losses curve parameter (IEC 62751-2 loss Correction).')
        self.register(key='alpha3', units='', tpe=float,
                      definition='Converter losses curve parameter (IEC 62751-2 loss Correction).')
        self.register(key='k', units='p.u./p.u.', tpe=float, definition='Converter factor, typically 0.866.')
        self.register(key='control_mode', units='', tpe=ConverterControlType, definition='Converter control mode')
        self.register(key='kdp', units='p.u./p.u.', tpe=float, definition='Droop Power/Voltage slope.')
        self.register(key='Pdc_set', units='MW', tpe=float, definition='DC power set point.')
        self.register(key='Qac_set', units='MVAr', tpe=float, definition='AC Reactive power set point.')
        self.register(key='Vac_set', units='p.u.', tpe=float, definition='AC voltage set point.')
        self.register(key='Vdc_set', units='p.u.', tpe=float, definition='DC voltage set point.')

    def get_weight(self):
        return np.sqrt(self.R1 * self.R1 + self.X1 * self.X1)

    def get_max_bus_nominal_voltage(self):
        return max(self.bus_from.Vnom, self.bus_to.Vnom)

    def get_min_bus_nominal_voltage(self):
        return min(self.bus_from.Vnom, self.bus_to.Vnom)

    @property
    def R(self):
        return self.R1

    @property
    def X(self):
        return self.X1

    def change_base(self, Sbase_old, Sbase_new):
        b = Sbase_new / Sbase_old

        self.R1 *= b
        self.X1 *= b
        self.G0sw *= b
        self.Beq *= b

    def get_coordinates(self):
        """
        Get the line defining coordinates
        """
        return [self.bus_from.get_coordinates(), self.bus_to.get_coordinates()]

    def correct_buses_connection(self):
        """
        Fix the buses connection (from: DC, To: AC)
        """
        # the VSC must only connect from an DC to a AC bus
        # this connectivity sense is done to keep track with the articles that set it
        # from -> DC
        # to   -> AC
        # assert(bus_from.is_dc != bus_to.is_dc)
        if self.bus_to is not None and self.bus_from is not None:
            # connectivity:
            # for the later primitives to make sense, the "bus from" must be AC and the "bus to" must be DC
            if self.bus_from.is_dc and not self.bus_to.is_dc:  # correct sense
                pass
            elif not self.bus_from.is_dc and self.bus_to.is_dc:  # opposite sense, revert
                self.bus_from, self.bus_to = self.bus_to, self.bus_from
                print('Corrected the connection direction of the VSC device:', self.name)
            else:
                raise Exception('Impossible connecting a VSC device here. '
                                'VSC devices must be connected between AC and DC buses')
        else:
            self.bus_from = None
            self.bus_to = None

    def get_properties_dict(self, version=3):
        """
        Get json dictionary
        :return:
        """

        if self.active_prof is not None:
            active_prof = self.active_prof.tolist()
            rate_prof = self.rate_prof.tolist()
        else:
            active_prof = list()
            rate_prof = list()

        modes = {ConverterControlType.type_0_free: 0,
                 ConverterControlType.type_I_1: 1,
                 ConverterControlType.type_I_2: 2,
                 ConverterControlType.type_I_3: 3,
                 ConverterControlType.type_II_4: 4,
                 ConverterControlType.type_II_5: 5,
                 ConverterControlType.type_III_6: 6,
                 ConverterControlType.type_III_7: 7,
                 ConverterControlType.type_IV_I: 8,
                 ConverterControlType.type_IV_II: 9}
        if version == 2:
            d = {'id': self.idtag,
                 'type': 'vsc',
                 'phases': 'ps',
                 'name': self.name,
                 'name_code': self.code,
                 'bus_from': self.bus_from.idtag,
                 'bus_to': self.bus_to.idtag,
                 'active': self.active,

                 'rate': self.rate,
                 'r': self.R1,
                 'x': self.X1,
                 'G0sw': self.G0sw,

                 'm': self.m,
                 'm_min': self.m_min,
                 'm_max': self.m_max,

                 'theta': self.theta,
                 'theta_min': self.theta_min,
                 'theta_max': self.theta_max,

                 'Beq': self.Beq,
                 'Beq_min': self.Beq_min,
                 'Beq_max': self.Beq_max,

                 'alpha1': self.alpha1,
                 'alpha2': self.alpha2,
                 'alpha3': self.alpha3,

                 'k': self.k,
                 'kdp': self.kdp,
                 'Pfset': self.Pdc_set,
                 'Qfset': self.Qac_set,
                 'vac_set': self.Vac_set,
                 'vdc_set': self.Vdc_set,

                 'mode': modes[self.control_mode]
                 }
        elif version == 3:
            d = {'id': self.idtag,
                 'type': 'vsc',
                 'phases': 'ps',
                 'name': self.name,
                 'name_code': self.code,
                 'bus_from': self.bus_from.idtag,
                 'bus_to': self.bus_to.idtag,
                 'active': self.active,

                 'rate': self.rate,
                 'contingency_factor1': self.contingency_factor,
                 'contingency_factor2': self.contingency_factor,
                 'contingency_factor3': self.contingency_factor,

                 'r': self.R1,
                 'x': self.X1,
                 'g': self.G0sw,

                 'm': self.m,
                 'm_min': self.m_min,
                 'm_max': self.m_max,

                 'theta': self.theta,
                 'theta_min': self.theta_min,
                 'theta_max': self.theta_max,

                 'Beq': self.Beq,
                 'Beq_min': self.Beq_min,
                 'Beq_max': self.Beq_max,

                 'alpha1': self.alpha1,
                 'alpha2': self.alpha2,
                 'alpha3': self.alpha3,

                 'k': self.k,
                 'kdp': self.kdp,
                 'Pfset': self.Pdc_set,
                 'Qfset': self.Qac_set,
                 'vac_set': self.Vac_set,
                 'vdc_set': self.Vdc_set,

                 'control_mode': modes[self.control_mode],

                 'overload_cost': self.Cost,
                 'capex': self.capex,
                 'opex': self.opex,
                 'build_status': str(self.build_status.value).lower(),
                 }
        else:
            d = dict()

        return d

    def get_profiles_dict(self, version=3):
        """

        :return:
        """
        if self.active_prof is not None:
            active_prof = self.active_prof.tolist()
            rate_prof = self.rate_prof.tolist()
        else:
            active_prof = list()
            rate_prof = list()

        return {'id': self.idtag,
                'active': active_prof,
                'rate': rate_prof}

    def get_units_dict(self, version=3):
        """
        Get units of the values
        """
        return {'rate': 'MW',
                'r': 'p.u.',
                'x': 'p.u.',
                'b': 'p.u.',
                'g': 'p.u.'}

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
