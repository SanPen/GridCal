# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Union
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType


class BranchGroup(EditableDevice):

    def __init__(self,
                 name='',
                 code='',
                 idtag: Union[str, None] = None):
        """
        BranchGroup
        :param name: name of the generator fuel
        :param code: secondary id
        :param idtag: UUID code
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.BranchGroupDevice)
