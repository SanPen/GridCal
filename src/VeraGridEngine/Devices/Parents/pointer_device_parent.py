# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.enumerations import DeviceType


class PointerDeviceParent(EditableDevice):
    """
    Investment
    """

    __slots__ = (
        '_device_idtag',
        '_tpe',
    )

    def __init__(self,
                 idtag: Union[str, None],
                 device: EditableDevice,
                 name: str,
                 code: str,
                 comment: str,
                 device_type: DeviceType):
        """
        Investment
        :param idtag: String. Element unique identifier
        :param device: Device to point at
        :param name: String. Contingency name
        :param code: String. Contingency code name
        :param comment: Comment
        """

        EditableDevice.__init__(self,
                                idtag=idtag,
                                code=code,
                                name=name,
                                device_type=device_type,
                                comment=comment)

        self._device_idtag: str = device.idtag if device is not None else ""
        self._tpe: DeviceType = device.device_type if device is not None else DeviceType.NoDevice

        self.register(key='device_idtag', units='', tpe=str, definition='Unique ID', editable=False)
        self.register(key='tpe', units='', tpe=DeviceType, definition='Device type', editable=False)

    @property
    def device_idtag(self) -> str:
        """
        Group of investments
        :return:
        """
        return self._device_idtag

    @device_idtag.setter
    def device_idtag(self, val: str):
        if isinstance(val, str):
            self._device_idtag = val
        else:
            raise ValueError(f"device_idtag must be a string not {val}")

    @property
    def tpe(self) -> DeviceType:
        """
        Display the group category
        :return:
        """
        return self._tpe

    @tpe.setter
    def tpe(self, val: DeviceType):
        if isinstance(val, DeviceType):
            self._tpe = val
        else:
            raise ValueError(f"tpe must be a string not {val}")

    def set_device(self, elm: EditableDevice):
        """
        Set the device
        :param elm: Device to be pointed
        """
        self._tpe = elm.device_type
        self._device_idtag = elm.idtag