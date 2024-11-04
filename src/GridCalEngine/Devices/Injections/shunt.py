# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

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
