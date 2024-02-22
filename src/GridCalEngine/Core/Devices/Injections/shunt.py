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
from GridCalEngine.Core.Devices.Parents.shunt_parent import ShuntParent


class Shunt(ShuntParent):

    def __init__(self, name='shunt', idtag=None, code='',
                 G=0.0, B=0.0, active=True,
                 controlled=False, Bmin=0.0, Bmax=0.0, vset=1.0, mttf=0.0, mttr=0.0,
                 G0=0, B0=0,
                 capex=0, opex=0, build_status: BuildStatus = BuildStatus.Commissioned):
        """

        :param name:
        :param idtag:
        :param code:
        :param G:
        :param B:
        :param active:
        :param controlled:
        :param Bmin:
        :param Bmax:
        :param vset:
        :param mttf:
        :param mttr:
        :param G0:
        :param B0:
        :param capex:
        :param opex:
        :param build_status:
        """

        ShuntParent.__init__(self,
                             name=name,
                             idtag=idtag,
                             code=code,
                             bus=None,
                             cn=None,
                             active=active,
                             G=G,
                             B=B,
                             G0=G0,
                             B0=B0,
                             Cost=0.0,
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

