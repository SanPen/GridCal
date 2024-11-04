# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Union
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType
from GridCalEngine.Devices.Aggregation.contingency_group import ContingencyGroup


class RemedialActionGroup(EditableDevice):
    """
    The RemedialAction group
    """

    def __init__(self,
                 idtag: Union[str, None] = None,
                 name="RemedialActionGroup",
                 category='',
                 conn_group: ContingencyGroup | None = None,):
        """
        RemedialAction group
        :param idtag: Unique identifier
        :param name: contingency group name
        :param category: tag to category the group
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code='',
                                device_type=DeviceType.RemedialActionGroupDevice)

        # Contingency type
        self.category = category

        self._conn_group: ContingencyGroup = conn_group

        self.register(key='category', units='', tpe=str, definition='Some tag to category the contingency group')

        self.register(key='conn_group', units='', tpe=DeviceType.ContingencyGroupDevice, definition='Contingency group')

    @property
    def conn_group(self) -> ContingencyGroup:
        """
        Contingency group
        :return:
        """
        return self._conn_group

    @conn_group.setter
    def conn_group(self, val: ContingencyGroup):
        self._conn_group = val
