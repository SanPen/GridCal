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
from matplotlib import pyplot as plt
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.enumerations import BuildStatus
from GridCalEngine.Core.Devices.Injections.injection_template import InjectionTemplate


class Shunt(InjectionTemplate):
    """
    Arguments:

        **name** (str, "shunt"): Name of the shunt

        **G** (float, 0.0): Conductance in MW at 1 p.u. voltage

        **B** (float, 0.0): Susceptance in MW at 1 p.u. voltage

        **G_prof** (DataFrame, None): Pandas DataFrame with the conductance profile in MW at 1 p.u. voltage

        **B_prof** (DataFrame, None): Pandas DataFrame with the susceptance profile in MW at 1 p.u. voltage

        **active** (bool, True): Is the shunt active?

        **mttf** (float, 0.0): Mean time to failure in hours

        **mttr** (float, 0.0): Mean time to recovery in hours

    """

    def __init__(self, name='shunt', idtag=None, code='',
                 G=0.0, B=0.0, G_prof=None, B_prof=None, active=True, active_prof=None,
                 controlled=False, Bmin=0.0, Bmax=0.0, vset=1.0, mttf=0.0, mttr=0.0,
                 G0=0, B0=0, G0_prof=None, B0_prof=None,
                 capex=0, opex=0, build_status: BuildStatus = BuildStatus.Commissioned):

        InjectionTemplate.__init__(self,
                                   name=name,
                                   idtag=idtag,
                                   code=code,
                                   bus=None,
                                   cn=None,
                                   active=active,
                                   active_prof=None,
                                   Cost=0.0,
                                   Cost_prof=None,
                                   mttf=mttf,
                                   mttr=mttr,
                                   capex=capex,
                                   opex=opex,
                                   build_status=build_status,
                                   device_type=DeviceType.ShuntDevice)

        self.is_controlled = controlled

        # Impedance (MVA)
        self.G = G
        self.B = B
        self.G0 = G0
        self.B0 = B0
        self.Bmin = Bmin
        self.Bmax = Bmax
        self.Vset = vset

        # admittance profile
        self.G_prof = G_prof
        self.B_prof = B_prof
        self.G0_prof = G0_prof
        self.B0_prof = B0_prof

        self.register(key='is_controlled', units='', tpe=bool, definition='Is the shunt controllable?')
        self.register(key='G', units='MW', tpe=float,
                      definition='Active power of the impedance component at V=1.0 p.u.', profile_name='G_prof')
        self.register(key='B', units='MVAr', tpe=float,
                      definition='Reactive power of the impedance component at V=1.0 p.u.', profile_name='B_prof')
        self.register(key='G0', units='MW', tpe=float,
                      definition='Zero sequence active power of the impedance component at V=1.0 p.u.')
        self.register(key='B0', units='MVAr', tpe=float,
                      definition='Zero sequence reactive power of the impedance component at V=1.0 p.u.')
        self.register(key='Bmin', units='MVAr', tpe=float, definition='Reactive power min control value at V=1.0 p.u.')
        self.register(key='Bmax', units='MVAr', tpe=float, definition='Reactive power max control value at V=1.0 p.u.')
        self.register(key='Vset', units='p.u.', tpe=float,
                      definition='Set voltage. This is used for controlled shunts.')


    def copy(self):
        """
        Copy of this object
        :return: a copy of this object
        """
        shu = Shunt(name=self.name,
                    G=self.G,
                    B=self.B,
                    G_prof=self.G_prof,
                    B_prof=self.B_prof,
                    G0=self.G0,
                    B0=self.B0,
                    G0_prof=self.G0_prof,
                    B0_prof=self.B0_prof,
                    active=self.active,
                    active_prof=self.active_prof,
                    Bmax=self.Bmax,
                    Bmin=self.Bmin,
                    vset=self.Vset,
                    mttf=self.mttf,
                    mttr=self.mttr)
        return shu

    def get_properties_dict(self, version=3):
        """
        Get json dictionary
        :return:
        """
        if version == 2:
            data = {'id': self.idtag,
                    'type': 'shunt',
                    'phases': 'ps',
                    'name': self.name,
                    'name_code': self.code,
                    'bus': self.bus.idtag,
                    'active': self.active,
                    'g': self.G,
                    'b': self.B,
                    'bmax': self.Bmax,
                    'bmin': self.Bmin,
                    'id_impedance_table': "",
                    'technology': ""
                    }
        elif version == 3:
            data = {'id': self.idtag,
                    'type': 'shunt',
                    'phases': 'ps',
                    'name': self.name,
                    'name_code': self.code,
                    'bus': self.bus.idtag,
                    'active': self.active,
                    'controlled': self.is_controlled,
                    'g': self.G,
                    'b': self.B,
                    'g0': self.G0,
                    'b0': self.B0,
                    'bmax': self.Bmax,
                    'bmin': self.Bmin,
                    'capex': self.capex,
                    'opex': self.opex,
                    'build_status': str(self.build_status.value).lower(),
                    'id_impedance_table': "",
                    'technology': ""
                    }
        else:
            data = dict()
        return data

    def get_profiles_dict(self, version=3):
        """

        :return:
        """

        if self.active_prof is not None:
            active_profile = self.active_prof.tolist()
            G_prof = self.G_prof.tolist()
            B_prof = self.B_prof.tolist()
        else:
            active_profile = list()
            G_prof = list()
            B_prof = list()

        return {'id': self.idtag,
                'active': active_profile,
                'g': G_prof,
                'b': B_prof}

    def get_units_dict(self, version=3):
        """
        Get units of the values
        """
        return {'g': 'MVAr at V=1 p.u.',
                'b': 'MVAr at V=1 p.u.'}

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

            # G
            y = self.G_prof
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_1.set_title('Conductance power', fontsize=14)
            ax_1.set_ylabel('MW', fontsize=11)
            df.plot(ax=ax_1)

            # B
            y = self.B_prof
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_2.set_title('Susceptance power', fontsize=14)
            ax_2.set_ylabel('MVAr', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

            if show_fig:
                plt.show()
