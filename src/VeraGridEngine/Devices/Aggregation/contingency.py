# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.Devices.Parents.pointer_device_parent import PointerDeviceParent
from VeraGridEngine.enumerations import ContingencyOperationTypes, DeviceType
from VeraGridEngine.Devices.Aggregation.contingency_group import ContingencyGroup


class Contingency(PointerDeviceParent):
    """
    The Contingency object
    """
    __slots__ = (
        '_prop',
        '_value',
        '_group',
    )

    def __init__(self,
                 device: EditableDevice | None = None,
                 idtag: Union[str, None] = None,
                 name="Contingency",
                 code='',
                 prop: ContingencyOperationTypes = ContingencyOperationTypes.Active,
                 value=0.0,
                 group: Union[None, ContingencyGroup] = None,
                 comment: str = ""):
        """
        Contingency
        :param device: Some device to point at
        :param idtag: String. Element unique identifier
        :param name: String. Contingency name
        :param code: String. Contingency code name
        :param prop: String. Property to modify when contingency is triggered out
        :param value: Float. Property value to apply when contingency happens
        :param group: ContingencyGroup. Contingency group
        """

        PointerDeviceParent.__init__(self,
                                     idtag=idtag,
                                     device=device,
                                     code=code,
                                     name=name,
                                     device_type=DeviceType.ContingencyDevice,
                                     comment=comment)

        # Contingency type
        self._prop: ContingencyOperationTypes = prop
        self._value = value
        self._group: ContingencyGroup = group

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
