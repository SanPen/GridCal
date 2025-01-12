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

        :param name: Name of the device
        :param idtag: unique id of the device (if None or "" a new one is generated)
        :param code: secondary code for compatibility
        :param active:active state
        :param G: positive conductance (MW @ v=1 p.u.)
        :param B: positive conductance (MVAr @ v=1 p.u.)
        :param G0: zero-sequence conductance (MW @ v=1 p.u.)
        :param B0: zero-sequence conductance (MVAr @ v=1 p.u.)
        :param mttf: mean time to failure (h)
        :param mttr: mean time to recovery (h)
        :param capex: capital expenditures (investment cost)
        :param opex: operational expenditures (maintenance cost)
        :param build_status: BuildStatus
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
