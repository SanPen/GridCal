# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType
from GridCalEngine.Devices.Aggregation.contingency_group import ContingencyGroup
from GridCalEngine.enumerations import ContingencyOperationTypes


class Contingency(EditableDevice):
    """
    The Contingency object
    """

    def __init__(self,
                 idtag: Union[str, None] = None,
                 device_idtag='',
                 name="Contingency",
                 code='',
                 prop: ContingencyOperationTypes = ContingencyOperationTypes.Active,
                 value=0.0,
                 group: Union[None, ContingencyGroup] = None):
        """
        Contingency
        :param idtag: String. Element unique identifier
        :param name: String. Contingency name
        :param code: String. Contingency code name
        :param prop: String. Property to modify when contingency is triggered out
        :param value: Float. Property value to apply when contingency happens
        :param group: ContingencyGroup. Contingency group
        """

        EditableDevice.__init__(self,
                                idtag=idtag,
                                code=code,
                                name=name,
                                device_type=DeviceType.ContingencyDevice)

        # Contingency type
        self.device_idtag = device_idtag
        self._prop: ContingencyOperationTypes = prop
        self._value = value
        self._group: ContingencyGroup = group

        self.register(key='device_idtag', units='', tpe=str, definition='Unique ID', editable=False)
        self.register(key='prop', units='', tpe=ContingencyOperationTypes,
                      definition=f'Object property to change')
        self.register(key='value', units='', tpe=float, definition='Property value')
        self.register(key='group', units='', tpe=DeviceType.ContingencyGroupDevice, definition='Contingency group')

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, val: str):
        self._name = val

    @property
    def prop(self) -> ContingencyOperationTypes:
        """
        Property to modify when contingency is triggered out
        :return: ContingencyOperationsTypes
        """
        return self._prop

    @prop.setter
    def prop(self, val: ContingencyOperationTypes):
        if isinstance(val, ContingencyOperationTypes):
            self._prop = val
        else:
            print(f"Not allowed property {val}")

    @property
    def value(self) -> float:
        """
        Property value to apply when contingency happens
        :return:
        """
        return self._value

    @value.setter
    def value(self, val: float):
        self._value = val

    @property
    def group(self) -> ContingencyGroup:
        """
        Contingency group
        :return:
        """
        return self._group

    @group.setter
    def group(self, val: ContingencyGroup):
        self._group = val

    @property
    def category(self):
        """

        :return:
        """
        return self.group.category

    @category.setter
    def category(self, val):
        # self.group.category = val
        pass
