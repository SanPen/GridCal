# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from typing import Union
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType


class InvestmentsGroup(EditableDevice):
    """
    Investments group
    """

    def __init__(self,
                 idtag: Union[str, None] = None,
                 name: str = "InvestmentGroup",
                 category: str = '',
                 comment: str = "",
                 discount_rate=5):
        """
        Contingency group
        :param idtag: Unique identifier
        :param name: contingency group name
        :param category: tag to category the group
        :param comment: comment
        :param discount_rate: discount rate (%)
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code='',
                                device_type=DeviceType.InvestmentsGroupDevice,
                                comment=comment)

        # Contingency type
        self.category = category

        self.discount_rate = discount_rate

        self.register(key='category', units='', tpe=str, definition='Some tag to category the investment group')
        self.register(key='discount_rate', units='%', tpe=float, definition='Investment group discount rate')