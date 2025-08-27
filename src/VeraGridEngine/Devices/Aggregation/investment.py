# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union

from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.Devices.Parents.pointer_device_parent import PointerDeviceParent
from VeraGridEngine.Devices.Aggregation.investments_group import InvestmentsGroup
from VeraGridEngine.enumerations import DeviceType


class Investment(PointerDeviceParent):
    """
    Investment
    """
    __slots__ = (
        'CAPEX',
        '_group',
        'status',
    )

    def __init__(self,
                 device: EditableDevice | None = None,
                 idtag: Union[str, None] = None,
                 name="Investment",
                 code='',
                 CAPEX: float = 0.0,
                 status: bool = True,
                 group: InvestmentsGroup = None,
                 comment: str = ""):
        """
        Investment
        :param device: Some device to point at
        :param idtag: String. Element unique identifier
        :param name: String. Contingency name
        :param code: String. Contingency code name
        :param CAPEX: Float. Capital expenditures
        :param status: If true the investment activates when applied, otherwise is deactivated
        :param group: InvestmentGroup. Investment group
        :param comment: Comment
        """

        PointerDeviceParent.__init__(self,
                                     idtag=idtag,
                                     device=device,
                                     code=code,
                                     name=name,
                                     device_type=DeviceType.InvestmentDevice,
                                     comment=comment)

        self.CAPEX: float = CAPEX
        self._group: InvestmentsGroup = group
        self.status: bool = status

        self.register(key='CAPEX', units='M€', tpe=float,
                      definition='Capital expenditures. This is the investment value, '
                                 'it overrides the CAPEX value of the device if it exits.')
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
        # The category is set through the group, so no implementation here
        pass
