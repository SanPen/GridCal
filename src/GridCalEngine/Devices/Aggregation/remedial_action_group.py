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
