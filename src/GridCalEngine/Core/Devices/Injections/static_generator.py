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

from GridCalEngine.enumerations import BuildStatus, DeviceType
from GridCalEngine.Core.Devices.Injections.injection_template import LoadLikeTemplate


class StaticGenerator(LoadLikeTemplate):

    def __init__(self, name='StaticGen', idtag=None, code='', P=0.0, Q=0.0, P_prof=None, Q_prof=None, active=True,
                 mttf=0.0, mttr=0.0, Cost=1200.0,
                 capex=0, opex=0, build_status: BuildStatus = BuildStatus.Commissioned):
        """

        :param name:
        :param idtag:
        :param code:
        :param P:
        :param Q:
        :param P_prof:
        :param Q_prof:
        :param active:
        :param mttf:
        :param mttr:
        :param Cost:
        :param capex:
        :param opex:
        :param build_status:
        """

        LoadLikeTemplate.__init__(self,
                                  name=name,
                                  idtag=idtag,
                                  code=code,
                                  bus=None,
                                  cn=None,
                                  active=active,
                                  active_prof=None,
                                  P=P,
                                  P_prof=P_prof,
                                  Q=Q,
                                  Q_prof=Q_prof,
                                  Cost=Cost,
                                  Cost_prof=None,
                                  mttf=mttf,
                                  mttr=mttr,
                                  capex=capex,
                                  opex=opex,
                                  build_status=build_status,
                                  device_type=DeviceType.StaticGeneratorDevice)


