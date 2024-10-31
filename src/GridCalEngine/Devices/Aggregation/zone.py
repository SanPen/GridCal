# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union
from GridCalEngine.Devices.Parents.editable_device import DeviceType
from GridCalEngine.Devices.Aggregation.area import GenericAreaGroup, Area


class Zone(GenericAreaGroup):

    def __init__(self, name='Zone',
                 idtag: Union[str, None] = None,
                 code='',
                 latitude=0.0,
                 longitude=0.0,
                 area: Union[Area, None] = None):
        """
        Zone
        :param name: name of the zone
        :param idtag: UUID code
        :param latitude: latitude (deg)
        :param longitude: longutide (deg)
        :param area: (optional)
        """
        GenericAreaGroup.__init__(self,
                                  name=name,
                                  idtag=idtag,
                                  code=code,
                                  device_type=DeviceType.ZoneDevice,
                                  latitude=latitude,
                                  longitude=longitude)

        self.area: Union[Area, None] = area

        self.register(key="area", units="", tpe=DeviceType.AreaDevice, definition="Area of this zone.")
