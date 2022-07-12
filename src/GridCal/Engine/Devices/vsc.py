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

import pandas as pd
import numpy as np
from matplotlib import pyplot as plt

from GridCal.Engine.Devices.bus import Bus
from GridCal.Engine.Devices.enumerations import BranchType, ConverterControlType

from GridCal.Engine.Devices.editable_device import EditableDevice, DeviceType, GCProp


class VSC(EditableDevice):

    def __init__(self, bus_from: Bus = None, bus_to: Bus = None, name='VSC', idtag=None, code='', active=True,
                 r1=0.0001, x1=0.05,
                 m=1.0, m_max=1.1, m_min=0.8,
                 theta=0.1, theta_max=6.28, theta_min=-6.28,
                 Beq=0.001, Beq_min=-0.1, Beq_max=0.1,
                 G0=1e-5, rate=1e-9, kdp=-0.05, k=1.0,
                 control_mode: ConverterControlType = ConverterControlType.type_0_free,
                 Pfset = 0.0, Qfset=0.0, Vac_set=1.0, Vdc_set=1.0,
                 alpha1=0.0001, alpha2=0.015, alpha3=0.2,
                 mttf=0, mttr=0, cost=100, cost_prof=None, rate_prof=None, active_prof=None, contingency_factor=1.0,
                 contingency_enabled=True, monitor_loading=True, contingency_factor_prof=None):
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
        :param G0:
        :param Beq:
        :param Beq_min:
        :param Beq_max:
        :param Inom:
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

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                active=active,
                                code=code,
                                device_type=DeviceType.VscDevice,
                                editable_headers={'name': GCProp('', str, 'Name of the branch.'),
                                                  'idtag': GCProp('', str, 'Unique ID', False),
                                                  'code': GCProp('', str, 'Secondary ID'),
                                                  'bus_from': GCProp('', DeviceType.BusDevice,
                                                                     'Name of the bus at the "DC" side of the branch.'),
                                                  'bus_to': GCProp('', DeviceType.BusDevice,
                                                                   'Name of the bus at the "AC" side of the branch.'),
                                                  'active': GCProp('', bool, 'Is the branch active?'),
                                                  'rate': GCProp('MVA', float, 'Thermal rating power of the branch.'),

                                                  'contingency_factor': GCProp('p.u.', float,
                                                                               'Rating multiplier for contingencies.'),
                                                  'contingency_enabled': GCProp('', bool,
                                                                                'Consider this VSC for contingencies.'),
                                                  'monitor_loading': GCProp('', bool,
                                                                            'Monitor this device loading for optimization, NTC or contingency studies.'),
                                                  'mttf': GCProp('h', float, 'Mean time to failure, '
                                                                 'used in reliability studies.'),
                                                  'mttr': GCProp('h', float, 'Mean time to recovery, '
                                                                 'used in reliability studies.'),
                                                  'R1': GCProp('p.u.', float, 'Resistive losses.'),
                                                  'X1': GCProp('p.u.', float, 'Magnetic losses.'),
                                                  'G0': GCProp('p.u.', float, 'Inverter losses.'),

                                                  'Beq': GCProp('p.u.', float, 'Total shunt susceptance.'),
                                                  'Beq_max': GCProp('p.u.', float, 'Max total shunt susceptance.'),
                                                  'Beq_min': GCProp('p.u.', float, 'Min total shunt susceptance.'),

                                                  'm': GCProp('', float, 'Tap changer module, it a value close to 1.0'),
                                                  'm_max': GCProp('', float, 'Max tap changer module'),
                                                  'm_min': GCProp('', float, 'Min tap changer module'),

                                                  'theta': GCProp('rad', float, 'Converter firing angle.'),
                                                  'theta_max': GCProp('rad', float, 'Max converter firing angle.'),
                                                  'theta_min': GCProp('rad', float, 'Min converter firing angle.'),

                                                  'alpha1': GCProp('', float,
                                                                   'Converter losses curve parameter (IEC 62751-2 loss Correction).'),
                                                  'alpha2': GCProp('', float,
                                                                   'Converter losses curve parameter (IEC 62751-2 loss Correction).'),
                                                  'alpha3': GCProp('', float,
                                                                   'Converter losses curve parameter (IEC 62751-2 loss Correction).'),

                                                  'k': GCProp('p.u./p.u.', float, 'Converter factor, typically 0.866.'),

                                                  'control_mode': GCProp('', ConverterControlType,
                                                                         'Converter control mode'),

                                                  'kdp': GCProp('p.u./p.u.', float, 'Droop Power/Voltage slope.'),
                                                  'Pdc_set': GCProp('MW', float, 'DC power set point.'),
                                                  'Qac_set': GCProp('MVAr', float, 'AC Reactive power set point.'),
                                                  'Vac_set': GCProp('p.u.', float, 'AC voltage set point.'),
                                                  'Vdc_set': GCProp('p.u.', float, 'DC voltage set point.'),
                                                  'Cost': GCProp('e/MWh', float, 'Cost of overloads. Used in OPF.'),
                                                  },
                                non_editable_attributes=['bus_from', 'bus_to', 'idtag'],
                                properties_with_profile={'active': 'active_prof',
                                                         'rate': 'rate_prof',
                                                         'contingency_factor': 'contingency_factor_prof',
                                                         'Cost': 'Cost_prof'})

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
        self.G0 = G0
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

        self.Cost = cost
        self.Cost_prof = cost_prof

        self.mttf = mttf
        self.mttr = mttr

        self.active = active
        self.active_prof = active_prof

        # branch rating in MVA
        self.rate = rate
        self.contingency_factor = contingency_factor
        self.contingency_enabled: bool = contingency_enabled
        self.monitor_loading: bool = monitor_loading
        self.rate_prof = rate_prof
        self.contingency_factor_prof = contingency_factor_prof

        # branch type: Line, Transformer, etc...
        self.branch_type = BranchType.VSC

    def get_weight(self):
        return np.sqrt(self.R1 * self.R1 + self.X1 * self.X1)

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
        self.G0 *= b
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
                 'g': self.G0,

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
                 'g': self.G0,

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

                 'control_mode': modes[self.control_mode]
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

            x = time_series.results.time

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
