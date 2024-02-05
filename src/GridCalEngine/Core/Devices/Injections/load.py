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
import pandas as pd
from matplotlib import pyplot as plt
from GridCalEngine.enumerations import DeviceType, BuildStatus
from GridCalEngine.Core.Devices.Injections.injection_template import LoadLikeTemplate
from GridCalEngine.Core.Devices.profile import Profile


class Load(LoadLikeTemplate):
    """
    Load
    """

    def __init__(self, name='Load', idtag=None, code='', G=0.0, B=0.0, Ir=0.0, Ii=0.0, P=0.0, Q=0.0, Cost=1200.0,
                 active=True, mttf=0.0, mttr=0.0, capex=0, opex=0,
                 build_status: BuildStatus = BuildStatus.Commissioned):
        """
        The load object implements the so-called ZIP model, in which the load can be
        represented by a combination of power (P), current(I), and impedance (Z).
        The sign convention is: Positive to act as a load, negative to act as a generator.
        :param name: Name of the load
        :param idtag: UUID code
        :param code: secondary ID code
        :param G: Conductance in equivalent MW
        :param B: Susceptance in equivalent MVAr
        :param Ir: Real current in equivalent MW
        :param Ii: Imaginary current in equivalent MVAr
        :param P: Active power in MW
        :param Q: Reactive power in MVAr
        :param Cost: Cost of load shedding
        :param active: Is the load active?
        :param mttf: Mean time to failure in hours
        :param mttr: Mean time to recovery in hours
        """
        LoadLikeTemplate.__init__(self,
                                  name=name,
                                  idtag=idtag,
                                  code=code,
                                  bus=None,
                                  cn=None,
                                  active=active,
                                  P=P,
                                  Q=Q,
                                  Cost=Cost,
                                  mttf=mttf,
                                  mttr=mttr,
                                  capex=capex,
                                  opex=opex,
                                  build_status=build_status,
                                  device_type=DeviceType.LoadDevice)

        self.G = G
        self.B = B
        self.Ir = Ir
        self.Ii = Ii

        self.G_prof = Profile()
        self.B_prof = Profile()
        self.Ir_prof = Profile()
        self.Ii_prof = Profile()

        self.register(key='Ir', units='MW', tpe=float,
                      definition='Active power of the current component at V=1.0 p.u.', profile_name='Ir_prof')
        self.register(key='Ii', units='MVAr', tpe=float,
                      definition='Reactive power of the current component at V=1.0 p.u.', profile_name='Ii_prof')
        self.register(key='G', units='MW', tpe=float,
                      definition='Active power of the impedance component at V=1.0 p.u.', profile_name='G_prof')
        self.register(key='B', units='MVAr', tpe=float,
                      definition='Reactive power of the impedance component at V=1.0 p.u.', profile_name='B_prof')

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
                    'q': self.Q,
                    'shedding_cost': self.Cost
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
            y = self.P_prof.toarray()
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_1.set_title('Active power', fontsize=14)
            ax_1.set_ylabel('MW', fontsize=11)
            df.plot(ax=ax_1)

            # Q
            y = self.Q_prof.toarray()
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_2.set_title('Reactive power', fontsize=14)
            ax_2.set_ylabel('MVAr', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

            if show_fig:
                plt.show()
