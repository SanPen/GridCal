# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union
from GridCalEngine.Devices.Parents.editable_device import EditableDevice
from GridCalEngine.Devices.Aggregation.modelling_authority import ModellingAuthority
from GridCalEngine.enumerations import DeviceType




class PhysicalDevice(EditableDevice):
    """
    Parent class for Injections, Branches, Buses and other physical devices
    """

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 device_type: DeviceType):
        """
        PhysicalDevice
        :param name: Name of the device
        :param idtag: unique id of the device (if None or "" a new one is generated)
        :param code: secondary code for compatibility
        :param device_type: DeviceType
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=device_type)

        self.modelling_authority: Union[ModellingAuthority, None] = None

        self.register(key='modelling_authority', units='', tpe=DeviceType.ModellingAuthority,
                      definition='Modelling authority of this asset')
