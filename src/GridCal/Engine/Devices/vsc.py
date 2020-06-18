# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import pandas as pd
import numpy as np
from matplotlib import pyplot as plt

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Devices.bus import Bus
from GridCal.Engine.Devices.enumerations import BranchType

from GridCal.Engine.Devices.editable_device import EditableDevice, DeviceType, GCProp


class VSC(EditableDevice):

    def __init__(self, bus_from: Bus = None, bus_to: Bus = None, name='VSC', idtag=None, active=True,
                 r1=0.0001, x1=0.05, m=1.0, theta=0.1, Gsw=1e-5, Beq=0.001, rate=1e-9,
                 mttf=0, mttr=0, cost=1200, cost_prof=None, rate_prof=None, active_prof=None):
        """
        Voltage source converter (VSC)
        :param bus_from:
        :param bus_to:
        :param name:
        :param active:
        :param r1:
        :param x1:
        :param m:
        :param theta:
        :param Gsw:
        :param Beq:
        :param rate:
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                active=active,
                                device_type=DeviceType.VscDevice,
                                editable_headers={'name': GCProp('', str, 'Name of the branch.'),
                                                  'idtag': GCProp('', str, 'Unique ID'),
                                                  'bus_from': GCProp('', DeviceType.BusDevice,
                                                                     'Name of the bus at the "from" side of the branch.'),
                                                  'bus_to': GCProp('', DeviceType.BusDevice,
                                                                   'Name of the bus at the "to" side of the branch.'),
                                                  'active': GCProp('', bool, 'Is the branch active?'),
                                                  'rate': GCProp('MVA', float, 'Thermal rating power of the branch.'),
                                                  'mttf': GCProp('h', float, 'Mean time to failure, '
                                                                 'used in reliability studies.'),
                                                  'mttr': GCProp('h', float, 'Mean time to recovery, '
                                                                 'used in reliability studies.'),
                                                  'R1': GCProp('p.u.', float, 'Resistive losses.'),
                                                  'X1': GCProp('p.u.', float, 'Magnetic losses.'),
                                                  'Gsw': GCProp('p.u.', float, 'Inverter losses.'),
                                                  'Beq': GCProp('p.u.', float, 'Total shunt susceptance.'),
                                                  'm': GCProp('', float, 'Tap changer module, it a value close to 1.0'),
                                                  'theta': GCProp('rad', float, 'Converter firing angle.'),
                                                  'Cost': GCProp('e/MWh', float,
                                                                 'Cost of overloads. Used in OPF.'),
                                                  },
                                non_editable_attributes=['bus_from', 'bus_to'],
                                properties_with_profile={'active': 'active_prof',
                                                         'rate': 'rate_prof',
                                                         'Cost': 'Cost_prof'})

        # the VSC must only connect from an AC to a DC bus
        # assert(bus_from.is_dc != bus_to.is_dc)
        if bus_to is not None and bus_from is not None:
            # connectivity:
            # for the later primitives to make sense, the "bus from" must be AC and the "bus to" must be DC
            if bus_to.is_dc:
                self.bus_from = bus_from
                self.bus_to = bus_to
            else:
                self.bus_from = bus_to
                self.bus_to = bus_from
                print('Corrected the connection direction of the VSC device:', self.name)
        else:
            self.bus_from = None
            self.bus_to = None

        # List of measurements
        self.measurements = list()

        # total impedance and admittance in p.u.
        self.R1 = r1
        self.X1 = x1
        self.Gsw = Gsw
        self.Beq = Beq
        self.m = m
        self.theta = theta

        self.Cost = cost
        self.Cost_prof = cost_prof

        self.mttf = mttf
        self.mttr = mttr

        self.active = active
        self.active_prof = active_prof

        # branch rating in MVA
        self.rate = rate
        self.rate_prof = rate_prof

        # branch type: Line, Transformer, etc...
        self.branch_type = BranchType.VSC

    def get_weight(self):
        return np.sqrt(self.R1 * self.R1 + self.X1 * self.X1)


    def get_properties_dict(self):
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

        d = {'id': self.idtag,
             'type': 'line',
             'phases': 'ps',
             'name': self.name,
             'bus_from': self.bus_from.idtag,
             'bus_to': self.bus_to.idtag,
             'active': self.active,

             'rate': self.rate,
             'r': self.R1,
             'x': self.X1,
             'b': self.Beq,
             'g': self.Gsw,

             'tap_module': self.m,
             'firing_angle': self.theta,

             'profiles': {
                 'active': active_prof,
                 'rate': rate_prof}
             }

        return d

    def get_units_dict(self):
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
            ax_2 = fig.add_subplot(212)

            x = time_series.results.time

            # loading
            y = time_series.results.loading * 100.0
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            ax_1.set_title('Loading', fontsize=14)
            ax_1.set_ylabel('Loading [%]', fontsize=11)
            df.plot(ax=ax_1)

            # losses
            y = time_series.results.losses
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            ax_2.set_title('Losses', fontsize=14)
            ax_2.set_ylabel('Losses [MVA]', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

        if show_fig:
            plt.show()
