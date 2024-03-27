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
from GridCalEngine.Devices.Parents.shunt_parent import ShuntParent


class Shunt(ShuntParent):

    def __init__(self, name='shunt', idtag=None, code='',
                 G=0.0, B=0.0, active=True,
                 mttf=0.0, mttr=0.0,
                 G0=0, B0=0,
                 capex=0, opex=0, build_status: BuildStatus = BuildStatus.Commissioned):
        """
        Fixed shunt, not controllable

        :param name:
        :param idtag:
        :param code:
        :param G:
        :param B:
        :param active:
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
