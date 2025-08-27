# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType


class RmsModelTemplate(EditableDevice):
    """
    This class serves to give flexible access to either a template or a custom model
    """
    def __init__(self, name: str = ""):

        super().__init__(name=name,
                         idtag=None,
                         code="",
                         device_type= DeviceType.RmsModelTemplateDevice)

        self._block: Block = Block()

    @property
    def block(self):
        return self._block

