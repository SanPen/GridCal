# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union
import numpy as np

from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.Devices.Parents.pointer_device_parent import PointerDeviceParent
from VeraGridEngine.Devices.Aggregation.rms_events_group import RmsEventsGroup
from VeraGridEngine.enumerations import DeviceType


class RmsEvent(PointerDeviceParent):
    """
    Investment
    """
    __slots__ = (
        'parameter',
        'times',
        'values',
        '_group'
    )

    def __init__(self,
                 device: EditableDevice | None = None,
                 parameter: str = None,
                 times: np.ndarray = None,
                 values: np.ndarray = None,
                 idtag: Union[str, None] = None,
                 name="RmsEvent",
                 code='',
                 group: RmsEventsGroup = None,
                 comment: str = ""):
        """
        Investment
        :param device: Some device to point at
        :param idtag: String. Element unique identifier
        :param name: String. Contingency name
        :param code: String. Contingency code name
        :param group: RmsEventsGroup. RmsEvent group
        :param parameter: parameter
        :param times: time
        :param values: value
        :param comment: Comment
        """

        PointerDeviceParent.__init__(self,
                                     idtag=idtag,
                                     device=device,
                                     code=code,
                                     name=name,
                                     device_type=DeviceType.RmsEventDevice,
                                     comment=comment)

        self._group: RmsEventsGroup = group
        self.parameter: str = parameter
        self.times: np.ndarray = times
        self.values: np.ndarray = values

        self.register(key='parameter', units='', tpe=str,
                      definition='parameter that the event changes')
        self.register(key='times', units='', tpe=float,
                      definition='Time when the event occurs')
        self.register(key='values', units='', tpe=float,
                      definition='New value for the parameter')
        self.register(key='group', units='', tpe=DeviceType.RmsEventsGroupDevice, definition='RmsEvent group')

    @property
    def group(self) -> RmsEventsGroup:
        """
        Group of investments
        :return:
        """
        return self._group

    @group.setter
    def group(self, val: RmsEventsGroup):
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
