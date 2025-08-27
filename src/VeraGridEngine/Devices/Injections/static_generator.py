# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


from VeraGridEngine.enumerations import BuildStatus, DeviceType
from VeraGridEngine.Devices.Parents.load_parent import LoadParent


class StaticGenerator(LoadParent):

    def __init__(self, name='StaticGen', idtag=None, code='', P=0.0, Q=0.0, active=True,
                 P1=0.0, P2=0.0, P3=0.0, Q1=0.0, Q2=0.0, Q3=0.0,
                 mttf=0.0, mttr=0.0, Cost=1200.0,
                 capex=0, opex=0, build_status: BuildStatus = BuildStatus.Commissioned):
        """

        :param name:
        :param idtag:
        :param code:
        :param P:
        :param P1:
        :param P2:
        :param P3:
        :param Q:
        :param Q1:
        :param Q2:
        :param Q3:
        :param active:
        :param mttf:
        :param mttr:
        :param Cost:
        :param capex:
        :param opex:
        :param build_status:
        """

        LoadParent.__init__(self,
                            name=name,
                            idtag=idtag,
                            code=code,
                            bus=None,
                            active=active,
                            P=P,
                            P1=P1,
                            P2=P2,
                            P3=P3,
                            Q=Q,
                            Q1=Q1,
                            Q2=Q2,
                            Q3=Q3,
                            Cost=Cost,
                            mttf=mttf,
                            mttr=mttr,
                            capex=capex,
                            opex=opex,
                            build_status=build_status,
                            device_type=DeviceType.StaticGeneratorDevice)