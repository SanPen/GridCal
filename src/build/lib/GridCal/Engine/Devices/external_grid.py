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
from GridCal.Engine.basic_structures import ExternalGridMode
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

    def __init__(self, name='External grid', idtag=None, active=True,
                 Vm=1.0, Va=0.0, Vm_prof=None, Va_prof=None, P=0.0, Q=0.0, P_prof=None, Q_prof=None,
                  mttf=0.0, mttr=0.0, cost=1200.0, mode: ExternalGridMode = ExternalGridMode.PQ):

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                active=active,
                                device_type=DeviceType.ExternalGridDevice,
                                editable_headers={'name': GCProp('', str, 'Load name'),
                                                  'idtag': GCProp('', str, 'Unique ID'),
                                                  'bus': GCProp('', DeviceType.BusDevice, 'Connection bus name'),
                                                  'active': GCProp('', bool, 'Is the load active?'),
                                                  'mode': GCProp('', ExternalGridMode,
                                                                 'Operation mode of the external grid (voltage or load)'),
                                                  'Vm': GCProp('p.u.', float, 'Active power'),
                                                  'Va': GCProp('radians', float, 'Reactive power'),
                                                  'P': GCProp('MW', float, 'Active power'),
                                                  'Q': GCProp('MVAr', float, 'Reactive power'),
                                                  'mttf': GCProp('h', float, 'Mean time to failure'),
                                                  'mttr': GCProp('h', float, 'Mean time to recovery'),
                                                  'Cost': GCProp('e/MWh', float,
                                                                 'Cost of not served energy. Used in OPF.')
                                                  },
                                non_editable_attributes=['bus', 'idtag'],
                                properties_with_profile={'active': 'active_prof',
                                                         'Vm': 'Vm_prof',
                                                         'Va': 'Va_prof',
                                                         'P': 'P_prof',
                                                         'Q': 'Q_prof',
                                                         'Cost': 'Cost_prof'
                                                         })

        self.bus = None

        self.active_prof = None

        self.mode = mode

        self.mttf = mttf

        self.mttr = mttr

        # Impedance in equivalent MVA
        self.Vm = Vm
        self.Va = Va
        self.Vm_prof = Vm_prof
        self.Va_prof = Va_prof

        self.P = P
        self.Q = Q
        self.P_prof = P_prof
        self.Q_prof = Q_prof

        self.Cost = cost
        self.Cost_prof = None

    def copy(self):

        elm = ExternalGrid()

        elm.name = self.name
        elm.active = self.active
        elm.active_prof = self.active_prof
        elm.Vm = self.Vm
        elm.Va = self.Va
        elm.Vm_prof = self.Vm_prof
        elm.Va_prof = self.Va_prof

        elm.P = self.P
        elm.Q = self.Q
        elm.P_prof = self.P_prof
        elm.Q_prof = self.Q_prof

        elm.mttf = self.mttf
        elm.mttr = self.mttr

        elm.Cost = self.Cost
        elm.Cost_prof = self.Cost_prof

        return elm

    def get_properties_dict(self, version=3):
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
             'Va': self.Va,
             'P': self.P,
             'Q': self.Q,
             'Cost': self.Cost}

        if self.active_prof is not None:
            d['active_profile'] = self.active_prof.tolist()
            d['Vm_prof'] = self.Vm_prof.tolist()
            d['Va_prof'] = self.Va_prof.tolist()
            d['P_prof'] = self.P_prof.tolist()
            d['Q_prof'] = self.Q_prof.tolist()
            d['Cost_prof'] = self.Cost_prof.tolist()

        return d

    def get_profiles_dict(self, version=3):
        """

        :return:
        """
        if self.active_prof is not None:
            active_profile = self.active_prof.tolist()
            Vm_prof = self.Vm_prof.tolist()
            Va_prof = self.Va_prof.tolist()
            P_prof = self.P_prof.tolist()
            Q_prof = self.Q_prof.tolist()
        else:
            active_profile = list()
            Vm_prof = list()
            Va_prof = list()
            P_prof = list()
            Q_prof = list()

        return {'id': self.idtag,
                'active': active_profile,
                'vm': Vm_prof,
                'va': Va_prof,
                'P': P_prof,
                'Q': Q_prof}

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

            if self.mode == ExternalGridMode.VD:
                y1 = self.Vm_prof
                title_1 = 'Voltage module'
                units_1 = 'p.u'

                y2 = self.Va_prof
                title_2 = 'Voltage angle'
                units_2 = 'radians'
            elif self.mode == ExternalGridMode.PQ:
                y1 = self.P_prof
                title_1 = 'Active Power'
                units_1 = 'MW'

                y2 = self.Q_prof
                title_2 = 'Reactive power'
                units_2 = 'MVAr'
            else:
                raise Exception('Unrecognised external grid mode: ' + str(self.mode))

            ax_1.set_title(title_1, fontsize=14)
            ax_1.set_ylabel(units_1, fontsize=11)
            df = pd.DataFrame(data=y1, index=time, columns=[self.name])
            df.plot(ax=ax_1)

            df = pd.DataFrame(data=y2, index=time, columns=[self.name])
            ax_2.set_title(title_2, fontsize=14)
            ax_2.set_ylabel(units_2, fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

            if show_fig:
                plt.show()
