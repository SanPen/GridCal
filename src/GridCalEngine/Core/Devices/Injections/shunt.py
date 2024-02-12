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
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.enumerations import BuildStatus
from GridCalEngine.Core.Devices.Injections.injection_template import ShuntLikeTemplate


class Shunt(ShuntLikeTemplate):

    def __init__(self, name='shunt', idtag=None, code='',
                 G=0.0, B=0.0, G_prof=None, B_prof=None, active=True, active_prof=None,
                 controlled=False, Bmin=0.0, Bmax=0.0, vset=1.0, mttf=0.0, mttr=0.0,
                 G0=0, B0=0, G0_prof=None, B0_prof=None,
                 capex=0, opex=0, build_status: BuildStatus = BuildStatus.Commissioned):
        """

        :param name:
        :param idtag:
        :param code:
        :param G:
        :param B:
        :param G_prof:
        :param B_prof:
        :param active:
        :param active_prof:
        :param controlled:
        :param Bmin:
        :param Bmax:
        :param vset:
        :param mttf:
        :param mttr:
        :param G0:
        :param B0:
        :param G0_prof:
        :param B0_prof:
        :param capex:
        :param opex:
        :param build_status:
        """

        ShuntLikeTemplate.__init__(self,
                                   name=name,
                                   idtag=idtag,
                                   code=code,
                                   bus=None,
                                   cn=None,
                                   active=active,
                                   active_prof=active_prof,
                                   G=G,
                                   G_prof=G_prof,
                                   B=B,
                                   B_prof=B_prof,
                                   G0=G0,
                                   G0_prof=G0_prof,
                                   B0=B0,
                                   B0_prof=B0_prof,
                                   Cost=0.0,
                                   Cost_prof=None,
                                   mttf=mttf,
                                   mttr=mttr,
                                   capex=capex,
                                   opex=opex,
                                   build_status=build_status,
                                   device_type=DeviceType.ShuntDevice)

        self.is_controlled = controlled

        self.Bmin = Bmin
        self.Bmax = Bmax
        self.Vset = vset

        self.register(key='is_controlled', units='', tpe=bool, definition='Is the shunt controllable?')

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

