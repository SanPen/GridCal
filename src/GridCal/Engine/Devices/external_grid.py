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
from matplotlib import pyplot as plt
from GridCal.Engine.Devices.editable_device import EditableDevice, DeviceType, GCProp


class ExternalGrid(EditableDevice):
    """
    External grid device
    In essence, this is a slack-enforcer device

    Arguments:

        **name** (str, "Load"): Name of the load

        **G** (float, 0.0): Conductance in equivalent MW

        **B** (float, 0.0): Susceptance in equivalent MVAr

        **Ir** (float, 0.0): Real current in equivalent MW

        **Ii** (float, 0.0): Imaginary current in equivalent MVAr

        **P** (float, 0.0): Active power in MW

        **Q** (float, 0.0): Reactive power in MVAr

        **G_prof** (DataFrame, None): Pandas DataFrame with the conductance profile in equivalent MW

        **B_prof** (DataFrame, None): Pandas DataFrame with the susceptance profile in equivalent MVAr

        **Ir_prof** (DataFrame, None): Pandas DataFrame with the real current profile in equivalent MW

        **Ii_prof** (DataFrame, None): Pandas DataFrame with the imaginary current profile in equivalent MVAr

        **P_prof** (DataFrame, None): Pandas DataFrame with the active power profile in equivalent MW

        **Q_prof** (DataFrame, None): Pandas DataFrame with the reactive power profile in equivalent MVAr

        **active** (bool, True): Is the load active?

        **mttf** (float, 0.0): Mean time to failure in hours

        **mttr** (float, 0.0): Mean time to recovery in hours

    """

    def __init__(self, name='External grid', idtag=None, active=True, Vm=1.0, Va=0.0, Vm_prof=None, Va_prof=None,
                  mttf=0.0, mttr=0.0):

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                active=active,
                                device_type=DeviceType.ExternalGridDevice,
                                editable_headers={'name': GCProp('', str, 'Load name'),
                                                  'idtag': GCProp('', str, 'Unique ID'),
                                                  'bus': GCProp('', DeviceType.BusDevice, 'Connection bus name'),
                                                  'active': GCProp('', bool, 'Is the load active?'),
                                                  'Vm': GCProp('p.u.', float, 'Active power'),
                                                  'Va': GCProp('radians', float, 'Reactive power'),
                                                  'mttf': GCProp('h', float, 'Mean time to failure'),
                                                  'mttr': GCProp('h', float, 'Mean time to recovery'),
                                                  },
                                non_editable_attributes=['bus', 'idtag'],
                                properties_with_profile={'active': 'active_prof',
                                                         'Vm': 'Vm_prof',
                                                         'Va': 'Va_prof'})

        self.bus = None

        self.active_prof = None

        self.mttf = mttf

        self.mttr = mttr

        # Impedance in equivalent MVA
        self.Vm = Vm
        self.Va = Va
        self.Vm_prof = Vm_prof
        self.Va_prof = Va_prof

    def copy(self):

        elm = ExternalGrid()

        elm.name = self.name
        elm.active = self.active
        elm.active_prof = self.active_prof
        elm.Vm = self.Vm
        elm.Va = self.Va
        elm.Vm_prof = self.Vm_prof
        elm.Va_prof = self.Va_prof

        elm.mttf = self.mttf
        elm.mttr = self.mttr

        return elm

    def get_properties_dict(self):
        """
        Get json dictionary
        :return:
        """

        d = {'id': self.idtag,
             'type': 'load',
             'phases': 'ps',
             'name': self.name,
             'bus': self.bus.idtag,
             'active': self.active,
             'Vm': self.Vm,
             'Va': self.Va}

        if self.active_prof is not None:
            d['active_profile'] = self.active_prof.tolist()
            d['Vm_prof'] = self.Vm_prof.tolist()
            d['Va_prof'] = self.Va_prof.tolist()

        return d

    def get_profiles_dict(self):
        """

        :return:
        """
        if self.active_prof is not None:
            active_profile = self.active_prof.tolist()
            Vm_prof = self.Vm_prof.tolist()
            Va_prof = self.Va_prof.tolist()
        else:
            active_profile = list()
            Vm_prof = list()
            Va_prof = list()

        return {'id': self.idtag,
                'active': active_profile,
                'vm': Vm_prof,
                'va': Va_prof}

    def plot_profiles(self, time=None, show_fig=True):
        """
        Plot the time series results of this object
        :param time: array of time values
        :param show_fig: Show the figure?
        """

        if time is not None:
            fig = plt.figure(figsize=(12, 8))

            ax_1 = fig.add_subplot(211)
            ax_2 = fig.add_subplot(212)

            # P
            y = self.Vm_prof
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_1.set_title('Voltage module', fontsize=14)
            ax_1.set_ylabel('p.u.', fontsize=11)
            df.plot(ax=ax_1)

            # Q
            y = self.Va_prof
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_2.set_title('Voltage angle', fontsize=14)
            ax_2.set_ylabel('radians', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

            if show_fig:
                plt.show()
