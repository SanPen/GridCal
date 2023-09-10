# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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

from typing import Union
from GridCalEngine.Core.Devices.editable_device import EditableDevice, DeviceType, GCProp


class ContingencyGroup(EditableDevice):
    """
    The Contingency object is the container of all the

    Arguments:

        **name** (str, "Contingency"): Name of the contingency

        **type** (float, 10.0): Nominal voltage in kV

        **loads** (list, list()): List of contingency elements

    """

    def __init__(self, idtag: Union[str, None] = None,  name="ContingencyGroup", category=''):
        """
        Contingency group
        :param idtag: Unique identifier
        :param name: contingency group name
        :param category: tag to category the group
        """

        EditableDevice.__init__(
            self,
            name=name,
            idtag=idtag,
            code='',
            active=True,
            device_type=DeviceType.ContingencyGroupDevice
        )

        # Contingency type
        self.category = category

        self.register(key='category', units='', tpe=str, definition='Some tag to category the contingency group')

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, val: str):
        self._name = val
        if self.graphic_obj is not None:
            self.graphic_obj.set_label(self._name)


    def get_properties_dict(self):
        """
        Get json dictionary
        :return:
        """

        return {
            'id': self.idtag,
            'name': self.name,
            'category': self.category,
        }