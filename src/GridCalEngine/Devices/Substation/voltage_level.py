# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Devices.Parents.physical_device import PhysicalDevice
from GridCalEngine.Devices.Substation.substation import Substation


class VoltageLevel(PhysicalDevice):

    def __init__(self, name='VoltageLevel',
                 idtag: Union[str, None] = None,
                 code: str = '',
                 Vnom: float = 1.0,
                 substation: Union[None, Substation] = None):
        """
        Constructor
        :param name: Name
        :param idtag: UUID
        :param code: secondary ID
        :param Vnom: Nominal voltage in kV
        :param substation: Substation object (optional)
        """
        PhysicalDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.VoltageLevelDevice)

        self.Vnom = float(Vnom)

        self.substation: Union[None, Substation] = substation

        self.register(key='Vnom', units='KV', tpe=float, definition='Nominal voltage')

        self.register(key="substation", tpe=DeviceType.SubstationDevice,
                      definition="Substation of this Voltage level (optional)")
