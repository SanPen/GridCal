# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.enumerations import DeviceType


class OptionsTemplate(EditableDevice):
    """
    Options template
    """

    def __init__(self, name: str):
        """

        :param name:
        """
        EditableDevice.__init__(self, name=name,
                                idtag=None,
                                code="",
                                device_type=DeviceType.SimulationOptionsDevice,
                                comment="")
