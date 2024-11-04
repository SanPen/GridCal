# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from typing import Union
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType


class ContingencyGroup(EditableDevice):
    """
    The Contingency group
    """

    def __init__(self, idtag: Union[str, None] = None, name="ContingencyGroup", category=''):
        """
        Contingency group
        :param idtag: Unique identifier
        :param name: contingency group name
        :param category: tag to category the group
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code='',
                                device_type=DeviceType.ContingencyGroupDevice)

        # Contingency type
        self.category = category

        self.register(key='category', units='', tpe=str, definition='Some tag to category the contingency group')
