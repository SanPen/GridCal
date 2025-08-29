# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from typing import Union
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice, DeviceType


class RmsEventsGroup(EditableDevice):
    """
    Investments group
    """
    __slots__ = (
        'category',
        'parameter',
        'time',
        'value',
    )

    def __init__(self,
                 idtag: Union[str, None] = None,
                 name: str ="RmsEventsGroup",
                 category: str = '',
                 parameter: str = None,
                 time: float = 0.0,
                 value: float = 0.0,
                 comment: str = ""):
        """
        Contingency group
        :param idtag: Unique identifier
        :param name: contingency group name
        :param category: tag to category the group
        :param comment: comment
        :param discount_rate: discount rate (%)
        :param CAPEX: Capital Expenditure of the group (added to the individual investments' capex)
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code='',
                                device_type=DeviceType.RmsEventsGroupDevice,
                                comment=comment)

        # Contingency type
        self.category = category
        self.parameter: str = parameter
        self.time: float = time
        self.value: float = value

        self.register(key='category', units='', tpe=str, definition='Some tag to category the RmsEvent group')
        self.register(key='parameter', units='', tpe=str,
                      definition='parameter that the event changes')
        self.register(key='time', units='', tpe=float,
                      definition='Time when the event occurs')
        self.register(key='value', units='', tpe=float,
                      definition='New value for the parameter')