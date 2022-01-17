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
from matplotlib import pyplot as plt
from GridCal.Engine.Devices.editable_device import EditableDevice, DeviceType, GCProp


class StaticGenerator(EditableDevice):
    """
    Arguments:

        **name** (str, "StaticGen"): Name of the static generator

        **P** (float, 0.0): Active power in MW

        **Q** (float, 0.0): Reactive power in MVAr

        **P_prof** (DataFrame, None): Pandas DataFrame with the active power profile in MW

        **Q_prof** (DataFrame, None): Pandas DataFrame with the reactive power profile in MVAr

        **active** (bool, True): Is the static generator active?

        **mttf** (float, 0.0): Mean time to failure in hours

        **mttr** (float, 0.0): Mean time to recovery in hours

    """

    def __init__(self, name='StaticGen', idtag=None, code='', P=0.0, Q=0.0, P_prof=None, Q_prof=None, active=True,
                 mttf=0.0, mttr=0.0):

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                active=active,
                                device_type=DeviceType.StaticGeneratorDevice,
                                editable_headers={'name': GCProp('', str, ''),
                                                  'idtag': GCProp('', str, 'Unique ID', False),
                                                  'code': GCProp('', str, 'Secondary ID'),
                                                  'bus': GCProp('', DeviceType.BusDevice, ''),
                                                  'active': GCProp('', bool, ''),
                                                  'P': GCProp('MW', float, 'Active power'),
                                                  'Q': GCProp('MVAr', float, 'Reactive power'),
                                                  'mttf': GCProp('h', float, 'Mean time to failure'),
                                                  'mttr': GCProp('h', float, 'Mean time to recovery')},
                                non_editable_attributes=['bus', 'idtag'],
                                properties_with_profile={'active': 'active_prof',
                                                         'P': 'P_prof',
                                                         'Q': 'Q_prof'})

        self.bus = None

        self.active_prof = None

        self.mttf = mttf

        self.mttr = mttr

        # Power (MW + jMVAr)
        self.P = P
        self.Q = Q

        # power profile for this load
        self.P_prof = P_prof
        self.Q_prof = Q_prof

    def copy(self):
        """
        Deep copy of this object
        :return:
        """
        return StaticGenerator(name=self.name,
                               P=self.P,
                               Q=self.Q,
                               P_prof=self.P_prof,
                               Q_prof=self.Q_prof,
                               mttf=self.mttf,
                               mttr=self.mttr)

    def get_properties_dict(self, version=3):
        """
        Get json dictionary
        :return:
        """

        data = {'id': self.idtag,
                'phases': 'ps',
                'name': self.name,
                'name_code': self.code,
                'bus': self.bus.idtag,
                'active': self.active,
                'P': self.P,
                'Q': self.Q,
                'technology': ""
                }

        return data

    def get_profiles_dict(self, version=3):
        """

        :return:
        """

        if self.active_prof is not None:
            active_profile = self.active_prof.tolist()
            P_prof = self.P_prof.tolist()
            Q_prof = self.Q_prof.tolist()
        else:
            active_profile = list()
            P_prof = list()
            Q_prof = list()

        return {'id': self.idtag,
                'active': active_profile,
                'p': P_prof,
                'q': Q_prof}

    def get_units_dict(self, version=3):
        """
        Get units of the values
        """
        return {'p': 'MW',
                'q': 'MVAr'}

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

            # Q
            y = self.Q_prof
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_2.set_title('Reactive power', fontsize=14)
            ax_2.set_ylabel('MVAr', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

            if show_fig:
                plt.show()
