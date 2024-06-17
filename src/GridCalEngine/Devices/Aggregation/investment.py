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

from typing import Union
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType
from GridCalEngine.Devices.Aggregation.investments_group import InvestmentsGroup


class Investment(EditableDevice):
    """
    Investment
    """

    def __init__(self,
                 idtag: Union[str, None] = None,
                 device_idtag: Union[str, None] = None,
                 name="Investment",
                 code='',
                 CAPEX=0.0,
                 OPEX=0.0,
                 status: bool = True,
                 group: InvestmentsGroup = None,
                 comment: str = ""):
        """
        Investment
        :param idtag: String. Element unique identifier
        :param name: String. Contingency name
        :param code: String. Contingency code name
        :param CAPEX: Float. Capital expenditures
        :param OPEX: Float. Operating expenditures
        :param status: If true the investment activates when applied, otherwise is deactivated
        :param group: ContingencyGroup. Contingency group
        :param comment: Comment
        """

        EditableDevice.__init__(self,
                                idtag=idtag,
                                code=code,
                                name=name,
                                device_type=DeviceType.InvestmentDevice,
                                comment=comment)

        # Contingency type
        self.device_idtag = device_idtag
        self.CAPEX = CAPEX
        self.OPEX = OPEX
        self._group: InvestmentsGroup = group
        self.status: bool = status

        self.register(key='device_idtag', units='', tpe=str, definition='Unique ID')
        self.register(key='CAPEX', units='Me', tpe=float,
                      definition='Capital expenditures. This is the initial investment.')
        self.register(key='OPEX', units='Me', tpe=float,
                      definition='Operation expenditures. Maintenance costs among other recurrent costs.')
        self.register(key='status', units='', tpe=bool,
                      definition='If true the investment activates when applied, otherwise is deactivated.')
        self.register(key='group', units='', tpe=DeviceType.InvestmentsGroupDevice, definition='Investment group')

    @property
    def group(self) -> InvestmentsGroup:
        """
        Group of investments
        :return:
        """
        return self._group

    @group.setter
    def group(self, val: InvestmentsGroup):
        self._group = val

    @property
    def category(self):
        """
        Display the group category
        :return:
        """
        return self.group.category

    @category.setter
    def category(self, val):
        # self.group.category = val
        pass
