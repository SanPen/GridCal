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


class Load(EditableDevice):
    """
    The load object implements the so-called ZIP model, in which the load can be
    represented by a combination of power (P), current(I), and impedance (Z).

    The sign convention is: Positive to act as a load, negative to act as a generator.

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

    def __init__(self, name='Load', idtag=None, code='', G=0.0, B=0.0, Ir=0.0, Ii=0.0, P=0.0, Q=0.0, cost=1200.0,
                 G_prof=None, B_prof=None, Ir_prof=None, Ii_prof=None, P_prof=None, Q_prof=None,
                 active=True, mttf=0.0, mttr=0.0):

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                active=active,
                                device_type=DeviceType.LoadDevice,
                                editable_headers={'name': GCProp('', str, 'Load name'),
                                                  'idtag': GCProp('', str, 'Unique ID', False),
                                                  'code': GCProp('', str, 'Secondary ID', True),
                                                  'bus': GCProp('', DeviceType.BusDevice, 'Connection bus name'),
                                                  'active': GCProp('', bool, 'Is the load active?'),
                                                  'P': GCProp('MW', float, 'Active power'),
                                                  'Q': GCProp('MVAr', float, 'Reactive power'),
                                                  'Ir': GCProp('MW', float,
                                                               'Active power of the current component at V=1.0 p.u.'),
                                                  'Ii': GCProp('MVAr', float,
                                                               'Reactive power of the current component at V=1.0 p.u.'),
                                                  'G': GCProp('MW', float,
                                                              'Active power of the impedance component at V=1.0 p.u.'),
                                                  'B': GCProp('MVAr', float,
                                                              'Reactive power of the impedance component at V=1.0 p.u.'),
                                                  'mttf': GCProp('h', float, 'Mean time to failure'),
                                                  'mttr': GCProp('h', float, 'Mean time to recovery'),
                                                  'Cost': GCProp('e/MWh', float,
                                                                 'Cost of not served energy. Used in OPF.')},
                                non_editable_attributes=['bus', 'idtag'],
                                properties_with_profile={'active': 'active_prof',
                                                         'P': 'P_prof',
                                                         'Q': 'Q_prof',
                                                         'Ir': 'Ir_prof',
                                                         'Ii': 'Ii_prof',
                                                         'G': 'G_prof',
                                                         'B': 'B_prof',
                                                         'Cost': 'Cost_prof'})

        self.bus = None

        self.active_prof = None

        self.mttf = mttf

        self.mttr = mttr

        self.Cost = cost

        self.Cost_prof = None

        # Impedance in equivalent MVA
        self.G = G
        self.B = B
        self.Ir = Ir
        self.Ii = Ii
        self.P = P
        self.Q = Q
        self.G_prof = G_prof
        self.B_prof = B_prof
        self.Ir_prof = Ir_prof
        self.Ii_prof = Ii_prof
        self.P_prof = P_prof
        self.Q_prof = Q_prof

    def copy(self):

        load = Load()

        load.name = self.name

        load.active = self.active
        load.active_prof = self.active_prof

        # Impedance (MVA)
        load.G = self.G
        load.B = self.B

        # Current (MVA)
        load.Ir = self.Ir
        load.Ii = self.Ii

        # Power (MVA)
        load.P = self.P
        load.Q = self.Q

        # Impedance (MVA)
        load.G_prof = self.G_prof
        load.B_prof = self.B_prof

        # Current (MVA)
        load.Ir_prof = self.Ir_prof
        load.Ii_prof = self.Ii_prof

        # Power (MVA)
        load.P_prof = self.P_prof
        load.Q_prof = self.Q_prof

        load.mttf = self.mttf
        load.mttr = self.mttr

        return load

    def get_properties_dict(self, version=3):
        """
        Get json dictionary
        :return:
        """
        if version in [2, 3]:
            return {'id': self.idtag,
                    'type': 'load',
                    'phases': 'ps',
                    'name': self.name,
                    'name_code': self.code,
                    'bus': self.bus.idtag,
                    'active': bool(self.active),
                    'g': self.G,
                    'b': self.B,
                    'ir': self.Ir,
                    'ii': self.Ii,
                    'p': self.P,
                    'q': self.Q
                    }
        else:
            return dict()

    def get_profiles_dict(self, version=3):
        """

        :return:
        """

        if self.active_prof is not None:
            active_profile = self.active_prof.tolist()
            P_prof = self.P_prof.tolist()
            Q_prof = self.Q_prof.tolist()
            Ir_prof = self.Ir_prof.tolist()
            Ii_prof = self.Ii_prof.tolist()
            G_prof = self.G_prof.tolist()
            B_prof = self.B_prof.tolist()

        else:
            active_profile = list()
            P_prof = list()
            Q_prof = list()
            Ir_prof = list()
            Ii_prof = list()
            G_prof = list()
            B_prof = list()

        return {'id': self.idtag,
                'active': active_profile,
                'p': P_prof,
                'q': Q_prof,
                'ir': Ir_prof,
                'ii': Ii_prof,
                'g': G_prof,
                'b': B_prof}

    def get_units_dict(self, version=3):
        """
        Get units of the values
        """
        return {'g': 'MVAr at V=1 p.u.',
                'b': 'MVAr at V=1 p.u.',
                'ir': 'MVAr at V=1 p.u.',
                'ii': 'MVAr at V=1 p.u.',
                'p': 'MW',
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
